# backend/ai/onboarding/onboarding_graph.py
# pylint: disable=broad-exception-caught,singleton-comparison
"""Langgraph graph for onboarding - evaluating the user on a topic"""

import logging
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict, cast

import google.generativeai as genai
import requests
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from langgraph.graph import END, StateGraph
from tavily import TavilyClient  # type: ignore

from backend.exceptions import log_and_raise_new

from .prompts import EVALUATE_ANSWER_PROMPT, GENERATE_QUESTION_PROMPT

# Add logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Tavily and Gemini API timeouts
TAVILY_TIMEOUT = 5  # seconds

# Configure Gemini API
# Define type hint before assignment
MODEL: Optional[genai.GenerativeModel] = None  # type: ignore[name-defined]
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gemini_model_name = os.environ.get("GEMINI_MODEL")
    if not gemini_api_key:
        log_and_raise_new(
            exception_type=KeyError,
            exception_message="GEMINI_API_KEY",
            exc_info=False,
        )
    if not gemini_model_name:
        log_and_raise_new(
            exception_type=KeyError,
            exception_message="GEMINI_MODEL",
            exc_info=False,
        )

    # Configuration within the try block (8 spaces indent)
    genai.configure(api_key=gemini_api_key)  # type: ignore[attr-defined]
    MODEL = genai.GenerativeModel(gemini_model_name)  # type: ignore[attr-defined]
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
        logger.error(
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
        except ResourceExhausted as ex:
            retries += 1
            if retries > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                    "Raising ResourceExhausted."
                )
                raise ex

            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            logger.warning(
                f"ResourceExhausted error calling {func.__name__}. Retrying in {current_delay:.2f} "
                f"seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except requests.exceptions.Timeout as ex:
            retries += 1
            if retries > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__} due to Timeout."
                )
                raise ex

            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            logger.warning(
                f"Timeout error calling {func.__name__}. Retrying in {current_delay:.2f} "
                f"seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except Exception as exc:
            logger.error(
                f"Non-retryable error calling {func.__name__}: {exc}", exc_info=True
            )
            raise exc


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

    def __init__(self) -> None:
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

    def _perform_internet_search(self, state: AgentState) -> Dict[str, Any]:
        """Performs internet search using Tavily API and stores results in state."""
        topic = state["topic"]
        self.search_status = (
            f"Searching the internet for information about '{topic}'..."
        )

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

            # Search Google (excluding Wikipedia)
            self.search_status = "Searching Google..."
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

            self.search_status = "Search completed successfully."
            return {
                "wikipedia_content": wikipedia_content,
                "google_results": google_results,
                "search_completed": True,
            }
        except Exception as ex:  # pylint: disable=broad-except
            self.search_status = f"Error during internet search: {ex}"
            logger.error(self.search_status, exc_info=True)
            return {
                "wikipedia_content": f"Error searching for {topic}: {str(ex)}",
                "google_results": [],
                "search_completed": True,
            }

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

        wikipedia_content = state["wikipedia_content"]
        google_results = state["google_results"]

        search_context = f"Wikipedia information:\n{wikipedia_content}\n\n"
        search_context += "Additional information from other sources:\n"
        for i, result in enumerate(google_results, 1):
            search_context += f"Source {i}:\n{result}\n\n"

        questions_asked_str = ", ".join(state["questions_asked"]) or "None"

        prompt = GENERATE_QUESTION_PROMPT.format(
            topic=state["topic"],
            knowledge_level=state["knowledge_level"],
            difficulty_name=difficulty_name,
            target_difficulty=target_difficulty,
            search_context=search_context,
            questions_asked_str=questions_asked_str,
        )

        try:
            response = call_with_retry(MODEL.generate_content, prompt)
            response_text = response.text

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
                except ValueError:
                    difficulty = target_difficulty

            question_match = question_pattern.search(response_text)
            if question_match:
                question = question_match.group(1).strip()

        except Exception as ex:
            logger.error(f"Error in _generate_question: {str(ex)}", exc_info=True)
            difficulty = MEDIUM
            question = f"Error generating question: {str(ex)}"

        return {
            "current_question": question,
            "current_question_difficulty": difficulty,
            "questions_asked": state["questions_asked"] + [question],
            "question_difficulties": state["question_difficulties"] + [difficulty],
        }

    # pylint: disable=too-many-branches, too-many-statements
    def _evaluate_answer(self, state: AgentState, answer: str = "") -> Dict[str, Any]:
        """Evaluates the answer using the Gemini API."""
        if not answer:
            raise ValueError("Answer is required")

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

        prompt = EVALUATE_ANSWER_PROMPT.format(
            topic=state["topic"],
            current_question=state["current_question"],
            answer=answer,
            search_context=search_context,
        )

        try:
            response = call_with_retry(MODEL.generate_content, prompt)
            evaluation = response.text

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
            except ValueError:
                classification = 0.0
                feedback = evaluation

        except Exception as ex:
            logger.error(f"Error in _evaluate_answer: {str(ex)}", exc_info=True)
            classification = 0.0
            feedback = f"Error evaluating answer: {str(ex)}"

        # Update state based on evaluation
        consecutive_wrong = state["consecutive_wrong"]
        difficulty = state["current_target_difficulty"]
        consecutive_hard_correct_or_partial = state[
            "consecutive_hard_correct_or_partial"
        ]

        if classification < 0.5:  # Incorrect
            consecutive_wrong += 1
            difficulty = max(EASY, difficulty - 1)
            consecutive_hard_correct_or_partial = 0
        else:  # Correct or partially correct
            consecutive_wrong = 0
            difficulty = min(HARD, difficulty + 1)
            if state["current_target_difficulty"] == HARD:
                if classification >= 0.5:
                    consecutive_hard_correct_or_partial += 1

        # Reset consecutive hard counter if current difficulty is not HARD
        if state["current_target_difficulty"] != HARD:
            consecutive_hard_correct_or_partial = 0

        return {
            "answers": state["answers"] + [answer],
            "answer_evaluations": state["answer_evaluations"] + [classification],
            "consecutive_wrong": consecutive_wrong,
            "current_target_difficulty": difficulty,
            "consecutive_hard_correct_or_partial": consecutive_hard_correct_or_partial,
            "feedback": feedback,
            "classification": classification,
        }

    def _end(self, state: AgentState) -> Dict[str, Any]:
        """Ends the quiz and calculates the final assessment."""
        self.is_quiz_complete = True

        # Calculate final score and level
        total_score = sum(state["answer_evaluations"])
        max_possible_score = len(state["questions_asked"])
        score_percentage = (
            (total_score / max_possible_score) * 100 if max_possible_score > 0 else 0
        )

        # Determine final level based on score percentage
        if score_percentage >= 75:
            final_level = "advanced"
        elif score_percentage >= 40:
            final_level = "intermediate"
        else:
            final_level = "beginner"

        self.final_assessment = {
            "topic": state["topic"],
            "knowledge_level": final_level,
            "score": score_percentage,
            "questions": state["questions_asked"],
            "responses": state["answers"],
            "evaluations": state["answer_evaluations"],
        }

        return {"knowledge_level": final_level}

    def _should_continue(self, state: AgentState) -> str:
        """Determines whether to continue the quiz or end."""
        if state["consecutive_wrong"] >= 3:
            return END
        if state["consecutive_hard_correct_or_partial"] >= 3:
            return END
        if len(state["questions_asked"]) >= 10:
            return END

        return "continue"

    def initialize(self, topic: str) -> Dict[str, Any]:
        """Initialize the agent with a topic."""
        try:
            initial_state_dict = self._initialize(topic=topic)
            self.state = cast(AgentState, initial_state_dict)
            return {"status": "initialized", "topic": topic}
        except Exception as ex:
            logger.error(f"Error initializing TechTreeAI: {str(ex)}", exc_info=True)
            raise

    def perform_search(self) -> Dict[str, Any]:
        """Perform the internet search."""
        if not self.state:
            log_and_raise_new(
                exception_type=ValueError,
                exception_message="Agent not initialized",
                exc_info=False,
            )

        try:
            result = self._perform_internet_search(self.state)
            # Update state carefully
            self.state["wikipedia_content"] = result["wikipedia_content"]
            self.state["google_results"] = result["google_results"]
            self.state["search_completed"] = result["search_completed"]
            return result
        except Exception as ex:
            logger.error(f"Error during search: {str(ex)}", exc_info=True)
            raise

    def generate_question(self) -> Dict[str, Any]:
        """Generate the next question."""
        if not self.state:
            log_and_raise_new(
                exception_type=ValueError,
                exception_message="Agent not initialized",
                exc_info=False,
            )
        if not self.state["search_completed"]:
            raise ValueError("Search must be completed before generating a question")

        result = self._generate_question(self.state)
        # Update state
        self.state["current_question"] = result["current_question"]
        self.state["current_question_difficulty"] = result[
            "current_question_difficulty"
        ]
        self.state["questions_asked"] = result["questions_asked"]
        self.state["question_difficulties"] = result["question_difficulties"]
        return {
            "question": result["current_question"],
            "difficulty": result["current_question_difficulty"],
        }

    def evaluate_answer(self, answer: str) -> Dict[str, Any]:
        """Evaluate the user's answer."""
        if not self.state:
            log_and_raise_new(
                exception_type=ValueError,
                exception_message="Agent not initialized",
                exc_info=False,
            )
        if not self.state["current_question"]:
            raise ValueError("No question has been generated yet")

        result = self._evaluate_answer(self.state, answer)
        # Update state
        self.state["answers"] = result["answers"]
        self.state["answer_evaluations"] = result["answer_evaluations"]
        self.state["consecutive_wrong"] = result["consecutive_wrong"]
        self.state["current_target_difficulty"] = result["current_target_difficulty"]
        self.state["consecutive_hard_correct_or_partial"] = result[
            "consecutive_hard_correct_or_partial"
        ]
        self.state["feedback"] = result["feedback"]
        self.state["classification"] = result["classification"]

        # Check if the quiz should end
        continue_status = self._should_continue(self.state)
        if continue_status == END:
            end_result = self._end(self.state)
            self.state["knowledge_level"] = end_result["knowledge_level"]

        return {
            "feedback": result["feedback"],
            "classification": result["classification"],
            "is_complete": self.is_quiz_complete,
            "final_level": (
                self.state.get("knowledge_level") if self.is_quiz_complete else None
            ),
        }

    def get_final_assessment(self) -> Dict[str, Any]:
        """Get the final assessment details after the quiz is complete."""
        if not self.is_quiz_complete:
            raise ValueError("Quiz is not yet complete")
        return self.final_assessment

    def is_complete(self) -> bool:
        """Check if the quiz is complete."""
        return self.is_quiz_complete

    def get_search_status(self) -> str:
        """Get the current status of the internet search."""
        return self.search_status

    def process_response(self, answer: str) -> Dict[str, Any]:
        """Process the user's response (answer) and return the evaluation."""
        if not self.state:
            log_and_raise_new(
                exception_type=ValueError,
                exception_message="Agent not initialized",
                exc_info=False,
            )
        if self.is_quiz_complete:
            raise ValueError("Quiz is already complete")

        evaluation_result = self.evaluate_answer(answer)

        if self.is_quiz_complete:
            return evaluation_result  # Contains final level etc.
        else:
            # Generate the next question if not complete
            next_question_result = self.generate_question()
            return {**evaluation_result, **next_question_result}
