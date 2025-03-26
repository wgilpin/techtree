"""Lesson logic, for generation and evaluation"""

import json
import re
from typing import Any, Dict, Optional

# Import necessary components from lessons_graph
from backend.ai.lessons.lessons_graph import model, call_with_retry
from backend.ai.app import LessonAI
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService
import json  # Added import
from backend.logger import logger  # Import the configured logger


class LessonService:
    """Service for managing and generating lesson content."""

    def __init__(self, db_service=None, syllabus_service=None):
        # LessonAI is still needed for generation
        self.lesson_ai = LessonAI()
        self.db_service = db_service or SQLiteDatabaseService()
        self.syllabus_service = syllabus_service or SyllabusService(self.db_service)

    async def get_or_generate_lesson(
        self,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get existing lesson content and conversational state,
        or generate new content and initialize state.
        """
        logger.info(
            f"Getting/Generating lesson: syllabus={syllabus_id}, mod={module_index}, lesson={lesson_index}, user={user_id}"
        )
        syllabus = await self.syllabus_service.get_syllabus(syllabus_id)
        if not syllabus:
            logger.error(f"Syllabus not found: {syllabus_id}")
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        topic = syllabus.get("topic", "Unknown Topic")
        level = syllabus.get("level", "beginner")

        # --- Fetch User Progress & State ---
        lesson_state = None
        progress_entry = None
        if user_id:
            # Use the new method to get specific lesson progress
            progress_entry = self.db_service.get_lesson_progress(
                user_id, syllabus_id, module_index, lesson_index
            )

            if (
                progress_entry
                and "lesson_state" in progress_entry
                and progress_entry["lesson_state"]
            ):  # Check if state is not None
                lesson_state = progress_entry["lesson_state"]
                logger.info(f"Loaded existing lesson state for user {user_id}")
            else:
                logger.info(f"No existing progress or state found for user {user_id}")

        # --- Check for Existing Lesson Content ---
        # Use get_lesson_by_id which combines lesson details and content
        # We need the lesson_id first, which might be in progress or need lookup
        lesson_db_id = None
        if progress_entry:
            # Assuming get_lesson_progress can join to get lesson_id
            # lesson_db_id = progress_entry.get('lesson_db_id') # Hypothetical field name
            # TEMP: Need to look up lesson_id separately if not joined
            try:
                lesson_details_temp = await self.syllabus_service.get_lesson_details(
                    syllabus_id, module_index, lesson_index
                )
                lesson_db_id = lesson_details_temp.get("lesson_id")
            except ValueError:
                lesson_db_id = None

        # If not in progress, find lesson_id via module/lesson index
        if not lesson_db_id:
            try:
                lesson_details = await self.syllabus_service.get_lesson_details(
                    syllabus_id, module_index, lesson_index
                )
                lesson_db_id = lesson_details.get(
                    "lesson_id"
                )  # Actual lesson primary key
            except ValueError:
                logger.error(
                    f"Could not find lesson details for mod={module_index}, lesson={lesson_index}"
                )
                lesson_db_id = None  # Ensure it's None if lookup fails

        existing_lesson_content = None
        if lesson_db_id:
            # TODO: Ensure get_lesson_by_id returns content correctly
            lesson_data = self.db_service.get_lesson_by_id(
                lesson_db_id
            )  # This gets lesson table data, not content table
            # Need to use get_lesson_content using syllabus_id, module_index, lesson_index
            content_data = self.db_service.get_lesson_content(
                syllabus_id, module_index, lesson_index
            )
            if content_data and "content" in content_data:
                existing_lesson_content = content_data["content"]
                logger.info(
                    f"Found existing lesson content for lesson_id {lesson_db_id}"
                )

        # --- Return Existing Content & State (if found) ---
        if existing_lesson_content:
            # Ensure topic and level are in the content
            if "topic" not in existing_lesson_content:
                existing_lesson_content["topic"] = topic
            if "level" not in existing_lesson_content:
                existing_lesson_content["level"] = level

            # If state wasn't loaded from progress, create a default initial state
            if (
                lesson_state is None and user_id
            ):  # Only create default if user is logged in
                logger.warning(
                    f"Content exists but no state found for user {user_id}. Creating default state."
                )
                # TODO: Refactor state initialization logic
                # Need module title here
                try:
                    module_details_temp = (
                        await self.syllabus_service.get_module_details(
                            syllabus_id, module_index
                        )
                    )
                    module_title_temp = module_details_temp.get(
                        "title", "Unknown Module"
                    )
                except ValueError:
                    module_title_temp = "Unknown Module"

                lesson_state = {
                    "topic": topic,
                    "knowledge_level": level,
                    "syllabus_id": syllabus_id,
                    "lesson_title": existing_lesson_content.get("metadata", {}).get(
                        "title", "Unknown"
                    ),
                    "module_title": module_title_temp,
                    "generated_content": existing_lesson_content,
                    "user_id": user_id,
                    "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",  # Or use lesson_db_id?
                    "conversation_history": [],
                    "current_interaction_mode": "chatting",
                    "current_exercise_index": -1,
                    "current_quiz_question_index": -1,
                    "user_responses": [],
                    "user_performance": {},
                }
                # Optionally get initial AI message here too
                try:
                    # TODO: Implement self.lesson_ai.start_chat
                    # Placeholder: Manually add initial message
                    initial_message = {
                        "role": "assistant",
                        "content": f"Welcome to the lesson on '{lesson_state['lesson_title']}'! You can ask questions, request an exercise, or start the quiz.",
                    }
                    lesson_state["conversation_history"].append(initial_message)
                    logger.info("Added initial AI welcome message to default state.")

                    # Save this default state
                    state_json = json.dumps(lesson_state)
                    self.db_service.save_user_progress(
                        user_id=user_id,
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        status="in_progress",  # Start as in_progress
                        lesson_state_json=state_json,
                    )
                    logger.info(f"Saved default initial state for user {user_id}")

                except Exception as ai_err:
                    logger.error(
                        f"Failed to get/save initial AI message for default state: {ai_err}",
                        exc_info=True,
                    )

            return {
                "lesson_id": lesson_db_id,  # Use the actual lesson PK
                "syllabus_id": syllabus_id,
                "module_index": module_index,
                "lesson_index": lesson_index,
                "content": existing_lesson_content,  # The generated structure
                "lesson_state": lesson_state,  # The conversational state (might be None if no user_id)
                "is_new": False,
            }

        # --- Generate New Lesson Content & Initialize State ---
        logger.info(
            "Existing lesson content not found. Generating new content and state."
        )
        try:
            module = await self.syllabus_service.get_module_details(
                syllabus_id, module_index
            )
            lesson_details = await self.syllabus_service.get_lesson_details(
                syllabus_id, module_index, lesson_index
            )
            module_title = module.get("title", "Unknown Module")
            lesson_title = lesson_details.get("title", "Unknown Lesson")
        except ValueError as e:
            logger.error(f"Failed to get module/lesson details for generation: {e}")
            raise ValueError(
                f"Could not find module/lesson details for syllabus {syllabus_id}, mod {module_index}, lesson {lesson_index}"
            ) from e

        # Generate the base lesson content structure (exposition, exercises, quiz defs)
        try:
            # Construct the state needed for the generation logic
            generation_input_state = {
                 "topic": topic,
                 "knowledge_level": level,
                 "module_title": module_title,
                 "lesson_title": lesson_title,
                 "user_id": user_id,
                 "syllabus": syllabus, # Pass the fetched syllabus
                 # Include other fields expected by _generate_lesson_content if any
            }
            # Call the generation logic directly (assuming it's available on the instance)
            # This returns a dict like {"generated_content": ...}
            generation_result = self.lesson_ai._generate_lesson_content(generation_input_state)
            generated_content = generation_result.get("generated_content")
            if not generated_content:
                 raise RuntimeError("Content generation logic did not return 'generated_content'.")

        except Exception as gen_err:
            logger.error(f"Lesson content generation failed: {gen_err}", exc_info=True)
            raise RuntimeError("Failed to generate lesson content") from gen_err

        # Save the generated content structure
        # TODO: Ensure save_lesson_content returns the actual lesson_id PK
        # This saves to lesson_content table, we need the lesson PK from lessons table
        # Let's assume lesson_details contains the lesson_id PK
        lesson_db_id = lesson_details.get("lesson_id")
        if not lesson_db_id:
            # This case shouldn't happen if get_lesson_details worked, but handle defensively
            logger.error("Could not determine lesson_id PK after getting details.")
            raise RuntimeError("Failed to determine lesson primary key.")

        # Save content linked to the lesson_id PK
        self.db_service.save_lesson_content(  # This method needs lesson_id PK, not indices
            lesson_id=lesson_db_id,  # Pass the actual lesson_id PK
            content=generated_content,
            # Remove syllabus_id, module_index, lesson_index if not needed by save_lesson_content
        )
        logger.info(f"Saved new lesson content for lesson_id: {lesson_db_id}")

        # Initialize conversational state
        initial_lesson_state = {
            "topic": topic,
            "knowledge_level": level,
            "syllabus_id": syllabus_id,  # Store ID instead of full syllabus
            "lesson_title": lesson_title,
            "module_title": module_title,
            "generated_content": generated_content,  # Include the generated structure
            "user_id": user_id,
            "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",  # Consistent UID
            "conversation_history": [],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "user_performance": {},
            # Add other necessary fields from LessonState TypedDict
        }

        # Get initial AI message using the new start_chat method
        try:
            # Pass the state we've built so far (without history) to start_chat
            initial_lesson_state = self.lesson_ai.start_chat(initial_lesson_state)
            logger.info(
                "Called start_chat and added initial AI welcome message to state."
            )
        except Exception as ai_err:
            logger.error(
                f"Failed to get initial AI message via start_chat: {ai_err}",
                exc_info=True,
            )
            # If start_chat fails, initial_lesson_state might not have history yet.
            # Add a basic fallback message manually if needed, or proceed without.
            if (
                "conversation_history" not in initial_lesson_state
                or not initial_lesson_state["conversation_history"]
            ):
                fallback_message = {
                    "role": "assistant",
                    "content": "Welcome! Let's start the lesson.",
                }
                initial_lesson_state["conversation_history"] = [fallback_message]
                initial_lesson_state["current_interaction_mode"] = "chatting"

        # Save initial progress and state if user_id is provided
        if user_id:
            try:
                state_json = json.dumps(initial_lesson_state)
                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",  # Start as in_progress if chat starts
                    lesson_state_json=state_json,
                )
                logger.info(f"Saved initial progress and state for user {user_id}")
            except Exception as db_err:
                logger.error(
                    f"Failed to save initial progress/state: {db_err}", exc_info=True
                )
                # Decide how to handle this - maybe raise error?

        return {
            "lesson_id": lesson_db_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": generated_content,  # Return base structure
            "lesson_state": initial_lesson_state,  # Return initial conversational state
            "is_new": True,
        }

    async def handle_chat_turn(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Handles one turn of the chat conversation for a lesson.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.
            user_message (str): The message sent by the user.

        Returns:
            Dict[str, Any]: Containing the AI's response message(s).
        """
        logger.info(
            f"Handling chat turn for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state from DB
        progress_entry = self.db_service.get_lesson_progress(
            user_id, syllabus_id, module_index, lesson_index
        )

        if not progress_entry or not progress_entry.get("lesson_state"):
            logger.error(
                f"Could not load lesson state for chat turn. User: {user_id}, Lesson: {syllabus_id}/{module_index}/{lesson_index}"
            )
            # Attempt to re-initialize? Or return error?
            # For now, raise error. The state should exist if chat is initiated.
            raise ValueError("Lesson state not found. Cannot process chat turn.")

        current_lesson_state = progress_entry["lesson_state"]

        # Ensure generated_content is loaded if missing (e.g., if state was somehow saved without it)
        if not current_lesson_state.get("generated_content"):
            logger.warning(
                "Lesson state missing 'generated_content'. Attempting to reload."
            )
            # Need lesson_id PK to load content
            try:
                lesson_details = await self.syllabus_service.get_lesson_details(
                    syllabus_id, module_index, lesson_index
                )
                lesson_db_id = lesson_details.get("lesson_id")
                if lesson_db_id:
                    content_data = self.db_service.get_lesson_content(
                        syllabus_id, module_index, lesson_index
                    )  # Use indices here
                    if content_data and "content" in content_data:
                        current_lesson_state["generated_content"] = content_data[
                            "content"
                        ]
                    else:
                        raise ValueError("Failed to reload generated_content.")
                else:
                    raise ValueError("Could not determine lesson_id to reload content.")
            except Exception as load_err:
                logger.error(
                    f"Fatal error: Could not reload generated_content for state: {load_err}"
                )
                raise ValueError("Failed to load necessary lesson content for chat.")

        # 2. Call LessonAI.process_chat_turn
        try:
            # Ensure LessonAI instance is ready (might need re-init if service is long-lived?)
            # Assuming self.lesson_ai is persistent for the service instance
            updated_lesson_state = self.lesson_ai.process_chat_turn(
                current_state=current_lesson_state, user_message=user_message
            )
        except Exception as ai_err:
            logger.error(
                f"Error during LessonAI.process_chat_turn: {ai_err}", exc_info=True
            )
            # Return an error message to the user
            return {"error": "Sorry, I encountered an error processing your message."}

        # 3. Serialize and save the updated state
        try:
            updated_state_json = json.dumps(updated_lesson_state)
            # Determine status (e.g., check if quiz/exercises completed in updated_state)
            # For now, keep it simple and assume "in_progress"
            current_status = "in_progress"
            # Extract score if updated
            current_score = updated_lesson_state.get("user_performance", {}).get(
                "score"
            )  # Example path

            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,  # Pass score if available
                lesson_state_json=updated_state_json,
            )
            logger.info(f"Saved updated lesson state for user {user_id}")
        except Exception as db_err:
            logger.error(
                f"Failed to save updated lesson state: {db_err}", exc_info=True
            )
            # Continue to return response, but log the save failure

        # 4. Return the AI's response(s)
        # Find messages added in the last turn (assistant messages after the last user message)
        last_user_msg_index = -1
        for i in range(
            len(updated_lesson_state.get("conversation_history", [])) - 1, -1, -1
        ):
            if updated_lesson_state["conversation_history"][i].get("role") == "user":
                last_user_msg_index = i
                break

        ai_responses = updated_lesson_state.get("conversation_history", [])[
            last_user_msg_index + 1 :
        ]

        return {"responses": ai_responses}

    async def get_lesson_by_id(self, lesson_id: str) -> Dict[str, Any]:
        """Retrieve a lesson by ID"""
        lesson = self.db_service.get_lesson_by_id(lesson_id)

        if not lesson:
            raise ValueError(f"Lesson with ID {lesson_id} not found")

        return lesson

    async def evaluate_exercise(
        self,
        lesson_id: str,
        exercise_index: int,
        user_answer: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a user's answer to an exercise in a lesson"""
        lesson = await self.get_lesson_by_id(lesson_id)

        if not lesson or "content" not in lesson:
            raise ValueError(f"Invalid lesson with ID {lesson_id}")

        content = lesson["content"]

        # Determine the correct key for exercises and get the list
        exercises_list = None
        if "exercises" in content and isinstance(content.get("exercises"), list):
            exercises_list = content["exercises"]
            logger.debug(f"Using 'exercises' key for lesson {lesson_id}")
        elif "active_exercises" in content and isinstance(
            content.get("active_exercises"), list
        ):
            exercises_list = content["active_exercises"]
            logger.debug(f"Using 'active_exercises' key for lesson {lesson_id}")
        else:
            logger.warning(
                "Neither 'exercises' nor 'active_exercises' key found"
                f" or valid list in content for lesson {lesson_id}"
            )

        # Check if exercises list is valid and index is within bounds
        # Added check for exercises_list being None
        if exercises_list is None or exercise_index >= len(exercises_list):
            raise ValueError(
                f"Exercise index {exercise_index} out of range or"
                f" exercises not found/invalid for lesson {lesson_id}"
            )

        exercise = exercises_list[exercise_index]
        # Log specific fields instead of the entire exercise data to avoid encoding issues
        logger.debug(
            f"Exercise index: {exercise_index}, type: {exercise.get('type', 'unknown')}"
        )
        logger.debug(f"Exercise ID: {exercise.get('id', 'unknown')}")

        # Check for different possible field names that might contain the question text
        instructions = exercise.get("instructions", None)
        question = exercise.get("question", None)

        logger.debug(f"Found 'instructions' field: {instructions is not None}")
        logger.debug(f"Found 'question' field: {question is not None}")

        # Use instructions if available, otherwise fall back to question
        question_text = (
            question
            if question is not None
            else (
                instructions
                if instructions is not None
                else "Error: Question text not found."
            )
        )
        logger.debug(f"Using question_text: '{question_text[:100]}...' (truncated)")

        exercise_type = exercise.get("type", "open_ended")  # Determine type for prompt
        user_answer_str = str(user_answer)  # Ensure user answer is a string

        # Construct specific prompt content based on exercise type
        prompt_content = ""
        if exercise_type == "ordering":
            # Ensure items are strings for joining
            items_to_order = [str(item) for item in exercise.get("items", [])]
            # Assuming correct_answer is stored as a list or string representing the sequence
            correct_sequence = exercise.get("correct_answer", "N/A")
            prompt_content = f"""
Question: {question_text}

Items to order:
{chr(10).join([f'- {item}' for item in items_to_order])}

Expected correct order: {correct_sequence}

User's submitted order: {user_answer_str}

Please evaluate if the user's submitted order matches the expected correct order.
"""
        else:
            # For other types, look for different possible field names for the expected answer
            expected_solution = (
                exercise.get("answer")
                or exercise.get("expected_solution")
                or exercise.get("correct_answer")
                or exercise.get("correct_answer_explanation", "N/A")
            )

            logger.debug(
                f"Using expected_solution: '{str(expected_solution)[:100]}...' (truncated)"
            )

            prompt_content = f"""
Question: {question_text}

Expected solution or correct answer: {expected_solution}

User's response: {user_answer_str}

Please evaluate the user's response.
"""

        # Construct the full prompt for Gemini
        prompt = f"""
You are evaluating a user's response to a {exercise_type} exercise.

{prompt_content}

Provide your evaluation as a JSON object with the following structure:
1. "score": A score between 0 (incorrect) and 1 (correct). For ordering, 1 if the order is exactly correct, 0 otherwise. For other types, grade appropriately.
2. "feedback": A brief explanation of the evaluation (e.g., "Correct order", "Incorrect order", or feedback on partial correctness for other types).
3. "explanation": An optional brief explanation of the correct answer, especially if the user was incorrect.
4. "is_correct": A boolean (true if score is 1.0 for ordering, true if score >= 0.8 for other types, false otherwise).

Example JSON format:
{{
  "score": 1.0,
  "feedback": "The sequence is correct.",
  "explanation": "The correct order is B, D, G, A, F, E, C because...",
  "is_correct": true
}}
"""

        # Call the Gemini model directly
        try:
            evaluation_response = call_with_retry(model.generate_content, prompt)
            evaluation_text = evaluation_response.text
            logger.debug(f"Raw evaluation response: {evaluation_text}")

            # Extract JSON from response (using patterns from _evaluate_response)
            json_patterns = [
                r"```(?:json)?\s*({.*?})```",
                r'({[\s\S]*"score"[\s\S]*"feedback"[\s\S]*"explanation"[\s\S]*"is_correct"[\s\S]*})',
                r"({[\s\S]*})",
            ]

            evaluation_result = None
            for pattern in json_patterns:
                json_match = re.search(pattern, evaluation_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    # Basic cleanup
                    json_str = re.sub(r"\\n", "", json_str)
                    json_str = re.sub(r"\\", "", json_str)  # Be careful with this one
                    try:
                        evaluation_result = json.loads(json_str)
                        # Basic validation
                        if all(
                            key in evaluation_result
                            for key in ["score", "feedback", "is_correct"]
                        ):
                            # Ensure explanation is present, even if empty
                            evaluation_result.setdefault("explanation", "")
                            logger.debug(
                                f"Parsed evaluation result: {evaluation_result}"
                            )
                            break  # Successfully parsed
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"JSON parsing failed for pattern {pattern}: {e}"
                        )
                        logger.warning(f"Problematic JSON string: {json_str}")
                        evaluation_result = None  # Reset on failure

            if evaluation_result is None:
                logger.error(
                    f"Failed to parse evaluation JSON from response: {evaluation_text}"
                )
                # Provide a default error response
                evaluation_result = {
                    "score": 0.0,
                    "feedback": "Sorry, I couldn't evaluate your answer at this time.",
                    "explanation": "",
                    "is_correct": False,
                }

        except Exception as e:
            logger.error(f"Error during exercise evaluation: {e}", exc_info=True)
            evaluation_result = {
                "score": 0.0,
                "feedback": "An error occurred during evaluation.",
                "explanation": "",
                "is_correct": False,
            }

        # If user_id is provided and this is the final exercise, mark the lesson as completed
        if (
            user_id
            and exercises_list is not None
            and exercise_index == len(exercises_list) - 1
        ):  # Use exercises_list here
            # Update user progress to completed
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=lesson["syllabus_id"],
                module_index=lesson["module_index"],
                lesson_index=lesson["lesson_index"],
                status="completed",
                score=evaluation_result.get("score", 0),  # Use score from parsed result
            )

        # Return the structured evaluation result
        return {
            "is_correct": evaluation_result["is_correct"],
            "score": evaluation_result["score"],
            "feedback": evaluation_result["feedback"],
            "explanation": evaluation_result["explanation"],
        }

    async def update_lesson_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
    ) -> Dict[str, Any]:
        """Update user's progress for a specific lesson"""
        # Validate status
        if status not in ["not_started", "in_progress", "completed"]:
            raise ValueError(f"Invalid status: {status}")

        # Update the progress
        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            status=status,
            # Score is only updated during evaluation, pass None here
            score=None,
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,
        }
