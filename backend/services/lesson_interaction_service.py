# backend/services/lesson_interaction_service.py
"""
Service layer for handling lesson interactions, coordinating between the database,
AI graph, and potentially other services.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError, BaseModel, model_serializer # Added model_serializer
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

# Helper function to serialize state, handling Pydantic models
def serialize_state_data(state: LessonState) -> str:
    """Converts the LessonState TypedDict, potentially containing Pydantic models, to a JSON string."""
    serializable_dict = {}
    for key, value in state.items():
        if isinstance(value, BaseModel):
            serializable_dict[key] = value.model_dump(mode='json') # Use mode='json'
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            serializable_dict[key] = [item.model_dump(mode='json') for item in value]
        elif isinstance(value, datetime): # Handle datetime objects
             serializable_dict[key] = value.isoformat()
        else:
            serializable_dict[key] = value
    return json.dumps(serializable_dict)

# Helper function to deserialize state, converting dicts back to Pydantic models
def deserialize_state_data(state_dict: Dict[str, Any]) -> LessonState:
    """Converts a dictionary (from DB) back into a LessonState structure with Pydantic models."""
    deserialized_state = state_dict.copy() # Start with a copy

    # Deserialize generated_content
    if isinstance(deserialized_state.get("generated_content"), dict):
        try:
            deserialized_state["generated_content"] = GeneratedLessonContent.model_validate(
                deserialized_state["generated_content"]
            )
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_content: {e}")
            deserialized_state["generated_content"] = None # Or handle error appropriately

    # Deserialize active_exercise
    if isinstance(deserialized_state.get("active_exercise"), dict):
        try:
            deserialized_state["active_exercise"] = Exercise.model_validate(
                deserialized_state["active_exercise"]
            )
        except ValidationError as e:
            logger.error(f"Failed to deserialize active_exercise: {e}")
            deserialized_state["active_exercise"] = None

    # Deserialize active_assessment
    if isinstance(deserialized_state.get("active_assessment"), dict):
        try:
            deserialized_state["active_assessment"] = AssessmentQuestion.model_validate(
                deserialized_state["active_assessment"]
            )
        except ValidationError as e:
            logger.error(f"Failed to deserialize active_assessment: {e}")
            deserialized_state["active_assessment"] = None

    # Deserialize conversation_history
    if isinstance(deserialized_state.get("conversation_history"), list):
        try:
            # Assuming ChatMessage is a Pydantic model or dict is fine
            # If ChatMessage is Pydantic:
            # deserialized_state["conversation_history"] = [
            #     ChatMessage.model_validate(msg) for msg in deserialized_state["conversation_history"]
            #     if isinstance(msg, dict)
            # ]
            pass # Assuming dicts are okay for history for now
        except ValidationError as e:
            logger.error(f"Failed to deserialize conversation_history: {e}")
            deserialized_state["conversation_history"] = []

    # Deserialize generated_exercises
    if isinstance(deserialized_state.get("generated_exercises"), list):
        try:
            deserialized_state["generated_exercises"] = [
                Exercise.model_validate(ex) for ex in deserialized_state["generated_exercises"]
                if isinstance(ex, dict)
            ]
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_exercises: {e}")
            deserialized_state["generated_exercises"] = []

    # Deserialize generated_assessment_questions
    if isinstance(deserialized_state.get("generated_assessment_questions"), list):
        try:
            deserialized_state["generated_assessment_questions"] = [
                AssessmentQuestion.model_validate(q) for q in deserialized_state["generated_assessment_questions"]
                if isinstance(q, dict)
            ]
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_assessment_questions: {e}")
            deserialized_state["generated_assessment_questions"] = []

    # Convert back to LessonState TypedDict type hint (runtime check won't enforce)
    return deserialized_state # type: ignore


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
        """
        logger.info(
            f"Loading/Initializing state for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Fetch static lesson content (exposition, metadata) using the correct method
        lesson_content: Optional[GeneratedLessonContent] = None
        lesson_db_id: Optional[int] = None # Store the lesson's DB ID
        try:
            lesson_content, lesson_db_id = (
                await self.exposition_service.get_or_generate_exposition(
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
            )
        except Exception as expo_err:
             logger.error(f"Error calling get_or_generate_exposition: {expo_err}", exc_info=True)
             raise ValueError("Failed to get or generate lesson exposition.") from expo_err

        if not lesson_content:
            logger.error(
                "Failed to retrieve or generate lesson content (exposition). Cannot proceed."
            )
            raise ValueError("Lesson content (exposition) could not be loaded or generated.")

        # 2. Try to load existing user-specific progress/state from DB using the correct method
        lesson_state: Optional[LessonState] = None
        progress_record = self.db_service.get_lesson_progress( # CORRECTED METHOD NAME
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )

        if progress_record and progress_record.get("lesson_state"):
            # Extract the state dictionary and deserialize Pydantic models within it
            try:
                 lesson_state = deserialize_state_data(progress_record["lesson_state"])
                 logger.info(f"Loaded and deserialized existing state for user {user_id}.")
                 # Ensure lesson_db_id is consistent
                 if "lesson_db_id" not in lesson_state or lesson_state["lesson_db_id"] is None:
                      lesson_state["lesson_db_id"] = lesson_db_id
                      logger.debug(f"Added/Updated lesson_db_id ({lesson_db_id}) to loaded state.")
                 elif lesson_state["lesson_db_id"] != lesson_db_id:
                      logger.warning(f"Mismatch between loaded state lesson_db_id ({lesson_state['lesson_db_id']}) and looked up ID ({lesson_db_id}). Using looked up ID.")
                      lesson_state["lesson_db_id"] = lesson_db_id

            except Exception as e:
                 logger.error(f"Error deserializing loaded lesson state: {e}", exc_info=True)
                 lesson_state = None # Treat as if state doesn't exist if deserialization fails

        # 3. If no state exists or deserialization failed, initialize a new one
        if lesson_state is None:
            logger.info(f"No valid existing state found for user {user_id}. Initializing.")
            topic = lesson_content.topic or "Unknown Topic"
            level = lesson_content.level or "beginner"
            lesson_title = (
                lesson_content.metadata.title
                if lesson_content.metadata
                else "Untitled Lesson"
            )
            module_title = f"Module {module_index + 1}" # Placeholder

            initial_state_dict: Dict[str, Any] = {
                "topic": topic,
                "knowledge_level": level,
                "syllabus": None,
                "lesson_title": lesson_title,
                "module_title": module_title,
                "generated_content": lesson_content.model_dump(), # Store raw dict
                "user_responses": [],
                "user_performance": {},
                "user_id": user_id,
                "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "conversation_history": [],
                "current_interaction_mode": "chatting",
                "current_exercise_index": None,
                "current_quiz_question_index": None,
                "generated_exercises": [],
                "generated_assessment_questions": [],
                "generated_exercise_ids": [],
                "generated_assessment_question_ids": [],
                "error_message": None,
                "active_exercise": None,
                "active_assessment": None,
                "potential_answer": None,
                "lesson_db_id": lesson_db_id, # Store the lesson's DB ID
            }
            lesson_state = initial_state_dict # type: ignore

            # Generate initial welcome message using LessonAI
            lesson_state = self.lesson_ai.start_chat(lesson_state) # type: ignore

            # Save the newly initialized state using the correct DB method
            try:
                state_json = serialize_state_data(lesson_state)
                self.db_service.save_user_progress( # CORRECTED METHOD NAME
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress", # Initial status
                    lesson_id=lesson_db_id, # Pass the lesson PK
                    lesson_state_json=state_json, # Pass serialized state
                )
                logger.info(f"Initialized and saved new state for user {user_id}.")
            except Exception as e:
                 logger.error(f"Failed to save initial lesson state: {e}", exc_info=True)
                 # Decide how to handle - raise error? Return state without saving?
                 raise RuntimeError("Failed to save initial lesson state.") from e

        # Ensure the state returned has Pydantic models for internal use
        # (Deserialization happens above if loaded, initialization creates dicts)
        # We might need to re-validate/deserialize the initial state if AI modifies it in start_chat
        # For now, assume start_chat returns a compatible structure or we handle it later.

        return lesson_state, lesson_content

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
        lesson_db_id: Optional[int] = None

        if user_id:
            # --- Authenticated User Flow ---
            try:
                loaded_state, loaded_content = await self._load_or_initialize_state(
                    user_id, syllabus_id, module_index, lesson_index
                )
                lesson_state = loaded_state
                lesson_content = loaded_content
                if lesson_state:
                    lesson_db_id = lesson_state.get("lesson_db_id")

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
                lesson_content, lesson_db_id = (
                    await self.exposition_service.get_or_generate_exposition(
                        syllabus_id=syllabus_id,
                        module_index=module_index,
                        lesson_index=lesson_index,
                    )
                )
                if not lesson_content:
                    raise ValueError("Lesson content could not be loaded or generated.")

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

        # Prepare response structure - serialize the state before sending back
        serializable_state_for_response = None
        if lesson_state:
             try:
                  # Use the helper to serialize the final state before returning
                  serializable_state_for_response = json.loads(serialize_state_data(lesson_state))
             except Exception as e:
                  logger.error(f"Error serializing final lesson state for response: {e}", exc_info=True)
                  # Decide how to handle - return error? Return None state?
                  raise HTTPException(status_code=500, detail="Error preparing lesson state.") from e


        response_data = {
            "lesson_id": lesson_db_id,
            "content": lesson_content.model_dump(mode='json') if lesson_content else None,
            "lesson_state": serializable_state_for_response, # Pass the JSON-compatible dict
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
            # 1. Load current state (returns state with Pydantic models)
            current_state, _ = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")

            # 2. Invoke the LessonAI graph
            updated_state = self.lesson_ai.process_chat_turn(
                current_state=current_state, user_message=user_message  # type: ignore
            )

            # 3. Save the updated state back to the database using the correct method
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id") # Get lesson PK from state
                self.db_service.save_user_progress( # CORRECTED METHOD NAME
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress", # Or derive status from state?
                    lesson_id=lesson_db_id, # Pass the lesson PK
                    lesson_state_json=state_json, # Pass serialized state
                )
                logger.info(f"Saved updated state for user {user_id}.")
            except Exception as e:
                 logger.error(f"Failed to save updated lesson state: {e}", exc_info=True)
                 # Decide how to handle - return error? Continue without saving?
                 raise RuntimeError("Failed to save updated lesson state.") from e


            # 4. Prepare response for the router
            new_messages = []
            num_current_messages = len(current_state.get("conversation_history", []))
            if (
                len(updated_state.get("conversation_history", []))
                > num_current_messages
            ):
                for msg in updated_state["conversation_history"][num_current_messages:]:
                    if msg.get("role") == "assistant":
                        new_messages.append(
                            {"role": msg.get("role"), "content": msg.get("content")}
                        )

            error_message = updated_state.get("error_message")
            response_payload: Dict[str, Any] = {"responses": new_messages}
            if error_message:
                response_payload["error"] = error_message
                # Clear error after reporting? (State needs saving again)
                # updated_state["error_message"] = None
                # state_json_cleared = serialize_state_data(updated_state)
                # self.db_service.save_user_progress(...) # Call save again

            return response_payload

        except ValueError as e:
            logger.error(f"Value error during chat turn: {e}", exc_info=True)
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during chat turn: {e}", exc_info=True)
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

            # 2. Call the generation node
            updated_state, new_exercise = nodes.generate_new_exercise(current_state) # type: ignore

            # 3. Save the updated state
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                self.db_service.save_user_progress( # CORRECTED METHOD NAME
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                )
                logger.info(
                    f"Saved updated state after exercise generation for user {user_id}."
                )
            except Exception as e:
                 logger.error(f"Failed to save state after exercise generation: {e}", exc_info=True)
                 raise RuntimeError("Failed to save state after exercise generation.") from e

            # 4. Return the generated exercise object
            if new_exercise and isinstance(new_exercise, dict):
                try:
                    return Exercise.model_validate(new_exercise)
                except ValidationError:
                    logger.error("Failed to validate exercise returned from node.")
                    return None
            elif isinstance(new_exercise, Exercise):
                return new_exercise
            else:
                return None

        except ValueError as e:
            logger.error(f"Value error during exercise generation: {e}", exc_info=True)
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error during exercise generation: {e}", exc_info=True
            )
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

            # 2. Call the generation node
            updated_state, new_question = nodes.generate_new_assessment(current_state) # type: ignore

            # 3. Save the updated state
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                self.db_service.save_user_progress( # CORRECTED METHOD NAME
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                )
                logger.info(
                    f"Saved updated state after assessment generation for user {user_id}."
                )
            except Exception as e:
                 logger.error(f"Failed to save state after assessment generation: {e}", exc_info=True)
                 raise RuntimeError("Failed to save state after assessment generation.") from e

            # 4. Return the generated question object
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
                return None

        except ValueError as e:
            logger.error(
                f"Value error during assessment generation: {e}", exc_info=True
            )
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error during assessment generation: {e}", exc_info=True
            )
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
        allowed_statuses = ["not_started", "in_progress", "completed"]
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid progress status: {status}. Must be one of {allowed_statuses}"
            )

        try:
            lesson_id_pk = self.db_service.get_lesson_id(syllabus_id, module_index, lesson_index)
            if lesson_id_pk is None:
                 raise ValueError("Cannot update progress: Lesson primary key not found.")

            # Call DB service to update progress, passing the lesson_id PK
            # Also fetch the current state to preserve it if only status is changing
            current_progress = self.db_service.get_lesson_progress(
                 user_id, syllabus_id, module_index, lesson_index
            )
            current_state_json = current_progress.get("lesson_state_json") if current_progress else None
            current_score = current_progress.get("score") if current_progress else None


            progress_id = self.db_service.save_user_progress( # CORRECTED METHOD NAME
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=status, # Update status
                lesson_id=lesson_id_pk,
                score=current_score, # Preserve score
                lesson_state_json=current_state_json, # Preserve state
            )

            if progress_id is None:
                raise ValueError(
                    "Failed to update progress record in database."
                )

            logger.info(f"Progress updated successfully for user {user_id}.")
            return {"status": "success", "progress_id": progress_id}

        except ValueError as e:
            logger.error(f"Value error updating progress: {e}", exc_info=True)
            raise e
        except Exception as e:
            logger.error(f"Unexpected error updating progress: {e}", exc_info=True)
            raise RuntimeError(
                "Failed to update progress due to an internal error."
            ) from e
