"""
Node logic functions for the lesson AI graph.

These functions are designed to be called by the langgraph StateGraph
and operate on the LessonState.
"""

import json
import uuid # For generating fallback IDs
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple # Added Tuple

from pydantic import ValidationError

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
    Option, # Import Option model
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
                    logger.debug("Routing to generate_new_exercise")
                    return "generate_new_exercise" # Route to the new generation node
                elif intent == "request_quiz":
                    logger.debug("Routing to generate_new_assessment_question")
                    return "generate_new_assessment_question" # Route to the new generation node
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
    # Get the full exposition content and ensure it's a Pydantic model
    raw_generated_content: Optional[Union[Dict, GeneratedLessonContent]] = state.get(
        "generated_content"
    )
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content") # Directly get the object
    exposition: Optional[str] = "No exposition available."

    # Validation is now handled in the service layer before state is passed to the graph.
    # We can assume generated_content is either a valid object or None.
    if not isinstance(generated_content, GeneratedLessonContent) and generated_content is not None:
         logger.error(f"generate_chat_response received unexpected type for generated_content: {type(generated_content)}")
         generated_content = None # Treat as None if type is wrong
    elif generated_content is None:
         logger.warning("generate_chat_response received None for generated_content.")

    if generated_content and generated_content.exposition_content:
        # Assuming exposition_content can be complex, convert to string representation
        # Adjust this if a specific format (like markdown) is needed for the prompt
        exposition = str(generated_content.exposition_content)

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


def evaluate_chat_answer(state: LessonState) -> Dict[str, Any]:
    """
    Evaluates a user's answer provided in the chat using an LLM.
    Corresponds to the _evaluate_chat_answer node logic.
    """
    mode: str = state.get("current_interaction_mode")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")
    # raw_generated_content: Optional[Union[Dict, GeneratedLessonContent]] = state.get( # No longer needed
    #     "generated_content"
    # )
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content") # Retrieve from state
    user_responses: List[Dict] = state.get(
        "user_responses", []
    )

    # Validation is now handled in the service layer.
    # Assume generated_content is a valid object or None.
    if not isinstance(generated_content, GeneratedLessonContent) and generated_content is not None:
         logger.error(f"evaluate_chat_answer received unexpected type for generated_content: {type(generated_content)}")
         generated_content = None # Treat as None if type is wrong
    elif generated_content is None:
         logger.warning("evaluate_chat_answer received None for generated_content.")

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
    current_exercise_id: Optional[str] = None
    current_assessment_question_id: Optional[str] = None

    # Identify the question being answered using ID from state
    if mode == "doing_exercise":
        question_type = "exercise"
        current_exercise_id = state.get("current_exercise_id")
        if current_exercise_id:
            logger.debug(f"Evaluate: Looking for exercise with ID: {current_exercise_id}")
            generated_exercises: List[Exercise] = state.get("generated_exercises", [])
            # Find the exercise by ID
            question = next((ex for ex in generated_exercises if ex.id == current_exercise_id), None)
            if question:
                question_id_str = question.id
                logger.debug(f"Evaluate: Found exercise by ID: {question_id_str}")
            else:
                 logger.warning(f"Evaluate: Exercise with ID {current_exercise_id} not found in state list.")
        else:
            logger.warning("Evaluate: Mode is 'doing_exercise' but 'current_exercise_id' is missing from state.")

    elif mode == "taking_quiz":
        question_type = "assessment"
        current_assessment_question_id = state.get("current_assessment_question_id")
        if current_assessment_question_id:
            logger.debug(f"Evaluate: Looking for assessment question with ID: {current_assessment_question_id}")
            generated_questions: List[AssessmentQuestion] = state.get("generated_assessment_questions", [])
            # Find the question by ID
            question = next((q for q in generated_questions if q.id == current_assessment_question_id), None)
            if question:
                question_id_str = question.id
                logger.debug(f"Evaluate: Found assessment question by ID: {question_id_str}")
            else:
                logger.warning(f"Evaluate: Assessment question with ID {current_assessment_question_id} not found in state list.")
        else:
            logger.warning("Evaluate: Mode is 'taking_quiz' but 'current_assessment_question_id' is missing from state.")
    else:
        logger.warning(f"Evaluate: Unexpected mode '{mode}' when trying to find question.")

    if question is None:
        logger.error(
            "Could not find question for evaluation using ID. "
            f"Mode: {mode}, ExerciseID: {current_exercise_id}, QuestionID: {current_assessment_question_id}, User: {user_id}"
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
    prompt_context: str = "" # Initialize prompt_context
    try: # Add try block around context building
        question_text: str = getattr(question, "question_text", None) or getattr(
            question, "instructions", "N/A"
        )

        # Determine expected solution based on question type and available fields
        expected_solution: str = "N/A"
        if isinstance(question, Exercise):
            expected_solution = getattr(question, "correct_answer", None) or getattr(question, "explanation", "N/A")
        elif isinstance(question, AssessmentQuestion):
            expected_solution = getattr(question, "correct_answer_id", None) or getattr(question, "correct_answer", None) or getattr(question, "explanation", "N/A")

        prompt_context = f"Question/Instructions:\n{question_text}\n" # Assign initial part
        q_type: str = question.type
        if q_type == "multiple_choice" and question.options and isinstance(question.options, list):
            # Safely format options only if it's a non-empty list of Option objects
            valid_options = [opt for opt in question.options if isinstance(opt, Option)]
            if valid_options:
                options_str = "\n".join(
                    [f"- {opt.id}) {opt.text}" for opt in valid_options]
                )
            else:
                options_str = "[Options formatting error]"
                logger.warning(f"MC question {getattr(question, 'id', 'unknown')} has invalid options format: {question.options}")
            prompt_context += f"""
                \nOptions:\n{options_str}\n\nThe user should respond with
                the key/letter or the full text of the correct option."""
        elif q_type == "true_false":
            prompt_context += \
                "\nOptions:\n- True\n- False\n\nThe user should respond with 'True' or 'False'."
        elif q_type == "ordering" and getattr(
            question, "items", None
        ):
            items_list: str = "\n".join([f"- {item}" for item in question.items])
            prompt_context += f"""
                        \nItems to order:\n{items_list}\n\n
                        The user should respond with the items in the correct order."""
        prompt_context += f"""
                    \n\nExpected Answer/Solution Context (if available):\n
                    {expected_solution}\n\nUser's Answer:\n{user_answer}"""
    except Exception as context_err: # Add except block
        logger.error(f"Error building prompt context for evaluation: {context_err}", exc_info=True)
        # Fallback context
        prompt_context = f"Error building context. User Answer: {user_answer}"

    # Call LLM for evaluation
    evaluation_result_obj: Optional[EvaluationResult] = None
    evaluation_result: Dict[str, Any]
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


async def generate_new_exercise(state: LessonState) -> Tuple[LessonState, Optional[Exercise]]:
    """
    Generates a new, unique exercise based on lesson context and presents it.
    """
    logger.info("Attempting to generate a new exercise.")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

    # --- 1. Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    syllabus: Optional[Dict] = state.get("syllabus") # For context
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    existing_exercise_ids: List[str] = state.get("generated_exercise_ids", [])

    # Basic validation
    if not generated_content or not generated_content.exposition_content:
        logger.error(f"Cannot generate exercise: Missing exposition content for user {user_id}.")
        # Add error message to state? Or just return None?
        state["error_message"] = "Sorry, I couldn't generate an exercise because the lesson content is missing."
        # Return original state and None for the exercise
        return state, None

    # Create exposition summary (simple string for now)
    exposition_summary = str(generated_content.exposition_content)[:1000] # Limit length

    # Create syllabus context (simplified - maybe just module/lesson titles?)
    syllabus_context = f"Module: {state.get('module_title', 'N/A')}, Lesson: {lesson_title}"
    # TODO: Potentially add more syllabus context if needed by the prompt

    # --- 2. Call LLM ---
    new_exercise: Optional[Exercise] = None
    try:
        prompt = load_prompt(
            "generate_exercises", # Use the new prompt file name
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            syllabus_context=syllabus_context,
            existing_exercise_descriptions_json=json.dumps(existing_exercise_ids) # Pass existing IDs
        )

        # Use call_llm_with_json_parsing to get a validated Exercise object
        # Making this async as call_llm_with_json_parsing might be async
        new_exercise = await call_llm_with_json_parsing(
            prompt, validation_model=Exercise, max_retries=2 # Allow fewer retries for generation
        )

    except Exception as e:
        logger.error(f"LLM call/parsing failed during exercise generation: {e}", exc_info=True)
        # Fall through, new_exercise will be None

    # --- 3. Process Result & Update State ---
    if new_exercise and isinstance(new_exercise, Exercise):
        # Ensure the exercise has an ID
        if not new_exercise.id:
            new_exercise.id = f"ex_{uuid.uuid4().hex[:6]}" # Generate a fallback ID
            logger.warning(f"Generated exercise lacked ID, assigned fallback: {new_exercise.id}")

        # Check if ID already exists (LLM might ignore novelty constraint)
        if new_exercise.id in existing_exercise_ids:
            logger.warning(f"LLM generated an exercise with a duplicate ID ({new_exercise.id}). Discarding.")
            # Add message indicating failure to generate a *new* one
            ai_message = {
                "role": "assistant",
                "content": "Sorry, I couldn't come up with a new exercise right now. Would you like to try again or ask something else?"
            }
            state["conversation_history"] = history + [ai_message]
            state["current_interaction_mode"] = "chatting"
            return state, None # Return original state and None exercise

        logger.info(f"Successfully generated new exercise with ID: {new_exercise.id}")

        # Update state lists
        updated_exercises = state.get("generated_exercises", []) + [new_exercise]
        updated_exercise_ids = existing_exercise_ids + [new_exercise.id]

        # Format presentation message
        exercise_type: str = new_exercise.type
        question_text: str = (
            new_exercise.question
            or new_exercise.instructions
            or "No instructions provided."
        )
        message_parts: List[str] = [
            f"Okay, here's a new exercise for you!",
            f"**Type:** {exercise_type.replace('_', ' ').capitalize()}",
            f"**Instructions:**\n{question_text}",
        ]
        # Add items for ordering exercises
        if exercise_type == "ordering" and new_exercise.items:
            items_list: str = "\n".join([f"- {item}" for item in new_exercise.items])
            message_parts.append(f"\n**Items to order:**\n{items_list}")
        # Add options for multiple choice
        elif exercise_type == "multiple_choice" and new_exercise.options:
             options_str = "\n".join([f"- {opt.id}) {opt.text}" for opt in new_exercise.options])
             message_parts.append(f"\n**Options:**\n{options_str}")
             message_parts.append("\nPlease respond with the letter/key of your chosen answer (e.g., 'A').")
        else:
             message_parts.append("\nPlease provide your answer.")

        ai_response_content: str = "\n\n".join(message_parts)
        ai_message: Dict[str, str] = {
            "role": "assistant",
            "content": ai_response_content,
        }

        # Update state dictionary
        state["generated_exercises"] = updated_exercises
        state["generated_exercise_ids"] = updated_exercise_ids
        state["conversation_history"] = history + [ai_message]
        state["current_interaction_mode"] = "doing_exercise"
        # We need a way to track *which* exercise is being answered now.
        # Let's add a temporary field, maybe 'current_exercise_id'?
        state["current_exercise_id"] = new_exercise.id # Track the ID of the presented exercise
        state["error_message"] = None # Clear any previous error

        return state, new_exercise

    else:
        # Handle LLM failure or invalid JSON
        logger.error(f"Failed to generate or validate a new exercise for user {user_id}.")
        ai_message = {
            "role": "assistant",
            "content": "Sorry, I wasn't able to generate an exercise right now. Please try again later or ask me a question."
        }
        state["conversation_history"] = history + [ai_message]
        state["current_interaction_mode"] = "chatting"
        state["error_message"] = "Failed to generate exercise." # Store error state

        return state, None # Return original state and None exercise


async def generate_new_assessment_question(state: LessonState) -> Tuple[LessonState, Optional[AssessmentQuestion]]:
    """
    Generates a new, unique assessment question based on lesson context and presents it.
    """
    logger.info("Attempting to generate a new assessment question.")
    history: List[Dict[str, str]] = state.get("conversation_history", [])
    user_id: str = state.get("user_id", "unknown_user")

    # --- 1. Extract Context ---
    topic: str = state.get("topic", "Unknown Topic")
    lesson_title: str = state.get("lesson_title", "Unknown Lesson")
    user_level: str = state.get("knowledge_level", "beginner")
    syllabus: Optional[Dict] = state.get("syllabus")
    generated_content: Optional[GeneratedLessonContent] = state.get("generated_content")
    existing_question_ids: List[str] = state.get("generated_assessment_question_ids", [])

    # Basic validation
    if not generated_content or not generated_content.exposition_content:
        logger.error(f"Cannot generate assessment question: Missing exposition content for user {user_id}.")
        state["error_message"] = "Sorry, I couldn't generate a question because the lesson content is missing."
        return state, None

    exposition_summary = str(generated_content.exposition_content)[:1000]
    syllabus_context = f"Module: {state.get('module_title', 'N/A')}, Lesson: {lesson_title}"
    # TODO: Add more syllabus context if needed

    # --- 2. Call LLM ---
    new_question: Optional[AssessmentQuestion] = None
    try:
        prompt = load_prompt(
            "generate_assessment", # Use the assessment prompt
            topic=topic,
            lesson_title=lesson_title,
            user_level=user_level,
            exposition_summary=exposition_summary,
            syllabus_context=syllabus_context,
            existing_question_descriptions_json=json.dumps(existing_question_ids) # Pass existing IDs
        )

        # Use call_llm_with_json_parsing for validation
        # Making this async as call_llm_with_json_parsing might be async
        new_question = await call_llm_with_json_parsing(
            prompt, validation_model=AssessmentQuestion, max_retries=2
        )

    except Exception as e:
        logger.error(f"LLM call/parsing failed during assessment question generation: {e}", exc_info=True)

    # --- 3. Process Result & Update State ---
    if new_question and isinstance(new_question, AssessmentQuestion):
        if not new_question.id:
            new_question.id = f"quiz_{uuid.uuid4().hex[:6]}"
            logger.warning(f"Generated assessment question lacked ID, assigned fallback: {new_question.id}")

        if new_question.id in existing_question_ids:
            logger.warning(f"LLM generated an assessment question with a duplicate ID ({new_question.id}). Discarding.")
            ai_message = {
                "role": "assistant",
                "content": "Sorry, I couldn't come up with a new assessment question right now. Would you like to try again or ask something else?"
            }
            state["conversation_history"] = history + [ai_message]
            state["current_interaction_mode"] = "chatting"
            return state, None

        logger.info(f"Successfully generated new assessment question with ID: {new_question.id}")

        # Update state lists
        updated_questions = state.get("generated_assessment_questions", []) + [new_question]
        updated_question_ids = existing_question_ids + [new_question.id]

        # Format presentation message
        question_type: str = new_question.type
        question_text: str = new_question.question_text
        message_parts: List[str] = [
            f"Okay, here's an assessment question for you:",
            f"{question_text}",
        ]
        options_lines: List[str] = []
        if question_type == "multiple_choice" and new_question.options:
            options_lines = [f"- {opt.id}) {opt.text}" for opt in new_question.options]
            options_lines.append("\nPlease respond with the letter/key of your chosen answer (e.g., 'A').")
        elif question_type == "true_false":
            options_lines = ["- True", "- False", "\nPlease respond with 'True' or 'False'."]

        if options_lines:
             options_text: str = "\n".join(options_lines)
             message_parts.append(f"\n{options_text}")
        else: # Short answer
             message_parts.append("\nPlease provide your answer.")


        ai_response_content: str = "\n\n".join(message_parts)
        ai_message: Dict[str, str] = {
            "role": "assistant",
            "content": ai_response_content,
        }

        # Update state dictionary
        state["generated_assessment_questions"] = updated_questions
        state["generated_assessment_question_ids"] = updated_question_ids
        state["conversation_history"] = history + [ai_message]
        state["current_interaction_mode"] = "taking_quiz"
        # Add field to track current question ID
        state["current_assessment_question_id"] = new_question.id
        state["error_message"] = None

        return state, new_question

    else:
        # Handle LLM failure or invalid JSON
        logger.error(f"Failed to generate or validate a new assessment question for user {user_id}.")
        ai_message = {
            "role": "assistant",
            "content": "Sorry, I wasn't able to generate an assessment question right now. Please try again later or ask me a question."
        }
        state["conversation_history"] = history + [ai_message]
        state["current_interaction_mode"] = "chatting"
        state["error_message"] = "Failed to generate assessment question."

        return state, None


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