# backend/services/lesson_interaction_service.py
"""
Service layer for handling lesson interactions, coordinating between the database,
AI graph, and potentially other services.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError, BaseModel  # Added BaseModel
from fastapi import HTTPException  # Added HTTPException

from backend.ai.app import LessonAI  # Import the LessonAI class
from backend.ai.lessons import nodes  # Import nodes directly for generation functions
from backend.models import (
    AssessmentQuestion,
    ChatMessage,
    Exercise,
    GeneratedLessonContent,
    LessonState,
)
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.sqlite_db import SQLiteDatabaseService

logger = logging.getLogger(__name__)


class LessonInteractionService:
    """
    Manages the state and interaction logic for lessons, including chat and
    on-demand content generation.
    """

    def __init__(
        self,
        db_service: SQLiteDatabaseService,
        exposition_service: LessonExpositionService,
        lesson_ai: LessonAI,
    ):
        """
        Initializes the LessonInteractionService.

        Args:
            db_service: Instance of the database service.
            exposition_service: Instance of the exposition service.
            lesson_ai: Instance of the LessonAI graph application.
        """
        self.db_service = db_service
        self.exposition_service = exposition_service
        self.lesson_ai = lesson_ai
        logger.info("LessonInteractionService initialized.")

    async def _load_or_initialize_state(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Tuple[Optional[LessonState], Optional[GeneratedLessonContent]]:
        """
        Loads existing lesson state or initializes a new one if not found.
        Also fetches the static lesson content.

        TODO: If LessonAI needs to call generate_exercise/assessment,
              it might need the full state including generated content.
              Consider how state is passed and updated.
        """
        logger.info(
            f"Loading/Initializing state for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Fetch static lesson content (exposition, metadata)
        lesson_content: Optional[GeneratedLessonContent] = (
            await self.exposition_service.get_or_generate_lesson_content(
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                user_id=user_id,  # Pass user_id if needed by exposition service
            )
        )

        if not lesson_content:
            logger.error(
                "Failed to retrieve or generate lesson content. Cannot proceed."
            )
            # Raise error or return None? Raising might be better upstream.
            raise ValueError("Lesson content could not be loaded or generated.")

        # 2. Try to load existing user-specific state from DB
        lesson_state: Optional[LessonState] = self.db_service.get_lesson_state(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )

        # 3. If no state exists, initialize a new one
        if lesson_state is None:
            logger.info(f"No existing state found for user {user_id}. Initializing.")
            # Extract necessary info from lesson_content for initial state
            topic = lesson_content.topic or "Unknown Topic"
            level = lesson_content.level or "beginner"  # Default level?
            lesson_title = (
                lesson_content.metadata.title
                if lesson_content.metadata
                else "Untitled Lesson"
            )
            # Get module title (assuming exposition service can provide it or look up syllabus)
            # This might require an extra call or data structure adjustment
            module_title = f"Module {module_index + 1}"  # Placeholder

            # Create the initial state structure matching LessonState TypedDict
            initial_state_dict: Dict[str, Any] = {
                "topic": topic,
                "knowledge_level": level,  # Assuming level maps to knowledge_level
                "syllabus": None,  # TODO: Load syllabus if needed by AI graph
                "lesson_title": lesson_title,
                "module_title": module_title,  # Placeholder
                "generated_content": lesson_content.model_dump(),  # Store raw dict for now
                "user_responses": [],
                "user_performance": {},
                "user_id": user_id,
                "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",  # Example UID
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "conversation_history": [],
                "current_interaction_mode": "chatting",  # Start in chat mode
                "current_exercise_index": None,
                "current_quiz_question_index": None,
                "generated_exercises": [],
                "generated_assessment_questions": [],
                "generated_exercise_ids": [],
                "generated_assessment_question_ids": [],
                "error_message": None,
                # Add fields for active items
                "active_exercise": None,
                "active_assessment": None,
                "potential_answer": None,
            }
            # Validate against LessonState TypedDict (runtime check won't enforce structure strictly)
            lesson_state = initial_state_dict  # type: ignore

            # Generate initial welcome message using LessonAI
            # Pass the validated initial_state dictionary
            lesson_state = self.lesson_ai.start_chat(lesson_state)  # type: ignore

            # Save the newly initialized state (including welcome message)
            # Ensure state is serializable before saving
            serializable_initial_state = {}
            for key, value in lesson_state.items():
                if isinstance(value, BaseModel):
                    serializable_initial_state[key] = value.model_dump()
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], BaseModel)
                ):
                    serializable_initial_state[key] = [
                        item.model_dump() for item in value
                    ]
                else:
                    serializable_initial_state[key] = value

            self.db_service.save_lesson_state(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                state_data=serializable_initial_state,  # Save serialized state
            )
            logger.info(f"Initialized and saved new state for user {user_id}.")

        else:
            logger.info(f"Loaded existing state for user {user_id}.")
            # Ensure loaded state has necessary keys, potentially merge with defaults
            # This is crucial if the LessonState structure changes over time.
            # For now, assume loaded state is valid.
            # Deserialize generated_content back into Pydantic model if needed by AI graph
            # Also deserialize active_exercise and active_assessment if they exist
            if isinstance(lesson_state.get("generated_content"), dict):
                try:
                    # Store the model in a different key to avoid type conflicts if needed later
                    lesson_state["generated_content_model"] = (
                        GeneratedLessonContent.model_validate(
                            lesson_state["generated_content"]
                        )
                    )
                except ValidationError:
                    logger.error("Failed to validate stored generated_content.")
                    lesson_state["generated_content_model"] = None  # Handle error state
            else:
                lesson_state["generated_content_model"] = None

            if isinstance(lesson_state.get("active_exercise"), dict):
                try:
                    lesson_state["active_exercise"] = Exercise.model_validate(
                        lesson_state["active_exercise"]
                    )
                except ValidationError:
                    logger.error("Failed to validate stored active_exercise.")
                    lesson_state["active_exercise"] = None
            elif (
                lesson_state.get("active_exercise") is not None
            ):  # If it's not a dict and not None, log warning
                logger.warning(
                    f"Stored active_exercise is not a dict: {type(lesson_state.get('active_exercise'))}"
                )
                lesson_state["active_exercise"] = None  # Clear invalid data

            if isinstance(lesson_state.get("active_assessment"), dict):
                try:
                    lesson_state["active_assessment"] = (
                        AssessmentQuestion.model_validate(
                            lesson_state["active_assessment"]
                        )
                    )
                except ValidationError:
                    logger.error("Failed to validate stored active_assessment.")
                    lesson_state["active_assessment"] = None
            elif (
                lesson_state.get("active_assessment") is not None
            ):  # If it's not a dict and not None, log warning
                logger.warning(
                    f"Stored active_assessment is not a dict: {type(lesson_state.get('active_assessment'))}"
                )
                lesson_state["active_assessment"] = None  # Clear invalid data

        return lesson_state, lesson_content  # Return state and static content

    async def get_or_create_lesson_state(
        self,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves the lesson content and the user's state for a specific lesson.
        If no user is provided, only static content is returned.
        If a user is provided but has no state, initializes it.

        Returns a dictionary suitable for the LessonDataResponse model.
        """
        logger.info(
            f"Get/Create state request: user={user_id}, "
            f"lesson={syllabus_id}/{module_index}/{lesson_index}"
        )

        lesson_state: Optional[LessonState] = None
        lesson_content: Optional[GeneratedLessonContent] = None
        lesson_db_id: Optional[int] = None  # To store the actual lesson ID from DB

        if user_id:
            # --- Authenticated User Flow ---
            try:
                # Load/initialize state AND get content
                loaded_state, loaded_content = await self._load_or_initialize_state(
                    user_id, syllabus_id, module_index, lesson_index
                )
                lesson_state = loaded_state
                lesson_content = loaded_content

                # Get the actual lesson ID from the database if available in state
                # This assumes the exposition service or state initialization stores it
                # We might need a more direct way to get this ID.
                # Placeholder: Try getting it from the loaded content's metadata if stored there
                # Or look it up based on syllabus_id/module/lesson indices
                lesson_lookup = self.db_service.get_lesson_indices_by_id(
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
                if lesson_lookup:
                    lesson_db_id = lesson_lookup.get("lesson_pk")

            except ValueError as e:
                logger.error(f"Error loading/initializing state: {e}", exc_info=True)
                raise HTTPException(status_code=404, detail=str(e)) from e
            except Exception as e:
                logger.error(f"Unexpected error getting state: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error getting lesson state.",
                ) from e
        else:
            # --- Unauthenticated User Flow ---
            logger.info("Unauthenticated user request. Fetching only static content.")
            try:
                # Only fetch static content
                lesson_content = (
                    await self.exposition_service.get_or_generate_lesson_content(
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        user_id=None,  # Indicate no user
                    )
                )
                if not lesson_content:
                    raise ValueError("Lesson content could not be loaded or generated.")

                # Get lesson DB ID (same logic as above, might need refinement)
                lesson_lookup = self.db_service.get_lesson_indices_by_id(
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
                if lesson_lookup:
                    lesson_db_id = lesson_lookup.get("lesson_pk")

            except ValueError as e:
                logger.error(f"Error loading static content: {e}", exc_info=True)
                raise HTTPException(status_code=404, detail=str(e)) from e
            except Exception as e:
                logger.error(
                    f"Unexpected error getting static content: {e}", exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error getting lesson content.",
                ) from e

        # Prepare response structure
        # Ensure the state is JSON serializable (Pydantic models need dumping)
        serializable_state = None
        if lesson_state:
            serializable_state = {}
            for key, value in lesson_state.items():
                # Check if value is a Pydantic model instance before dumping
                if isinstance(value, BaseModel):
                    serializable_state[key] = value.model_dump()
                # Check if value is a list containing Pydantic models
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], BaseModel)
                ):
                    serializable_state[key] = [item.model_dump() for item in value]
                # Otherwise, assume it's already serializable (dict, str, int, etc.)
                else:
                    serializable_state[key] = value

        response_data = {
            "lesson_id": lesson_db_id,  # The actual DB ID of the lesson
            "content": lesson_content.model_dump() if lesson_content else None,
            "lesson_state": serializable_state,  # Pass the serialized state
        }
        return response_data

    async def handle_chat_turn(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Processes a single turn of the chat conversation.

        Loads state, invokes the LessonAI graph, saves the updated state,
        and returns the AI responses.
        """
        logger.info(
            f"Handling chat turn for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state (and content, though maybe not needed directly here)
            current_state, _ = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                # This shouldn't happen if _load_or_initialize_state raises errors
                raise RuntimeError("Failed to load or initialize lesson state.")

            # 2. Invoke the LessonAI graph
            # Ensure the state passed matches the LessonState structure expected by the graph
            updated_state = self.lesson_ai.process_chat_turn(
                current_state=current_state, user_message=user_message  # type: ignore
            )

            # 3. Save the updated state back to the database
            # Ensure state is serializable before saving
            serializable_updated_state = {}
            for key, value in updated_state.items():
                if isinstance(value, BaseModel):
                    serializable_updated_state[key] = value.model_dump()
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], BaseModel)
                ):
                    serializable_updated_state[key] = [
                        item.model_dump() for item in value
                    ]
                else:
                    serializable_updated_state[key] = value

            self.db_service.save_lesson_state(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                state_data=serializable_updated_state,  # Save the serialized version
            )
            logger.info(f"Saved updated state for user {user_id}.")

            # 4. Prepare response for the router
            # Extract only the AI responses from the latest turn
            # The graph should append messages to conversation_history
            new_messages = []
            # Use the original state for comparison before it was potentially modified by serialization
            num_current_messages = len(current_state.get("conversation_history", []))
            if (
                len(updated_state.get("conversation_history", []))
                > num_current_messages
            ):
                # Find messages added in this turn (usually just the last one)
                for msg in updated_state["conversation_history"][num_current_messages:]:
                    if msg.get("role") == "assistant":
                        # Ensure message structure matches ChatMessage for response model
                        new_messages.append(
                            {"role": msg.get("role"), "content": msg.get("content")}
                        )

            # Check for errors set by the graph
            error_message = updated_state.get("error_message")

            response_payload: Dict[str, Any] = {"responses": new_messages}
            if error_message:
                response_payload["error"] = error_message
                # Clear error after reporting?
                updated_state["error_message"] = None
                # Save again to clear error (use serialized state)
                serializable_updated_state["error_message"] = None
                self.db_service.save_lesson_state(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    state_data=serializable_updated_state,
                )

            return response_payload

        except ValueError as e:
            logger.error(f"Value error during chat turn: {e}", exc_info=True)
            # Re-raise or return error structure? Re-raising seems appropriate here.
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during chat turn: {e}", exc_info=True)
            # Return error structure for the router to handle
            return {"responses": [], "error": "An internal server error occurred."}

    async def generate_exercise(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[Exercise]:
        """
        Handles the request to generate a new exercise on demand.

        Loads state, calls the specific generation node, saves state, returns exercise.
        """
        logger.info(
            f"Generating exercise for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state
            current_state, _ = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")

            # 2. Call the generation node directly (synchronous)
            # The node function returns the updated state and the generated item
            updated_state, new_exercise = nodes.generate_new_exercise(current_state)  # type: ignore

            # 3. Save the updated state (ensure it's serializable)
            serializable_updated_state = {}
            for key, value in updated_state.items():
                if isinstance(value, BaseModel):
                    serializable_updated_state[key] = value.model_dump()
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], BaseModel)
                ):
                    serializable_updated_state[key] = [
                        item.model_dump() for item in value
                    ]
                else:
                    serializable_updated_state[key] = value

            self.db_service.save_lesson_state(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                state_data=serializable_updated_state,  # Save serialized state
            )
            logger.info(
                f"Saved updated state after exercise generation for user {user_id}."
            )

            # 4. Return the generated exercise object (or None if failed)
            # Ensure the returned object is the Pydantic model instance
            if new_exercise and isinstance(new_exercise, dict):
                # If the node returned a dict, try to validate it back
                try:
                    return Exercise.model_validate(new_exercise)
                except ValidationError:
                    logger.error("Failed to validate exercise returned from node.")
                    return None
            elif isinstance(new_exercise, Exercise):
                return new_exercise
            else:
                return None  # Return None if generation failed or type is wrong

        except ValueError as e:
            logger.error(f"Value error during exercise generation: {e}", exc_info=True)
            raise e  # Let the router handle 404 etc.
        except Exception as e:
            logger.error(
                f"Unexpected error during exercise generation: {e}", exc_info=True
            )
            # Raise a runtime error for the router to catch as 500
            raise RuntimeError(
                "Failed to generate exercise due to an internal error."
            ) from e

    async def generate_assessment_question(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[AssessmentQuestion]:
        """
        Handles the request to generate a new assessment question on demand.

        Loads state, calls the specific generation node, saves state, returns question.
        """
        logger.info(
            f"Generating assessment question for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state
            current_state, _ = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")

            # 2. Call the generation node directly (synchronous)
            # Corrected function name used here
            updated_state, new_question = nodes.generate_new_assessment(current_state)  # type: ignore

            # 3. Save the updated state (ensure it's serializable)
            serializable_updated_state = {}
            for key, value in updated_state.items():
                if isinstance(value, BaseModel):
                    serializable_updated_state[key] = value.model_dump()
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], BaseModel)
                ):
                    serializable_updated_state[key] = [
                        item.model_dump() for item in value
                    ]
                else:
                    serializable_updated_state[key] = value

            self.db_service.save_lesson_state(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                state_data=serializable_updated_state,  # Save serialized state
            )
            logger.info(
                f"Saved updated state after assessment generation for user {user_id}."
            )

            # 4. Return the generated question object (or None if failed)
            # Ensure the returned object is the Pydantic model instance
            if new_question and isinstance(new_question, dict):
                try:
                    return AssessmentQuestion.model_validate(new_question)
                except ValidationError:
                    logger.error(
                        "Failed to validate assessment question returned from node."
                    )
                    return None
            elif isinstance(new_question, AssessmentQuestion):
                return new_question
            else:
                return None  # Return None if generation failed or type is wrong

        except ValueError as e:
            logger.error(
                f"Value error during assessment generation: {e}", exc_info=True
            )
            raise e  # Let the router handle 404 etc.
        except Exception as e:
            logger.error(
                f"Unexpected error during assessment generation: {e}", exc_info=True
            )
            # Raise a runtime error for the router to catch as 500
            raise RuntimeError(
                "Failed to generate assessment question due to an internal error."
            ) from e

    async def update_lesson_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
    ) -> Dict[str, Any]:
        """
        Updates the progress status for a specific lesson for the user.
        """
        logger.info(
            f"Updating progress for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index} to status: {status}"
        )
        # Validate status
        allowed_statuses = ["not_started", "in_progress", "completed"]
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid progress status: {status}. Must be one of {allowed_statuses}"
            )

        try:
            # Call DB service to update progress
            progress_record = self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=status,
                # Pass None for score/details unless available
                score=None,
                details=None,
            )
            if progress_record is None:
                # This might happen if the lesson doesn't exist for lookup within save_user_progress
                raise ValueError(
                    "Failed to update progress. Lesson or user might not exist."
                )

            logger.info(f"Progress updated successfully for user {user_id}.")
            # Return the updated progress record details
            return progress_record  # This should be a dictionary

        except ValueError as e:
            logger.error(f"Value error updating progress: {e}", exc_info=True)
            raise e  # Let router handle 400/404
        except Exception as e:
            logger.error(f"Unexpected error updating progress: {e}", exc_info=True)
            raise RuntimeError(
                "Failed to update progress due to an internal error."
            ) from e
