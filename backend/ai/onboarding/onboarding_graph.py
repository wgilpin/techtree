# backend/ai/onboarding/onboarding_graph.py
# pylint: disable=broad-exception-caught,singleton-comparison
"""Langgraph graph for onboarding - evaluating the user on a topic"""

import os
import re
import time
import random
from collections import Counter
from typing import (
    Dict,
    List,
    TypedDict,
    Optional,
    cast,
    Callable,
    Any,
)  # Added Callable, Any
import logging

import requests
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from tavily import TavilyClient  # type: ignore

# Add logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Tavily and Gemini API timeouts
TAVILY_TIMEOUT = 5  # seconds

# Configure Gemini API
# Define type hint before assignment
MODEL: Optional[genai.GenerativeModel] = None # type: ignore[name-defined]
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gemini_model_name = os.environ.get("GEMINI_MODEL")
    if not gemini_api_key:
        logger.error("Missing environment variable: GEMINI_API_KEY")
        raise KeyError("GEMINI_API_KEY")
    if not gemini_model_name:
        logger.error("Missing environment variable: GEMINI_MODEL")
        raise KeyError("GEMINI_MODEL")

    # Configuration within the try block (8 spaces indent)
    genai.configure(api_key=gemini_api_key) # type: ignore[attr-defined]
    MODEL = genai.GenerativeModel(gemini_model_name) # type: ignore[attr-defined]
    logger.info(f"Onboarding Config: Gemini model '{gemini_model_name}' configured.")

# Except block aligned with try (0 spaces indent)
except KeyError as e:
    # Content of except block (4 spaces indent)
    logger.error(
        f"Onboarding Config: Gemini configuration failed due to missing env var: {e}"
    )
    MODEL = None
except Exception as e:
    logger.error(f"Onboarding Config: Error configuring Gemini: {e}", exc_info=True)
    MODEL = None


# Configure Tavily API
# Define type hint before assignment
TAVILY: Optional[TavilyClient] = None
try:
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.warning(
            "Missing environment variable TAVILY_API_KEY. Tavily search disabled."
        )
    else:
        TAVILY = TavilyClient(api_key=tavily_api_key)
        logger.info("Onboarding Config: Tavily client configured.")
except Exception as e:
    logger.error(f"Onboarding Config: Error configuring Tavily: {e}", exc_info=True)
    TAVILY = None


# Added type annotations
def call_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """Call a function with exponential backoff retry logic for quota errors."""
    retries = 0
    delay = initial_delay
    while True:
        try:
            # Ensure model is configured before calling generate_content
            if func == getattr(MODEL, "generate_content", None) and MODEL is None:
                raise RuntimeError("Gemini model is not configured.")
            # Ensure tavily client is configured before calling search
            if func == getattr(TAVILY, "search", None) and TAVILY is None:
                raise RuntimeError("Tavily client is not configured.")
            return func(*args, **kwargs)
        except ResourceExhausted as e:
            retries += 1
            if retries > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                    "Raising ResourceExhausted."
                )
                raise e

            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            logger.warning(
                f"ResourceExhausted error calling {func.__name__}. Retrying in {current_delay:.2f} "
                f"seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except requests.exceptions.Timeout as e:
            retries += 1
            if retries > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__} due to Timeout."
                )
                raise e

            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            logger.warning(
                f"Timeout error calling {func.__name__}. Retrying in {current_delay:.2f} "
                f"seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except Exception as e:
            logger.error(
                f"Non-retryable error calling {func.__name__}: {e}", exc_info=True
            )
            raise e


# --- Define State ---
class AgentState(TypedDict):
    """langgraph state"""

    topic: str
    knowledge_level: str
    questions_asked: List[str]
    question_difficulties: List[int]
    answers: List[str]
    answer_evaluations: List[float]
    current_question: str
    current_question_difficulty: int
    current_target_difficulty: int
    consecutive_wrong: int
    wikipedia_content: str
    google_results: List[str]
    search_completed: bool
    consecutive_hard_correct_or_partial: int
    feedback: Optional[str]
    classification: Optional[float]


# --- Define Constants ---
EASY = 1
MEDIUM = 2
HARD = 3


class TechTreeAI:
    """Encapsulates the Tech Tree langgraph app"""

    def __init__(self) -> None:  # Added return type hint
        """Initialize the TechTreeAI."""
        self.state: Optional[AgentState] = None
        self.workflow: StateGraph = self._create_workflow()  # Added type hint
        self.graph = self.workflow.compile()
        self.is_quiz_complete: bool = False  # Added type hint
        self.search_status: str = ""  # Added type hint
        self.final_assessment: Dict[str, Any] = {}  # Added type hint

    def _create_workflow(self) -> StateGraph:
        """Create the langgraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("initialize", self._initialize)
        workflow.add_node("perform_internet_search", self._perform_internet_search)
        workflow.add_node("generate_question", self._generate_question)
        workflow.add_node("evaluate_answer", self._evaluate_answer)
        workflow.add_node("end", self._end)

        # Add edges
        workflow.add_edge("initialize", "perform_internet_search")
        workflow.add_edge("perform_internet_search", "generate_question")
        workflow.add_edge("generate_question", "evaluate_answer")
        workflow.add_conditional_edges(
            "evaluate_answer",
            self._should_continue,
            {"continue": "generate_question", END: "end"},
        )

        workflow.set_entry_point("initialize")
        return workflow

    # Added type hints
    def _initialize(
        self, _: Optional[AgentState] = None, topic: str = ""
    ) -> Dict[str, Any]:
        """Initialize the agent state with the given topic."""
        if not topic:
            raise ValueError("Topic is required")

        # Ensure return matches Dict[str, Any]
        initial_state: Dict[str, Any] = {
            "topic": topic,
            "knowledge_level": "beginner",
            "questions_asked": [],
            "question_difficulties": [],
            "answers": [],
            "answer_evaluations": [],
            "current_question": "",
            "current_question_difficulty": 0,
            "current_target_difficulty": EASY,
            "consecutive_wrong": 0,
            "wikipedia_content": "",
            "google_results": [],
            "search_completed": False,
            "consecutive_hard_correct_or_partial": 0,
            "feedback": None,
            "classification": None,
        }
        return initial_state

    # Added return type hint
    def _perform_internet_search(self, state: AgentState) -> Dict[str, Any]:
        """Performs internet search using Tavily API and stores results in state."""
        topic = state["topic"]
        self.search_status = (
            f"Searching the internet for information about '{topic}'..."
        )
        logger.info(self.search_status)

        # Check if Tavily client is configured
        if TAVILY is None:
            logger.warning("Tavily client not configured. Skipping internet search.")
            self.search_status = "Search skipped: Tavily client not configured."
            return {
                "wikipedia_content": "Search skipped: Tavily client not configured.",
                "google_results": [],
                "search_completed": True,
            }

        try:
            # Search Wikipedia
            self.search_status = "Searching Wikipedia..."
            logger.info(self.search_status)
            tavily_key = os.environ.get("TAVILY_API_KEY")
            key_preview = f"{tavily_key[:8]}..." if tavily_key else "Not Set"
            logger.debug(f"DEBUG: TAVILY_API_KEY = {key_preview}")

            wiki_search = call_with_retry(
                TAVILY.search,
                query=f"{topic} wikipedia",
                search_depth="advanced",
                include_domains=["en.wikipedia.org"],
                max_results=1,
            )
            wikipedia_content = (
                wiki_search.get("results", [{}])[0].get("content", "")
                if wiki_search.get("results")
                else ""
            )
            logger.debug(f"Wikipedia search result length: {len(wikipedia_content)}")

            # Search Google (excluding Wikipedia)
            self.search_status = "Searching Google..."
            logger.info(self.search_status)
            google_search = call_with_retry(
                TAVILY.search,
                query=topic,
                search_depth="advanced",
                exclude_domains=["wikipedia.org"],
                max_results=4,
            )
            google_results = [
                result.get("content", "") for result in google_search.get("results", [])
            ]
            logger.debug(f"Google search returned {len(google_results)} results.")

            self.search_status = "Search completed successfully."
            logger.info(self.search_status)
            return {
                "wikipedia_content": wikipedia_content,
                "google_results": google_results,
                "search_completed": True,
            }
        except Exception as e:  # pylint: disable=broad-except
            self.search_status = f"Error during internet search: {e}"
            logger.error(self.search_status, exc_info=True)
            return {
                "wikipedia_content": f"Error searching for {topic}: {str(e)}",
                "google_results": [],
                "search_completed": True,
            }

    # Added return type hint
    def _generate_question(self, state: AgentState) -> Dict[str, Any]:
        """Generates a question using the Gemini API and search results."""
        if MODEL is None:
            logger.error("Gemini model not configured. Cannot generate question.")
            return {
                "current_question": "Error: LLM model not configured.",
                "current_question_difficulty": MEDIUM,
                "questions_asked": state["questions_asked"],
                "question_difficulties": state["question_difficulties"],
            }

        target_difficulty = state["current_target_difficulty"]
        difficulty_name = (
            "easy"
            if target_difficulty == EASY
            else "medium" if target_difficulty == MEDIUM else "hard"
        )
        logger.info(
            f"Generating question for topic '{state['topic']}' at difficulty: {difficulty_name}"
        )

        wikipedia_content = state["wikipedia_content"]
        google_results = state["google_results"]

        search_context = f"Wikipedia information:\n{wikipedia_content}\n\n"
        search_context += "Additional information from other sources:\n"
        for i, result in enumerate(google_results, 1):
            search_context += f"Source {i}:\n{result}\n\n"
        logger.debug(f"Search context length: {len(search_context)}")

        prompt = f"""
        You are an expert tutor creating questions on the topic of {state['topic']} so
        you can assess their level of understanding of the topic to decide what help
        they will need to master it.
        Assume the user is UK based, and currency is in GBP.

        The student is at a {state['knowledge_level']} knowledge level.
        Ask a question on the topic, avoiding questions already asked.
        Avoid questions if the answer is the name of the topic.
        Questions should only require short answers, not detailed responses.
        Never mention the sources, or the provided information,  as the user has no
        access to the source documents and does not know they exist.

        The question should be at {difficulty_name} difficulty level ({target_difficulty}).

        Use the following information from internet searches to create an accurate and
        up-to-date question:

        {search_context}

        Format your response as follows:
        Difficulty: {target_difficulty}
        Question: [your question here]

        Questions already asked: {', '.join(state['questions_asked']) or 'None'}
        """

        try:
            response = call_with_retry(MODEL.generate_content, prompt)
            response_text = response.text
            logger.debug(
                f"LLM response for question generation: {response_text[:200]}..."
            )

            difficulty = MEDIUM
            question = response_text

            difficulty_pattern = re.compile(r"Difficulty:\s*(\d+)", re.IGNORECASE)
            question_pattern = re.compile(
                r"Question:\s*(.*?)(?:\n|$)", re.IGNORECASE | re.DOTALL
            )

            difficulty_match = difficulty_pattern.search(response_text)
            if difficulty_match:
                try:
                    difficulty = int(difficulty_match.group(1))
                    logger.debug(f"Extracted difficulty: {difficulty}")
                except ValueError:
                    logger.warning(
                        f"Could'nt parse extracted difficulty '{difficulty_match.group(1)}' as int."
                    )
                    difficulty = target_difficulty

            question_match = question_pattern.search(response_text)
            if question_match:
                question = question_match.group(1).strip()
                logger.debug(f"Extracted question: {question[:100]}...")
            else:
                logger.warning(
                    "Could not extract question using regex, using full response."
                )

        except Exception as e:
            logger.error(f"Error in _generate_question: {str(e)}", exc_info=True)
            difficulty = MEDIUM
            question = f"Error generating question: {str(e)}"

        return {
            "current_question": question,
            "current_question_difficulty": difficulty,
            "questions_asked": state["questions_asked"] + [question],
            "question_difficulties": state["question_difficulties"] + [difficulty],
        }

    # Added return type hint
    def _evaluate_answer(self, state: AgentState, answer: str = "") -> Dict[str, Any]:
        """Evaluates the answer using the Gemini API."""
        if not answer:
            raise ValueError("Answer is required")
        logger.info(
            f"Evaluating answer for question: {state['current_question'][:100]}..."
        )
        logger.debug(f"User answer: {answer}")

        if MODEL is None:
            logger.error("Gemini model not configured. Cannot evaluate answer.")
            return {
                "answers": state["answers"] + [answer],
                "answer_evaluations": state["answer_evaluations"] + [0.0],
                "consecutive_wrong": state["consecutive_wrong"] + 1,
                "current_target_difficulty": state["current_target_difficulty"],
                "consecutive_hard_correct_or_partial": 0,
                "feedback": "Error: LLM model not configured.",
                "classification": 0.0,
            }

        wikipedia_content = state["wikipedia_content"]
        google_results = state["google_results"]

        search_context = f"Wikipedia information:\n{wikipedia_content}\n\n"
        search_context += "Additional information from other sources:\n"
        for i, result in enumerate(google_results, 1):
            search_context += f"Source {i}:\n{result}\n\n"

        prompt = f"""
        You are an expert tutor in {state['topic']}.
        Here is a question that was asked:

        Question: {state['current_question']}

        Here is the student's answer:

        Answer: {answer}

        Use the following information from internet searches to evaluate the answer accurately:

        {search_context}

        Evaluate the answer for correctness and completeness, allowing that only short
        answers were requested.
        Provide feedback on the answer, but never mention the sources, or provided information,
        as the user has no access to the source documents or other information and does not know
        they exist.

        Important: If the student responds with "I don't know" or similar, the answer is incorrect
        and this does not need explaining: classify the answer as incorrect return the correct
        answer as feedback.

        Classify the answer as one of: correct=1, partially correct=0.5, or incorrect=0.
        Make sure to include the classification explicitly as a number in your response.
        Respond with the classification: the feedback. For example:
        1:Correct answer because that is the correct name
        or
        0:That is the wrong answer because swans can't live in space
        """

        try:
            response = call_with_retry(MODEL.generate_content, prompt)
            evaluation = response.text
            logger.debug(f"LLM evaluation response: {evaluation[:200]}...")

            parts = evaluation.split(":", 1)
            classification_str = parts[0].strip()
            feedback = parts[1].strip() if len(parts) > 1 else ""

            try:
                classification = float(classification_str)
                if classification > 0.75:
                    classification = 1.0
                elif classification > 0.25:
                    classification = 0.5
                else:
                    classification = 0.0
                logger.debug(f"Extracted classification: {classification}")
            except ValueError:
                logger.warning(
                    f"Could not parse classification '{classification_str}' "
                    "as float. Defaulting to 0.0."
                )
                classification = 0.0
                feedback = evaluation

        except Exception as e:
            logger.error(f"Error in _evaluate_answer: {str(e)}", exc_info=True)
            classification = 0.0
            feedback = f"Error evaluating answer: {str(e)}"

        current_difficulty = state["current_target_difficulty"]
        consecutive_wrong = state["consecutive_wrong"]
        consecutive_hard_correct_or_partial = state.get(
            "consecutive_hard_correct_or_partial", 0
        )

        if classification == 0.0:
            consecutive_wrong += 1
            next_difficulty = current_difficulty
            consecutive_hard_correct_or_partial = 0
            logger.debug(
                f"Incorrect answer. Consecutive wrong: {consecutive_wrong}. "
                f"Next difficulty: {next_difficulty}"
            )
        else:
            consecutive_wrong = 0
            if current_difficulty == EASY:
                next_difficulty = MEDIUM
            elif current_difficulty == MEDIUM:
                next_difficulty = HARD
            else:  # current_difficulty == HARD
                next_difficulty = HARD
                if classification >= 0.5:
                    consecutive_hard_correct_or_partial += 1
            logger.debug(
                f"Correct/Partial answer. Consecutive wrong reset. Next difficulty: "
                f"{next_difficulty}. Consecutive HARD correct/partial: "
                f"{consecutive_hard_correct_or_partial}"
            )

        if current_difficulty != HARD:
            consecutive_hard_correct_or_partial = 0
            logger.debug(
                "Reset consecutive HARD counter as current difficulty is not HARD."
            )

        return {
            "answers": state["answers"] + [answer],
            "answer_evaluations": state["answer_evaluations"] + [classification],
            "consecutive_wrong": consecutive_wrong,
            "current_target_difficulty": next_difficulty,
            "consecutive_hard_correct_or_partial": consecutive_hard_correct_or_partial,
            "feedback": feedback,
            "classification": classification,
        }

    # Added return type hint
    def _end(self, state: AgentState) -> Dict[str, Any]:
        """Provides a final assessment of the user's knowledge level."""
        self.is_quiz_complete = True
        logger.info("Quiz ended. Calculating final assessment.")

        total_score = 0.0
        max_possible_score = 0

        for i, evaluation in enumerate(state["answer_evaluations"]):
            if i < len(state["question_difficulties"]):
                difficulty = state["question_difficulties"][i]
                total_score += evaluation * difficulty
                max_possible_score += difficulty

        weighted_percentage = (
            (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        )
        logger.debug(
            f"Total score: {total_score}, Max possible: {max_possible_score},"
            f" Weighted %: {weighted_percentage:.2f}"
        )

        if weighted_percentage >= 85:
            final_level = "advanced"
        elif weighted_percentage >= 65:
            final_level = "good knowledge"
        elif weighted_percentage >= 35:
            final_level = "early learner"
        else:
            final_level = "beginner"
        logger.info(f"Final determined knowledge level: {final_level}")

        counts = Counter(state["answer_evaluations"])

        self.final_assessment = {
            "correct_answers": counts[1.0],
            "partially_correct_answers": counts[0.5],
            "incorrect_answers": counts[0.0],
            "total_score": total_score,
            "max_possible_score": max_possible_score,
            "weighted_percentage": weighted_percentage,
            "knowledge_level": final_level,
        }
        logger.debug(f"Final assessment details: {self.final_assessment}")

        return {}  # Return empty dict as per convention for end nodes

    # Added return type hint
    def _should_continue(self, state: AgentState) -> str:
        """Decides whether to continue or end the conversation."""
        if state["consecutive_wrong"] >= 2:
            logger.info("Ending quiz: 2 consecutive wrong answers.")
            return END

        if state.get("consecutive_hard_correct_or_partial", 0) >= 3:
            logger.info(
                "Ending quiz: 3 consecutive correct/partial answers at HARD difficulty."
            )
            return END

        logger.debug("Continuing quiz.")
        return "continue"

    # Added return type hint
    def initialize(self, topic: str) -> Dict[str, Any]:
        """Initialize the agent with a topic."""
        logger.debug(f"Initializing TechTreeAI with topic: {topic}")
        try:
            initial_state_dict = self._initialize(topic=topic)
            self.state = cast(AgentState, initial_state_dict)
            logger.debug(f"Successfully initialized state for topic: {topic}")
            return {"status": "initialized", "topic": topic}
        except Exception as e:
            logger.error(f"Error initializing TechTreeAI: {str(e)}", exc_info=True)
            raise

    # Added return type hint
    def perform_search(self) -> Dict[str, Any]:
        """Perform internet search for the topic."""
        if not self.state:
            logger.error("Error - Agent not initialized for search")
            raise ValueError("Agent not initialized")
        logger.debug(f"Starting search for topic: {self.state['topic']}")

        try:
            result = self._perform_internet_search(self.state)
            logger.debug(f"Search completed with result keys: {list(result.keys())}")
            # Update state carefully
            for key, value in result.items():
                if key in AgentState.__annotations__:
                    self.state[key] = value  # type: ignore
                else:
                    logger.warning(
                        f"Ignoring unexpected key '{key}' from search node result."
                    )
            return {"status": "search_completed", "search_status": self.search_status}
        except Exception as e:
            logger.error(f"Error during search: {str(e)}", exc_info=True)
            raise

    # Added return type hint
    def generate_question(self) -> Dict[str, Any]:
        """Generate a question based on the current state."""
        if not self.state:
            logger.error("Error - Agent not initialized for question generation")
            raise ValueError("Agent not initialized")

        result = self._generate_question(self.state)
        logger.debug(
            f"Question generation completed with result keys: {list(result.keys())}"
        )
        # Update state carefully
        for key, value in result.items():
            if key in AgentState.__annotations__:
                self.state[key] = value  # type: ignore
            else:
                logger.warning(
                    f"Ignoring unexpected key '{key}' from generate_question node result."
                )

        difficulty = self.state["current_question_difficulty"]
        difficulty_str = (
            "EASY"
            if difficulty == EASY
            else "MEDIUM" if difficulty == MEDIUM else "HARD"
        )

        return {
            "question": self.state["current_question"],
            "difficulty": difficulty,
            "difficulty_str": difficulty_str,
        }

    # Added return type hint
    def evaluate_answer(self, answer: str) -> Dict[str, Any]:
        """Evaluate the user's answer."""
        if not self.state:
            logger.error("Error - Agent not initialized for answer evaluation")
            raise ValueError("Agent not initialized")

        result = self._evaluate_answer(self.state, answer)
        logger.debug(
            f"Answer evaluation completed with result keys: {list(result.keys())}"
        )
        # Update state carefully
        for key, value in result.items():
            if key in AgentState.__annotations__:
                self.state[key] = value  # type: ignore
            else:
                logger.warning(
                    f"Ignoring unexpected key '{key}' from evaluate_answer node result."
                )

        # Check if we should continue or end
        continue_or_end = self._should_continue(self.state)
        if continue_or_end == END:
            self._end(self.state)

        # Ensure classification is treated as float
        classification_val = result.get("classification", 0.0)
        if not isinstance(classification_val, float):
            try:
                classification_val = float(classification_val)
            except (ValueError, TypeError):
                classification_val = 0.0

        return {
            "classification": classification_val,
            "feedback": result.get("feedback", ""),
            "is_correct": classification_val == 1.0,
            "is_partially_correct": classification_val == 0.5,
            "is_incorrect": classification_val == 0.0,
            "is_complete": self.is_quiz_complete,
        }

    # Added return type hint
    def get_final_assessment(self) -> Dict[str, Any]:
        """Get the final assessment of the user's knowledge level."""
        if not self.is_quiz_complete:
            logger.warning("Attempted to get final assessment before quiz completion.")
            return {"status": "quiz_not_complete"}

        return self.final_assessment

    # Added return type hint
    def is_complete(self) -> bool:
        """Check if the quiz is complete."""
        return self.is_quiz_complete

    # Added return type hint
    def get_search_status(self) -> str:
        """Return the search status."""
        return self.search_status

    # Added return type hint
    def process_response(self, answer: str) -> Dict[str, Any]:
        """Process the user's response and return the result."""
        if not self.state:
            logger.error("Error - Agent not initialized for processing response")
            raise ValueError("Agent not initialized")

        result = self.evaluate_answer(answer)

        return {
            "completed": self.is_quiz_complete,
            "feedback": result.get("feedback", ""),  # Use get for safety
        }
