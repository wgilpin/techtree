"""Lesson logic, for generation and evaluation"""

import json
import re
from typing import Any, Dict, Optional, Tuple, List # Added Tuple and List

# Import necessary components
from backend.ai.app import LessonAI # Keep LessonAI for chat interaction
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService
from backend.logger import logger  # Import the configured logger
# Import LLM utils and prompt loader
from backend.ai.llm_utils import call_with_retry, MODEL as llm_model # Import MODEL from llm_utils
from backend.ai.prompt_loader import load_prompt
from backend.models import GeneratedLessonContent # For validation
from pydantic import ValidationError
from google.api_core.exceptions import ResourceExhausted


# Need to import SyllabusService and SQLiteDatabaseService for type hinting
from .syllabus_service import SyllabusService
from .sqlite_db import SQLiteDatabaseService

class LessonService:
    """Service for managing and generating lesson content."""

    # Require db_service and syllabus_service, add type hints
    def __init__(self, db_service: SQLiteDatabaseService, syllabus_service: SyllabusService):
        # LessonAI is still needed for chat interaction
        self.lesson_ai = LessonAI()
        # Remove fallbacks
        self.db_service = db_service
        self.syllabus_service = syllabus_service

    async def _generate_and_save_lesson_content(
        self,
        syllabus: Dict,
        module_title: str,
        lesson_title: str,
        knowledge_level: str,
        user_id: Optional[str], # Keep user_id if needed for prompt context (e.g., performance)
        syllabus_id: str,
        module_index: int,
        lesson_index: int
    ) -> Tuple[Dict[str, Any], str]:
        """
        Generates lesson content using the LLM, validates it, saves it to the DB,
        and returns the content along with the lesson's database ID.

        Raises:
            RuntimeError: If content generation or saving fails.
        """
        logger.info(
            f"Generating new content for {syllabus_id}/{module_index}/{lesson_index}"
        )
        # Read the system prompt
        system_prompt: str
        try:
            # Assuming system_prompt.txt is relative to the backend directory
            with open("backend/system_prompt.txt", "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            logger.error("system_prompt.txt not found!")
            system_prompt = "You are a helpful tutor."  # Fallback prompt

        # Get user's previous performance if available (Simplified)
        previous_performance: Dict = {}
        # TODO: Implement logic to fetch actual previous performance if needed

        response_text: str
        try:
            # Load and format the prompt
            prompt = load_prompt(
                "generate_lesson_content",
                system_prompt=system_prompt,
                topic=syllabus.get("topic", "Unknown Topic"),
                syllabus_json=json.dumps(syllabus, indent=2),
                lesson_name=lesson_title,
                user_level=knowledge_level,
                previous_performance_json=json.dumps(previous_performance, indent=2),
                time_constraint="5 minutes",
            )
            # Use call_with_retry from llm_utils with the imported llm_model
            response = call_with_retry(llm_model.generate_content, prompt)
            response_text = response.text
        except ResourceExhausted:
             logger.error("LLM call failed after multiple retries due to resource exhaustion in content generation.")
             raise RuntimeError("LLM content generation failed due to resource limits.") from None
        except Exception as e:
            logger.error(f"LLM call failed during content generation: {e}", exc_info=True)
            raise RuntimeError("LLM content generation failed") from e

        # Extract JSON from response
        json_patterns: List[str] = [
            r"```(?:json)?\s*({.*?})```",
            r'({[\s\S]*"exposition_content"[\s\S]*"active_exercises"[\s\S]*"knowledge_assessment"[\s\S]*"metadata"[\s\S]*})',
            r"({[\s\S]*})",
        ]

        generated_content_dict: Optional[Dict] = None
        for pattern in json_patterns:
            json_match: Optional[re.Match] = re.search(pattern, response_text, re.DOTALL)
            if json_match:
                json_str: str = json_match.group(1)
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)
                try:
                    content_parsed: Dict = json.loads(json_str)
                    # Attempt Pydantic validation
                    try:
                        validated_model = GeneratedLessonContent.model_validate(content_parsed)
                        # Add topic/level if missing
                        if not validated_model.topic:
                            validated_model.topic = syllabus.get("topic", "Unknown Topic")
                        if not validated_model.level:
                            validated_model.level = knowledge_level
                        generated_content_dict = validated_model.model_dump(mode='json')
                        logger.info("Successfully parsed and validated generated lesson content.")
                        break # Success
                    except ValidationError as ve:
                         logger.warning(f"Pydantic validation failed for parsed JSON: {ve}")
                         # Continue to next pattern if validation fails
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed for pattern {pattern}: {e}")

        if generated_content_dict is None:
            logger.error(f"Failed to parse valid JSON content from LLM response: {response_text[:500]}...")
            raise RuntimeError("Failed to parse valid content structure from LLM.")

        # Save the generated content structure
        try:
            lesson_db_id = self.db_service.save_lesson_content(
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                content=generated_content_dict,
            )
            if not lesson_db_id:
                 logger.error("save_lesson_content did not return a valid lesson_id.")
                 raise RuntimeError("Failed to save lesson content or retrieve lesson ID.")
            logger.info(f"Saved new lesson content, associated lesson_id: {lesson_db_id}")
            return generated_content_dict, str(lesson_db_id) # Return content and ID
        except Exception as save_err:
             logger.error(f"Failed to save lesson content: {save_err}", exc_info=True)
             raise RuntimeError("Database error saving lesson content") from save_err


    def _initialize_lesson_state(
        self,
        topic: str,
        level: str,
        syllabus_id: str,
        module_title: str,
        lesson_title: str,
        generated_content: Dict[str, Any],
        user_id: Optional[str],
        module_index: int,
        lesson_index: int,
        lesson_db_id: Optional[str] # Added lesson_db_id for consistency if needed later
    ) -> Dict[str, Any]:
        """Helper function to create and initialize lesson state."""
        logger.info(f"Initializing lesson state for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}")

        initial_state = {
            "topic": topic,
            "knowledge_level": level,
            "syllabus_id": syllabus_id, # Keep syllabus_id for context
            "lesson_title": lesson_title,
            "module_title": module_title,
            "generated_content": generated_content,
            "user_id": user_id,
            # Use lesson_db_id if available, otherwise construct UID. Consider standardizing.
            "lesson_uid": str(lesson_db_id) if lesson_db_id else f"{syllabus_id}_{module_index}_{lesson_index}",
            "conversation_history": [],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "user_performance": {},
            # Add syllabus dict itself if needed by LessonAI, though content is primary
            "syllabus": self.syllabus_service.get_syllabus_sync(syllabus_id) # Add sync version or make init async
        }

        if not user_id: # No need to call AI or save state if no user
             return initial_state

        try:
            # Pass the state to start_chat.
            updated_state = self.lesson_ai.start_chat(initial_state.copy()) # Pass a copy
            initial_state = updated_state # Use the returned state
            logger.info(
                "Called start_chat and potentially added initial AI welcome message to state."
            )
        except Exception as ai_err:
            logger.error(
                f"Failed to get initial AI message via start_chat: {ai_err}",
                exc_info=True,
            )
            # Fallback logic if start_chat fails or doesn't add history
            if (
                "conversation_history" not in initial_state
                or not initial_state.get("conversation_history") # Check if empty list too
            ):
                fallback_message = {
                    "role": "assistant",
                    "content": f"Welcome to the lesson on '{lesson_title}'! Let's begin.", # Simplified fallback
                }
                initial_state["conversation_history"] = [fallback_message]
                initial_state["current_interaction_mode"] = "chatting" # Ensure mode is set
                logger.warning("Added fallback welcome message as start_chat failed or returned no history.")

        return initial_state

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
            f"Getting/Generating lesson: syllabus={syllabus_id}, mod={module_index},"
            f" lesson={lesson_index}, user={user_id}"
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
        existing_lesson_content = None
        lesson_db_id = None # Initialize lesson_db_id

        # Try to get lesson_db_id from progress first
        if progress_entry and progress_entry.get('lesson_id'):
             lesson_db_id = progress_entry.get('lesson_id')
             logger.debug(f"Found lesson_id {lesson_db_id} from progress entry.")
        # If not in progress or progress doesn't have it, look up via indices
        if not lesson_db_id:
             try:
                 lesson_details = await self.syllabus_service.get_lesson_details(
                     syllabus_id, module_index, lesson_index
                 )
                 lesson_db_id = lesson_details.get("lesson_id")
                 logger.debug(f"Looked up lesson_id {lesson_db_id} via indices.")
             except ValueError:
                 logger.error(
                     f"Could not find lesson details for mod={module_index}, lesson={lesson_index}"
                 )
                 # lesson_db_id remains None

        # Now try fetching content using indices (as DB method expects this)
        content_data = self.db_service.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )
        if content_data:
            existing_lesson_content = content_data # Assign directly
            logger.info(
                f"Found existing lesson content for {syllabus_id}/{module_index}/{lesson_index}"
            )

        # --- Return Existing Content & State (if found) ---
        if existing_lesson_content:
            # Ensure topic and level are in the content
            if "topic" not in existing_lesson_content:
                existing_lesson_content["topic"] = topic
            if "level" not in existing_lesson_content:
                existing_lesson_content["level"] = level

            # If state wasn't loaded from progress, create and initialize state using the helper
            if lesson_state is None and user_id:
                logger.warning(
                    f"Content exists but no state found for user {user_id}. Initializing state."
                )
                try:
                    # Fetch necessary details for state initialization
                    module_details = await self.syllabus_service.get_module_details(
                        syllabus_id, module_index
                    )
                    module_title = module_details.get("title", "Unknown Module")
                    # Get lesson title from content metadata if possible
                    lesson_title = existing_lesson_content.get("metadata", {}).get(
                        "title", "Unknown Lesson"
                    )

                    # Call the helper function to initialize state
                    lesson_state = self._initialize_lesson_state(
                        topic=topic,
                        level=level,
                        syllabus_id=syllabus_id,
                        module_title=module_title,
                        lesson_title=lesson_title,
                        generated_content=existing_lesson_content,
                        user_id=user_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        lesson_db_id=lesson_db_id # Pass the db id
                    )

                    # Save the newly initialized state
                    state_json = json.dumps(lesson_state)
                    self.db_service.save_user_progress(
                        user_id=user_id,
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        status="in_progress",
                        lesson_state_json=state_json,
                        lesson_id=lesson_db_id # Ensure lesson_id is saved with progress
                    )
                    logger.info(f"Saved initialized state for user {user_id}")

                except Exception as init_err:
                    logger.error(
                        f"Failed to initialize or save lesson state: {init_err}",
                        exc_info=True,
                    )
                    # Proceed but lesson_state might remain None

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

        # Generate the base lesson content structure using the new helper
        try:
            generated_content, lesson_db_id = await self._generate_and_save_lesson_content(
                 syllabus=syllabus,
                 module_title=module_title,
                 lesson_title=lesson_title,
                 knowledge_level=level,
                 user_id=user_id,
                 syllabus_id=syllabus_id,
                 module_index=module_index,
                 lesson_index=lesson_index
            )
        except Exception as gen_err:
            # Error logging happens within the helper
            raise RuntimeError("Failed to generate and save lesson content") from gen_err


        # Initialize conversational state using the helper function
        initial_lesson_state = self._initialize_lesson_state(
            topic=topic,
            level=level,
            syllabus_id=syllabus_id,
            module_title=module_title,
            lesson_title=lesson_title,
            generated_content=generated_content,
            user_id=user_id,
            module_index=module_index,
            lesson_index=lesson_index,
            lesson_db_id=lesson_db_id # Pass the db id from generation step
        )

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
                    lesson_id=lesson_db_id # Ensure lesson_id is saved
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
            try:
                # Use indices to fetch content
                content_data = self.db_service.get_lesson_content(
                    syllabus_id, module_index, lesson_index
                )
                if content_data:
                    current_lesson_state["generated_content"] = content_data
                else:
                    raise ValueError("Failed to reload generated_content using indices.")
            except Exception as load_err:
                logger.error(
                    f"Fatal error: Could not reload generated_content for state: {load_err}"
                )
                raise ValueError("Failed to load necessary lesson content for chat.")

        # 2. Call LessonAI.process_chat_turn
        try:
            # Ensure LessonAI instance is ready
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
            current_status = "in_progress" # Default status during chat
            # Extract score if updated (assuming structure)
            current_score = updated_lesson_state.get("user_performance", {}).get("score")

            # Get lesson_id from the state if possible, otherwise fallback needed
            lesson_db_id = updated_lesson_state.get("lesson_uid") # Assuming lesson_uid holds the DB ID

            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id # Pass lesson_id if available
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
        history = updated_lesson_state.get("conversation_history", [])
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                last_user_msg_index = i
                break

        ai_responses = history[last_user_msg_index + 1 :]

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
            # Use call_with_retry and llm_model imported from llm_utils
            evaluation_response = call_with_retry(llm_model.generate_content, prompt)
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
                lesson_id=lesson_id # Pass lesson_id
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
            # Need lesson_id if updating progress without state
            # lesson_id= ? # How to get lesson_id here reliably?
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,
        }
