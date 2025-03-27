"""Langgraph code for the lessons AI"""

# pylint: disable=broad-exception-caught,singleton-comparison

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union  # Added Union

from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from langgraph.graph import StateGraph


# Import the new LLM utility functions and the MODEL instance
from backend.ai.llm_utils import call_llm_with_json_parsing, call_with_retry
from backend.ai.llm_utils import MODEL as llm_model
from backend.logger import logger  # Ensure logger is available
from backend.ai.prompt_loader import load_prompt  # Import the prompt loader

# Import LessonState and other models from backend.models
from backend.models import (  # Added Exercise, AssessmentQuestion
    AssessmentQuestion,
    EvaluationResult,
    Exercise,
    GeneratedLessonContent,
    IntentClassificationResult,
    LessonState,
)

# Load environment variables
load_dotenv()


class LessonAI:
    """Encapsulates the Tech Tree lesson langgraph app."""

    chat_workflow: StateGraph  # Add type hint for instance variable
    chat_graph: Any  # Compiled graph type might be complex, use Any for now

    def __init__(self) -> None:
        """Initialize the LessonAI."""
        # Compile the chat turn workflow
        self.chat_workflow = self._create_chat_workflow()
        self.chat_graph = self.chat_workflow.compile()

    # --- Placeholder Methods for New Nodes ---
    def _start_conversation(self, state: LessonState) -> Dict[str, Any]:
        """Generates the initial AI welcome message."""

        lesson_title: str = state.get("lesson_title", "this lesson")
        user_id: str = state.get("user_id", "unknown_user")
        history: List[Dict[str, str]] = state.get("conversation_history", [])

        logger.debug(
            f"Starting conversation for user {user_id}, lesson '{lesson_title}'"
        )

        # Check if history is already present (shouldn't be if this is truly the start)
        if history:
            logger.warning(
                f"_start_conversation called but history is not empty for user {user_id}."
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

    def _process_user_message(self, _: LessonState) -> Dict[str, Any]:
        """ Graph node: Initial state """
        print("Placeholder: _process_user_message")
        return {}

    def _route_message_logic(self, state: LessonState) -> str:
        """Determines the next node based on interaction mode and user message intent."""
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

    def _generate_chat_response(self, state: LessonState) -> Dict[str, Any]:
        """Generates a conversational response using the AI based on history and context."""

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
                response: Any = call_with_retry(llm_model.generate_content, prompt)
                ai_response_content = response.text
                logger.debug(f"Generated chat response: {ai_response_content[:100]}...")
            except ResourceExhausted:
                # Let call_with_retry handle retries; this catches final failure
                logger.error(
                    "LLM call failed after multiple retries due to "
                    "resource exhaustion in _generate_chat_response."
                )
                ai_response_content = """
                    Sorry, I'm having trouble connecting right now. Please try again in a moment."""
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

    def _present_exercise(self, state: LessonState) -> Dict[str, Any]:
        """Presents the next exercise to the user via chat and updates state."""

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

    def _present_quiz_question(self, state: LessonState) -> Dict[str, Any]:
        """Presents the next quiz question to the user via chat and updates state."""

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
            # TODO: Calculate and present final score?
            ai_response_content = """
                You've completed the quiz for this lesson! What would you like to do now?"""
            ai_message = {"role": "assistant", "content": ai_response_content}
            updated_history = history + [ai_message]

            return {
                "conversation_history": updated_history,
                "current_interaction_mode": "chatting",  # Reset mode
                "current_quiz_question_index": current_index,  # Preserve the current index
            }

    # Refactored _evaluate_chat_answer function
    def _evaluate_chat_answer(self, state: LessonState) -> Dict[str, Any]:
        """Evaluates a user's answer provided in the chat using an LLM."""

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
        next_mode: str = "chatting"
        if evaluation_result["is_correct"]:
            follow_up_text: Optional[str] = None
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
            "current_interaction_mode": next_mode,
            "user_responses": updated_user_responses,
        }

    def _update_progress(self, _: LessonState) -> Dict[str, Any]:
        """
        Graph node: Placeholder for updating/saving user progress.

        Note: As per the design, progress saving is intended to be handled
        externally by the service layer after a graph turn completes.
        This node performs no state modifications.
        """
        print("Placeholder: _update_progress")
        return {}

    # --- _generate_lesson_content removed, logic moved to LessonService ---

    # --- Modified Workflow Creation ---
    def _create_chat_workflow(self) -> StateGraph:
        """Create the langgraph workflow for a single chat turn."""
        workflow = StateGraph(LessonState)

        # Add nodes for the chat turn
        workflow.add_node("process_user_message", self._process_user_message)
        workflow.add_node("generate_chat_response", self._generate_chat_response)
        workflow.add_node("present_exercise", self._present_exercise)
        workflow.add_node("present_quiz_question", self._present_quiz_question)
        workflow.add_node("evaluate_chat_answer", self._evaluate_chat_answer)
        workflow.add_node(
            "update_progress", self._update_progress
        )  # Node to potentially save state

        # Entry point for a chat turn
        workflow.set_entry_point("process_user_message")

        # Conditional routing after processing user message
        workflow.add_conditional_edges(
            "process_user_message",
            self._route_message_logic,
            {
                "generate_chat_response": "generate_chat_response",
                "present_exercise": "present_exercise",
                "present_quiz_question": "present_quiz_question",
                # Route directly if mode requires evaluation
                "evaluate_chat_answer": "evaluate_chat_answer",
            },
        )

        # Edges leading to update_progress (and potentially loop or end)
        workflow.add_edge("generate_chat_response", "update_progress")
        workflow.add_edge("present_exercise", "update_progress")
        workflow.add_edge("present_quiz_question", "update_progress")
        workflow.add_edge("evaluate_chat_answer", "update_progress")

        # End the turn after updating progress
        workflow.add_edge("update_progress", "__end__")  # Use built-in end

        return workflow

    # --- New Method to Handle Chat Turns ---
    def process_chat_turn(
        self, current_state: LessonState, user_message: str
    ) -> LessonState:
        """Processes one turn of the conversation."""
        if not current_state:
            raise ValueError("Current state must be provided for a chat turn.")

        # Add user message to history before invoking graph
        updated_history: List[Dict[str, str]] = current_state.get(
            "conversation_history", []
        ) + [{"role": "user", "content": user_message}]
        # type: ignore
        input_state: LessonState = {**current_state, "conversation_history": updated_history}

        # Invoke the chat graph
        output_state: Any = self.chat_graph.invoke(input_state)

        # Merge output state changes back (langgraph does this implicitly, but good practice)
        # Ensure the final state conforms to LessonState structure
        final_state: LessonState = {**input_state, **output_state}  # type: ignore
        return final_state

    # --- New Method to Start Chat ---
    def start_chat(self, initial_state: LessonState) -> LessonState:
        """
        Generates the initial welcome message and sets up the state for conversation.
        Assumes initial_state contains necessary context (topic, title, user_id, etc.)
        but has an empty conversation_history.
        """
        # Directly call the logic from the _start_conversation node
        # This avoids running the full graph just for the first message
        try:
            start_result: Dict[str, Any] = self._start_conversation(initial_state)
            # Merge the result (history, mode) back into the initial state
            return {**initial_state, **start_result}  # type: ignore
        except Exception as e:
            # Log error, return state with a fallback message
            logger.error(f"Error during start_chat: {e}", exc_info=True)
            fallback_message: Dict[str, str] = {
                "role": "assistant",
                "content": "Welcome! Ready to start the lesson?",
            }
            # Ensure the returned state matches LessonState structure
            return {
                **initial_state,
                "conversation_history": [fallback_message],
                "current_interaction_mode": "chatting",
            }  # type: ignore
