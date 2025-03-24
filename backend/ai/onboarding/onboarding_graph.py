# pylint: disable=broad-exception-caught,singleton-comparison
""" Langgraph graph for onboarding - evaluating the user on a topic """

import os
import re
import time
import random
from collections import Counter
from typing import Dict, List, TypedDict, Optional

import requests
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from tavily import TavilyClient

# Load environment variables
load_dotenv()

# Configure Tavily and Gemini API timeouts
TAVILY_TIMEOUT = 5  # seconds

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(
    "gemini-2.0-pro-exp-02-05"
)  # User specified gemini 2 flash, but using gemini-pro for now

# Configure Tavily API
tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


def call_with_retry(func, *args, max_retries=5, initial_delay=1, **kwargs):
    """Call a function with exponential backoff retry logic for quota errors."""
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            time.sleep(delay)
        except requests.exceptions.Timeout:
            retries += 1
            if retries > max_retries:
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            time.sleep(delay)


# --- Define State ---
class AgentState(TypedDict):
    """ langgraph state """
    topic: str
    knowledge_level: str
    questions_asked: List[str]
    question_difficulties: List[int]  # Store difficulty level of each question
    answers: List[str]
    answer_evaluations: List[float]  # Store the evaluation results
    current_question: str
    current_question_difficulty: int  # Store difficulty of current question
    current_target_difficulty: int  # Target difficulty for the next question
    consecutive_wrong: int  # Track consecutive wrong answers
    wikipedia_content: str  # Content from Wikipedia search
    google_results: List[str]  # Content from Google search results
    search_completed: bool  # Flag to indicate if search has been completed
    consecutive_hard_correct_or_partial: (
        int  # Track consecutive correct/partially correct at HARD
    )


# --- Define Constants ---
EASY = 1
MEDIUM = 2
HARD = 3


class TechTreeAI:
    """Encapsulates the Tech Tree langgraph app """

    def __init__(self):
        """Initialize the TechTreeAI."""
        self.state: Optional[AgentState] = None
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()
        self.is_quiz_complete = False
        self.search_status = ""
        self.final_assessment = {}

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

    def _initialize(self, _: Optional[AgentState] = None, topic: str = "") -> Dict:
        """Initialize the agent state with the given topic."""
        if not topic:
            raise ValueError("Topic is required")

        return {
            "topic": topic,
            "knowledge_level": "beginner",  # Initial knowledge level
            "questions_asked": [],
            "question_difficulties": [],  # Initialize question difficulties
            "answers": [],
            "answer_evaluations": [],  # Initialize answer_evaluations
            "current_question": "",
            "current_question_difficulty": 0,  # Initialize current question difficulty
            "current_target_difficulty": EASY,  # Start with easy questions
            "consecutive_wrong": 0,  # Track consecutive wrong answers
            "continue_flag": True,  # Initialize continue_flag
            "wikipedia_content": "",  # Initialize Wikipedia content
            "google_results": [],  # Initialize Google results
            "search_completed": False,  # Initialize search completion flag
            "consecutive_hard_correct_or_partial": 0,  # Initialize the new counter
        }

    def _perform_internet_search(self, state: AgentState) -> Dict:
        """Performs internet search using Tavily API and stores results in state."""
        topic = state["topic"]
        self.search_status = (
            f"Searching the internet for information about '{topic}'..."
        )

        try:
            # Search Wikipedia
            self.search_status = "Searching Wikipedia..."
            print(f"DEBUG: TAVILY_API_KEY = {os.environ.get('TAVILY_API_KEY')[0:8]}...")
            wiki_search = call_with_retry(
                tavily.search,
                query=f"{topic} wikipedia",
                search_depth="advanced",
                include_domains=["en.wikipedia.org"],
                max_results=1,
                timeout=TAVILY_TIMEOUT
            )
            wikipedia_content = (
                wiki_search.get("results", [{}])[0].get("content", "")
                if wiki_search.get("results")
                else ""
            )

            # Search Google (excluding Wikipedia)
            self.search_status = "Searching Google..."
            google_search = call_with_retry(
                tavily.search,
                query=topic,
                search_depth="advanced",
                exclude_domains=["wikipedia.org"],
                max_results=4,
                timeout=TAVILY_TIMEOUT
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
        except Exception as e: #pylint: disable=broad-except
            self.search_status = f"Error during internet search: {e}"
            # Return empty results but mark as completed to continue the flow
            return {
                "wikipedia_content": f"Error searching for {topic}: {str(e)}",
                "google_results": [],
                "search_completed": True,
            }

    def _generate_question(self, state: AgentState) -> Dict:
        """Generates a question using the Gemini API and search results."""
        # Get the target difficulty level
        target_difficulty = state["current_target_difficulty"]
        difficulty_name = (
            "easy"
            if target_difficulty == EASY
            else "medium" if target_difficulty == MEDIUM else "hard"
        )

        # Prepare search content for the prompt
        wikipedia_content = state["wikipedia_content"]
        google_results = state["google_results"]

        # Combine search results into a single context
        search_context = f"Wikipedia information:\n{wikipedia_content}\n\n"
        search_context += "Additional information from other sources:\n"
        for i, result in enumerate(google_results, 1):
            search_context += f"Source {i}:\n{result}\n\n"

        # Construct the prompt for Gemini
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

        Use the following information from internet searches to create an accurate and up-to-date question:

        {search_context}

        Format your response as follows:
        Difficulty: {target_difficulty}
        Question: [your question here]

        Questions already asked: {', '.join(state['questions_asked']) or 'None'}
        """

        try:
            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text

            # Parse the response to extract difficulty and question
            difficulty = MEDIUM  # Default difficulty
            question = response_text
        except Exception as e:
            print(f"Error in _generate_question: {str(e)}")
            difficulty = MEDIUM  # Default difficulty
            question = f"Error generating question: {str(e)}"

        # Try to extract difficulty and question from formatted response using regex

        # Pattern to match "Difficulty: X" and "Question: Y"
        difficulty_pattern = re.compile(r"Difficulty:\s*(\d+)", re.IGNORECASE)
        question_pattern = re.compile(
            r"Question:\s*(.*?)(?:\n|$)", re.IGNORECASE | re.DOTALL
        )

        # Extract difficulty
        difficulty_match = difficulty_pattern.search(response_text)
        if difficulty_match:
            difficulty = int(difficulty_match.group(1))

        # Extract question
        question_match = question_pattern.search(response_text)
        if question_match:
            question = question_match.group(1).strip()

        # Update state with the new question and its difficulty
        return {
            "current_question": question,
            "current_question_difficulty": difficulty,
            "questions_asked": state["questions_asked"] + [question],
            "question_difficulties": state["question_difficulties"] + [difficulty],
        }

    def _evaluate_answer(self, state: AgentState, answer: str = "") -> Dict:
        """Evaluates the answer using the Gemini API."""
        if not answer:
            raise ValueError("Answer is required")

        # Prepare search content for the prompt
        wikipedia_content = state["wikipedia_content"]
        google_results = state["google_results"]

        # Combine search results into a single context
        search_context = f"Wikipedia information:\n{wikipedia_content}\n\n"
        search_context += "Additional information from other sources:\n"
        for i, result in enumerate(google_results, 1):
            search_context += f"Source {i}:\n{result}\n\n"

        # Construct the prompt for Gemini to evaluate the answer
        prompt = f"""
        You are an expert tutor in {state['topic']}.
        Here is a question that was asked:

        Question: {state['current_question']}

        Here is the student's answer:

        Answer: {answer}

        Use the following information from internet searches to evaluate the answer accurately:

        {search_context}

        Evaluate the answer for correctness and completeness, allowing that only short answers were requested.
        Provide feedback on the answer, but never mention the sources, or provided information,
        as the user has no access to the source documents or other information and does not know they
        exist.

        Important: If the student responds with "I don't know" or similar, the answer is incorrect and
        this does not need explaining: classify the answer as incorrect return the correct answer as feedback.

        Classify the answer as one of: correct=1, partially correct=0.5, or incorrect=0.
        Make sure to include the classification explicitly as a number in your response.
        Respond with the classification: the feedback. For example:
        1:Correct answer because that is the correct name
        or
        0:That is the wrong answer because swans can't live in space
        """

        try:
            response = call_with_retry(model.generate_content, prompt)
            evaluation = response.text

            # Extract the classification, the bit before the ':'
            parts = evaluation.split(":")
            classification: float = float(parts[0])
            feedback = parts[1] if len(parts) > 1 else ""
        except Exception as e:
            print(f"Error in _evaluate_answer: {str(e)}")
            classification = 0.0  # Default to incorrect
            feedback = f"Error evaluating answer: {str(e)}"

        # Update consecutive wrong counter and target difficulty
        current_difficulty = state["current_target_difficulty"]
        consecutive_wrong = state["consecutive_wrong"]
        consecutive_hard_correct_or_partial = state.get(
            "consecutive_hard_correct_or_partial", 0
        )

        if classification == 0.0:  # Incorrect
            consecutive_wrong += 1
            # Keep the same difficulty level for the next question
            next_difficulty = current_difficulty
            # Reset the consecutive HARD counter
            consecutive_hard_correct_or_partial = 0
        else:
            consecutive_wrong = 0
            # If correct or partially correct, increase difficulty if possible
            if current_difficulty == EASY:
                next_difficulty = MEDIUM
            elif current_difficulty == MEDIUM:
                next_difficulty = HARD
            else:
                next_difficulty = HARD  # Stay at HARD if already at HARD
                # Increment if at HARD and correct/partially correct
                if classification >= 0.5:
                    consecutive_hard_correct_or_partial += 1

        # Reset the counter if the difficulty is not HARD
        if current_difficulty != HARD:
            consecutive_hard_correct_or_partial = 0

        return {
            "answers": state["answers"] + [answer],
            "answer_evaluations": state["answer_evaluations"] + [classification],
            "consecutive_wrong": consecutive_wrong,
            "current_target_difficulty": next_difficulty,
            "consecutive_hard_correct_or_partial": consecutive_hard_correct_or_partial,
            "feedback": feedback,
            "classification": classification,
        }

    def _end(self, state: AgentState) -> Dict:
        """Provides a final assessment of the user's knowledge level."""
        self.is_quiz_complete = True

        # Calculate score directly
        total_score = 0
        max_possible_score = 0

        for i, evaluation in enumerate(state["answer_evaluations"]):
            if i < len(state["question_difficulties"]):
                difficulty = state["question_difficulties"][i]

                # Calculate score: answer correctness * difficulty level
                total_score += evaluation * difficulty
                max_possible_score += difficulty

        # Calculate percentage
        weighted_percentage = (
            (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        )

        # Determine knowledge level
        if weighted_percentage >= 85:
            final_level = "advanced"
        elif weighted_percentage >= 65:
            final_level = "good knowledge"
        elif weighted_percentage >= 35:
            final_level = "early learner"
        else:
            final_level = "beginner"

        counts = Counter(state["answer_evaluations"])

        # Store final assessment
        self.final_assessment = {
            "correct_answers": counts[1.0],
            "partially_correct_answers": counts[0.5],
            "incorrect_answers": counts[0.0],
            "total_score": total_score,
            "max_possible_score": max_possible_score,
            "weighted_percentage": weighted_percentage,
            "knowledge_level": final_level,
        }

        return {}

    def _should_continue(self, state: AgentState) -> str:
        """Decides whether to continue or end the conversation."""
        # End if the user has gotten 2 consecutive wrong answers
        if state["consecutive_wrong"] >= 2:
            return END

        # End if user has 3 consecutive correct or partially correct answers at HARD difficulty
        if state.get("consecutive_hard_correct_or_partial", 0) >= 3:
            return END

        # Otherwise continue
        return "continue"

    def initialize(self, topic: str) -> Dict:
        """Initialize the agent with a topic."""
        print(f"DEBUG: Initializing TechTreeAI with topic: {topic}")
        try:
            self.state = self._initialize(topic=topic)
            print(f"DEBUG: Successfully initialized state for topic: {topic}")
            return {"status": "initialized", "topic": topic}
        except Exception as e:
            print(f"DEBUG: Error initializing TechTreeAI: {str(e)}")
            raise

    def perform_search(self) -> Dict:
        """Perform internet search for the topic."""
        print(f"DEBUG: Starting search for topic: {self.state['topic'] if self.state else 'None'}")
        if not self.state:
            print("DEBUG: Error - Agent not initialized")
            raise ValueError("Agent not initialized")

        try:
            result = self._perform_internet_search(self.state)
            print(f"DEBUG: Search completed with result: {result}")
            self.state.update(result)
            return {"status": "search_completed", "search_status": self.search_status}
        except Exception as e:
            print(f"DEBUG: Error during search: {str(e)}")
            raise

    def generate_question(self) -> Dict:
        """Generate a question based on the current state."""
        if not self.state:
            raise ValueError("Agent not initialized")

        result = self._generate_question(self.state)
        self.state.update(result)

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

    def evaluate_answer(self, answer: str) -> Dict:
        """Evaluate the user's answer."""
        if not self.state:
            raise ValueError("Agent not initialized")

        result = self._evaluate_answer(self.state, answer)
        self.state.update(result)

        # Check if we should continue or end
        continue_or_end = self._should_continue(self.state)
        if continue_or_end == END:
            self._end(self.state)

        return {
            "classification": result["classification"],
            "feedback": result.get("feedback", ""),
            "is_correct": result["classification"] == 1.0,
            "is_partially_correct": result["classification"] == 0.5,
            "is_incorrect": result["classification"] == 0.0,
            "is_complete": self.is_quiz_complete,
        }

    def get_final_assessment(self) -> Dict:
        """Get the final assessment of the user's knowledge level."""
        if not self.is_quiz_complete:
            return {"status": "quiz_not_complete"}

        return self.final_assessment

    def is_complete(self) -> bool:
        """Check if the quiz is complete."""
        return self.is_quiz_complete

    def get_search_status(self) -> str:
        """Return the search status."""
        return self.search_status

    def process_response(self, answer: str) -> Dict:
        """Process the user's response and return the result."""
        if not self.state:
            raise ValueError("Agent not initialized")

        result = self.evaluate_answer(answer)

        # Check if we should continue or end
        continue_or_end = self._should_continue(self.state)
        if continue_or_end == END:
            self._end(self.state)
            return {
                "completed": True,
                "feedback": result["feedback"],
            }

        return {
            "completed": False,
            "feedback": result["feedback"],
        }
