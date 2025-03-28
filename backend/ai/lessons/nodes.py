"""
Node logic functions for the lesson AI graph.

These functions are designed to be called by the langgraph StateGraph
and operate on the LessonState.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from backend.ai.llm_utils import call_llm_with_json_parsing, call_with_retry
from backend.ai.llm_utils import MODEL as llm_model
from backend.ai.prompt_loader import load_prompt
from backend.logger import logger
from backend.models import (
    AssessmentQuestion,
    EvaluationResult,
    Exercise,
    GeneratedLessonContent,
    IntentClassificationResult,
    LessonState,
)


def start_conversation(state: LessonState) -> Dict[str, Any]:
    """
    Generates the initial AI welcome message.
    Corresponds to the _start_conversation node logic.
    """
    lesson_title: str = state.get("lesson_title", "this lesson")
    user_id: str = state.get("user_id", "unknown_user")
    history: List[Dict[str, str]] = state.get("conversation_history", [])

    logger.debug(
        f"Starting conversation for user {user_id}, lesson '{lesson_title}'"
    )

    # Check if history is already present (shouldn't be if this is truly the start)
    if history:
        logger.warning(
            f"start_conversation called but history is not empty for user {user_id}."
            " Returning current state."
        )
        return {}  # Return no changes if history exists

    # Construct the initial message
    welcome_content: str = (
        f"Welcome to the lesson on **'{lesson_title}'**! 👋\n\n"
        "I'm here to help you learn. You can:\n"
        "- Ask me questions about the introduction or topic.\n"
        "- Request an 'exercise' to practice.\n"
        "- Ask to take the 'quiz' when you feel ready.\n\n"
        "What would you like to do first?"
    )

    initial_message: Dict[str, str] = {
        "role": "assistant",
        "content": welcome_content,
    }

    return {
        "conversation_history": [
            initial_message
        ],  # Start history with this message
        "current_interaction_mode": "chatting",
    }


def process_user_message(state: LessonState) -> Dict[str, Any]:
    """
    Graph node: Placeholder for initial processing if needed.
    Currently, the main logic happens in routing.
    Corresponds to the _process_user_message node logic.
    """
    # In the original code, this node was essentially a pass-through.
    # The routing logic (_route_message_logic) handled the decision-making.
    # We keep it as a potential hook for future pre-processing.
    logger.debug("Processing user message node executed.")
    # No state changes are made here by default.
    return {}

# --- Other node functions will be added below ---


def route_message_logic(state: LessonState) -> str:
    """
    Determines the next node based on interaction mode and user message intent.
    Corresponds to the _route_message_logic conditional edge logic.
    """
    mode: str = state.get("current_interaction_mode", "chatting")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    last_message: Dict[str, str] = history[-1] if history else {}
    user_id: str = state.get("user_id", "unknown_user")

    logger.debug(
        f"Routing message for user {user_id}. Mode: {mode}. "
        f"Last message: '{last_message.get('content', '')[:50]}...'"
    )

    # 1. Check Mode First: If user is answering an exercise/quiz
    if mode == "doing_exercise" or mode == "taking_quiz":
        logger.debug("Mode is exercise/quiz, routing to evaluation.")
        return "evaluate_chat_answer"

    # 2. LLM Intent Classification (if mode is 'chatting')
    if mode == "chatting":
        if not last_message or last_message.get("role") != "user":
            logger.warning(
                "Routing in 'chatting' mode without a preceding user message."
                " Defaulting to chat response."
            )
            return "generate_chat_response"

        user_input: str = last_message.get("content", "")
        # Limit history for prompt efficiency
        history_for_prompt: List[Dict[str, str]] = history[
            -5:
        ]  # Last 5 messages (user + assistant)

        try:
            # Load and format the prompt
            prompt: str = load_prompt(
                "intent_classification",
                history_json=json.dumps(history_for_prompt, indent=2),
                user_input=user_input,
            )
            # LLM call and JSON parsing/validation
            result: Optional[IntentClassificationResult] = (
                call_llm_with_json_parsing(
                    prompt, validation_model=IntentClassificationResult
                )
            )

            if result and isinstance(result, IntentClassificationResult):
                intent: str = result.intent
                logger.info(f"Classified intent: {intent}")

                # 3. Route Based on Intent
                if intent == "request_exercise":
                    return "present_exercise"
                elif intent == "request_quiz":
                    return "present_quiz_question"
                elif intent == "ask_question" or intent == "other_chat":
                    return "generate_chat_response"
                else:
                    logger.warning(
                        f"Unknown or unexpected intent '{intent}'. Defaulting to chat response."
                    )
                    return "generate_chat_response"
            else:
                # Handle cases where LLM call failed, JSON parsing failed, or validation failed
                logger.warning(
                    "Failed to get valid intent classification from LLM. "
                    "Defaulting to chat response."
                )
                return "generate_chat_response"

        except Exception as e:
            logger.error(
                f"Error during intent classification LLM call: {e}", exc_info=True
            )
            # Fallback to default chat response on error
            return "generate_chat_response"
    else:
        # Should not happen if modes are handled correctly, but default just in case
        logger.warning(
            f"Routing encountered unexpected mode '{mode}'. Defaulting to chat response."
        )
        return "generate_chat_response"


def generate_chat_response(state: LessonState) -> Dict[str, Any]:
    """
    Generates a conversational response using the AI based on history and context.
    Corresponds to the _generate_chat_response node logic.
    """
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    lesson_title: str = state.get("lesson_title", "this lesson")
    # Get the full exposition content
    generated_content = state.get("generated_content")
    exposition: Optional[str] = "No exposition available."
    if generated_content:
        exposition = str(generated_content.exposition_content)
    # Cast to str for prompt

    logger.debug(
        f"Generating chat response for user {user_id} in lesson '{lesson_title}'"
    )

    ai_response_content: str
    if not history or history[-1].get("role") != "user":
        logger.warning(
            "generate_chat_response called without a preceding user message."
        )
        ai_response_content = (
            "Is there something specific I can help you with regarding the lesson?"
        )
    else:
        # Limit history for prompt efficiency
        history_for_prompt: List[Dict[str, str]] = history[-10:]  # Last 10 messages

        try:
            # Load and format the prompt
            prompt: str = load_prompt(
                "chat_response",
                lesson_title=lesson_title,
                exposition=exposition or "",  # Ensure exposition is not None
                history_json=json.dumps(history_for_prompt, indent=2),
            )
            # Use call_with_retry from llm_utils with the imported llm_model
            # Note: Assuming llm_model is correctly imported and configured
            response: Any = call_with_retry(llm_model.generate_content, prompt)
            ai_response_content = response.text
            logger.debug(f"Generated chat response: {ai_response_content[:100]}...")
        # except ResourceExhausted: # Handled by call_with_retry
        #     logger.error(...)
        #     ai_response_content = "..."
        except Exception as e:
            logger.error(
                f"Error during chat response LLM call/prompt loading: {e}",
                exc_info=True,
            )
            ai_response_content = """
            Sorry, I encountered an error trying to generate a response. Please try again."""

    # Format the response and update history
    ai_message: Dict[str, str] = {
        "role": "assistant",
        "content": ai_response_content,
    }
    updated_history: List[Dict[str, str]] = history + [ai_message]

    return {"conversation_history": updated_history}


def present_exercise(state: LessonState) -> Dict[str, Any]:
    """
    Presents the next exercise to the user via chat and updates state.
    Corresponds to the _present_exercise node logic.
    """
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    generated_content: Optional[GeneratedLessonContent] = state.get(
        "generated_content"
    )
    exercises: List[Exercise] = (
        generated_content.active_exercises if generated_content else []
    )

    # Get current index and increment
    current_index: int = state.get("current_exercise_index", -1)
    next_index: int = current_index + 1

    logger.debug(
        f"Presenting exercise for user {user_id}. "
        f"Current index: {current_index}, attempting next: {next_index}"
    )

    if 0 <= next_index < len(exercises):
        exercise: Exercise = exercises[next_index]
        exercise_type: str = exercise.type
        question_text: str = (
            exercise.question
            or exercise.instructions
            or "No instructions provided."
        )

        # Format the message content
        message_parts: List[str] = [
            f"Alright, let's try exercise {next_index + 1}!",
            f"**Type:** {exercise_type.replace('_', ' ').capitalize()}",
            f"**Instructions:**\n{question_text}",
        ]

        # Add items for ordering exercises
        if exercise_type == "ordering" and exercise.items:
            items_list: str = "\n".join([f"- {item}" for item in exercise.items])
            message_parts.append(f"\n**Items to order:**\n{items_list}")

        message_parts.append("\nPlease provide your answer.")
        ai_response_content: str = "\n\n".join(message_parts)

        ai_message: Dict[str, str] = {
            "role": "assistant",
            "content": ai_response_content,
        }
        updated_history: List[Dict[str, str]] = history + [ai_message]

        logger.info(f"Presented exercise {next_index} to user {user_id}")

        return {
            "conversation_history": updated_history,
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": next_index,  # Update index
        }
    else:
        # No more exercises
        logger.info(f"No more exercises available for user {user_id}")
        ai_response_content = """
            Great job, you've completed all the exercises for this lesson!
            What would you like to do next? (e.g., ask questions, take the quiz)"""
        ai_message = {"role": "assistant", "content": ai_response_content}
        updated_history = history + [ai_message]

        return {
            "conversation_history": updated_history,
            "current_interaction_mode": "chatting",
            "current_exercise_index": current_index,  # Preserve the current index
        }


def present_quiz_question(state: LessonState) -> Dict[str, Any]:
    """
    Presents the next quiz question to the user via chat and updates state.
    Corresponds to the _present_quiz_question node logic.
    """
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    generated_content: Optional[GeneratedLessonContent] = state.get(
        "generated_content"
    )
    questions: List[AssessmentQuestion] = (
        generated_content.knowledge_assessment if generated_content else []
    )

    # Get current index and increment
    current_index: int = state.get("current_quiz_question_index", -1)
    next_index: int = current_index + 1

    logger.debug(
        f"Presenting quiz question for user {user_id}. "
        f"Current index: {current_index}, attempting next: {next_index}"
    )

    if 0 <= next_index < len(questions):
        question: AssessmentQuestion = questions[next_index]
        question_type: str = question.type
        question_text: str = question.question

        # Format options based on type
        options_lines: List[str] = []
        if question_type == "multiple_choice" and question.options:
            options: Union[Dict[str, str], List[str]] = question.options
            if isinstance(options, dict):
                options_lines = [
                    f"- {key}) {value}" for key, value in options.items()
                ]
            elif isinstance(options, list):  # Handle list options if necessary
                options_lines = [f"- {opt}" for opt in options]
            # Add instruction for MC questions
            options_lines.append(
                "\nPlease respond with the letter/key of your chosen answer (e.g., 'A')."
            )
        elif question_type == "true_false":
            options_lines = [
                "- True",
                "- False",
                "\nPlease respond with 'True' or 'False'.",
            ]

        options_text: str = "\n".join(options_lines)

        # Format the message content
        message_parts: List[str] = [
            f"Okay, here's quiz question {next_index + 1}:",
            f"{question_text}",
        ]
        if options_text:
            message_parts.append(f"\n{options_text}")

        ai_response_content: str = "\n\n".join(message_parts)

        ai_message: Dict[str, str] = {
            "role": "assistant",
            "content": ai_response_content,
        }
        updated_history: List[Dict[str, str]] = history + [ai_message]

        logger.info(f"Presented quiz question {next_index} to user {user_id}")

        return {
            "conversation_history": updated_history,
            "current_interaction_mode": "taking_quiz",
            "current_quiz_question_index": next_index,  # Update index
        }
    else:
        # No more quiz questions
        logger.info(f"No more quiz questions available for user {user_id}")
        # TODO: Calculate and present final score? (Handled by LessonService now)
        ai_response_content = """
            You've completed the quiz for this lesson! What would you like to do now?"""
        ai_message = {"role": "assistant", "content": ai_response_content}
        updated_history = history + [ai_message]

        return {
            "conversation_history": updated_history,
            "current_interaction_mode": "chatting",  # Reset mode
            "current_quiz_question_index": current_index,  # Preserve the current index
        }


def evaluate_chat_answer(state: LessonState) -> Dict[str, Any]:
    """
    Evaluates a user's answer provided in the chat using an LLM.
    Corresponds to the _evaluate_chat_answer node logic.
    """
    mode: str = state.get("current_interaction_mode")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    generated_content: Optional[GeneratedLessonContent] = state.get(
        "generated_content"
    )
    user_responses: List[Dict] = state.get(
        "user_responses", []
    )

    if not history or history[-1].get("role") != "user":
        logger.warning(
            f"evaluate_chat_answer called without a preceding user message for user {user_id}."
        )
        ai_message: Dict[str, str] = {
            "role": "assistant",
            "content": """
                It looks like you haven't provided an answer yet.
                Please provide your answer to the question.""",
        }
        return {
            "conversation_history": history + [ai_message],
            "current_interaction_mode": mode,
            "user_responses": user_responses,
        }

    user_answer: str = history[-1].get("content", "")
    question: Optional[Union[Exercise, AssessmentQuestion]] = None
    question_type: Optional[str] = None
    question_index: int = -1
    question_id_str: str = "unknown"

    # Identify the question being answered
    if generated_content:
        if mode == "doing_exercise":
            question_type = "exercise"
            question_index = state.get("current_exercise_index", -1)
            exercises: List[Exercise] = generated_content.active_exercises
            if 0 <= question_index < len(exercises):
                question = exercises[question_index]
                question_id_str = question.id
        elif mode == "taking_quiz":
            question_type = "assessment"
            question_index = state.get("current_quiz_question_index", -1)
            questions: List[AssessmentQuestion] = (
                generated_content.knowledge_assessment
            )
            if 0 <= question_index < len(questions):
                question = questions[question_index]
                question_id_str = question.id

    if question is None:
        logger.error(
            "Could not find question for evaluation. "
            f"Mode: {mode}, Index: {question_index}, User: {user_id}"
        )
        ai_message = {
            "role": "assistant",
            "content": """
                Sorry, I lost track of which question you were answering.
                Could you clarify or ask to try again?""",
        }
        return {
            "conversation_history": history + [ai_message],
            "current_interaction_mode": "chatting",
            "user_responses": user_responses,
        }

    # Prepare prompt context
    question_text: str = question.question or getattr(
        question, "instructions", "N/A"
    )  # Handle Exercise/AssessmentQuestion
    expected_solution: str = (
        getattr(question, "answer", None)  # Check for 'answer' if defined in models
        or getattr(question, "expected_solution", None)
        or question.correct_answer
        or question.explanation
        or "N/A"
    )
    prompt_context: str = f"Question/Instructions:\n{question_text}\n"
    q_type: str = question.type
    if q_type == "multiple_choice" and question.options:
        options: Union[Dict[str, str], List[str]] = question.options
        options_str: str = ""
        if isinstance(options, dict):
            options_str = "\n".join(
                [f"- {key}) {value}" for key, value in options.items()]
            )
        elif isinstance(options, list):
            options_str = "\n".join([f"- {opt}" for opt in options])
        prompt_context += f"""
            \nOptions:\n{options_str}\n\nThe user should respond with
            the key/letter or the full text of the correct option."""
    elif q_type == "true_false":
        prompt_context += \
            "\nOptions:\n- True\n- False\n\nThe user should respond with 'True' or 'False'."
    elif q_type == "ordering" and getattr(
        question, "items", None
    ):  # Check if 'items' exists (for Exercise)
        items_list: str = "\n".join([f"- {item}" for item in question.items])
        prompt_context += f"""
                    \nItems to order:\n{items_list}\n\n
                    The user should respond with the items in the correct order."""
    prompt_context += f"""
                \n\nExpected Answer/Solution Context (if available):\n
                {expected_solution}\n\nUser's Answer:\n{user_answer}"""

    # Call LLM for evaluation
    evaluation_result_obj: Optional[EvaluationResult] = None
    evaluation_result: Dict[str, Any]  # Define type for the dict version
    try:
        prompt = load_prompt(
            "evaluate_answer",
            question_type=question_type or "question",  # Provide default
            prompt_context=prompt_context,
        )
        evaluation_result_obj = call_llm_with_json_parsing(
            prompt, validation_model=EvaluationResult
        )
        if not evaluation_result_obj:
            logger.error(
                f"Failed to get valid evaluation from LLM for q_id {question_id_str}."
            )
    except Exception as e:
        logger.error(
            f"Error in evaluation prompt loading/formatting for q_id {question_id_str}: {e}",
            exc_info=True,
        )

    # Use fallback if evaluation failed, otherwise convert model to dict
    if evaluation_result_obj is None:
        evaluation_result = {
            "score": 0.0,
            "is_correct": False,
            "feedback": """
                Sorry, I encountered an error while evaluating your answer.
                Let's move on for now.""",
            "explanation": "",
        }
    else:
        evaluation_result = evaluation_result_obj.model_dump()
        logger.info(
            f"Parsed evaluation for q_id {question_id_str}: "
            f"Score={evaluation_result['score']}, Correct={evaluation_result['is_correct']}"
        )

    # Create assistant feedback message
    feedback_text: str = evaluation_result["feedback"]
    if not evaluation_result["is_correct"] and evaluation_result.get("explanation"):
        feedback_text += f"\n\n*Explanation:* {evaluation_result['explanation']}"
    ai_feedback_message: Dict[str, str] = {
        "role": "assistant",
        "content": feedback_text,
    }
    updated_history: List[Dict[str, str]] = history + [ai_feedback_message]

    # Record the evaluation attempt
    user_response_record: Dict[str, Any] = {
        "question_id": question_id_str,
        "question_type": question_type,
        "response": user_answer,
        "evaluation": evaluation_result,
        "timestamp": datetime.now().isoformat(),
    }
    updated_user_responses: List[Dict] = user_responses + [user_response_record]

    # Decide next step and potentially add follow-up message
    # In the refactored design, the graph simply returns the state.
    # The LessonService will decide the *actual* next step (next question, chat, etc.)
    # based on the evaluation result and adaptivity rules.
    # For now, we just reset the mode to 'chatting' as a default transition after evaluation.
    next_mode: str = "chatting"
    follow_up_text: Optional[str] = None

    # Add a simple follow-up prompt if correct, otherwise just the feedback.
    # More complex logic (like suggesting next exercise/quiz based on score)
    # belongs in the LessonService.
    if evaluation_result["is_correct"]:
        if mode == "doing_exercise":
            follow_up_text = \
                "That's correct! Would you like the next exercise, or something else?"
        elif mode == "taking_quiz":
            follow_up_text = "Correct! Ready for the next quiz question?"

        if follow_up_text:
            ai_followup_message: Dict[str, str] = {
                "role": "assistant",
                "content": follow_up_text,
            }
            updated_history.append(ai_followup_message)
    # else: # If incorrect, feedback message is already added

    return {
        "conversation_history": updated_history,
        "current_interaction_mode": next_mode, # Default transition
        "user_responses": updated_user_responses,
    }


def update_progress(state: LessonState) -> Dict[str, Any]:
    """
    Graph node: Placeholder for updating/saving user progress.

    Note: As per the refactored design, progress saving is intended to be handled
    externally by the LessonService after a graph turn completes.
    This node performs no state modifications by default. It serves as a designated
    endpoint for the graph turn before returning control to the service layer.
    """
    logger.debug("Update progress node executed (placeholder).")
    # No state changes are made here.
    return {}