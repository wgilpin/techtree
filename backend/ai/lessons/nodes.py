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
    ChatMessage,
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
def classify_intent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifies the user's intent based on the latest message and conversation history.

    Updates the state with the classified intent ('chatting', 'request_exercise',
    'request_assessment', 'submit_answer', 'unknown').
    """
    logger.info("Classifying user intent.")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

    if not history or history[-1].get("role") != "user":
        logger.warning(
            f"Cannot classify intent: No user message found for user {user_id}."
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
            f"{active_exercise.instructions or active_exercise.question}")
    elif active_assessment:
        active_task_context = (
            f"Active Assessment Question: {active_assessment.type} - "
            f"{active_assessment.question_text}")

    # --- Call LLM for Intent Classification ---
    intent_classification_result: Optional[
        Union[IntentClassificationResult, Dict[str, Any]]
    ] = None
    intent_classification: Optional[IntentClassificationResult] = None
    try:
        prompt = load_prompt(
            "intent_classification",
            user_message=last_user_message,
            conversation_history=formatted_history,
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

        # Map classified intent to interaction mode
        if "exercise" in classified_intent:
            state["current_interaction_mode"] = "request_exercise"
        elif "assessment" in classified_intent:
            state["current_interaction_mode"] = "request_assessment"
        elif "answer" in classified_intent or "submit" in classified_intent:
            # Check if there's an active task to submit against
            if active_exercise or active_assessment:
                state["current_interaction_mode"] = "submit_answer"
                # Store the potential answer for the evaluation node
                state["potential_answer"] = last_user_message
            else:
                # Treat as chat if there's nothing active to answer
                logger.info(
                    "User tried to submit answer, but no active task. Treating as chat."
                )
                state["current_interaction_mode"] = "chatting"
        elif "chat" in classified_intent or "question" in classified_intent:
            state["current_interaction_mode"] = "chatting"
        else:
            logger.warning(
                f"Unknown intent classified: {classified_intent}. Defaulting to chatting."
            )
            state["current_interaction_mode"] = (
                "chatting"  # Default for unknown intents
            )
    else:
        logger.error(
            f"Intent classification failed for user {user_id}. Defaulting to chatting."
        )
        state["current_interaction_mode"] = (
            "chatting"  # Default if classification fails completely
        )

    return state


# Changed to synchronous
def generate_chat_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a chat response based on the conversation history and context.

    Assumes the intent is 'chatting'. Appends the AI's response to the
    conversation history in the state.
    """
    logger.info("Generating chat response.")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

    if not history or history[-1].get("role") != "user":
        logger.warning(
            f"Cannot generate chat response: No user message found for user {user_id}."
        )
        # Optionally add a default message if needed, or just return state
        return state

    last_user_message = history[-1].get("content", "")
    truncated_history = _truncate_history(history[:-1])  # History *before* last message
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
        # Convert ExpositionContent to string for summary
        exposition_summary = str(generated_content.exposition_content)[
            :1000
        ]  # Limit length

    active_task_context = "None"
    if active_exercise:
        active_task_context = (
            f"Active Exercise: {active_exercise.type} - "
            f"{active_exercise.instructions or active_exercise.question}")
    elif active_assessment:
        active_task_context = (
            f"Active Assessment Question: {active_assessment.type} - "
            f"{active_assessment.question_text}")

    # --- Call LLM for Chat Response ---
    ai_response_content = (
        "Sorry, I'm having trouble understanding right now."  # Default fallback
    )
    try:
        prompt = load_prompt(
            "chat_response",
            user_message=last_user_message,
            conversation_history=formatted_history,
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            active_task_context=active_task_context,
        )

        # Use call_llm_plain_text for direct chat response
        ai_response_content_result = call_llm_plain_text(prompt, max_retries=3)
        # Ensure response is not None before creating ChatMessage
        if ai_response_content_result is None:
            ai_response_content = (
                "Sorry, I couldn't generate a response."  # More specific fallback
            )
        else:
            ai_response_content = ai_response_content_result

    except Exception as e:
        logger.error(
            f"LLM call failed during chat response generation: {e}", exc_info=True
        )
        # Keep the default fallback message

    # --- Update State ---
    ai_message = ChatMessage(role="assistant", content=ai_response_content)
    # Ensure history is a list before appending
    if not isinstance(history, list):
        logger.warning(
            f"Conversation history for user {user_id} was not a list, resetting."
        )
        history = []
    state["conversation_history"] = history + [
        ai_message.model_dump()
    ]  # Append new AI message
    state["current_interaction_mode"] = "chatting"  # Ensure mode is reset/confirmed

    logger.info(f"Generated chat response for user {user_id}.")
    return state


# Changed to synchronous
def evaluate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates the user's submitted answer against the active exercise or assessment question.

    Updates the state with feedback and clears the active task if evaluation is successful.
    """
    logger.info("Evaluating user answer.")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    user_answer: Optional[str] = state.get("potential_answer")  # Get answer from state

    if not user_answer:
        logger.error(
            f"Cannot evaluate: No user answer found in state for user {user_id}."
        )
        # Add error message to history?
        ai_message = ChatMessage(
            role="assistant", content="Sorry, I couldn't find your answer to evaluate."
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [ai_message.model_dump()]
        state["current_interaction_mode"] = "chatting"  # Revert to chat
        return state

    active_exercise: Optional[Exercise] = state.get("active_exercise")
    active_assessment: Optional[AssessmentQuestion] = state.get("active_assessment")

    if not active_exercise and not active_assessment:
        logger.error(
            f"Cannot evaluate: No active exercise or assessment found for user {user_id}."
        )
        ai_message = ChatMessage(
            role="assistant",
            content="There doesn't seem to be an active question or exercise to answer right now.",
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [ai_message.model_dump()]
        state["current_interaction_mode"] = "chatting"  # Revert to chat
        return state

    # --- Prepare Context for Evaluation Prompt ---
    task_type = ""
    task_details = ""
    correct_answer_details = (
        ""  # Optional, might not always be available/needed for LLM eval
    )

    if active_exercise:
        task_type = "Exercise"
        task_details = (
            f"Type: {active_exercise.type}\nInstructions/Question: "
            f"{active_exercise.instructions or active_exercise.question}")
        if active_exercise.options:
            options = json.dumps([opt.model_dump() for opt in active_exercise.options])
            task_details += f"\nOptions: {options}"
        if active_exercise.correct_answer:
            correct_answer_details = (
                f"Correct Answer/Criteria: {active_exercise.correct_answer}"
            )
        # Add items for ordering tasks
        if active_exercise.type == "ordering" and active_exercise.items:
            task_details += f"\nItems to Order: {json.dumps(active_exercise.items)}"

    elif active_assessment:
        task_type = "Assessment Question"
        task_details = (
            f"Type: {active_assessment.type}"
            f"\nQuestion: {active_assessment.question_text}")
        if active_assessment.options:
            options = json.dumps([opt.model_dump() for opt in active_assessment.options])
            task_details += f"\nOptions: {options}"
        if active_assessment.correct_answer:
            correct_answer_details = (
                f"Correct Answer/Criteria: {active_assessment.correct_answer}"
            )

    # --- Call LLM for Evaluation ---
    evaluation_feedback = (
        "Sorry, I couldn't evaluate your answer at this time."  # Default fallback
    )
    try:
        prompt = load_prompt(
            "evaluate_answer",
            task_type=task_type,
            task_details=task_details,
            correct_answer_details=correct_answer_details,  # May be empty
            user_answer=user_answer,
        )

        # Use call_llm_plain_text for evaluation feedback
        evaluation_feedback_result = call_llm_plain_text(prompt, max_retries=2)
        if evaluation_feedback_result is not None:
            evaluation_feedback = evaluation_feedback_result
        else:
            logger.warning("LLM returned None for evaluation feedback.")
            # Keep the default fallback message

    except Exception as e:
        logger.error(f"LLM call failed during answer evaluation: {e}", exc_info=True)
        # Keep the default fallback message

    # --- Update State ---
    ai_message = ChatMessage(role="assistant", content=evaluation_feedback)
    if not isinstance(history, list):
        history = []  # Ensure history is list
    state["conversation_history"] = history + [
        ai_message.model_dump()
    ]  # Append feedback

    # Clear the active task and potential answer regardless of evaluation success/failure?
    # Or only clear if evaluation was positive? Let's clear it for now to avoid re-evaluation.
    state["active_exercise"] = None
    state["active_assessment"] = None
    state["potential_answer"] = None
    state["current_interaction_mode"] = "chatting"  # Revert to chat after evaluation

    logger.info(f"Generated evaluation feedback for user {user_id}.")
    return state


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
) -> Tuple[Dict[str, Any], Optional[Union[Exercise, Dict[str, Any]]]]:
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
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

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
        # Add error message to state? Or just return None?
        state["error_message"] = (
            "Sorry, I couldn't generate an exercise because the lesson content is missing."
        )
        # Return original state and None for the exercise
        return state, None

    # Create exposition summary (simple string for now)
    exposition_summary = str(generated_content.exposition_content)[
        :1000
    ]  # Limit length

    # Create syllabus context (simplified - maybe just module/lesson titles?)
    syllabus_context = (
        f"Module: {state.get('module_title', 'N/A')}, Lesson: {lesson_title}"
    )
    # TODO: Potentially add more syllabus context if needed by the prompt

    # --- 2. Call LLM ---
    # Updated type hint
    new_exercise_result: Optional[Union[Exercise, Dict[str, Any]]] = None
    try:
        prompt = load_prompt(
            "generate_exercises",  # Use the new prompt file name
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            syllabus_context=syllabus_context,
            existing_exercise_descriptions_json=json.dumps(
                existing_exercise_ids
            ),  # Pass existing IDs
        )

        # Use call_llm_with_json_parsing to get a validated Exercise object
        new_exercise_result = call_llm_with_json_parsing(
            prompt,
            validation_model=Exercise,
            max_retries=2,  # Allow fewer retries for generation
        )

    except Exception as e:
        logger.error(
            f"LLM call/parsing failed during exercise generation: {e}", exc_info=True
        )
        # Fall through, new_exercise_result will be None

    # --- 3. Process Result & Update State ---
    # Check if the result is a valid Exercise Pydantic model
    if isinstance(new_exercise_result, Exercise):
        new_exercise = (
            new_exercise_result  # Assign to correctly typed variable for clarity
        )
        # Ensure the exercise has an ID
        if not new_exercise.id:
            new_exercise.id = f"ex_{uuid.uuid4().hex[:6]}"  # Generate a fallback ID
            logger.warning(
                f"Generated exercise lacked ID, assigned fallback: {new_exercise.id}"
            )

        # Check if ID already exists (LLM might ignore novelty constraint)
        if new_exercise.id in existing_exercise_ids:
            logger.warning(
                f"LLM generated an exercise with a duplicate ID ({new_exercise.id}). Discarding."
            )
            # Add message indicating failure to generate a *new* one
            # Explicitly type ai_message
            ai_message: ChatMessage = ChatMessage(
                role="assistant",
                content=\
                    "Sorry, I couldn't come up with a new exercise right now. "
                    "Would you like to try again or ask something else?",
            )
            if not isinstance(history, list):
                history = []  # Ensure history is list
            state["conversation_history"] = history + [ai_message.model_dump()]
            state["current_interaction_mode"] = "chatting"
            return state, None  # Return original state and None exercise

        logger.info(f"Successfully generated new exercise with ID: {new_exercise.id}")

        # Update state
        state["active_exercise"] = new_exercise  # Set as the currently active one
        state["active_assessment"] = None  # Clear any active assessment
        state["generated_exercise_ids"] = existing_exercise_ids + [new_exercise.id]

        # Add confirmation message to history
        # Explicitly type confirmation_message
        confirmation_message: ChatMessage = ChatMessage(
            role="assistant",
            content=(
                f"Okay, I've generated a new {new_exercise.type.replace('_', ' ')}"
                " exercise for you. Please see below and provide your answer in the chat."),
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [confirmation_message.model_dump()]
        state["current_interaction_mode"] = (
            "awaiting_answer"  # Mode expecting an answer
        )

        return state, new_exercise  # Return updated state and the new exercise object

    else:  # Handle generation failure or unexpected return type
        if new_exercise_result is not None:
            logger.error(
                f"Exercise generation returned unexpected type: {type(new_exercise_result)}"
            )
        logger.error(f"Failed to generate a valid new exercise for user {user_id}.")
        # Explicitly type and rename ai_message
        error_ai_message: ChatMessage = ChatMessage(
            role="assistant",
            content=("""
                     Sorry, I wasn't able to generate an exercise for you right now.
                     Please try again later or ask me something else."""),
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [error_ai_message.model_dump()]
        state["current_interaction_mode"] = "chatting"  # Revert to chat
        state["error_message"] = "Exercise generation failed."  # Add error flag/message
        return state, None  # Return original state and None exercise


# Changed to synchronous
# Updated return type hint
def generate_new_assessment(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Union[AssessmentQuestion, Dict[str, Any]]]]:
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
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

    # --- 1. Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    existing_assessment_ids: List[str] = state.get(
        "generated_assessment_question_ids", []
    )  # Corrected key name

    # Basic validation
    if not generated_content or not generated_content.exposition_content:
        logger.error(
            f"Cannot generate assessment: Missing exposition content for user {user_id}."
        )
        state["error_message"] = (
            "Sorry, I couldn't generate an assessment question"
            " because the lesson content is missing."
        )
        return state, None

    exposition_summary = str(generated_content.exposition_content)[:1000]

    # --- 2. Call LLM ---
    # Updated type hint
    new_assessment_result: Optional[Union[AssessmentQuestion, Dict[str, Any]]] = None
    try:
        prompt = load_prompt(
            "generate_assessment",  # Use the correct prompt file name
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            existing_question_descriptions_json=json.dumps(existing_assessment_ids),
        )

        # Use call_llm_with_json_parsing to get a validated AssessmentQuestion object
        new_assessment_result = call_llm_with_json_parsing(
            prompt, validation_model=AssessmentQuestion, max_retries=2
        )

    except Exception as e:
        logger.error(
            f"LLM call/parsing failed during assessment generation: {e}", exc_info=True
        )
        # Fall through

    # --- 3. Process Result & Update State ---
    # Check if the result is a valid AssessmentQuestion Pydantic model
    if isinstance(new_assessment_result, AssessmentQuestion):
        new_assessment = new_assessment_result  # Assign to correctly typed variable
        # Ensure ID exists
        if not new_assessment.id:
            new_assessment.id = f"as_{uuid.uuid4().hex[:6]}"
            logger.warning(
                f"Generated assessment lacked ID, assigned fallback: {new_assessment.id}"
            )

        # Check for duplicates
        if new_assessment.id in existing_assessment_ids:
            logger.warning(
                "LLM generated an assessment with a duplicate ID "
                f"({new_assessment.id}). Discarding."
            )
            # Explicitly type ai_message
            ai_message: ChatMessage = ChatMessage(
                role="assistant",
                content="""
                    Sorry, I couldn't come up with a new assessment question right now.
                    Would you like to try again or ask something else?""",
            )
            if not isinstance(history, list):
                history = []  # Ensure history is list
            state["conversation_history"] = history + [ai_message.model_dump()]
            state["current_interaction_mode"] = "chatting"
            return state, None

        logger.info(
            f"Successfully generated new assessment question with ID: {new_assessment.id}"
        )

        # Update state
        state["active_assessment"] = new_assessment  # Set as active
        state["active_exercise"] = None  # Clear active exercise
        # Correctly append the new ID to the list
        state["generated_assessment_question_ids"] = existing_assessment_ids + [
            new_assessment.id
        ]  # Corrected key name

        # Add confirmation message
        # Explicitly type confirmation_message
        confirmation_message: ChatMessage = ChatMessage(
            role="assistant",
            content=f"""
                      Okay, here's an assessment question for you
                      ({new_assessment.type.replace('_', ' ')}).
                      Please see below and provide your answer in the chat.""",
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [confirmation_message.model_dump()]
        state["current_interaction_mode"] = "awaiting_answer"

        return state, new_assessment

    else:  # Handle generation failure or unexpected return type
        if new_assessment_result is not None:
            logger.error(
                f"Assessment generation returned unexpected type: {type(new_assessment_result)}"
            )
        logger.error(
            f"Failed to generate a valid new assessment question for user {user_id}."
        )
        # Explicitly type and rename ai_message
        error_ai_message: ChatMessage = ChatMessage(
            role="assistant",
            content="""
                Sorry, I wasn't able to generate an assessment question for you right now.
                Please try again later or ask me something else.""",
        )
        if not isinstance(history, list):
            history = []  # Ensure history is list
        state["conversation_history"] = history + [error_ai_message.model_dump()]
        state["current_interaction_mode"] = "chatting"
        state["error_message"] = "Assessment generation failed."
        return state, None
