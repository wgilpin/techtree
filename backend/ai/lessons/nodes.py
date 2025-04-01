# backend/ai/lessons/nodes.py
"""LangGraph nodes for lesson interaction graph."""
# pylint: disable=broad-exception-caught

import json
import logging
import uuid

# Ensure Union is imported from typing
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.ai.llm_utils import call_llm_with_json_parsing, call_llm_plain_text
from backend.ai.prompt_loader import load_prompt
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
    IntentClassificationResult,
)

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_HISTORY_TURNS = 10  # Limit conversation history length for prompts


# --- Helper Functions ---
def _truncate_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Truncates conversation history to the last MAX_HISTORY_TURNS."""
    return history[-MAX_HISTORY_TURNS:]


def _format_history_for_prompt(history: List[Dict[str, str]]) -> str:
    """Formats conversation history into a simple string for prompts."""
    formatted = []
    for msg in history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        formatted.append(f"{role.capitalize()}: {content}")
    return "\n".join(formatted)


# --- Node Functions ---


# Changed to synchronous
def _map_intent_to_mode(intent_str: str, state: Dict[str, Any]) -> str:
    """Maps the classified intent string to an interaction mode."""
    intent_lower = intent_str.lower()
    if "exercise" in intent_lower:
        return "request_exercise"
    if "assessment" in intent_lower:
        return "request_assessment"
    if "answer" in intent_lower or "submit" in intent_lower:
        # Only map to submit_answer if there's an active task
        if state.get("active_exercise") or state.get("active_assessment"):
            return "submit_answer"
        else:
            # If user tries to submit without active task, treat as chatting
            logger.warning("User tried to submit answer but no active task found.")
            return "chatting"
    # Add more specific intent mappings if needed
    # ...
    # Default to chatting if no specific intent matches
    return "chatting"


def classify_intent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifies the user's intent based on the latest message and conversation history.

    Updates the state with the classified intent ('chatting', 'request_exercise',
    'request_assessment', 'submit_answer', 'unknown').
    """
    logger.info("Classifying user intent.")
    history: List[Dict[str, Any]] = state.get(
        "history_context", []
    )  # Use history_context from state
    user_id: str = state.get("user_id", "unknown_user")

    # Use the 'history' variable defined above
    if not history or history[-1].get("role") != "user":
        logger.warning(
            f"Cannot classify intent: No user message found in history_context for user {user_id}."
        )
        state["current_interaction_mode"] = "chatting"  # Default if no user message
        return state

    last_user_message = history[-1].get("content", "")
    truncated_history = _truncate_history(history[:-1])  # History *before* last message
    formatted_history = _format_history_for_prompt(truncated_history)

    # --- Context Extraction (Similar to generate_chat_response) ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    active_exercise: Optional[Exercise] = state.get("active_exercise")
    active_assessment: Optional[AssessmentQuestion] = state.get("active_assessment")

    exposition_summary = ""
    if generated_content and generated_content.exposition_content:
        exposition_summary = str(generated_content.exposition_content)[
            :500
        ]  # Limit length

    active_task_context = "None"
    if active_exercise:
        active_task_context = (
            f"Active Exercise: {active_exercise.type} - "
            f"{active_exercise.instructions or active_exercise.question}"
        )
    elif active_assessment:
        active_task_context = (
            f"Active Assessment Question: {active_assessment.type} - "
            f"{active_assessment.question_text}"
        )

    # --- Call LLM for Intent Classification ---
    intent_classification_result: Optional[
        Union[IntentClassificationResult, Dict[str, Any]]
    ] = None
    intent_classification: Optional[IntentClassificationResult] = None
    try:
        prompt = load_prompt(
            "intent_classification",
            user_input=last_user_message,  # Correct key for the prompt template
            history_json=formatted_history,  # Correct key for the prompt template
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            active_task_context=active_task_context,
        )

        # Use call_llm_with_json_parsing to get a validated IntentClassificationResult object
        intent_classification_result = call_llm_with_json_parsing(
            prompt, validation_model=IntentClassificationResult, max_retries=3
        )
        # Check if the result is the correct Pydantic model instance
        if isinstance(intent_classification_result, IntentClassificationResult):
            intent_classification = intent_classification_result
        elif intent_classification_result is not None:
            logger.warning(
                "Intent classification returned unexpected type: "
                f"{type(intent_classification_result)}"
            )
            intent_classification = None  # Treat unexpected type as failure

    except Exception as e:
        logger.error(
            f"LLM call/parsing failed during intent classification: {e}", exc_info=True
        )
        # Fallback to default intent if classification fails
        state["current_interaction_mode"] = "chatting"
        return state

    # --- Update State with Classified Intent ---
    if intent_classification and intent_classification.intent:
        classified_intent = intent_classification.intent.lower()
        logger.info(f"Classified intent for user {user_id}: {classified_intent}")

        # Use helper function to map intent to mode
        interaction_mode = _map_intent_to_mode(classified_intent, state)
        state["current_interaction_mode"] = interaction_mode

        # Store potential answer if intent is submit_answer
        if interaction_mode == "submit_answer":
            state["potential_answer"] = last_user_message
        else:
            # Clear potential answer if not submitting
            state["potential_answer"] = None

    else:
        # If classification failed or returned no intent, default to chatting
        logger.warning(f"Intent classification failed for user {user_id}. Defaulting to chatting.")
        state["current_interaction_mode"] = "chatting"
        state["potential_answer"] = None # Ensure potential answer is cleared

    return state


# Changed to synchronous
def generate_chat_response(
    state: Dict[str, Any],
) -> Dict[str, Any]: # Return only state changes dictionary
    """
    Generates a chat response based on the conversation history and context.

    Assumes the intent is 'chatting'. Appends the AI's response to the
    conversation history in the state.
    """
    logger.info("Generating chat response.")
    history: List[Dict[str, Any]] = state.get(
        "history_context", []
    )  # Use history_context from state
    user_id: str = state.get("user_id", "unknown_user")
    new_ai_message: Optional[Dict[str, Any]] = None  # To store the message to return

    # Use the 'history' variable defined above
    if not history or history[-1].get("role") != "user":
        logger.warning(
            "Cannot generate chat response: "
            f"No user message found in history_context for user {user_id}."""
        )
        # Return only the state dictionary as no changes occurred
        return state

    # Use the 'history' variable defined above
    last_user_message = history[-1].get("content", "")
    # Use the history from state for truncation and formatting
    truncated_history = _truncate_history(history[:-1])
    formatted_history = _format_history_for_prompt(truncated_history)

    # --- Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    active_exercise: Optional[Exercise] = state.get("active_exercise")
    active_assessment: Optional[AssessmentQuestion] = state.get("active_assessment")

    exposition_summary = ""
    if generated_content and generated_content.exposition_content:
        exposition_summary = str(generated_content.exposition_content)[:1000]

    active_task_context = "None"
    if active_exercise:
        active_task_context = (
            f"Active Exercise: {active_exercise.type} - "
            f"{active_exercise.instructions or active_exercise.question}"
        )
    elif active_assessment:
        active_task_context = (
            f"Active Assessment Question: {active_assessment.type} - "
            f"{active_assessment.question_text}"
        )

    # --- Call LLM for Chat Response ---
    ai_response_content = None  # Initialize as None
    try:
        prompt = load_prompt(
            "chat_response",
            user_message=last_user_message,
            history_json=formatted_history,
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition=exposition_summary,
            active_task_context=active_task_context,
        )
        ai_response_content = call_llm_plain_text(prompt, max_retries=3)

    except Exception as e:
        logger.error(
            f"LLM call failed during chat response generation: {e}", exc_info=True
        )
        ai_response_content = "Sorry, I encountered an error while generating a response."

    # --- Prepare new message and update state (without history append) ---
    if ai_response_content is None:
        ai_response_content = (
            "Sorry, I couldn't generate a response."  # Fallback if LLM returned None
        )

    # Create the message dictionary to be returned and saved by the service
    new_ai_message = {"role": "assistant", "content": ai_response_content}

    # Update state (mode and error message only)
    state["current_interaction_mode"] = "chatting"
    state["error_message"] = None  # Clear any previous error

    logger.info(f"Generated chat response content for user {user_id}.")
    # Add the new message to the state changes dictionary
    state_changes = {
        "current_interaction_mode": "chatting",
        "error_message": None,
        "new_assistant_message": new_ai_message # Include the generated message
    }
    return state_changes


# Changed to synchronous
def _prepare_evaluation_context(
    active_exercise: Optional[Exercise],
    active_assessment: Optional[AssessmentQuestion],
) -> Dict[str, str]:
    """Prepares the context dictionary needed for the evaluation prompt."""
    context = {
        "task_type": "Unknown",
        "task_details": "N/A",
        "correct_answer_details": "N/A",
    }

    if active_exercise:
        context["task_type"] = "Exercise"
        details = (
            f"Type: {active_exercise.type}\nInstructions/Question: "
            f"{active_exercise.instructions or active_exercise.question}"
        )
        if active_exercise.options:
            options = json.dumps([opt.model_dump() for opt in active_exercise.options])
            details += f"\nOptions: {options}"
        if active_exercise.type == "ordering" and active_exercise.items:
            details += f"\nItems to Order: {json.dumps(active_exercise.items)}"
        context["task_details"] = details

        if active_exercise.correct_answer:
            context["correct_answer_details"] = (
                f"Correct Answer/Criteria: {active_exercise.correct_answer}"
            )

    elif active_assessment:
        context["task_type"] = "Assessment Question"
        details = (
            f"Type: {active_assessment.type}"
            f"\nQuestion: {active_assessment.question_text}"
        )
        if active_assessment.options:
            options = json.dumps([opt.model_dump() for opt in active_assessment.options])
            details += f"\nOptions: {options}"
        context["task_details"] = details

        if active_assessment.correct_answer:
            context["correct_answer_details"] = (
                f"Correct Answer: {active_assessment.correct_answer}"
            )

    return context


def evaluate_answer(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Evaluates the user's submitted answer against the active exercise or assessment question.

    Updates the state with feedback and clears the active task if evaluation is successful.
    """
    logger.info("Evaluating user answer.")
    # History is now passed as an argument
    user_id: str = state.get("user_id", "unknown_user")
    user_answer: Optional[str] = state.get("potential_answer")
    feedback_message: Optional[Dict[str, Any]] = None  # To store the message to return

    if not user_answer:
        logger.error(
            f"Cannot evaluate: No user answer found in state for user {user_id}."
        )
        feedback_message = {
            "role": "assistant",
            "content": "Sorry, I couldn't find your answer to evaluate.",
        }
        state["current_interaction_mode"] = "chatting"
        # Return state and the error message
        return state, feedback_message

    active_exercise: Optional[Exercise] = state.get("active_exercise")
    active_assessment: Optional[AssessmentQuestion] = state.get("active_assessment")

    if not active_exercise and not active_assessment:
        logger.error(
            f"Cannot evaluate: No active exercise or assessment found for user {user_id}."
        )
        feedback_message = {
            "role": "assistant",
            "content": """
                There doesn't seem to be an active question or exercise to answer right now.""",
        }
        state["current_interaction_mode"] = "chatting"
        # Return state and the error message
        return state, feedback_message

    # --- Prepare Context using Helper ---
    eval_context = _prepare_evaluation_context(active_exercise, active_assessment)
    task_type = eval_context["task_type"]
    task_details = eval_context["task_details"]
    correct_answer_details = eval_context["correct_answer_details"]

    # --- Call LLM for Evaluation ---
    evaluation_feedback_content = None  # Initialize as None
    try:
        prompt = load_prompt(
            "evaluate_answer",
            task_type=task_type,
            task_details=task_details,
            correct_answer_details=correct_answer_details,
            user_answer=user_answer,
        )
        evaluation_feedback_content = call_llm_plain_text(prompt, max_retries=2)
        if evaluation_feedback_content is None:
            logger.warning("LLM returned None for evaluation feedback.")
            evaluation_feedback_content = (
                "Sorry, I couldn't evaluate your answer properly."  # Fallback
            )

    except Exception as e:
        logger.error(f"LLM call failed during answer evaluation: {e}", exc_info=True)
        evaluation_feedback_content = "Sorry, I encountered an error while evaluating your answer."

    # --- Prepare feedback message and update state ---
    feedback_message = {"role": "assistant", "content": evaluation_feedback_content}

    # Clear the active task and potential answer
    state["active_exercise"] = None
    state["active_assessment"] = None
    state["potential_answer"] = None
    state["current_interaction_mode"] = "chatting"
    state["error_message"] = None  # Clear any previous error

    logger.info(f"Generated evaluation feedback for user {user_id}.")
    # Return the updated state and the feedback message dictionary
    return state, feedback_message


# --- On-Demand Generation Nodes ---

# Define a type alias for the return type for clarity
# Updated type hint for generated item
GenerateNodeReturnType = Tuple[
    Dict[str, Any], Optional[Union[Exercise, AssessmentQuestion, Dict[str, Any]]]
]

# Note: These generation functions now return the state AND the generated item
# This allows the service layer to access the generated item directly if needed.


# Changed to synchronous
# Updated return type hint
def generate_new_exercise(
    state: Dict[str, Any],
) -> Tuple[
    Dict[str, Any], Optional[Union[Exercise, Dict[str, Any]]], Optional[Dict[str, Any]]
]:  # Keep message return
    """
    Generates a new, unique exercise based on the lesson context.

    Updates the state by adding the new exercise to 'active_exercise' and
    its ID to 'generated_exercise_ids'. Appends a confirmation message
    to the conversation history.

    Returns:
        Tuple[Dict[str, Any], Optional[Union[Exercise, Dict[str, Any]]]]:
            The updated state and the generated Exercise object (or dict/None).
    """
    logger.info("Attempting to generate a new exercise.")
    user_id: str = state.get("user_id", "unknown_user")
    assistant_message: Optional[Dict[str, Any]] = None  # To store the message to return

    # --- 1. Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    existing_exercise_ids: List[str] = state.get("generated_exercise_ids", [])

    # Basic validation
    if not generated_content or not generated_content.exposition_content:
        logger.error(
            f"Cannot generate exercise: Missing exposition content for user {user_id}."
        )
        state["error_message"] = (
            "Sorry, I couldn't generate an exercise because the lesson content is missing."
        )
        assistant_message = {"role": "assistant", "content": state["error_message"]}
        # Return original state, None exercise, and the error message
        return state, None, assistant_message

    # Create exposition summary
    exposition_summary = str(generated_content.exposition_content)[:1000]

    # Create syllabus context
    syllabus_context = (
        f"Module: {state.get('module_title', 'N/A')}, Lesson: {lesson_title}"
    )

    # --- 2. Call LLM ---
    new_exercise_result: Optional[Union[Exercise, Dict[str, Any]]] = None
    try:
        prompt = load_prompt(
            "generate_exercises",
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            syllabus_context=syllabus_context,
            existing_exercise_descriptions_json=json.dumps(existing_exercise_ids),
        )
        new_exercise_result = call_llm_with_json_parsing(
            prompt, validation_model=Exercise, max_retries=2
        )
    except Exception as e:
        logger.error(
            f"LLM call/parsing failed during exercise generation: {e}", exc_info=True
        )

    # --- 3. Process Result & Update State ---
    validated_exercise: Optional[Exercise] = None
    if isinstance(new_exercise_result, Exercise):
        validated_exercise = new_exercise_result
        if not validated_exercise.id:
            validated_exercise.id = f"ex_{uuid.uuid4().hex[:6]}"
            logger.warning(
                f"Generated exercise lacked ID, assigned fallback: {validated_exercise.id}"
            )

        # Check for duplicate ID
        if validated_exercise.id in existing_exercise_ids:
            logger.warning(
                f"""LLM generated an exercise with a duplicate ID
                    ({validated_exercise.id}). Discarding."""
            )
            assistant_message = {
                "role": "assistant",
                "content": """
                    Sorry, I couldn't come up with a new exercise right now.
                    Would you like to try again or ask something else?""",
            }
            state["current_interaction_mode"] = "chatting"
            state["error_message"] = "Duplicate exercise ID generated."
            return (
                state,
                None,
                assistant_message,
            )  # Return state, None exercise, failure message
        else:
            # Successfully generated new exercise
            logger.info(
                f"Successfully generated new exercise with ID: {validated_exercise.id}"
            )
            state["active_exercise"] = validated_exercise
            state["active_assessment"] = None
            state["generated_exercise_ids"] = existing_exercise_ids + [
                validated_exercise.id
            ]
            assistant_message = {
                "role": "assistant",
                "content": (
                    f"Okay, I've generated a new {validated_exercise.type.replace('_', ' ')} "
                    "exercise for you. Please see below and provide your answer in the chat."),
            }
            state["current_interaction_mode"] = "awaiting_answer"
            state["error_message"] = None
            return (
                state,
                validated_exercise,
                assistant_message,
            )  # Return state, exercise, success message

    else:  # Handle generation failure or unexpected return type
        if new_exercise_result is not None:
            logger.error(
                f"Exercise generation returned unexpected type: {type(new_exercise_result)}"
            )
        logger.error(f"Failed to generate a valid new exercise for user {user_id}.")
        assistant_message = {
            "role": "assistant",
            "content": """
                Sorry, I wasn't able to generate an exercise for you right now.
                Please try again later or ask me something else.""",
        }
        state["current_interaction_mode"] = "chatting"
        state["error_message"] = "Exercise generation failed."
        return (
            state,
            None,
            assistant_message,
        )  # Return state, None exercise, failure message


# Changed to synchronous
# Updated return type hint
def generate_new_assessment(
    state: Dict[str, Any],
) -> Tuple[
    Dict[str, Any],
    Optional[Union[AssessmentQuestion, Dict[str, Any]]],
    Optional[Dict[str, Any]],
]:  # Keep message return
    """
    Generates a new, unique assessment question based on the lesson context.

    Updates the state by adding the new question to 'active_assessment' and
    its ID to 'generated_assessment_ids'. Appends a confirmation message
    to the conversation history.

    Returns:
        Tuple[Dict[str, Any], Optional[Union[AssessmentQuestion, Dict[str, Any]]]]:
             The updated state and the generated AssessmentQuestion object (or dict/None).
    """
    logger.info("Attempting to generate a new assessment question.")
    user_id: str = state.get("user_id", "unknown_user")
    assistant_message: Optional[Dict[str, Any]] = None  # To store the message to return

    # --- 1. Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    existing_assessment_ids: List[str] = state.get(
        "generated_assessment_question_ids", []
    )

    # Basic validation
    if not generated_content or not generated_content.exposition_content:
        logger.error(
            f"Cannot generate assessment: Missing exposition content for user {user_id}."
        )
        state["error_message"] = (
            """Sorry, I couldn't generate an assessment
               question because the lesson content is missing."""
        )
        assistant_message = {"role": "assistant", "content": state["error_message"]}
        # Return original state, None question, and the error message
        return state, None, assistant_message

    exposition_summary = str(generated_content.exposition_content)[:1000]

    # --- 2. Call LLM ---
    new_assessment_result: Optional[Union[AssessmentQuestion, Dict[str, Any]]] = None
    try:
        prompt = load_prompt(
            "generate_assessment",
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            existing_question_descriptions_json=json.dumps(existing_assessment_ids),
        )
        new_assessment_result = call_llm_with_json_parsing(
            prompt, validation_model=AssessmentQuestion, max_retries=2
        )
    except Exception as e:
        logger.error(
            f"LLM call/parsing failed during assessment generation: {e}", exc_info=True
        )

    # --- 3. Process Result & Update State ---
    validated_question: Optional[AssessmentQuestion] = None
    if isinstance(new_assessment_result, AssessmentQuestion):
        validated_question = new_assessment_result
        if not validated_question.id:
            validated_question.id = f"as_{uuid.uuid4().hex[:6]}"
            logger.warning(
                f"Generated assessment lacked ID, assigned fallback: {validated_question.id}"
            )

        # Check for duplicates
        if validated_question.id in existing_assessment_ids:
            logger.warning(
                "LLM generated an assessment with a duplicate ID "
                f"({validated_question.id}). Discarding."
            )
            assistant_message = {
                "role": "assistant",
                "content": """
                    Sorry, I couldn't come up with a new assessment question right now.
                    Would you like to try again or ask something else?""",
            }
            state["current_interaction_mode"] = "chatting"
            state["error_message"] = "Duplicate assessment ID generated."
            return (
                state,
                None,
                assistant_message,
            )  # Return state, None question, failure message
        else:
            # Successfully generated new assessment question
            logger.info(
                f"Successfully generated new assessment question with ID: {validated_question.id}"
            )
            state["active_assessment"] = validated_question
            state["active_exercise"] = None
            state["generated_assessment_question_ids"] = existing_assessment_ids + [
                validated_question.id
            ]
            assistant_message = {
                "role": "assistant",
                "content": f"""
                    Okay, here's an assessment question for you
                    ({validated_question.type.replace('_', ' ')}).
                    Please see below and provide your answer in the chat.""",
            }
            state["current_interaction_mode"] = "awaiting_answer"
            state["error_message"] = None
            return (
                state,
                validated_question,
                assistant_message,
            )  # Return state, question, success message

    else:  # Handle generation failure or unexpected return type
        if new_assessment_result is not None:
            logger.error(
                f"Assessment generation returned unexpected type: {type(new_assessment_result)}"
            )
        logger.error(
            f"Failed to generate a valid new assessment question for user {user_id}."
        )
        assistant_message = {
            "role": "assistant",
            "content": ("Sorry, I wasn't able to generate an assessment question for you "
                        "right now. Please try again later or ask me something else."),
        }
        state["current_interaction_mode"] = "chatting"
        state["error_message"] = "Assessment generation failed."
        return (
            state,
            None,
            assistant_message,
        )  # Return state, None question, failure message
