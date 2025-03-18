# pylint: disable=missing-class-docstring,missing-module-docstring

from collections import Counter
import os
import re
import time
import random
from typing import Dict, List, TypedDict

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(
    "gemini-2.0-pro-exp-02-05"
)  # User specified gemini 2 flash, but using gemini-pro for now


def call_with_retry(func, *args, max_retries=5, initial_delay=1, **kwargs):
    """Call a function with exponential backoff retry logic for quota errors."""
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                print(f"\nExceeded maximum retries ({max_retries}). Giving up.")
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            print(
                f"\nQuota exceeded. Retrying in {delay:.1f} seconds"
                + f"(attempt {retries}/{max_retries})..."
            )
            time.sleep(delay)


# --- Define State ---
class AgentState(TypedDict):
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


# --- Define Nodes (Functions) ---
EASY = 1
MEDIUM = 2
HARD = 3


def intro(_: AgentState) -> Dict:
    """Gets user input for topic."""
    print("Welcome to the Tech Tree demo!")
    print("You'll be asked questions of increasing difficulty.")
    print("If you get a question right, you'll move to a harder question.")
    print("If you get a question wrong, you'll get another question at the same level.")
    print("If you get 2 questions wrong in a row, the quiz will end.")

    topic = input("What topic would you like to explore? ")

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
    }


def generate_question(state: AgentState) -> Dict:
    """Generates a question using the Gemini API."""
    # Get the target difficulty level
    target_difficulty = state["current_target_difficulty"]
    difficulty_name = (
        "easy"
        if target_difficulty == EASY
        else "medium" if target_difficulty == MEDIUM else "hard"
    )

    # Construct the prompt for Gemini
    prompt = f"""
    You are an expert tutor creating questions on the topic of {state['topic']}.
    The student is at a {state['knowledge_level']} knowledge level.
    Ask a question on the topic, avoiding questions already asked.
    Questions should only require short answers, not detailed responses.
    
    The question should be at {difficulty_name} difficulty level ({target_difficulty}).
    
    Format your response as follows:
    Difficulty: {target_difficulty}
    Question: [your question here]
    
    Questions already asked: {', '.join(state['questions_asked']) or 'None'}
    """

    response = call_with_retry(model.generate_content, prompt)
    response_text = response.text

    # Parse the response to extract difficulty and question
    difficulty = MEDIUM  # Default difficulty
    question = response_text

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


def present_question(state: AgentState) -> Dict:
    """Presents the question to the user."""
    difficulty = state["current_question_difficulty"]
    difficulty_str = (
        "EASY" if difficulty == EASY else "MEDIUM" if difficulty == MEDIUM else "HARD"
    )
    print(f"\n[Difficulty: {difficulty_str}]")
    print(state["current_question"])
    return {}


def evaluate_answer(state: AgentState) -> Dict:
    """Gets user input for the answer and evaluates it using the Gemini API."""
    answer = input("Your answer: ")

    # Construct the prompt for Gemini to evaluate the answer
    prompt = f"""
    You are an expert tutor in {state['topic']}.
    Here is a question that was asked:

    Question: {state['current_question']}

    Here is the student's answer:

    Answer: {answer}

    Evaluate the answer for correctness and completeness, allowing that only short answers were requested.
    Provide feedback on the answer.
    
    Important: If the student responds with "I don't know" or similar, assume the user failed to 
    demonstrate understanding of the topic in response to the question, and classify the answer as incorrect.
    
    Classify the answer as one of: correct=1, partially correct=0.5, or incorrect=0.
    Make sure to include the classification explicitly as a number in your response. 
    Do not include any other text, only the number.
    """

    response = call_with_retry(model.generate_content, prompt)
    evaluation = response.text

    print("\nEvaluation:", evaluation)  # Print Gemini's evaluation

    # Determine the classification
    classification: float = float(evaluation)

    # Update consecutive wrong counter and target difficulty
    current_difficulty = state["current_target_difficulty"]
    consecutive_wrong = state["consecutive_wrong"]

    if classification == 0.0:  # Incorrect
        consecutive_wrong += 1
        # Keep the same difficulty level for the next question
        next_difficulty = current_difficulty
    else:
        consecutive_wrong = 0
        # If correct or partially correct, increase difficulty if possible
        if current_difficulty == EASY:
            next_difficulty = MEDIUM
        elif current_difficulty == MEDIUM:
            next_difficulty = HARD
        else:
            next_difficulty = HARD  # Stay at HARD if already at HARD

    return {
        "answers": state["answers"] + [answer],
        "answer_evaluations": state["answer_evaluations"] + [classification],
        "consecutive_wrong": consecutive_wrong,
        "current_target_difficulty": next_difficulty,
    }


def end(state: AgentState) -> Dict:
    """Prints a final message and provides a final assessment of the user's knowledge level."""
    print("\nThanks for playing the Tech Tree demo!")

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

    # Print results
    print("\nFinal Assessment:")
    print(f"Correct answers: {counts[1.0]}")
    print(f"Partially correct answers: {counts[0.5]}")
    print(f"Incorrect answers: {counts[0.0]}")
    print(
        f"\nWeighted score: {total_score:.1f}/{max_possible_score:.1f} ({weighted_percentage:.1f}%)"
    )
    print(f"Overall knowledge level: {final_level}")

    return {}


# --- Define Edges (Conditional Logic) ---


def should_continue(state: AgentState) -> str:
    """Decides whether to continue or end the conversation."""
    # End if the user has gotten 2 consecutive wrong answers
    if state["consecutive_wrong"] >= 2:
        return END

    # Otherwise continue
    return "continue"


# --- Create the Graph ---

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("intro", intro)
workflow.add_node("generate_question", generate_question)
workflow.add_node("present_question", present_question)
workflow.add_node("evaluate_answer", evaluate_answer)
workflow.add_node("end", end)

# Add edges
workflow.add_edge("intro", "generate_question")
workflow.add_edge("generate_question", "present_question")
workflow.add_edge("present_question", "evaluate_answer")
workflow.add_conditional_edges(
    "evaluate_answer", should_continue, {"continue": "generate_question", END: "end"}
)


workflow.set_entry_point("intro")

graph = workflow.compile()


# --- Run the Graph ---
if __name__ == "__main__":
    inputs = {"": ""}  # dummy
    for output in graph.stream(inputs):
        # stream() will send one "event" per node for every time
        # it is invoked. The event structure is:
        # {key: value}
        # where key is the name of the node, and value is the output of that node.
        # for key, value in output.items():
        #     if key != "__end__":
        #         print(f"Node '{key}':")
        pass
