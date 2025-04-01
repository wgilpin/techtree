# backend/services/lesson_interaction_service.py
"""
Service layer for handling lesson interactions, coordinating between the database,
AI graph, and potentially other services.
"""

# backend/services/lesson_interaction_service.py

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar, Union, cast

from fastapi import HTTPException
from pydantic import BaseModel

from backend.exceptions import log_and_propagate
from backend.ai.app import LessonAI
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
    LessonState,
)
from backend.exceptions import validate_internal_model
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.sqlite_db import SQLiteDatabaseService

# Import helpers from utility file
from .lesson_state_utils import (
    deserialize_state_data,
    format_assessment_question_for_chat_history,
    format_exercise_for_chat_history,
    prepare_state_for_response,
    serialize_state_data,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


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
    ) -> Tuple[Optional[LessonState], Optional[GeneratedLessonContent], Optional[str]]:
        """
        Loads existing lesson state or initializes a new one if not found.
        Also fetches the static lesson content and the progress record ID.

        Returns:
            A tuple containing:
                - The loaded or initialized LessonState (or None if exposition failed).
                - The fetched GeneratedLessonContent (or None if exposition failed).
                - The progress_id (str) if a progress record exists, otherwise None.

        Raises:
            ValueError: If lesson exposition cannot be fetched or generated.
            RuntimeError: If saving the initial state fails.
        """
        logger.info(
            f"Loading/Initializing state for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Fetch static lesson content (exposition, metadata)
        lesson_content: Optional[GeneratedLessonContent] = None
        lesson_db_id: Optional[int] = None
        try:
            # Assume get_or_generate_exposition returns
            # Tuple[Optional[GeneratedLessonContent], Optional[int]]
            lesson_content, lesson_db_id = (
                await self.exposition_service.get_or_generate_exposition(
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
            )
        except Exception as expo_err:
            # Use helper to log and propagate the error
            log_and_propagate(
                new_exception_type=ValueError,
                new_exception_message="Failed to get or generate lesson exposition.",
                original_exception=expo_err,
                exc_info=True,  # Keep stack trace logging
            )

        if not lesson_content:
            logger.error("Exposition service returned no content. Cannot proceed.")
            raise ValueError("Lesson content could not be loaded or generated.")

        # 2. Try to load existing user-specific progress/state from DB
        lesson_state: Optional[LessonState] = None
        progress_record = self.db_service.get_lesson_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        progress_id: Optional[str] = (
            progress_record.get("progress_id") if progress_record else None
        )

        if progress_record and progress_record.get("lesson_state"):
            state_from_db = progress_record["lesson_state"]
            if isinstance(state_from_db, dict):
                # Deserialization handles internal errors and logs them
                lesson_state = deserialize_state_data(state_from_db)
                if lesson_state:  # Check if deserialization was successful
                    logger.info(f"Loaded and deserialized state for user {user_id}.")
                    # Ensure lesson_db_id is consistent
                    if lesson_state.get("lesson_db_id") != lesson_db_id:
                        logger.warning(
                            f"Mismatch between loaded state lesson_db_id "
                            f"({lesson_state.get('lesson_db_id')}) and looked up ID "
                            f"({lesson_db_id}). Using looked up ID."
                        )
                        lesson_state["lesson_db_id"] = lesson_db_id
                else:
                    logger.warning(
                        f"Deserialization of loaded state failed for user {user_id}."
                        " Will re-initialize."
                    )
                    # lesson_state remains None
            else:
                logger.error(
                    "Loaded lesson_state from DB is not a dictionary. Will re-initialize."
                )
                # lesson_state remains None

        # 3. If no state exists or deserialization failed, initialize a new one
        if lesson_state is None:
            logger.info(
                f"No valid existing state found for user {user_id}. Initializing."
            )
            # Ensure lesson_content is not None before accessing attributes
            topic = lesson_content.topic or "Unknown Topic"
            level = lesson_content.level or "beginner"
            lesson_title = (
                lesson_content.metadata.title
                if lesson_content.metadata
                else "Untitled Lesson"
            )
            module_title = f"Module {module_index + 1}"  # Use f-string

            initial_state_dict: Dict[str, Any] = {
                "topic": topic,
                "knowledge_level": level,
                "syllabus": None,  # Consider fetching/linking syllabus if needed
                "lesson_title": lesson_title,
                "module_title": module_title,
                "generated_content": lesson_content.model_dump(mode="json"),
                "user_responses": [],
                "user_performance": {},
                "user_id": user_id,
                "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
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
                "lesson_db_id": lesson_db_id,  # Use the id fetched earlier
            }
            # Cast to LessonState for type checking
            lesson_state = cast(LessonState, initial_state_dict)

            # Generate initial welcome message using LessonAI
            # Assuming start_chat modifies the state in place or returns a new one
            lesson_state = self.lesson_ai.start_chat(lesson_state)

            # Save the newly initialized state
            try:
                state_json = serialize_state_data(lesson_state)
                # Save and get the new progress_id
                new_progress_id = self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",
                    lesson_id=lesson_db_id,  # Use the fetched lesson_db_id
                    lesson_state_json=state_json,
                )
                if new_progress_id is None:
                    # Should not happen if save_user_progress guarantees return on success
                    logger.error(
                        "save_user_progress did not return"
                        " a progress_id after saving initial state."
                    )
                    raise RuntimeError(
                        "Failed to retrieve progress ID after saving initial state."
                    )
                progress_id = new_progress_id  # Update progress_id for return value
                logger.info(
                    f"Initialized and saved new state (progress_id: {progress_id}) for user {user_id}."
                )
            except Exception as db_err:  # Catch potential DB errors
                logger.error(
                    f"Failed to save initial lesson state: {db_err}", exc_info=True
                )
                raise RuntimeError("Failed to save initial lesson state.") from db_err

        # Return the final state, content, and the progress_id
        return lesson_state, lesson_content, progress_id

# pylint: disable=too-many-branches
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
        progress_id: Optional[str] = None  # Initialize progress_id

        if user_id:
            # --- Authenticated User Flow ---
            try:
                # Capture progress_id
                loaded_state, loaded_content, progress_id = (
                    await self._load_or_initialize_state(
                        user_id, syllabus_id, module_index, lesson_index
                    )
                )
                lesson_state = loaded_state
                lesson_content = loaded_content
                if lesson_state:
                    lesson_db_id = lesson_state.get("lesson_db_id")
                else:  # Ensure lesson_db_id is initialized even if state is None initially
                    lesson_db_id = None

            except ValueError as e:
                logger.error(f"Error loading/initializing state: {e}", exc_info=True)
                raise HTTPException(status_code=404, detail=str(e)) from e
            except Exception as e:
                logger.error(f"Unexpected error getting state: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error getting lesson state.",
                ) from e

            # Prepare response structure using the new helper for authenticated users
            serializable_state_for_response = prepare_state_for_response(lesson_state)

            # Fetch conversation history if progress_id exists
            conversation_history = []
            if progress_id:
                try:
                    conversation_history = self.db_service.get_conversation_history(
                        progress_id
                    )
                    logger.info(
                        f"Fetched {len(conversation_history)} messages for progress_id {progress_id}"
                    )
                except Exception as hist_err:
                    logger.error(
                        f"Failed to fetch conversation history for progress {progress_id}: {hist_err}",
                        exc_info=True,
                    )
                    # Proceed without history, maybe add an error indicator?

            # Add history to the state dictionary before returning
            if serializable_state_for_response:
                serializable_state_for_response["conversation_history"] = (
                    conversation_history
                )
            else:
                # Handle case where state might be None but we still need a structure for history
                serializable_state_for_response = {
                    "conversation_history": conversation_history
                }

            response_data = {
                "lesson_id": lesson_db_id,
                "content": (
                    lesson_content.model_dump(mode="json") if lesson_content else None
                ),
                "lesson_state": serializable_state_for_response,  # Now includes history
            }
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

            # Prepare response structure using the new helper for unauthenticated users
            # This handles serialization of Pydantic models/datetimes within the state
            # Note: lesson_state will be None here, prepare_state_for_response handles this
            serializable_state_for_response = prepare_state_for_response(
                lesson_state
            )  # Will be None
            # No need for try-except here as the helper handles internal types;
            # JSON encoding happens at the FastAPI response level.

            response_data = {
                "lesson_id": lesson_db_id,
                "content": (
                    lesson_content.model_dump(mode="json") if lesson_content else None
                ),
                "lesson_state": serializable_state_for_response,  # Will be None
            }
        return response_data  # This return needs to be at the function level

    # pylint: disable=too-many-nested-blocks, too-many-branches, too-many-statements
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

        Raises:
            RuntimeError: If state/progress_id cannot be loaded/found.
            HTTPException: For internal server errors during processing.
        """
        logger.info(
            f"Handling chat turn for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state and progress_id
            current_state, _, progress_id = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            # _load_or_initialize_state raises ValueError if content fails,
            # which will be caught below and turned into HTTPException(404)
            if not current_state:
                # This should ideally not happen if _load_or_initialize_state works correctly
                logger.error("State is None after _load_or_initialize_state succeeded.")
                raise RuntimeError("Failed to load lesson state unexpectedly.")
            if not progress_id:
                # This case happens if initialization failed before the first save
                logger.error(
                    f"Failed to retrieve progress_id for user {user_id}, "
                    f"lesson {syllabus_id}/{module_index}/{lesson_index}. State might be new and unsaved."
                )
                raise RuntimeError(
                    "Failed to retrieve progress ID. Cannot process chat turn."
                )

            # 2. Save incoming user message
            try:
                self.db_service.save_conversation_message(
                    progress_id=progress_id,
                    role="user",
                    message_type="CHAT_USER",
                    content=user_message,
                )
            except Exception as save_err:
                logger.error(
                    f"Failed to save user message to history: {save_err}", exc_info=True
                )
                # Logged error, proceed with turn

            # 3. Get current history for AI context
            history = self.db_service.get_conversation_history(progress_id)

            # 4. Invoke the LessonAI graph - it now returns only the updated state dict
            updated_state = self.lesson_ai.process_chat_turn(
                current_state=current_state,
                user_message=user_message, # Pass original message directly
                history=history,
            )
            # Cast removed - process_chat_turn should return LessonState directly

            # 5. Extract the new assistant message from the state and save it
            saved_assistant_messages_for_response = []
            new_assistant_message = updated_state.get(
                "new_assistant_message"
            )  # Extract message

            # Remove the message from the state dict so it's not saved in the state blob itself
            if "new_assistant_message" in updated_state:
                del updated_state["new_assistant_message"]

            if (
                isinstance(new_assistant_message, dict)
                and new_assistant_message.get("role") == "assistant"
            ):
                content_to_save = new_assistant_message.get("content", "")
                metadata_to_save = new_assistant_message.get(
                    "metadata"
                )  # Get metadata if present
                try:
                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="assistant",
                        message_type="CHAT_ASSISTANT",  # Use appropriate type
                        content=content_to_save,
                        metadata=metadata_to_save,  # Pass metadata
                    )
                    # Add the successfully saved message to the list for the response payload
                    saved_assistant_messages_for_response.append(
                        {"role": "assistant", "content": content_to_save}
                    )
                except Exception as save_err:
                    logger.error(
                        f"Failed to save assistant message to history: {save_err}",
                        exc_info=True,
                    )
                    # Optionally add an error indicator to the response if save fails
                    saved_assistant_messages_for_response.append(
                        {
                            "role": "assistant",
                            "content": f"[Save Error] {content_to_save}",
                        }
                    )
            elif new_assistant_message:
                # Log if the structure is unexpected but exists
                logger.warning(
                    f"Received unexpected structure for new_assistant_message: {type(new_assistant_message)}"
                )
            # If new_assistant_message is None, nothing is saved or added to response list

            # (The rest of the function continues from here, saving the updated_state without the message)

            # 6. Save the updated state back to the database (state no longer contains the message)
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get(
                    "lesson_db_id"
                )  # Already validated or None
                status = "in_progress"  # TODO: Determine status based on state logic if needed # pylint: disable=fixme

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status=status,
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                    # score=updated_state.get("score") # Add score if relevant
                )
                logger.info(f"Saved updated state for user {user_id} after chat turn.")
            except Exception as e:
                logger.error(
                    f"Failed to save updated lesson state after chat turn: {e}",
                    exc_info=True,
                )
                # Logged error, but proceed to return messages

            # 7. Prepare response for the router
            error_message_from_state = updated_state.get("error_message")
            response_payload: Dict[str, Any] = {
                "responses": saved_assistant_messages_for_response  # Use the list built above
            }
            if error_message_from_state:
                response_payload["error"] = error_message_from_state
                # Optionally, save this error message to history as well
                try:
                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="system",  # Use 'system' for state-level errors
                        message_type="SYSTEM_ERROR",  # Added message_type
                        content=error_message_from_state,
                    )
                except Exception as save_err:
                    logger.error(
                        f"Failed to save error message from state to history: {save_err}",
                        exc_info=True,
                    )

            return response_payload

        except (ValueError, RuntimeError) as e:
            logger.error(f"Error during chat turn: {e}", exc_info=True)
            # Re-raise as HTTPException for the router
            status_code = 404 if isinstance(e, ValueError) else 500
            raise HTTPException(status_code=status_code, detail=str(e)) from e
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error during chat turn: {e}", exc_info=True)
            # Add specific detail about the error type if helpful
            error_detail = f"An internal server error occurred during chat processing: {type(e).__name__}"
            raise HTTPException(
                status_code=500,
                detail=error_detail,
            ) from e

    # --- On-Demand Generation Handling ---

    # pylint: disable=too-many-branches, too-many-statements
    async def _handle_generation_request(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        node_function: Callable[
            [Dict[str, Any]],
            Tuple[
                Dict[str, Any],
                Optional[Union[BaseModel, Dict[str, Any]]],
                Optional[Dict[str, Any]],
            ],
        ],  # Added type params for Dict
        model_cls: Type[T],
        format_function: Callable[[T], str],
        item_type_name: str,  # e.g., "exercise", "assessment question"
        metadata_key: str,  # e.g., "exercise_id"
    ) -> Dict[str, Any]:
        """
        Generic handler for generating items like exercises or assessments.

        Loads state, calls the appropriate node, validates/formats the result,
        saves messages and state, and returns the response dict.

        Raises:
            RuntimeError: If state/progress_id cannot be loaded/found or saving state fails.
            HTTPException: For internal server errors or value errors during processing.
        """
        logger.info(
            f"Handling generation request for {item_type_name} for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )  # Added missing closing parenthesis
        try:
            # 1. Load current state and progress_id
            current_state, _, progress_id = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError(
                    f"Failed to load state for {item_type_name} generation."
                )
            if not progress_id:
                logger.error(
                    f"Failed to retrieve progress_id for user {user_id}, "
                    f"lesson {syllabus_id}/{module_index}/{lesson_index}."
                )
                raise RuntimeError(
                    f"Failed to retrieve progress ID. Cannot generate {item_type_name}."
                )

            # 2. Call the specific generation node function
            # Node function now returns state_changes, generated_item, assistant_message_dict
            state_changes, new_item_obj, assistant_message_dict = node_function(
                cast(Dict[str, Any], current_state)
            )
            # Merge state changes into the current state
            # Be careful with potential overwrites if keys overlap unexpectedly
            updated_state = {**current_state, **state_changes}

            # 3. Validate the generated item object
            validated_item: Optional[T] = None
            if isinstance(new_item_obj, model_cls):
                validated_item = new_item_obj
            elif isinstance(new_item_obj, dict):
                # Use helper to validate and raise specific internal error
                validated_item = validate_internal_model(
                    model_cls,
                    new_item_obj,
                    context_message=f"Failed to validate {item_type_name} dict from node",
                )

            # 4. Determine message content and type
            assistant_message_content: Optional[str] = None

            if validated_item:
                assistant_message_content = format_function(validated_item)
                # Assuming validated_item has an 'id' attribute
                item_id = getattr(validated_item, "id", "UNKNOWN")
                logger.info(
                    f"Generated {item_type_name} {item_id} for progress {progress_id}"
                )
            else:
                # Generation failed or returned invalid object
                # Prefer message from node if available (e.g., error message from node)
                if isinstance(
                    assistant_message_dict, dict
                ) and assistant_message_dict.get("content"):
                    assistant_message_content = assistant_message_dict["content"]
                else:
                    # Check state for error message as a fallback
                    error_msg_from_state = updated_state.get("error_message")
                    if error_msg_from_state:
                        assistant_message_content = error_msg_from_state
                        logger.warning(
                            f"Using error message from state: {assistant_message_content}"
                        )
                    else:
                        # Generic fallback
                        logger.warning(
                            f"{item_type_name.capitalize()} generation failed for "
                            f"progress {progress_id}, and no specific message found."
                        )
                        assistant_message_content = (
                            f"Sorry, I couldn't generate a {item_type_name} right now."
                        )

            # Determine message type based on success/failure
            message_type: str
            if validated_item:
                # e.g., "exercise" -> "EXERCISE_PROMPT"
                # e.g., "assessment question" -> "ASSESSMENT_QUESTION_PROMPT"
                message_type = f"{item_type_name.upper().replace(' ', '_')}_PROMPT"
            else:
                message_type = "GENERATION_FAILURE"

            # 5. Save the assistant message (item prompt or failure) to history
            if assistant_message_content:  # Check if there's content to save
                try:
                    metadata = None
                    if validated_item:
                        # Assuming validated_item has an 'id' attribute
                        item_id = getattr(validated_item, "id", None)
                        if item_id:
                            metadata = {metadata_key: item_id}

                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="assistant",
                        message_type=message_type,  # Pass the determined message type
                        content=assistant_message_content,
                        metadata=metadata,
                    )
                except Exception as save_err:
                    logger.error(
                        f"Failed to save {item_type_name}/failure message to history: {save_err}",
                        exc_info=True,
                    )
                    # Continue, but the history record is missing

            # 6. Save the updated state
            try:
                # Cast updated_state before serialization
                state_json = serialize_state_data(cast(LessonState, updated_state))
                lesson_db_id = updated_state.get("lesson_db_id")

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                )
                logger.info(
                    f"Saved updated state after {item_type_name} generation attempt for user {user_id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to save state after {item_type_name} generation: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Failed to save state after {item_type_name} generation."
                ) from e

            # 7. Return the result dictionary
            return {
                item_type_name.split(" ")[0]: (
                    validated_item.model_dump(mode="json") if validated_item else None
                ),
                "message": assistant_message_content,
            }

        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Error during {item_type_name} generation: {e}", exc_info=True
            )
            status_code = 404 if isinstance(e, ValueError) else 500
            raise HTTPException(status_code=status_code, detail=str(e)) from e
        except Exception as e:
            logger.error(
                f"Unexpected error during {item_type_name} generation: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"An internal server error occurred while generating the {item_type_name}.",
            ) from e

    # --- Start of generate_exercise ---
    async def generate_exercise(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Dict[str, Any]:
        """
        Handles the request to generate a new exercise on demand.

        Delegates to _handle_generation_request.
        """
        return await self._handle_generation_request(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            node_function=nodes.generate_new_exercise,
            model_cls=Exercise,
            format_function=format_exercise_for_chat_history,
            item_type_name="exercise",
            metadata_key="exercise_id",
        )

    # --- Start of generate_assessment_question ---
    async def generate_assessment_question(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Dict[str, Any]:
        """
        Handles the request to generate a new assessment question on demand.

        Delegates to _handle_generation_request.
        """
        return await self._handle_generation_request(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            node_function=nodes.generate_new_assessment,
            model_cls=AssessmentQuestion,
            format_function=format_assessment_question_for_chat_history,
            item_type_name="assessment question",
            metadata_key="question_id",
        )

    # --- Start of update_lesson_progress ---
    async def update_lesson_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
    ) -> Dict[str, Any]:
        """
        Updates the progress status for a specific lesson.

        Args:
            user_id: The ID of the user.
            syllabus_id: The ID of the syllabus.
            module_index: The index of the module.
            lesson_index: The index of the lesson.
            status: The new status ("not_started", "in_progress", "completed").

        Returns:
            A dictionary containing the updated progress details.

        Raises:
            ValueError: If the status is invalid or lesson cannot be found.
        """
        logger.info(
            f"Updating progress for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index} to status: {status}"
        )
        # Validate status
        allowed_statuses = ["not_started", "in_progress", "completed"]
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {allowed_statuses}"
            )

        # Use save_user_progress which handles upsert logic
        try:
            # We need the lesson_id (primary key) to save progress correctly.
            # Fetch it first.
            lesson_db_id = self.db_service.get_lesson_id(
                syllabus_id, module_index, lesson_index
            )
            if lesson_db_id is None:
                raise ValueError(
                    f"Lesson not found for {syllabus_id}/{module_index}/{lesson_index}"
                )

            # Save the progress (this will update if exists)
            progress_id = self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=status,
                lesson_id=lesson_db_id,
                # We don't update lesson_state here, only status
            )

            # Return the updated progress details
            # Fetch the updated record to be sure? Or construct from input?
            # Constructing is simpler if save_user_progress doesn't return full record.
            return {
                "progress_id": progress_id,  # Assuming save_user_progress returns the ID
                "user_id": user_id,
                "syllabus_id": syllabus_id,
                "module_index": module_index,
                "lesson_index": lesson_index,
                "status": status,
            }
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)
            # Re-raise potentially as a different error type if needed
            raise RuntimeError("Failed to update lesson progress in database.") from e

    async def handle_rerun_message(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        message_content: str,
    ) -> Dict[str, Any]:
        """
        Saves a re-run message (exercise/assessment) to the conversation history
        as an assistant message without triggering AI interaction.

        Args:
            user_id: The ID of the user initiating the rerun.
            syllabus_id: The ID of the parent syllabus.
            module_index: The index of the parent module.
            lesson_index: The index of the lesson.
            message_content: The HTML content of the message to save.

        Returns:
            A dictionary indicating success or failure.

        Raises:
            HTTPException: If the progress record cannot be found or saving fails.
        """
        logger.info(
            f"Handling rerun message for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Get the progress_id (we need it to save the message)
            # We don't need the full state, just the progress record
            progress_record = self.db_service.get_lesson_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
            )
            if not progress_record or not progress_record.get("progress_id"):
                logger.error(
                    f"Could not find progress record for rerun: user {user_id}, "
                    f"lesson {syllabus_id}/{module_index}/{lesson_index}"
                )
                raise HTTPException(
                    status_code=404, detail="Lesson progress not found for rerun."
                )
            progress_id = progress_record["progress_id"]

            # 2. Save the message to history
            self.db_service.save_conversation_message(
                progress_id=progress_id,
                role="assistant", # Save as assistant message
                message_type="ASSISTANT_RERUN", # Specific type for reruns
                content=message_content,
                metadata=None, # No specific metadata needed for simple rerun
            )
            logger.info(f"Saved rerun message to history for progress_id {progress_id}")
            return {"status": "success", "message": "Rerun message saved."}

        except HTTPException as http_exc:
            # Re-raise known HTTP exceptions
            raise http_exc
        except Exception as e:
            logger.error(
                f"Unexpected error handling rerun message: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Failed to save rerun message."
            ) from e
