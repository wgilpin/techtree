"""Lesson logic, for generation and evaluation"""
# pylint: disable=broad-exception-caught

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from google.api_core.exceptions import ResourceExhausted
from pydantic import ValidationError

# Import necessary components
from backend.ai.app import LessonAI
from backend.ai.lessons import nodes

# Import LLM utils and prompt loader
from backend.ai.llm_utils import MODEL as llm_model
from backend.ai.llm_utils import call_with_retry
from backend.ai.prompt_loader import load_prompt
from backend.logger import logger
from backend.models import (
    AssessmentQuestion,  # For validation + new models
    Exercise,
    GeneratedLessonContent,
    Metadata, # Added Metadata import
)
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService

from .sqlite_db import SQLiteDatabaseService
from .syllabus_service import SyllabusService


class LessonService:
    """Service for managing and generating lesson content."""

    # Require db_service and syllabus_service, add type hints
    def __init__(
        self, db_service: SQLiteDatabaseService, syllabus_service: SyllabusService
    ):
        # LessonAI is still needed for chat interaction
        self.lesson_ai = LessonAI()
        # Remove fallbacks
        self.db_service = db_service
        self.syllabus_service = syllabus_service

    async def _generate_and_save_lesson_content(
        self,
        syllabus: Dict,
        # module_title: str, # Removed - Unused
        lesson_title: str,
        knowledge_level: str,
        # user_id: Optional[ # Removed - Unused (previous_performance not implemented)
        #     str
        # ],
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Tuple[GeneratedLessonContent, int]:  # Return Pydantic object and int ID
        """
        Generates lesson content using the LLM, validates it, saves it to the DB,
        and returns the validated content object along with the lesson's database ID.

        Raises:
            RuntimeError: If content generation or saving fails.
        """
        logger.info(
            f"Generating new content for {syllabus_id}/{module_index}/{lesson_index}"
        )
        # System prompt is now merged into generate_lesson_content.prompt

        # Get user's previous performance if available (Simplified)
        previous_performance: Dict = {}
        # TODO: Implement logic to fetch actual previous performance if needed

        response_text: str
        try:
            # Load and format the prompt (system_prompt is now part of the template)
            prompt = load_prompt(
                "generate_lesson_content",
                # system_prompt=system_prompt, # Removed - Merged into prompt file
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
            logger.error(
                "LLM call failed after multiple retries due to resource exhaustion in content generation."
            )
            raise RuntimeError(
                "LLM content generation failed due to resource limits."
            ) from None
        except Exception as e:
            logger.error(
                f"LLM call failed during content generation: {e}", exc_info=True
            )
            raise RuntimeError("LLM content generation failed") from e

        # --- Construct GeneratedLessonContent from plain text response ---
        # The system prompt now returns only the markdown exposition.
        logger.info("Constructing GeneratedLessonContent from plain text LLM response.")
        try:
            # Create metadata
            lesson_metadata = Metadata(title=lesson_title)

            # Create the main content object
            generated_content_object = GeneratedLessonContent(
                topic=syllabus.get("topic", "Unknown Topic"),
                level=knowledge_level,
                exposition_content=response_text.strip(), # Use the raw text
                metadata=lesson_metadata,
            )
            logger.info("Successfully constructed GeneratedLessonContent object.")

        except Exception as construct_err:
            logger.error(
                f"Failed to construct GeneratedLessonContent object: {construct_err}",
                exc_info=True
            )
            logger.error(f"LLM response text was: {response_text[:500]}...")
            raise RuntimeError("Failed to construct lesson content object from LLM response.") from construct_err

        # --- Save the generated content structure ---
        try:
            # save_lesson_content now returns the integer lesson_id
            lesson_db_id_int = self.db_service.save_lesson_content(
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                content=generated_content_object.model_dump(
                    mode="json"
                ),  # Dump here for DB
            )
            if not lesson_db_id_int: # Check if it's a valid ID (e.g., > 0)
                logger.error("save_lesson_content did not return a valid integer lesson_id.")
                raise RuntimeError(
                    "Failed to save lesson content or retrieve lesson ID."
                )
            logger.info(
                f"Saved new lesson content, associated lesson_id: {lesson_db_id_int}"
            )
            # Return object and the integer ID
            return generated_content_object, lesson_db_id_int
        except Exception as save_err:
            logger.error(f"Failed to save lesson content: {save_err}", exc_info=True)
            raise RuntimeError("Database error saving lesson content") from save_err

    async def _initialize_lesson_state( # Changed to async def
        self,
        topic: str,
        level: str,
        syllabus_id: str,
        module_title: str,
        lesson_title: str,
        generated_content: GeneratedLessonContent,  # Expect Pydantic object
        user_id: Optional[str],
        module_index: int,
        lesson_index: int,
        lesson_db_id: Optional[
            int # Changed to int
        ],
    ) -> Dict[str, Any]:
        """Helper function to create and initialize lesson state."""
        logger.info(
            f"Initializing lesson state for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index} (lesson_id: {lesson_db_id})"
        )

        # Fetch the full syllabus asynchronously (still needed for topic/level if not in content)
        # syllabus_data = await self.syllabus_service.get_syllabus(syllabus_id) # Removed - Not needed in state

        initial_state = {
            "topic": topic,
            "knowledge_level": level,
            "syllabus_id": syllabus_id,  # Keep syllabus_id for context
            "lesson_title": lesson_title,
            "module_title": module_title,
            "generated_content": generated_content,  # Store the object directly
            "user_id": user_id,
            # Use lesson_db_id directly now it's consistently an int
            "lesson_uid": lesson_db_id, # Use the integer lesson_id as the UID
            "conversation_history": [],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            # Add fields for on-demand generated items
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "user_responses": [],
            "user_performance": {},
            # Removed syllabus dict itself
            # "syllabus": syllabus_data, # REMOVED - Causes circular reference
        }

        if not user_id:  # No need to call AI or save state if no user
            return initial_state

        try:
            # Pass the state to start_chat.
            updated_state = self.lesson_ai.start_chat(
                initial_state.copy()
            )  # Pass a copy
            initial_state = updated_state  # Use the returned state
            logger.info(
                "Called start_chat and potentially added initial AI welcome message to state."
            )
        except Exception as ai_err:
            logger.error(
                f"Failed to get initial AI message via start_chat: {ai_err}",
                exc_info=True,
            )
            # Fallback logic if start_chat fails or doesn't add history
            if "conversation_history" not in initial_state or not initial_state.get(
                "conversation_history"
            ):  # Check if empty list too
                fallback_message = {
                    "role": "assistant",
                    "content": f"Welcome to the lesson on '{lesson_title}'! Let's begin.",
                }
                initial_state["conversation_history"] = [fallback_message]
                initial_state["current_interaction_mode"] = (
                    "chatting"  # Ensure mode is set
                )
                logger.warning(
                    "Added fallback welcome message as start_chat failed or returned no history."
                )

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
        lesson_db_id = None # Initialize lesson_db_id (now expected as int)
        if user_id:
            # Use the new method to get specific lesson progress
            progress_entry = self.db_service.get_lesson_progress(
                user_id, syllabus_id, module_index, lesson_index
            )

            if progress_entry:
                # Prioritize getting lesson_id from the progress entry
                lesson_db_id = progress_entry.get("lesson_id")
                if lesson_db_id is not None: # Check if it's not None
                     logger.debug(f"Found lesson_id {lesson_db_id} from progress entry.")
                else:
                     logger.warning(f"Progress entry found but lesson_id is missing/null for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}")

                if "lesson_state" in progress_entry and progress_entry["lesson_state"]:
                    lesson_state = progress_entry["lesson_state"]
                    logger.info(f"Loaded existing lesson state for user {user_id}")
                else:
                    logger.info(f"Progress entry found but no state for user {user_id}")
            else:
                logger.info(f"No existing progress entry found for user {user_id}")


        # --- Check for Existing Lesson Content ---
        # Fetch content separately as it might exist even if progress doesn't
        existing_lesson_content_obj: Optional[GeneratedLessonContent] = None
        content_data_dict = self.db_service.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )

        if content_data_dict:
            try:
                existing_lesson_content_obj = GeneratedLessonContent.model_validate(
                    content_data_dict
                )
                logger.info(
                    "Found and validated existing lesson content for"
                    f" {syllabus_id}/{module_index}/{lesson_index}"
                )
                # MODIFIED LOGIC: Only try index lookup if lesson_db_id is STILL None after checking progress
                if lesson_db_id is None:
                    logger.debug("lesson_db_id not found via progress, attempting lookup via indices...")
                    try:
                        lesson_details = await self.syllabus_service.get_lesson_details(
                            syllabus_id, module_index, lesson_index
                        )
                        # Ensure we get an integer ID or None
                        retrieved_id = lesson_details.get("lesson_id")
                        if isinstance(retrieved_id, int):
                             lesson_db_id = retrieved_id
                             logger.debug(f"Looked up lesson_id {lesson_db_id} via indices after finding content.")
                        else:
                             # Log error if lookup failed or returned non-int
                             logger.error(f"Content found, but failed to look up valid lesson_id via indices for {syllabus_id}/{module_index}/{lesson_index}. Retrieved: {retrieved_id}")
                    except ValueError as e:
                        logger.error(f"Content found, but error looking up lesson_id via indices for {syllabus_id}/{module_index}/{lesson_index}: {e}")
                    except Exception as e: # Catch other potential errors during lookup
                         logger.error(f"Unexpected error during index lookup for lesson_id: {e}", exc_info=True)

            except ValidationError as ve:
                logger.error(
                    f"Failed to validate existing lesson content from DB: {ve}",
                    exc_info=True,
                )
                # existing_lesson_content_obj remains None, generation will proceed

        # --- Return Existing Content & State (if found and valid) ---
        if existing_lesson_content_obj:
            # Ensure topic and level are in the content object
            if not existing_lesson_content_obj.topic:
                existing_lesson_content_obj.topic = topic
            if not existing_lesson_content_obj.level:
                existing_lesson_content_obj.level = level

            # If state wasn't loaded from progress, create and initialize state using the helper
            if lesson_state is None and user_id:
                # We MUST have a lesson_db_id at this point if content exists
                if lesson_db_id is None: # Check explicitly for None again
                     logger.error(f"CRITICAL: Content exists for {syllabus_id}/{module_index}/{lesson_index} but lesson_id could not be determined. Cannot initialize state.")
                     raise RuntimeError("Failed to determine lesson ID for existing content.")

                logger.warning(
                    f"Content exists but no state found for user {user_id}. Initializing state for lesson_id {lesson_db_id}."
                )
                try:
                    # Fetch necessary details for state initialization
                    module_details = await self.syllabus_service.get_module_details(
                        syllabus_id, module_index
                    )
                    module_title = module_details.get("title", "Unknown Module")
                    lesson_title = (
                        existing_lesson_content_obj.metadata.title
                        if existing_lesson_content_obj.metadata
                        else "Unknown Lesson"
                    )

                    # Call the helper function to initialize state
                    lesson_state = await self._initialize_lesson_state( # Await the async call
                        topic=topic,
                        level=level,
                        syllabus_id=syllabus_id,
                        module_title=module_title,
                        lesson_title=lesson_title,
                        generated_content=existing_lesson_content_obj,  # Pass the object
                        user_id=user_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        lesson_db_id=lesson_db_id,  # Pass the int db id
                    )

                    # Save the newly initialized state, including lesson_id
                    state_json = json.dumps(
                        lesson_state,
                        default=lambda o: (
                            o.model_dump(mode="json")
                            if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion))
                            else o
                        ),
                    )
                    self.db_service.save_user_progress(
                        user_id=user_id,
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        status="in_progress",
                        lesson_state_json=state_json,
                        lesson_id=lesson_db_id, # Pass the lesson_id here
                    )
                    logger.info(f"Saved initialized state for user {user_id}, lesson_id {lesson_db_id}")

                except Exception as init_err:
                    logger.error(
                        f"Failed to initialize or save lesson state: {init_err}",
                        exc_info=True,
                    )
                    # MODIFIED: Raise error instead of proceeding silently
                    raise RuntimeError("Failed to save initialized lesson state") from init_err

            # Ensure the returned state also has the validated object if it was loaded separately
            if lesson_state and not isinstance(
                lesson_state.get("generated_content"), GeneratedLessonContent
            ):
                lesson_state["generated_content"] = existing_lesson_content_obj

            # Ensure lesson_uid in state matches the determined lesson_db_id and save if needed
            state_updated = False # Flag to track if state was modified
            if lesson_state and lesson_state.get("lesson_uid") != lesson_db_id:
                 logger.warning(f"State lesson_uid ({lesson_state.get('lesson_uid')}) differs from determined lesson_id ({lesson_db_id}). Updating state.")
                 lesson_state["lesson_uid"] = lesson_db_id
                 state_updated = True # Mark state as updated

            # ADDED: Save the state if the lesson_uid was corrected
            if state_updated and user_id:
                try:
                    logger.info(f"Saving updated lesson_state with corrected lesson_uid ({lesson_db_id}) for user {user_id}")
                    state_json = json.dumps(
                        lesson_state,
                        default=lambda o: (
                            o.model_dump(mode="json")
                            if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion))
                            else o
                        ),
                    )
                    # Use current status from progress_entry if available, else default
                    current_status = progress_entry.get("status", "in_progress") if progress_entry else "in_progress"
                    current_score = progress_entry.get("score") if progress_entry else None

                    self.db_service.save_user_progress(
                        user_id=user_id,
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        status=current_status, # Use existing status
                        score=current_score, # Use existing score
                        lesson_state_json=state_json,
                        lesson_id=lesson_db_id, # Pass the correct lesson_id
                    )
                    logger.info(f"Successfully saved corrected lesson state for user {user_id}, lesson_id {lesson_db_id}")
                except Exception as save_err:
                    # Log error but don't block returning the data
                    logger.error(f"Failed to save corrected lesson state: {save_err}", exc_info=True)


            return {
                "lesson_id": lesson_db_id,  # Return the integer lesson PK
                "syllabus_id": syllabus_id,
                "module_index": module_index,
                "lesson_index": lesson_index,
                "content": existing_lesson_content_obj,  # Return the validated object
                "lesson_state": lesson_state,  # conversational state (might be None if no user_id)
                "is_new": False,
            }

        # --- Generate New Lesson Content & Initialize State ---
        logger.info(
            "Existing lesson content not found or invalid. Generating new content and state."
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
                f"Could not find module/lesson details for syllabus {syllabus_id},"
                f" mod {module_index}, lesson {lesson_index}"
            ) from e

        # Generate the base lesson content structure using the new helper
        try:
            # Expect int lesson_db_id now
            generated_content_obj, lesson_db_id = (
                await self._generate_and_save_lesson_content(
                    syllabus=syllabus,
                    lesson_title=lesson_title,
                    knowledge_level=level,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
            )
        except Exception as gen_err:
            # Error logging happens within the helper
            raise RuntimeError(
                "Failed to generate and save lesson content"
            ) from gen_err

        # Initialize conversational state using the helper function (now async)
        initial_lesson_state = await self._initialize_lesson_state(
            topic=topic,
            level=level,
            syllabus_id=syllabus_id,
            module_title=module_title,
            lesson_title=lesson_title,
            generated_content=generated_content_obj,  # Pass the object
            user_id=user_id,
            module_index=module_index,
            lesson_index=lesson_index,
            lesson_db_id=lesson_db_id,  # Pass the int db id from generation step
        )

        # Save initial progress and state if user_id is provided
        if user_id:
            try:
                # Need to handle potential Pydantic objects within the state for JSON serialization
                state_json = json.dumps(
                    initial_lesson_state,
                    default=lambda o: (
                        o.model_dump(mode="json")
                        if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion))
                        else o
                    ),
                )
                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",  # Start as in_progress if chat starts
                    lesson_state_json=state_json,
                    lesson_id=lesson_db_id, # Pass the lesson_id here
                )
                logger.info(f"Saved initial progress and state for user {user_id}, lesson_id {lesson_db_id}")
            except Exception as db_err:
                logger.error(
                    f"Failed to save initial progress/state: {db_err}", exc_info=True
                )
                # MODIFIED: Raise error instead of proceeding silently
                raise RuntimeError("Failed to save initial progress/state") from db_err

        return {
            "lesson_id": lesson_db_id, # Return the integer lesson PK
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": generated_content_obj,  # Return validated object
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
            f"Handling chat turn for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state from DB
        progress_entry = self.db_service.get_lesson_progress(
            user_id, syllabus_id, module_index, lesson_index
        )

        if not progress_entry:
             logger.error(
                "Could not load progress entry for chat turn. "
                f"User: {user_id}, Lesson: {syllabus_id}/{module_index}/{lesson_index}"
            )
             raise ValueError("Progress entry not found. Cannot process chat turn.")

        lesson_db_id = progress_entry.get("lesson_id") # Get lesson_id from progress
        if not lesson_db_id:
             logger.error(
                "Progress entry loaded but lesson_id is missing. "
                f"User: {user_id}, Lesson: {syllabus_id}/{module_index}/{lesson_index}"
            )
             raise ValueError("Lesson ID missing in progress entry. Cannot process chat turn.")


        if not progress_entry.get("lesson_state"):
            logger.error(
                "Progress entry loaded but lesson state is missing. "
                f"User: {user_id}, Lesson: {syllabus_id}/{module_index}/{lesson_index}"
            )
            raise ValueError("Lesson state not found. Cannot process chat turn.")

        current_lesson_state = progress_entry["lesson_state"]

        # Ensure generated_content is loaded and is a Pydantic object
        content_in_state = current_lesson_state.get("generated_content")
        if not isinstance(content_in_state, GeneratedLessonContent):
            logger.warning(
                "Lesson state 'generated_content' is not a Pydantic object "
                f"(type: {type(content_in_state)}). Attempting to reload and validate."
            )
            try:
                # Use indices to fetch content dict from DB
                content_data_dict = self.db_service.get_lesson_content(
                    syllabus_id, module_index, lesson_index
                )
                if content_data_dict:
                    # Validate the dict loaded from DB
                    validated_content_obj = GeneratedLessonContent.model_validate(
                        content_data_dict
                    )
                    current_lesson_state["generated_content"] = (
                        validated_content_obj  # Replace dict with object
                    )
                    logger.info(
                        "Successfully reloaded and validated generated_content."
                    )
                else:
                    raise ValueError(
                        "Failed to reload generated_content using indices."
                    )
            except (ValidationError, Exception) as load_err:
                logger.error(
                    "Fatal error: Could not reload/validate"
                    f" generated_content for state: {load_err}",
                    exc_info=True,
                )
                raise ValueError("Failed to load necessary lesson content for chat.") from load_err

        # Ensure lesson_uid in state matches the loaded lesson_db_id
        if current_lesson_state.get("lesson_uid") != lesson_db_id:
            logger.warning(f"State lesson_uid ({current_lesson_state.get('lesson_uid')}) differs from progress lesson_id ({lesson_db_id}). Updating state.")
            current_lesson_state["lesson_uid"] = lesson_db_id
            # Note: We don't save the corrected state here during chat turn,
            # it will be saved after the AI processing anyway.

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

        # 2.5 Apply Adaptivity Rules (Example: Log consecutive incorrect answers)
        try:
            user_responses = updated_lesson_state.get("user_responses", [])
            if len(user_responses) >= 2:
                last_response = user_responses[-1]
                prev_response = user_responses[-2]

                # Check if both last responses were evaluations and incorrect
                if "evaluation" in last_response and "evaluation" in prev_response:
                    last_eval = last_response["evaluation"]
                    prev_eval = prev_response["evaluation"]
                    last_type = last_response.get("question_type")
                    prev_type = prev_response.get("question_type")

                    if (
                        not last_eval.get("is_correct", True)
                        and not prev_eval.get("is_correct", True)
                        and last_type
                        == prev_type  # Check if they are the same type (e.g., both exercises)
                        and last_type is not None
                    ):  # Ensure type is known

                        logger.warning(
                            f"Adaptivity Alert: User {user_id} answered 2 consecutive "
                            f"{last_type} questions incorrectly. "
                            f"(Last Q: {last_response.get('question_id', 'unknown')}, "
                            f"Prev Q: {prev_response.get('question_id', 'unknown')})"
                        )
                        # TODO: Implement more complex adaptivity logic here:
                        # - Adjust difficulty (e.g., flag for easier questions next time)
                        # - Suggest revisiting prerequisite topics
                        # - Modify user_performance in state?
                        # - Potentially alter the next step suggested by the AI?
            elif user_responses:  # Handle the case of only one response
                last_response = user_responses[-1]
                if "evaluation" in last_response:
                    evaluation = last_response["evaluation"]
                    if not evaluation.get("is_correct", True):
                        logger.info(
                            f"Adaptivity Check: Incorrect answer detected for user {user_id}, "
                            f"question {last_response.get('question_id', 'unknown')}. "
                            f"Score: {evaluation.get('score', 'N/A')}"
                        )

        except Exception as adapt_err:
            logger.error(f"Error during adaptivity logic: {adapt_err}", exc_info=True)
            # Continue even if adaptivity logic fails

        # 3. Serialize and save the updated state
        try:
            # Need to handle potential Pydantic objects within the state for JSON serialization
            updated_state_json = json.dumps(
                updated_lesson_state,
                default=lambda o: (
                    o.model_dump(mode="json")
                    if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion)) # Handle all known Pydantic models
                    else o
                ),
            )
            current_status = "in_progress"  # Default status during chat
            # Extract score if updated (assuming structure)
            current_score = updated_lesson_state.get("user_performance", {}).get(
                "score"
            )

            # Use the lesson_db_id retrieved from the progress entry
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id # Pass the lesson_id
            )
            logger.info(f"Saved updated lesson state for user {user_id}, lesson_id {lesson_db_id}")
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

    async def generate_exercise_for_lesson(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[Exercise]:
        """
        Generates a new exercise for the lesson on demand, ensuring novelty.
        """
        logger.info(
            f"Generating new exercise for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state
        progress_entry = self.db_service.get_lesson_progress(
            user_id, syllabus_id, module_index, lesson_index
        )
        if not progress_entry:
             logger.error(
                f"Could not load progress entry for exercise generation. User: {user_id}"
            )
             raise ValueError("Progress entry not found. Cannot generate exercise.")

        lesson_db_id = progress_entry.get("lesson_id") # Get lesson_id from progress
        if not lesson_db_id:
             logger.error(
                f"Progress entry loaded but lesson_id is missing for exercise generation. User: {user_id}"
            )
             raise ValueError("Lesson ID missing in progress entry. Cannot generate exercise.")

        if not progress_entry.get("lesson_state"):
            logger.error(
                f"Could not load lesson state for exercise generation. User: {user_id}"
            )
            raise ValueError("Lesson state not found. Cannot generate exercise.")

        current_lesson_state = progress_entry["lesson_state"]

        # Ensure generated_content is loaded and valid (similar to handle_chat_turn)
        content_in_state = current_lesson_state.get("generated_content")
        if not isinstance(content_in_state, GeneratedLessonContent):
            logger.warning(
                "Lesson state 'generated_content' is not a Pydantic object. Reloading."
            )
            try:
                content_data_dict = self.db_service.get_lesson_content(
                    syllabus_id, module_index, lesson_index
                )
                if content_data_dict:
                    validated_content_obj = GeneratedLessonContent.model_validate(
                        content_data_dict
                    )
                    current_lesson_state["generated_content"] = validated_content_obj
                else:
                    raise ValueError("Failed to reload generated_content.")
            except (ValidationError, Exception) as load_err:
                logger.error(
                    f"Fatal error: Could not reload/validate generated_content: {load_err}",
                    exc_info=True,
                )
                raise ValueError(
                    "Failed to load necessary lesson content for exercise generation."
                ) from load_err

        # Ensure lesson_uid in state matches the loaded lesson_db_id
        if current_lesson_state.get("lesson_uid") != lesson_db_id:
            logger.warning(f"State lesson_uid ({current_lesson_state.get('lesson_uid')}) differs from progress lesson_id ({lesson_db_id}). Updating state.")
            current_lesson_state["lesson_uid"] = lesson_db_id
            # Save the corrected state immediately before generation
            try:
                logger.info(f"Saving corrected lesson state before exercise generation for user {user_id}")
                state_json = json.dumps(
                    current_lesson_state,
                    default=lambda o: (
                        o.model_dump(mode="json")
                        if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion))
                        else o
                    ),
                )
                self.db_service.save_user_progress(
                    user_id=user_id, syllabus_id=syllabus_id, module_index=module_index,
                    lesson_index=lesson_index, status=progress_entry.get("status", "in_progress"),
                    score=progress_entry.get("score"), lesson_state_json=state_json,
                    lesson_id=lesson_db_id
                )
            except Exception as save_err:
                 logger.error(f"Failed to save corrected lesson state before exercise generation: {save_err}", exc_info=True)
                 # Decide if we should raise here or proceed with potentially inconsistent state for generation


        # 2. Call the new generation node function
        try:
            # We expect the node to return the *updated* state and the *newly generated* exercise
            updated_state, new_exercise = await nodes.generate_new_exercise(
                current_lesson_state.copy() # Pass the potentially corrected state
            )
            if not new_exercise:
                logger.warning(
                    f"generate_new_exercise node did not return a new exercise for user {user_id}."
                )
                return None

        except Exception as gen_err:
            logger.error(
                f"Error during exercise generation node call: {gen_err}", exc_info=True
            )
            raise RuntimeError("Failed to generate new exercise.") from gen_err

        # 3. Save the updated state (after generation)
        try:
            updated_state_json = json.dumps(
                updated_state,
                default=lambda o: (
                    o.model_dump(mode="json")
                    if isinstance(
                        o, (GeneratedLessonContent, Exercise, AssessmentQuestion)
                    )
                    else o
                ),
            )
            current_status = "in_progress"
            current_score = updated_state.get("user_performance", {}).get("score")

            # Use the lesson_db_id retrieved from the progress entry
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id # Pass the lesson_id
            )
            logger.info(
                f"Saved updated lesson state after generating exercise for user {user_id}, lesson_id {lesson_db_id}"
            )
        except Exception as db_err:
            logger.error(
                f"Failed to save updated lesson state after exercise generation: {db_err}",
                exc_info=True,
            )
            # Decide if we should raise here or just log

        # 4. Return the newly generated exercise
        return new_exercise

    async def generate_assessment_question_for_lesson(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[AssessmentQuestion]:
        """
        Generates a new assessment question for the lesson on demand, ensuring novelty.
        """
        logger.info(
            f"Generating new assessment question for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state (similar to generate_exercise_for_lesson)
        progress_entry = self.db_service.get_lesson_progress(
            user_id, syllabus_id, module_index, lesson_index
        )
        if not progress_entry:
             logger.error(
                f"Could not load progress entry for assessment generation. User: {user_id}"
            )
             raise ValueError("Progress entry not found. Cannot generate assessment question.")

        lesson_db_id = progress_entry.get("lesson_id") # Get lesson_id from progress
        if not lesson_db_id:
             logger.error(
                f"Progress entry loaded but lesson_id is missing for assessment generation. User: {user_id}"
            )
             raise ValueError("Lesson ID missing in progress entry. Cannot generate assessment question.")

        if not progress_entry.get("lesson_state"):
            logger.error(
                f"Could not load lesson state for assessment generation. User: {user_id}"
            )
            raise ValueError(
                "Lesson state not found. Cannot generate assessment question."
            )

        current_lesson_state = progress_entry["lesson_state"]

        # Ensure generated_content is loaded and valid (similar logic)
        content_in_state = current_lesson_state.get("generated_content")
        if not isinstance(content_in_state, GeneratedLessonContent):
            logger.warning(
                "Lesson state 'generated_content' is not a Pydantic object. Reloading."
            )
            try:
                # Reload logic... (same as above)
                content_data_dict = self.db_service.get_lesson_content(
                    syllabus_id, module_index, lesson_index
                )
                if content_data_dict:
                    validated_content_obj = GeneratedLessonContent.model_validate(
                        content_data_dict
                    )
                    current_lesson_state["generated_content"] = validated_content_obj
                else:
                    raise ValueError("Failed to reload generated_content.")
            except (ValidationError, Exception) as load_err:
                logger.error(
                    f"Fatal error: Could not reload/validate generated_content: {load_err}",
                    exc_info=True,
                )
                raise ValueError(
                    "Failed to load necessary lesson content for assessment generation."
                ) from load_err

        # Ensure lesson_uid in state matches the loaded lesson_db_id
        if current_lesson_state.get("lesson_uid") != lesson_db_id:
            logger.warning(f"State lesson_uid ({current_lesson_state.get('lesson_uid')}) differs from progress lesson_id ({lesson_db_id}). Updating state.")
            current_lesson_state["lesson_uid"] = lesson_db_id
            # Save the corrected state immediately before generation
            try:
                logger.info(f"Saving corrected lesson state before assessment generation for user {user_id}")
                state_json = json.dumps(
                    current_lesson_state,
                    default=lambda o: (
                        o.model_dump(mode="json")
                        if isinstance(o, (GeneratedLessonContent, Exercise, AssessmentQuestion))
                        else o
                    ),
                )
                self.db_service.save_user_progress(
                    user_id=user_id, syllabus_id=syllabus_id, module_index=module_index,
                    lesson_index=lesson_index, status=progress_entry.get("status", "in_progress"),
                    score=progress_entry.get("score"), lesson_state_json=state_json,
                    lesson_id=lesson_db_id
                )
            except Exception as save_err:
                 logger.error(f"Failed to save corrected lesson state before assessment generation: {save_err}", exc_info=True)
                 # Decide if we should raise here or proceed with potentially inconsistent state for generation


        # 2. Call the new generation node function
        try:
            # Expect node to return updated state and the new question
            updated_state, new_question = await nodes.generate_new_assessment_question(
                current_lesson_state.copy() # Pass the potentially corrected state
            )
            if not new_question:
                logger.warning(
                    "generate_new_assessment_question node did not "
                    f"return a new question for user {user_id}."
                )
                return None

        except Exception as gen_err:
            logger.error(
                f"Error during assessment question generation node call: {gen_err}",
                exc_info=True,
            )
            raise RuntimeError(
                "Failed to generate new assessment question."
            ) from gen_err

        # 3. Save the updated state (after generation)
        try:
            updated_state_json = json.dumps(
                updated_state,
                default=lambda o: (
                    o.model_dump(mode="json")
                    if isinstance(
                        o, (GeneratedLessonContent, Exercise, AssessmentQuestion)
                    )
                    else o
                ),
            )
            current_status = "in_progress"
            current_score = updated_state.get("user_performance", {}).get("score")

            # Use the lesson_db_id retrieved from the progress entry
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id # Pass the lesson_id
            )
            logger.info(
                "Saved updated lesson state after generating assessment "
                f"question for user {user_id}, lesson_id {lesson_db_id}"
            )
        except Exception as db_err:
            logger.error(
                f"Failed to save updated lesson state after assessment generation: {db_err}",
                exc_info=True,
            )
            # Decide if we should raise here or just log

        # 4. Return the newly generated question
        return new_question

    async def get_lesson_by_id(self, lesson_id: str) -> Dict[str, Any]:
        """Retrieve a lesson by ID"""
        lesson = self.db_service.get_lesson_by_id(lesson_id)

        if not lesson:
            raise ValueError(f"Lesson with ID {lesson_id} not found")

        return lesson

    # Removed redundant evaluate_exercise method (lines 559-776).
    # Evaluation is now handled within the graph via nodes.evaluate_chat_answer

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

        # Fetch lesson_id to ensure it's included in the progress update
        lesson_db_id = None
        try:
            # Try getting from existing progress first
            progress_entry = self.db_service.get_lesson_progress(user_id, syllabus_id, module_index, lesson_index)
            if progress_entry and progress_entry.get("lesson_id"):
                lesson_db_id = progress_entry.get("lesson_id")
            else:
                # If not in progress, look up via indices
                lesson_details = await self.syllabus_service.get_lesson_details(
                    syllabus_id, module_index, lesson_index
                )
                lesson_db_id = lesson_details.get("lesson_id") # Should be int

            if not lesson_db_id:
                 logger.error(f"Could not determine lesson_id for progress update: {syllabus_id}/{module_index}/{lesson_index}")
                 raise ValueError("Could not find lesson_id for progress update.")

        except ValueError as e:
            logger.error(f"Failed to get lesson_id for progress update: {e}")
            raise ValueError("Could not find lesson details to update progress.") from e


        # Update the progress, including lesson_id
        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            status=status,
            # Score is only updated during evaluation, pass None here
            score=None,
            lesson_id=lesson_db_id # Pass the determined lesson_id
            # lesson_state_json is not updated here, only status
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,
        }
