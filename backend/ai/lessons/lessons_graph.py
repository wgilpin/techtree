"""Langgraph code for the lessons AI"""

# pylint: disable=broad-exception-caught,singleton-comparison

import os
import re
import time
import random
import json
from typing import Dict, List, TypedDict, Optional
from datetime import datetime

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import StateGraph

# from tinydb import TinyDB, Query

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(os.environ["GEMINI_MODEL"])

# Import the shared database service instance
from backend.dependencies import db_service as db  # Import and alias as 'db'

# Direct instantiation removed


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


# --- Define State ---
class LessonState(TypedDict):
    """Stae for the lessons LLM"""

    topic: str
    knowledge_level: str
    syllabus: Optional[Dict]
    lesson_title: Optional[str]
    module_title: Optional[str]
    generated_content: Optional[Dict]
    user_responses: List[Dict]
    user_performance: Optional[Dict]
    user_id: Optional[str]
    lesson_uid: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    # New fields for conversational flow
    conversation_history: List[
        Dict
    ]  # Stores {'role': 'user'/'assistant', 'content': '...'}
    current_interaction_mode: str  # e.g., 'chatting', 'doing_exercise', 'taking_quiz'
    current_exercise_index: Optional[int]
    current_quiz_question_index: Optional[int]


class LessonAI:
    """Encapsulates the Tech Tree lesson langgraph app."""

    def __init__(self):
        """Initialize the LessonAI."""
        self.state: Optional[LessonState] = None
        # Compile the chat turn workflow
        self.chat_workflow = self._create_chat_workflow()
        self.chat_graph = self.chat_workflow.compile()
        # Note: Initialization workflow might be separate or handled differently

    # --- Placeholder Methods for New Nodes ---
    def _start_conversation(self, state: LessonState) -> Dict:
        """Generates the initial AI welcome message."""
        from backend.logger import logger  # Ensure logger is available

        lesson_title = state.get("lesson_title", "this lesson")
        user_id = state.get("user_id", "unknown_user")
        history = state.get("conversation_history", [])

        logger.debug(
            f"Starting conversation for user {user_id}, lesson '{lesson_title}'"
        )

        # Check if history is already present (shouldn't be if this is truly the start)
        if history:
            logger.warning(
                f"_start_conversation called but history is not empty for user {user_id}. Returning current state."
            )
            return {}  # Return no changes if history exists

        # Construct the initial message
        welcome_content = (
            f"Welcome to the lesson on **'{lesson_title}'**! 👋\n\n"
            "I'm here to help you learn. You can:\n"
            "- Ask me questions about the introduction or topic.\n"
            "- Request an 'exercise' to practice.\n"
            "- Ask to take the 'quiz' when you feel ready.\n\n"
            "What would you like to do first?"
        )

        initial_message = {"role": "assistant", "content": welcome_content}

        return {
            "conversation_history": [
                initial_message
            ],  # Start history with this message
            "current_interaction_mode": "chatting",
        }

    def _process_user_message(self, state: LessonState) -> Dict:
        """Adds the latest user message to the history."""
        print("Placeholder: _process_user_message")
        # This node mainly updates history; the message content is assumed to be passed in the input
        # The actual message content needs to be injected into the state when invoking the graph
        # For now, just return the state as is, assuming history is updated externally before invocation
        return {}  # No state change within this node itself for now

    def _route_message_logic(self, state: LessonState) -> str:
        """Determines the next node based on interaction mode and user message intent."""
        mode = state.get("current_interaction_mode", "chatting")
        history = state.get("conversation_history", [])
        last_message = history[-1] if history else {}
        user_id = state.get("user_id", "unknown_user")  # For logging
        # Import logger if not already imported at top level
        from backend.logger import logger

        logger.debug(
            f"Routing message for user {user_id}. Mode: {mode}. Last message: '{last_message.get('content', '')[:50]}...'"
        )

        # 1. Check Mode First: If user is answering an exercise/quiz
        if mode == "doing_exercise" or mode == "taking_quiz":
            logger.debug("Mode is exercise/quiz, routing to evaluation.")
            return "evaluate_chat_answer"

        # 2. LLM Intent Classification (if mode is 'chatting')
        if mode == "chatting":
            if not last_message or last_message.get("role") != "user":
                logger.warning(
                    "Routing in 'chatting' mode without a preceding user message. Defaulting to chat response."
                )
                return "generate_chat_response"

            user_input = last_message.get("content", "")
            # Limit history for prompt efficiency
            history_for_prompt = history[-5:]  # Last 5 messages (user + assistant)

            prompt = f"""
            Analyze the user's latest message in the context of the conversation history to determine their intent.
            The user is currently in a general chat mode within an educational lesson.

            Conversation History (most recent last):
            {json.dumps(history_for_prompt, indent=2)}

            User's latest message: "{user_input}"

            Possible intents:
            - "ask_question": User is asking a question about the lesson material or seeking clarification.
            - "request_exercise": User explicitly wants to do a learning exercise or task.
            - "request_quiz": User explicitly wants to start or take the lesson quiz/assessment.
            - "other_chat": User is making a general comment, greeting, or statement not fitting other categories.

            Based *only* on the user's latest message and the immediate context, what is the most likely intent?
            Respond with ONLY a JSON object containing the key "intent" and one of the possible intent values listed above.
            Example: {{"intent": "ask_question"}}
            """

            try:
                response = call_with_retry(model.generate_content, prompt)
                response_text = response.text
                logger.debug(f"Intent classification response: {response_text}")

                # Extract JSON
                json_match = re.search(r"\{.*?\}", response_text, re.DOTALL)
                if json_match:
                    intent_json = json.loads(json_match.group(0))
                    intent = intent_json.get("intent")
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
                    logger.warning(
                        "Could not parse JSON from intent classification response. Defaulting to chat response."
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

    def _generate_chat_response(self, state: LessonState) -> Dict:
        """Generates a conversational response using the AI based on history and context."""
        from backend.logger import logger  # Ensure logger is available

        history = state.get("conversation_history", [])
        user_id = state.get("user_id", "unknown_user")
        lesson_title = state.get("lesson_title", "this lesson")
        # Get the full exposition content
        exposition = state.get("generated_content", {}).get(
            "exposition_content", "No exposition available."
        )

        logger.debug(
            f"Generating chat response for user {user_id} in lesson '{lesson_title}'"
        )

        if not history or history[-1].get("role") != "user":
            logger.warning(
                "generate_chat_response called without a preceding user message."
            )
            ai_response_content = (
                "Is there something specific I can help you with regarding the lesson?"
            )
        else:
            # Limit history for prompt efficiency
            history_for_prompt = history[-10:]  # Last 10 messages

            prompt = f"""
            You are a helpful and encouraging tutor explaining '{lesson_title}'.
            Your goal is to help the user understand the material based on the provided context and conversation history.
            Keep your responses concise and focused on the lesson topic.

            **Instructions:**
            1. Prioritize answering the user's LAST message based on the RECENT conversation history.
            2. Use the full 'Lesson Exposition Context' below primarily as a factual reference if the user asks specific questions about the material covered there. Do not simply repeat parts of the exposition unless directly relevant to the user's query.
            3. If the user makes a general comment, respond conversationally.
            4. Do not suggest exercises or quizzes unless explicitly asked in the user's last message.

            **Lesson Exposition Context:**
            ---
            {exposition}
            ---

            **Recent Conversation History (most recent last):**
            {json.dumps(history_for_prompt, indent=2)}

            Based on the history and context, generate an appropriate and helpful response to the user's last message.
            """

            try:
                response = call_with_retry(model.generate_content, prompt)
                ai_response_content = response.text
                logger.debug(f"Generated chat response: {ai_response_content[:100]}...")
            except Exception as e:
                logger.error(f"Error during chat response LLM call: {e}", exc_info=True)
                ai_response_content = "Sorry, I encountered an error trying to generate a response. Please try again."

        # Format the response and update history
        ai_message = {"role": "assistant", "content": ai_response_content}
        updated_history = history + [ai_message]

        return {"conversation_history": updated_history}

    def _present_exercise(self, state: LessonState) -> Dict:
        """Presents the next exercise to the user via chat and updates state."""
        from backend.logger import logger  # Ensure logger is available

        history = state.get("conversation_history", [])
        user_id = state.get("user_id", "unknown_user")
        generated_content = state.get("generated_content", {})
        exercises = generated_content.get("active_exercises", [])

        # Get current index and increment
        current_index = state.get("current_exercise_index", -1)
        next_index = current_index + 1

        logger.debug(
            f"Presenting exercise for user {user_id}. Current index: {current_index}, attempting next: {next_index}"
        )

        if 0 <= next_index < len(exercises):
            exercise = exercises[next_index]
            exercise_type = exercise.get("type", "open_ended")
            question_text = exercise.get("question") or exercise.get(
                "instructions", "No instructions provided."
            )

            # Format the message content
            message_parts = [
                f"Alright, let's try exercise {next_index + 1}!",
                f"**Type:** {exercise_type.replace('_', ' ').capitalize()}",
                f"**Instructions:**\n{question_text}",
            ]

            # Add items for ordering exercises
            if exercise_type == "ordering" and exercise.get("items"):
                items_list = "\n".join([f"- {item}" for item in exercise["items"]])
                message_parts.append(f"\n**Items to order:**\n{items_list}")

            message_parts.append("\nPlease provide your answer.")
            ai_response_content = "\n\n".join(message_parts)

            ai_message = {"role": "assistant", "content": ai_response_content}
            updated_history = history + [ai_message]

            logger.info(f"Presented exercise {next_index} to user {user_id}")

            return {
                "conversation_history": updated_history,
                "current_interaction_mode": "doing_exercise",
                "current_exercise_index": next_index,  # Update index
            }
        else:
            # No more exercises
            logger.info(f"No more exercises available for user {user_id}")
            ai_response_content = "Great job, you've completed all the exercises for this lesson! What would you like to do next? (e.g., ask questions, take the quiz)"
            ai_message = {"role": "assistant", "content": ai_response_content}
            updated_history = history + [ai_message]

            return {
                "conversation_history": updated_history,
                "current_interaction_mode": "chatting",  # Reset mode
                # Keep current_exercise_index as is, indicating the last one completed
            }

    def _present_quiz_question(self, state: LessonState) -> Dict:
        """Presents the next quiz question to the user via chat and updates state."""
        from backend.logger import logger  # Ensure logger is available

        history = state.get("conversation_history", [])
        user_id = state.get("user_id", "unknown_user")
        generated_content = state.get("generated_content", {})
        questions = generated_content.get("knowledge_assessment", [])

        # Get current index and increment
        current_index = state.get("current_quiz_question_index", -1)
        next_index = current_index + 1

        logger.debug(
            f"Presenting quiz question for user {user_id}. Current index: {current_index}, attempting next: {next_index}"
        )

        if 0 <= next_index < len(questions):
            question = questions[next_index]
            question_type = question.get("type", "unknown")
            question_text = question.get("question", "No question text provided.")

            # Format options based on type
            options_lines = []
            if question_type == "multiple_choice" and question.get("options"):
                options = question["options"]
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
            # Add other types like 'confidence_check' if needed
            # else: # Default for open-ended or other types
            #    options_lines.append("Please provide your answer.")

            options_text = "\n".join(options_lines)

            # Format the message content
            message_parts = [
                f"Okay, here's quiz question {next_index + 1}:",
                f"{question_text}",
            ]
            if options_text:
                message_parts.append(f"\n{options_text}")

            ai_response_content = "\n\n".join(message_parts)

            ai_message = {"role": "assistant", "content": ai_response_content}
            updated_history = history + [ai_message]

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
            ai_response_content = "You've completed the quiz for this lesson! What would you like to do now?"
            ai_message = {"role": "assistant", "content": ai_response_content}
            updated_history = history + [ai_message]

            return {
                "conversation_history": updated_history,
                "current_interaction_mode": "chatting",  # Reset mode
                # Keep current_quiz_question_index as is
            }

    def _evaluate_chat_answer(self, state: LessonState) -> Dict:
        """Evaluates a user's answer provided in the chat using an LLM."""
        from backend.logger import logger  # Ensure logger is available

        mode = state.get("current_interaction_mode")
        history = state.get("conversation_history", [])
        user_id = state.get("user_id", "unknown_user")
        generated_content = state.get("generated_content", {})
        user_responses = state.get("user_responses", [])

        if not history or history[-1].get("role") != "user":
            logger.warning(
                f"evaluate_chat_answer called without a preceding user message for user {user_id}."
            )
            # Cannot evaluate without an answer, return to chatting mode with a message
            ai_message = {
                "role": "assistant",
                "content": "It looks like you haven't provided an answer yet. Please provide your answer to the question.",
            }
            return {
                "conversation_history": history + [ai_message],
                "current_interaction_mode": mode,  # Stay in the current mode
                "user_responses": user_responses,
            }

        user_answer = history[-1].get("content", "")
        question = None
        question_type = None
        question_index = -1
        question_id_str = "unknown"  # For logging/record

        # Identify the question being answered
        if mode == "doing_exercise":
            question_type = "exercise"
            question_index = state.get("current_exercise_index", -1)
            exercises = generated_content.get("active_exercises", [])
            if 0 <= question_index < len(exercises):
                question = exercises[question_index]
                question_id_str = question.get("id", f"ex_{question_index}")
        elif mode == "taking_quiz":
            question_type = "assessment"
            question_index = state.get("current_quiz_question_index", -1)
            questions = generated_content.get("knowledge_assessment", [])
            if 0 <= question_index < len(questions):
                question = questions[question_index]
                question_id_str = question.get("id", f"q_{question_index}")

        if question is None:
            logger.error(
                f"Could not find question for evaluation. Mode: {mode}, Index: {question_index}, User: {user_id}"
            )
            ai_message = {
                "role": "assistant",
                "content": "Sorry, I lost track of which question you were answering. Could you clarify or ask to try again?",
            }
            return {
                "conversation_history": history + [ai_message],
                "current_interaction_mode": "chatting",  # Reset to chat
                "user_responses": user_responses,
            }

        # Prepare prompt for LLM evaluation
        question_text = question.get("question") or question.get("instructions", "N/A")
        expected_solution = (
            question.get("answer")
            or question.get("expected_solution")
            or question.get("correct_answer")
            or question.get("explanation")  # Use explanation as fallback context
            or "N/A"
        )

        # --- Refined Prompt Section ---
        prompt_context = f"""
        Question/Instructions:
        {question_text}
        """

        # Add options context for specific types
        q_type = question.get("type")
        if q_type == "multiple_choice" and question.get("options"):
            options = question["options"]
            options_str = ""
            if isinstance(options, dict):
                options_str = "\n".join(
                    [f"- {key}) {value}" for key, value in options.items()]
                )
            elif isinstance(options, list):
                options_str = "\n".join([f"- {opt}" for opt in options])
            prompt_context += f"\n\nOptions:\n{options_str}"
            prompt_context += "\nThe user should respond with the key/letter or the full text of the correct option."
        elif q_type == "true_false":
            prompt_context += "\n\nOptions:\n- True\n- False"
            prompt_context += "\nThe user should respond with 'True' or 'False'."
        elif q_type == "ordering" and question.get("items"):
            items_list = "\n".join([f"- {item}" for item in question["items"]])
            prompt_context += f"\n\nItems to order:\n{items_list}"
            prompt_context += (
                "\nThe user should respond with the items in the correct order."
            )

        prompt_context += f"""

        Expected Answer/Solution Context (if available):
        {expected_solution}

        User's Answer:
        {user_answer}
        """

        prompt = f"""
        You are evaluating a user's answer to the following {question_type}.

        {prompt_context}

        Please evaluate the user's answer based on the question and expected solution context.
        Provide your evaluation as a JSON object with the following structure:
        1. "score": A score between 0.0 (completely incorrect) and 1.0 (completely correct). Grade appropriately based on correctness and completeness. For multiple choice/true-false, usually 1.0 or 0.0. For ordering, 1.0 only if exact order matches.
        2. "is_correct": A boolean (true if score >= 0.8, false otherwise).
        3. "feedback": Constructive feedback for the user explaining the evaluation. If incorrect, briefly explain why and hint towards the correct answer without giving it away directly if possible.
        4. "explanation": (Optional) A more detailed explanation of the correct answer, especially useful if the user was incorrect. Keep it concise.

        Example JSON format:
        {{
          "score": 1.0,
          "is_correct": true,
          "feedback": "Correct! 'B' is the right answer.",
          "explanation": "Option B is correct because..."
        }}

        Respond ONLY with the JSON object.
        """
        # --- End Refined Prompt Section ---

        evaluation_result = None
        try:
            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text
            logger.debug(
                f"Raw evaluation response for q_id {question_id_str}: {response_text}"
            )

            # Extract JSON
            json_match = re.search(r"\{.*?\}", response_text, re.DOTALL)
            if json_match:
                evaluation_result = json.loads(json_match.group(0))
                # Validate basic structure
                if not all(
                    k in evaluation_result for k in ["score", "is_correct", "feedback"]
                ):
                    raise ValueError("Evaluation JSON missing required keys.")
                evaluation_result.setdefault(
                    "explanation", ""
                )  # Ensure explanation key exists
                logger.info(
                    f"Parsed evaluation for q_id {question_id_str}: Score={evaluation_result['score']}, Correct={evaluation_result['is_correct']}"
                )
            else:
                raise ValueError("Could not parse JSON from evaluation response.")

        except Exception as e:
            logger.error(
                f"Error during answer evaluation LLM call or parsing for q_id {question_id_str}: {e}",
                exc_info=True,
            )
            # Fallback evaluation
            evaluation_result = {
                "score": 0.0,
                "is_correct": False,
                "feedback": "Sorry, I encountered an error while evaluating your answer. Let's move on for now.",
                "explanation": "",
            }

        # Create assistant feedback message
        feedback_text = evaluation_result["feedback"]
        if not evaluation_result["is_correct"] and evaluation_result.get("explanation"):
            # Optionally add explanation to feedback if incorrect
            feedback_text += f"\n\n*Explanation:* {evaluation_result['explanation']}"
        ai_feedback_message = {"role": "assistant", "content": feedback_text}
        updated_history = history + [ai_feedback_message]

        # Record the evaluation attempt
        user_response_record = {
            "question_id": question_id_str,
            "question_type": question_type,
            "response": user_answer,
            "evaluation": evaluation_result,  # Store the full evaluation dict
            "timestamp": datetime.now().isoformat(),
        }
        updated_user_responses = user_responses + [user_response_record]

        # Decide next step and potentially add follow-up message
        next_mode = "chatting"  # Default back to chatting
        if evaluation_result["is_correct"]:
            follow_up_text = None
            if mode == "doing_exercise":
                follow_up_text = "That's correct! Would you like the next exercise, or something else?"
            elif mode == "taking_quiz":
                follow_up_text = "Correct! Ready for the next quiz question?"

            if follow_up_text:
                ai_followup_message = {"role": "assistant", "content": follow_up_text}
                updated_history.append(ai_followup_message)
            # Stay in chatting mode after correct answer + follow-up question
        else:
            # If incorrect, just provide feedback and return to chatting mode
            pass  # Already added feedback message

        return {
            "conversation_history": updated_history,
            "current_interaction_mode": next_mode,
            "user_responses": updated_user_responses,
        }

    def _update_progress(self, state: LessonState) -> Dict:
        """Saves progress based on the latest interaction."""
        print("Placeholder: _update_progress")
        # TODO: Adapt existing _save_progress logic if needed, or call DB service directly
        # This might be better handled outside the graph after each turn completes
        return {}  # No state change within graph for now

    # --- Logic from old graph nodes (potentially called by service layer now) ---
    # Make sure imports like db are handled if these are called directly or refactored
    def _generate_lesson_content(self, state: LessonState) -> Dict:
        """Generate lesson content based on the syllabus, module title, and lesson title."""
        # Access values from self.state instead of state parameter
        syllabus = state["syllabus"]
        lesson_title = state.get("lesson_title")
        module_title = state.get("module_title")
        knowledge_level = state["knowledge_level"]
        user_id = state.get("user_id")
        from backend.logger import logger  # Ensure logger is available

        # Remove local import and instantiation; use module-level 'db' alias

        # Debug print
        logger.debug(
            f"_generate_lesson_content: module_title={module_title}, lesson_title={lesson_title}"
        )

        # Check if module_title and lesson_title are provided
        if not module_title or not lesson_title:
            raise ValueError("Module title and lesson title are required")

        # Find the lesson in the syllabus
        lesson_found = False
        module_index = -1
        lesson_index = -1
        if syllabus and syllabus.get("content", {}).get("modules"):
            for i, module in enumerate(syllabus["content"]["modules"]):
                if module["title"] == module_title:
                    module_index = i
                    for j, lesson in enumerate(module.get("lessons", [])):
                        if lesson["title"] == lesson_title:
                            lesson_index = j
                            lesson_found = True
                            break
                if lesson_found:
                    break
        else:
            raise ValueError("Invalid syllabus structure provided.")

        if not lesson_found:
            raise ValueError(
                f"Lesson '{lesson_title}' not found in module '{module_title}' within the provided syllabus."
            )

        # Check if we already have generated content for this lesson in DB
        # This requires syllabus_id, module_index, lesson_index
        syllabus_id = syllabus.get("syllabus_id")
        if not syllabus_id:
            raise ValueError("Syllabus ID missing from syllabus data.")

        # Use get_lesson_content to check for existing content based on indices
        existing_content_data = db.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )

        if existing_content_data and "content" in existing_content_data:
            logger.info(
                f"Found existing content in DB for {syllabus_id}/{module_index}/{lesson_index}"
            )
            # Need to return in the expected format if called by graph (though it won't be)
            # If called by service, service layer handles the return
            return {"generated_content": existing_content_data["content"]}

        logger.info(
            f"Generating new content for {syllabus_id}/{module_index}/{lesson_index}"
        )
        # Read the system prompt
        try:
            with open("backend/system_prompt.txt", "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            logger.error("system_prompt.txt not found!")
            system_prompt = "You are a helpful tutor."  # Fallback prompt

        # Get user's previous performance if available (Simplified - needs proper implementation if used)
        previous_performance = {}
        # if user_id:
        #     # Query user_progress table... (complex logic omitted for now)

        # Construct the prompt for Gemini
        prompt = f"""
        {system_prompt}

        ## Input Parameters
        - topic: {syllabus['topic']}
        - syllabus: {json.dumps(syllabus, indent=2)}
        - lesson_name: {lesson_title}
        - user_level: {knowledge_level}
        - previous_performance: {json.dumps(previous_performance, indent=2)}
        - time_constraint: 5 minutes

        Please generate the lesson content following the output format specified in the system prompt.
        """

        try:
            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text
        except Exception as e:
            logger.error(
                f"LLM call failed during content generation: {e}", exc_info=True
            )
            raise RuntimeError("LLM content generation failed") from e

        # Extract JSON from response
        json_patterns = [
            r"```(?:json)?\s*({.*?})```",
            r'({[\s\S]*"exposition_content"[\s\S]*"active_exercises"[\s\S]*"knowledge_assessment"[\s\S]*"metadata"[\s\S]*})',
            r"({[\s\S]*})",
        ]

        generated_content = None
        for pattern in json_patterns:
            json_match = re.search(pattern, response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)  # Be careful with this
                try:
                    content_parsed = json.loads(json_str)
                    # Basic validation
                    if all(
                        k in content_parsed
                        for k in [
                            "exposition_content",
                            "active_exercises",
                            "knowledge_assessment",
                            "metadata",
                        ]
                    ):
                        generated_content = content_parsed
                        logger.info("Successfully parsed generated lesson content.")
                        break
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed for pattern {pattern}: {e}")

        if generated_content is None:
            logger.error(
                f"Failed to parse valid JSON content from LLM response: {response_text[:500]}..."
            )
            # TODO: Implement better fallback? Raise error?
            # For now, raise error as content generation failed
            raise RuntimeError("Failed to parse valid content structure from LLM.")

        # NOTE: Saving to DB is now handled by the service layer after calling this logic.
        # This function should just return the generated content dict.
        return {"generated_content": generated_content}

    # --- Existing Methods (Keep for Initialization/Reference) ---
    # _initialize, _retrieve_syllabus, # _generate_lesson_content (uncommenting below), _evaluate_response,
    # _provide_feedback, _save_progress, _end
    # Need to ensure these don't conflict with new node names if reused

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
                "evaluate_chat_answer": "evaluate_chat_answer",  # Route directly if mode requires evaluation
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
        updated_history = current_state.get("conversation_history", []) + [
            {"role": "user", "content": user_message}
        ]
        input_state = {**current_state, "conversation_history": updated_history}

        # Invoke the chat graph
        output_state = self.chat_graph.invoke(input_state)

        # Merge output state changes back (langgraph does this implicitly, but good practice)
        final_state = {**input_state, **output_state}
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
            # Ensure logger is available if needed inside _start_conversation
            # from backend.logger import logger
            start_result = self._start_conversation(initial_state)
            # Merge the result (history, mode) back into the initial state
            return {**initial_state, **start_result}
        except Exception as e:
            # Log error, return state with a fallback message?
            from backend.logger import logger

            logger.error(f"Error during start_chat: {e}", exc_info=True)
            fallback_message = {
                "role": "assistant",
                "content": "Welcome! Ready to start the lesson?",
            }
            return {
                **initial_state,
                "conversation_history": [fallback_message],
                "current_interaction_mode": "chatting",
            }

    # --- Keep existing methods like initialize, get_lesson_content etc. ---
    # --- but they need to be adapted to work with the new state/flow ---
    # --- For example, initialize might run a separate init graph ---
    # --- get_lesson_content might just retrieve from state if already generated ---

    def _initialize(
        self,
        state: Optional[LessonState] = None,
        topic: str = "",
        knowledge_level: str = "beginner",
        user_id: Optional[str] = None,
    ) -> Dict:
        """Initialize the state with the topic, user knowledge level, and user email."""
        # Debug print to see what's being passed
        print(
            f"_initialize called with state: {state}, topic: {topic},"
            f"knowledge_level: {knowledge_level}, user_id: {user_id}"
        )

        # Check if topic is in state (which might be the case when called through the graph)
        if state and isinstance(state, dict) and "topic" in state and not topic:
            topic = state["topic"]
            knowledge_level = state.get("knowledge_level", knowledge_level)
            user_id = state.get("user_id", user_id)
            print(f"Using topic from state: {topic}")

        if not topic:
            raise ValueError("Topic is required")

        # Validate knowledge level
        valid_levels = ["beginner", "early learner", "good knowledge", "advanced"]
        if knowledge_level not in valid_levels:
            knowledge_level = "beginner"  # Default to beginner if invalid

        # Preserve lesson_title and module_title from state if they exist
        lesson_title = None
        module_title = None
        if state and isinstance(state, dict):
            lesson_title = state.get("lesson_title")
            module_title = state.get("module_title")

        return {
            "topic": topic,
            "knowledge_level": knowledge_level,
            "syllabus": None,
            "lesson_title": lesson_title,
            "module_title": module_title,
            "generated_content": None,
            "user_responses": [],
            "user_performance": {},
            "user_id": user_id,
        }

    def _retrieve_syllabus(self, state: LessonState) -> Dict:
        """Retrieve the syllabus for the specified topic and knowledge level."""
        topic = state["topic"]
        knowledge_level = state["knowledge_level"]
        user_id = state.get("user_id")

        # Preserve module_title and lesson_title if they're in the inputs
        module_title = state.get("module_title")
        lesson_title = state.get("lesson_title")

        # Debug print
        print(
            f"_retrieve_syllabus: module_title={module_title}, lesson_title={lesson_title}"
        )

        # Search for match on topic and knowledge level using SQLite
        if user_id:
            # First try to find a user-specific version
            user_specific = db.get_syllabus(topic, knowledge_level, user_id)
            if user_specific:
                return {
                    **state,  # Merge with existing state
                    "syllabus": user_specific,
                    "module_title": module_title,
                    "lesson_title": lesson_title,
                }

        # If no user-specific version or no user_id provided, look for master version
        master_version = db.get_syllabus(topic, knowledge_level)

        if master_version:
            return {
                **state,  # Merge with existing state
                "syllabus": master_version,
                "module_title": module_title,
                "lesson_title": lesson_title,
            }

        # If no syllabus found, return an error
        raise ValueError(
            f"No syllabus found for topic '{topic}' at level '{knowledge_level}'"
        )

    def _generate_lesson_content(self, state: LessonState) -> Dict:
        """Generate lesson content based on the syllabus, module title, and lesson title."""
        # Access values from self.state instead of state parameter
        syllabus = state["syllabus"]
        lesson_title = state.get("lesson_title")
        module_title = state.get("module_title")
        knowledge_level = state["knowledge_level"]
        user_id = state.get("user_id")

        # Debug print
        print(
            f"_generate_lesson_content: module_title={module_title}, lesson_title={lesson_title}"
        )

        # Check if module_title and lesson_title are provided
        if not module_title or not lesson_title:
            raise ValueError("Module title and lesson title are required")

        # Find module and lesson indices
        module_index = -1
        lesson_index = -1
        for i, module in enumerate(syllabus["content"]["modules"]):
            if module["title"] == module_title:
                module_index = i
                for j, lesson in enumerate(module["lessons"]):
                    if lesson["title"] == lesson_title:
                        lesson_index = j
                        break
            if lesson_index != -1:
                break

        if module_index == -1 or lesson_index == -1:
            # This should ideally not happen if validation occurred earlier, but check just in case
            raise ValueError(
                f"Lesson '{lesson_title}' not found in module '{module_title}' during index lookup."
            )

        # Check if we already have generated content for this lesson using indices
        syllabus_id = syllabus["syllabus_id"]
        existing_content_data = db.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )

        if existing_content_data:
            print(
                f"Found existing content for syllabus {syllabus_id}, module {module_index}, lesson {lesson_index}"
            )
            # Assuming get_lesson_content returns the content dict directly or None
            return {"generated_content": existing_content_data}
        else:
            print(
                f"No existing content found for syllabus {syllabus_id}, module {module_index}, lesson {lesson_index}. Generating..."
            )

            # Read the system prompt
            with open("backend/system_prompt.txt", "r", encoding="utf-8") as f:
                system_prompt = f.read()

            # Get user's previous performance if available
            previous_performance = {}
            if user_id:
                # Query user_progress table for the user's performance
                progress_query = """
                    SELECT * FROM user_progress
                    WHERE user_id = ?
                """
                progress_params = (user_id,)
                user_progress = db.execute_query(progress_query, progress_params)

                if user_progress:
                    # Convert SQLite row to dict and get performance data
                    progress_dict = dict(user_progress[0])
                    # Performance might be stored as JSON
                    if "performance" in progress_dict:
                        try:
                            previous_performance = json.loads(
                                progress_dict["performance"]
                            )
                        except json.JSONDecodeError:
                            previous_performance = {}

            # Construct the prompt for Gemini
            prompt = f"""
            {system_prompt}

            ## Input Parameters
            - topic: {syllabus['topic']}
            - syllabus: {json.dumps(syllabus, indent=2)}
            - lesson_name: {lesson_title}
            - user_level: {knowledge_level}
            - previous_performance: {json.dumps(previous_performance, indent=2)}
            - time_constraint: 5 minutes

            Please generate the lesson content following the output format specified in the system prompt.
            """

            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text

            # Extract JSON from response
            json_patterns = [
                r"```(?:json)?\s*({.*?})```",  # Code blocks
                r'({[\s\S]*"exposition_content"[\s\S]*"thought_questions"[\s\S]*"active_exercises"[\s\S]*"knowledge_assessment"[\s\S]*"metadata"[\s\S]*})',  # Full structure
                r"({[\s\S]*})",  # Any JSON object
            ]

            generated_content = None
            json_str = None
            for pattern in json_patterns:
                json_match = re.search(pattern, response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    # Clean up the JSON string
                    json_str = re.sub(r"\\n", "", json_str)
                    json_str = re.sub(r"\\", "", json_str)
                    # --- DEBUG LOG ---
                    print(
                        f"DEBUG_JSON: Attempting to parse JSON string:\n{json_str}\n--- END JSON ---"
                    )
                    # --- END DEBUG LOG ---
                    try:
                        content_candidate = json.loads(json_str)
                        # Validate the structure
                        if all(
                            key in content_candidate
                            for key in [
                                "exposition_content",
                                "thought_questions",
                                "active_exercises",
                                "knowledge_assessment",
                                "metadata",
                            ]
                        ):
                            generated_content = content_candidate
                            break  # Successfully parsed and validated
                    except Exception as e:
                        print(f"Failed to parse JSON with pattern '{pattern}': {e}")
                        continue  # Try next pattern

            # If JSON parsing failed or structure was invalid after trying all patterns
            if generated_content is None:
                print(
                    f"Failed to parse valid JSON from response: {response_text[:200]}..."
                )
                generated_content = {
                    "exposition_content": f"# {lesson_title}\n\nThis is a placeholder for the lesson content.",
                    "thought_questions": [
                        "What do you think about this topic?",
                        "How might this apply to real-world scenarios?",
                    ],
                    "active_exercises": [
                        {
                            "id": "ex1",
                            "type": "scenario",
                            "question": "Consider the following scenario...",
                            "expected_solution": "The correct approach would be...",
                            "hints": ["Think about...", "Consider..."],
                            "explanation": "This works because...",
                            "misconceptions": {
                                "common_error_1": "This is incorrect because...",
                                "common_error_2": "This approach fails because...",
                            },
                        }
                    ],
                    "knowledge_assessment": [
                        {
                            "id": "q1",
                            "type": "multiple_choice",
                            "question": "Which of the following best describes...?",
                            "options": ["Option A", "Option B", "Option C", "Option D"],
                            "correct_answer": "Option B",
                            "explanation": "Option B is correct because...",
                        }
                    ],
                    "metadata": {
                        "tags": ["placeholder"],
                        "difficulty": 3,
                        "related_topics": ["Related Topic 1", "Related Topic 2"],
                        "prerequisites": ["Prerequisite 1"],
                    },
                }

            # Save the newly generated (or placeholder) content
            print(
                f"Saving content for syllabus {syllabus_id}, module {module_index}, lesson {lesson_index}"
            )
            # --- DEBUG LOG ---
            print(
                f"DEBUG_SAVE: Content being saved: {json.dumps(generated_content, indent=2)}"
            )
            # --- END DEBUG LOG ---
            db.save_lesson_content(
                syllabus_id, module_index, lesson_index, generated_content
            )
            return {"generated_content": generated_content}

    def _evaluate_response(
        self, state: LessonState, response: str, question_id: str
    ) -> Dict:
        """Evaluate a user's response to a question."""
        generated_content = state["generated_content"]

        # Find the question in the content
        question = None
        question_type = None

        # Check active exercises
        for exercise in generated_content["active_exercises"]:
            if exercise["id"] == question_id:
                question = exercise
                question_type = "exercise"
                break

        # Check knowledge assessment
        if not question:
            for assessment in generated_content["knowledge_assessment"]:
                if assessment["id"] == question_id:
                    question = assessment
                    question_type = "assessment"
                    break

        if not question:
            raise ValueError(f"Question with ID '{question_id}' not found")

        # Construct the prompt for Gemini
        prompt = f"""
        You are evaluating a user's response to a {question_type}.

        Question: {question['question']}

        Expected solution or correct answer: {question.get('expected_solution')
        or question.get('correct_answer')}

        User's response: {response}

        Please evaluate the user's response and provide:
        1. A score between 0 and 1, where 1 is completely correct and 0 is completely incorrect
        2. Feedback explaining what was correct and what could be improved
        3. Whether the user has any misconceptions that should be addressed

        Format your response as a JSON object with the following structure:
        {
          "score": 0.75,
          "feedback": "Your feedback here...",
          "misconceptions": ["Misconception 1", "Misconception 2"]
        }
        """

        evaluation_response = call_with_retry(model.generate_content, prompt)
        evaluation_text = evaluation_response.text

        # Extract JSON from response
        json_patterns = [
            r"```(?:json)?\s*({.*?})```",
            r'({[\s\S]*"score"[\s\S]*"feedback"[\s\S]*"misconceptions"[\s\S]*})',
            r"({[\s\S]*})",
        ]

        for pattern in json_patterns:
            json_match = re.search(pattern, evaluation_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)
                try:
                    evaluation = json.loads(json_str)
                    if all(
                        key in evaluation
                        for key in ["score", "feedback", "misconceptions"]
                    ):
                        # Add the response and evaluation to the user_responses list
                        user_response = {
                            "question_id": question_id,
                            "question_type": question_type,
                            "response": response,
                            "evaluation": evaluation,
                            "timestamp": datetime.now().isoformat(),
                        }

                        return {
                            "user_responses": state["user_responses"] + [user_response],
                        }
                except Exception:
                    pass

        # If all patterns fail, create a basic evaluation
        basic_evaluation = {
            "score": 0.5,
            "feedback": "I couldn't properly evaluate your response. Please try again.",
            "misconceptions": [],
        }

        user_response = {
            "question_id": question_id,
            "question_type": question_type,
            "response": response,
            "evaluation": basic_evaluation,
            "timestamp": datetime.now().isoformat(),
        }

        return {
            "user_responses": state["user_responses"] + [user_response],
        }

    def _provide_feedback(self, state: LessonState) -> Dict:
        """Provide feedback based on the user's responses."""
        user_responses = state["user_responses"]

        if not user_responses:
            return {}

        # Get the most recent response
        latest_response = user_responses[-1]

        # Return the evaluation as feedback
        return {
            "feedback": latest_response["evaluation"]["feedback"],
            "misconceptions": latest_response["evaluation"]["misconceptions"],
        }

    def _save_progress(self, state: LessonState) -> Dict:
        """Save the user's progress to the database."""
        user_id = state.get("user_id")

        if not user_id:
            return {}

        syllabus = state["syllabus"]
        lesson_title = state["lesson_title"]
        module_title = state["module_title"]
        user_responses = state["user_responses"]

        # Calculate the overall score for this lesson
        assessment_scores = []
        for response in user_responses:
            if response["question_type"] == "assessment":
                assessment_scores.append(response["evaluation"]["score"])

        lesson_score = (
            sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0
        )

        # Get existing user progress from SQLite for the syllabus
        syllabus_id = syllabus["syllabus_id"]
        now = datetime.now().isoformat()

        # Find module and lesson indices
        module_index = -1
        lesson_index = -1
        for i, module in enumerate(syllabus["content"]["modules"]):
            if module["title"] == module_title:
                module_index = i
                for j, lesson in enumerate(module["lessons"]):
                    if lesson["title"] == lesson_title:
                        lesson_index = j
                        break
            if lesson_index != -1:
                break

        if module_index == -1 or lesson_index == -1:
            raise ValueError(
                f"Lesson '{lesson_title}' not found in module '{module_title}'"
            )

        # Assuming if we're saving, it's completed. Could add logic for "in_progress"
        status = "completed"

        db.save_user_progress(
            user_id, syllabus_id, module_index, lesson_index, status, lesson_score
        )

        # Construct user perf data - might need adjustment depending on use.
        performance = {
            lesson_title: {
                "score": lesson_score,
                "completed_at": now,
            }
        }

        return {"user_performance": performance[lesson_title]}

    def _end(self, _: LessonState) -> Dict:
        """End the workflow."""
        return {}

    # --- Old Public Methods (Commented Out - Superseded by process_chat_turn) ---
    # def initialize(
    #     self, topic: str, knowledge_level: str, module_title: str, lesson_title: str, user_id: Optional[str] = None
    # ) -> Dict:
    #     """Initialize the LessonAI with a topic, knowledge level, and user email."""
    #     # This needs to be adapted for the new flow.
    #     # It might involve running a separate initialization graph or sequence.
    #     inputs = {
    #         "topic": topic,
    #         "knowledge_level": knowledge_level,
    #         "user_id": user_id,
    #         "module_title": module_title,
    #         "lesson_title": lesson_title,
    #         # Initialize new state fields
    #         "conversation_history": [],
    #         "current_interaction_mode": "chatting",
    #         "current_exercise_index": -1,
    #         "current_quiz_question_index": -1,
    #     }
    #     # Needs to compile and run an init graph, not the chat graph
    #     # init_graph = self._create_init_workflow().compile()
    #     # try:
    #     #     self.state = init_graph.invoke(inputs)
    #     # except ValueError as e:
    #     #     raise ValueError(
    #     #         f"Failed to initialize lesson: {e}. Ensure a syllabus exists."
    #     #     ) from e
    #     # return self.state
    #     pass # Placeholder

    # def get_lesson_content(self) -> Dict:
    #     """Get or generate content for the current lesson."""
    #     # This should likely just retrieve from self.state['generated_content']
    #     # if initialization already happened.
    #     if not self.state or not self.state.get('generated_content'):
    #          raise ValueError("LessonAI not initialized or content not generated.")
    #     # The old logic invoked the graph, which is incorrect now.
    #     # return self.state["generated_content"]
    #     pass # Placeholder

    # def evaluate_response(self, response: str, question_id: str) -> Dict:
    #     """Evaluate a user's response to a question."""
    #     # This is now handled within the chat graph via _evaluate_chat_answer
    #     # and process_chat_turn.
    #     # if not self.state:
    #     #     raise ValueError("LessonAI not initialized. Call initialize() first.")
    #     # inputs = {**self.state, "response": response, "question_id": question_id} # Pass full state?
    #     # self.state = self.chat_graph.invoke(inputs, {"current": "evaluate_chat_answer"}) # Invoke chat graph?
    #     # return self.state.get("feedback") # Assuming feedback is stored
    #     pass # Placeholder

    # def save_progress(self) -> Dict:
    #     """Save the user's progress."""
    #     # Progress saving is likely better handled by the service layer after a turn.
    #     # if not self.state:
    #     #     raise ValueError("LessonAI not initialized. Call initialize() first.")
    #     # self.state = self.chat_graph.invoke(self.state, {"current": "update_progress"}) # Invoke chat graph?
    #     # return self.state.get("user_performance")
    #     pass # Placeholder

    def get_user_progress(self, user_id: str, topic: Optional[str] = None) -> Dict:
        """Get the user's progress for a topic or all topics."""
        progress_data = db.get_user_in_progress_courses(user_id)

        if not progress_data:
            return {}

        if topic:
            # Filter for the specific topic
            filtered_progress = [
                course for course in progress_data if course["topic"] == topic
            ]
            if filtered_progress:
                # Assuming we only care about 1st match if multiple syllabi for same topic
                return filtered_progress[0]
            else:
                return {}  # No progress found for the specified topic
        else:
            # Return all progress
            return {"all_progress": progress_data}

    #     # return self.state
    #     pass # Placeholder

    # def get_lesson_content(self) -> Dict:
    #     """Get or generate content for the current lesson."""
    #     # This should likely just retrieve from self.state['generated_content']
    #     # if initialization already happened.
    #     if not self.state or not self.state.get('generated_content'):
    #          raise ValueError("LessonAI not initialized or content not generated.")
    #     # The old logic invoked the graph, which is incorrect now.
    #     # return self.state["generated_content"]
    #     pass # Placeholder

    # def evaluate_response(self, response: str, question_id: str) -> Dict:
    #     """Evaluate a user's response to a question."""
    #     # This is now handled within the chat graph via _evaluate_chat_answer
    #     # and process_chat_turn.
    #     # if not self.state:
    #     #     raise ValueError("LessonAI not initialized. Call initialize() first.")
    #     # inputs = {**self.state, "response": response, "question_id": question_id} # Pass full state?
    #     # self.state = self.chat_graph.invoke(inputs, {"current": "evaluate_chat_answer"}) # Invoke chat graph?
    #     # return self.state.get("feedback") # Assuming feedback is stored
    #     pass # Placeholder

    # def save_progress(self) -> Dict:
    #     """Save the user's progress."""
    #     # Progress saving is likely better handled by the service layer after a turn.
    #     # if not self.state:
    #     #     raise ValueError("LessonAI not initialized. Call initialize() first.")
    #     # self.state = self.chat_graph.invoke(self.state, {"current": "update_progress"}) # Invoke chat graph?
    #     # return self.state.get("user_performance")
    #     pass # Placeholder

    # Removed get_user_progress method as it seemed misplaced in LessonAI
