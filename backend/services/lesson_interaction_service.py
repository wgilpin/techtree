# backend/services/lesson_interaction_service.py
"""
Service layer for handling lesson interactions, coordinating between the database,
AI graph, and potentially other services.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, cast

from pydantic import (
    ValidationError,
    BaseModel,
)
from fastapi import HTTPException

from backend.ai.app import LessonAI
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
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
    # Add explicit type hint
    serializable_dict: Dict[str, Any] = {}
    # Ensure state is treated as a dictionary
    state_items = state.items() if isinstance(state, dict) else []
    for key, value in state_items:
        if isinstance(value, BaseModel):
            serializable_dict[key] = value.model_dump(mode="json")
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            # This assignment is now clearly compatible with Dict[str, Any]
            serializable_dict[key] = [item.model_dump(mode="json") for item in value]
        elif isinstance(value, datetime):
            # This assignment is now clearly compatible
            serializable_dict[key] = value.isoformat()
        else:
            # This assignment is now clearly compatible
            serializable_dict[key] = value
    return json.dumps(serializable_dict)


# Helper function to deserialize state, converting dicts back to Pydantic models
def deserialize_state_data(state_dict: Dict[str, Any]) -> LessonState:
    """Converts a dictionary (from DB) back into a LessonState structure with Pydantic models."""
    deserialized_state = state_dict.copy()

    # Deserialize generated_content
    if isinstance(deserialized_state.get("generated_content"), dict):
        try:
            deserialized_state["generated_content"] = (
                GeneratedLessonContent.model_validate(
                    deserialized_state["generated_content"]
                )
            )
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_content: {e}")
            deserialized_state["generated_content"] = None

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

    # Deserialize generated_exercises
    if isinstance(deserialized_state.get("generated_exercises"), list):
        try:
            deserialized_state["generated_exercises"] = [
                Exercise.model_validate(ex)
                for ex in deserialized_state["generated_exercises"]
                if isinstance(ex, dict)
            ]
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_exercises: {e}")
            deserialized_state["generated_exercises"] = []

    # Deserialize generated_assessment_questions
    if isinstance(deserialized_state.get("generated_assessment_questions"), list):
        try:
            deserialized_state["generated_assessment_questions"] = [
                AssessmentQuestion.model_validate(q)
                for q in deserialized_state["generated_assessment_questions"]
                if isinstance(q, dict)
            ]
        except ValidationError as e:
            logger.error(f"Failed to deserialize generated_assessment_questions: {e}")
            deserialized_state["generated_assessment_questions"] = []

    # Cast to LessonState type hint
    return cast(LessonState, deserialized_state)


def _format_exercise_for_chat_history(exercise: Exercise) -> str:
    """Formats an Exercise object into an HTML string for chat history."""
    if not exercise:
        return "<p><em>Error: Could not format exercise.</em></p>"

    # Use model_dump to get a dictionary, handling potential None values
    exercise_dict = exercise.model_dump(mode='json')

    exercise_type = exercise_dict.get('type', 'unknown').replace('_', ' ')
    instructions = exercise_dict.get('instructions') or exercise_dict.get('question') or 'N/A'
    options = exercise_dict.get('options', [])
    items = exercise_dict.get('items', [])

    content_html = f'<div class="generated-item exercise-item">'
    content_html += f'<h3>Exercise ({exercise_type})</h3>'
    content_html += f'<p><strong>Instructions:</strong> {instructions}</p>'

    if exercise_dict.get('type') == 'multiple_choice' and options:
        content_html += '<ul>'
        for opt in options:
            opt_id = opt.get('id', '?')
            opt_text = opt.get('text', '')
            content_html += f'<li><strong>{opt_id})</strong> {opt_text}</li>'
        content_html += '</ul>'
        content_html += '<p><small><em>Submit your answer (e.g., \"A\") in the chat.</em></small></p>'
    elif exercise_dict.get('type') == 'ordering' and items:
        content_html += '<p><strong>Items to order:</strong></p><ul>'
        for item in items:
            content_html += f'<li>{item}</li>'
        content_html += '</ul>'
        content_html += '<p><small><em>Submit your ordered list (e.g., \"Item B, Item A, Item C\") in the chat.</em></small></p>'
    else:
        content_html += '<p><small><em>Submit your answer in the chat.</em></small></p>' # Indent this line

    content_html += '</div>' # This should be outside the else
    return content_html # This should be outside the else


def _format_assessment_question_for_chat_history(question: AssessmentQuestion) -> str:
    """Formats an AssessmentQuestion object into an HTML string for chat history."""
    if not question:
        return "<p><em>Error: Could not format assessment question.</em></p>"

    question_dict = question.model_dump(mode='json')

    q_type = question_dict.get('type', 'unknown').replace('_', ' ')
    q_text = question_dict.get('question_text', 'N/A')
    options = question_dict.get('options', [])

    content_html = f'<div class="generated-item assessment-item">'
    content_html += f'<h3>Assessment Question ({q_type})</h3>'
    content_html += f'<p>{q_text}</p>'

    if (question_dict.get('type') == 'multiple_choice' or question_dict.get('type') == 'true_false') and options:
        content_html += '<ul>'
        for opt in options:
            opt_id = opt.get('id', '?')
            opt_text = opt.get('text', '')
            content_html += f'<li><strong>{opt_id})</strong> {opt_text}</li>'
        content_html += '</ul>'
        if question_dict.get('type') == 'multiple_choice':
            content_html += '<p><small><em>Submit your answer (e.g., \"A\") in the chat.</em></small></p>'
        else: # true_false
            content_html += '<p><small><em>Submit your answer (\"True\" or \"False\") in the chat.</em></small></p>'
    else: # short_answer
        content_html += '<p><small><em>Submit your answer in the chat.</em></small></p>'

    content_html += '</div>'
    return content_html


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
    ) -> Tuple[Optional[LessonState], Optional[GeneratedLessonContent], Optional[str]]: # Added progress_id
        """
        Loads existing lesson state or initializes a new one if not found.
        Also fetches the static lesson content.
        """
        logger.info(
            f"Loading/Initializing state for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Fetch static lesson content (exposition, metadata)
        lesson_content: Optional[GeneratedLessonContent] = None
        lesson_db_id: Optional[int] = None
        try:
            lesson_content, lesson_db_id = (
                await self.exposition_service.get_or_generate_exposition(
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
            )
        except Exception as expo_err:
            logger.error(
                f"Error calling get_or_generate_exposition: {expo_err}", exc_info=True
            )
            raise ValueError(
                "Failed to get or generate lesson exposition."
            ) from expo_err

        if not lesson_content:
            logger.error(
                "Failed to retrieve or generate lesson content (exposition). Cannot proceed."
            )
            raise ValueError(
                "Lesson content (exposition) could not be loaded or generated."
            )
        # Ensure lesson_db_id is an int if found
        if lesson_db_id is not None and not isinstance(lesson_db_id, int):
             logger.error(f"Exposition service returned non-integer lesson_db_id: {lesson_db_id}")
             lesson_db_id = None # Treat as not found if type is wrong

        # 2. Try to load existing user-specific progress/state from DB
        lesson_state: Optional[LessonState] = None
        progress_record = self.db_service.get_lesson_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )

        if progress_record and progress_record.get("lesson_state"):
            try:
                # Ensure the state from DB is a dict before deserializing
                state_from_db = progress_record["lesson_state"]
                if isinstance(state_from_db, dict):
                    lesson_state = deserialize_state_data(state_from_db)
                    logger.info(
                        f"Loaded and deserialized existing state for user {user_id}."
                    )
                    # Ensure lesson_db_id is consistent
                    if lesson_state.get("lesson_db_id") != lesson_db_id:
                        logger.warning(
                            f"Mismatch between loaded state lesson_db_id ({lesson_state.get('lesson_db_id')}) "
                            f"and looked up ID ({lesson_db_id}). Using looked up ID."
                        )
                        lesson_state["lesson_db_id"] = lesson_db_id
                else:
                    logger.error("Loaded lesson_state from DB is not a dictionary.")
                    lesson_state = None

            except Exception as e:
                logger.error(
                    f"Error deserializing loaded lesson state: {e}", exc_info=True
                )
                lesson_state = None

        # 3. If no state exists or deserialization failed, initialize a new one
        if lesson_state is None:
            logger.info(
                f"No valid existing state found for user {user_id}. Initializing."
            )
            topic = lesson_content.topic or "Unknown Topic"
            level = lesson_content.level or "beginner"
            lesson_title = (
                lesson_content.metadata.title
                if lesson_content.metadata
                else "Untitled Lesson"
            )
            module_title = f"Module {module_index + 1}"

            initial_state_dict: Dict[str, Any] = {
                "topic": topic,
                "knowledge_level": level,
                "syllabus": None,
                "lesson_title": lesson_title,
                "module_title": module_title,
                "generated_content": lesson_content.model_dump(),
                "user_responses": [],
                "user_performance": {},
                "user_id": user_id,
                "lesson_uid": f"{syllabus_id}_{module_index}_{lesson_index}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                # "conversation_history": [], # Removed, handled by separate table
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
                "lesson_db_id": lesson_db_id,
            }
            # Cast to LessonState for type checking, though it's a dict at runtime
            lesson_state = cast(LessonState, initial_state_dict)

            # Generate initial welcome message using LessonAI
            lesson_state = self.lesson_ai.start_chat(lesson_state)

            # Save the newly initialized state
            try:
                state_json = serialize_state_data(lesson_state)
                # Ensure lesson_db_id is int or None before saving
                lesson_id_to_save = lesson_state.get("lesson_db_id")
                if lesson_id_to_save is not None and not isinstance(lesson_id_to_save, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_id_to_save)}) before saving initial state.")
                     lesson_id_to_save = None # Or raise error

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress",
                    lesson_id=lesson_id_to_save,
                    lesson_state_json=state_json,
                )
                logger.info(f"Initialized and saved new state for user {user_id}.")
            except Exception as e:
                logger.error(f"Failed to save initial lesson state: {e}", exc_info=True)
                raise RuntimeError("Failed to save initial lesson state.") from e

        # Get progress_id from the record (it might be None if initialization failed before saving)
        progress_id = progress_record.get("progress_id") if progress_record else None
        return lesson_state, lesson_content, progress_id

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
                # Unpack 3 values, ignore progress_id with '_'
                loaded_state, loaded_content, _ = await self._load_or_initialize_state(
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
                serializable_state_for_response = json.loads(
                    serialize_state_data(lesson_state)
                )
            except Exception as e:
                logger.error(
                    f"Error serializing final lesson state for response: {e}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500, detail="Error preparing lesson state."
                ) from e

        response_data = {
            "lesson_id": lesson_db_id,
            "content": (
                lesson_content.model_dump(mode="json") if lesson_content else None
            ),
            "lesson_state": serializable_state_for_response,
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
            # 1. Load current state and progress_id
            current_state, _, progress_id = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                # Error already logged in _load_or_initialize_state if content failed
                raise RuntimeError("Failed to load or initialize lesson state.")
            if not progress_id:
                 # This case happens if initialization failed before the first save
                 logger.error(f"Failed to retrieve progress_id for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}. State might be new and unsaved.")
                 raise RuntimeError("Failed to retrieve progress ID. Cannot process chat turn.")

            # 2. Save incoming user message
            try:
                self.db_service.save_conversation_message(
                    progress_id=progress_id,
                    role="user",
                    message_type="CHAT_USER", # Simplified user type
                    content=user_message
                )
            except Exception as save_err:
                 logger.error(f"Failed to save user message to history: {save_err}", exc_info=True)
                 # Logged error, proceed with turn but history context might be incomplete

            # 3. Get current history for AI context
            history = self.db_service.get_conversation_history(progress_id)

            # 4. Invoke the LessonAI graph (ASSUMES MODIFIED SIGNATURE AND RETURN VALUE)
            # Pass history, expect updated state and list of new assistant messages back
            # TODO: Modify LessonAI.process_chat_turn signature and implementation
            updated_state, new_assistant_messages = self.lesson_ai.process_chat_turn(
                current_state=current_state,
                user_message=user_message,
                history=history # Pass history to AI
            )

            # 5. Save new assistant messages to history
            saved_assistant_messages_for_response = []
            if isinstance(new_assistant_messages, list):
                for msg_data in new_assistant_messages:
                    if isinstance(msg_data, dict) and msg_data.get("role") == "assistant":
                        # Determine message type based on interaction mode in updated_state
                        interaction_mode = updated_state.get("current_interaction_mode", "chatting")
                        message_type = "CHAT_ASSISTANT" # Default
                        if interaction_mode == "awaiting_answer":
                            # Check if feedback is related to exercise or assessment
                            # This logic might need refinement based on how feedback is structured
                            if updated_state.get("active_exercise"):
                                message_type = "EXERCISE_FEEDBACK"
                            elif updated_state.get("active_assessment"):
                                message_type = "ASSESSMENT_FEEDBACK"
                        elif interaction_mode == "error":
                             message_type = "ERROR"
                        # Add other specific types if needed (e.g., SYSTEM_INFO)

                        try:
                            self.db_service.save_conversation_message(
                                progress_id=progress_id,
                                role="assistant",
                                message_type=message_type,
                                content=msg_data.get("content", ""),
                                metadata=msg_data.get("metadata") # Pass optional metadata if AI provides it
                            )
                            # Add to list to return to frontend
                            saved_assistant_messages_for_response.append(
                                {"role": "assistant", "content": msg_data.get("content", "")}
                            )
                        except Exception as save_err:
                            logger.error(f"Failed to save assistant message to history: {save_err}", exc_info=True)
                            # Add to response even if save failed, maybe with an indicator?
                            saved_assistant_messages_for_response.append(
                                {"role": "assistant", "content": f"[Save Error] {msg_data.get('content', '')}"}
                            )

            # 6. Save the updated state (without history) back to the database
            try:
                # Ensure state is serializable (should be handled by serialize_state_data)
                # updated_state should be compatible with LessonState after graph execution
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                if lesson_db_id is not None and not isinstance(lesson_db_id, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_db_id)}) before saving state after chat turn.")
                     lesson_db_id = None

                # Determine status based on state if possible, otherwise default to in_progress
                status = "in_progress" # TODO: Potentially update based on state logic

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status=status,
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                    # score=updated_state.get("score") # Add score if relevant here
                )
                logger.info(f"Saved updated state for user {user_id} after chat turn.")
            except Exception as e:
                logger.error(f"Failed to save updated lesson state after chat turn: {e}", exc_info=True)
                # Logged error, but proceed to return messages if any were generated

            # 7. Prepare response for the router
            error_message = updated_state.get("error_message")
            response_payload: Dict[str, Any] = {"responses": saved_assistant_messages_for_response}
            if error_message:
                # If there was an error message in the state, ensure it's included
                # even if it wasn't saved as a separate history message of type ERROR
                response_payload["error"] = error_message
                # Optionally, save this error message to history as well
                try:
                     self.db_service.save_conversation_message(
                         progress_id=progress_id, role="system", message_type="ERROR", content=error_message
                     )
                except Exception as save_err:
                     logger.error(f"Failed to save error message to history: {save_err}", exc_info=True)


            return response_payload

        except ValueError as e:
            logger.error(f"Value error during chat turn: {e}", exc_info=True)
            raise e # Re-raise specific value errors
        except Exception as e:
            logger.error(f"Unexpected error during chat turn: {e}", exc_info=True)
            # Generic error response if something else went wrong
            return {"responses": [], "error": "An internal server error occurred during chat processing."}
            return {"responses": [], "error": "An internal server error occurred."}

    async def generate_exercise(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Dict[str, Any]: # Return dict for router
        """
        Handles the request to generate a new exercise on demand.
        """
        logger.info(
            f"Generating exercise for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state and progress_id
            current_state, _, progress_id = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")
            if not progress_id:
                 logger.error(f"Failed to retrieve progress_id for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}.")
                 raise RuntimeError("Failed to retrieve progress ID. Cannot generate exercise.")

            # 2. Call the generation node (cast state to Dict)
            # TODO: Ideally, modify node to not add messages to state directly
            updated_state_dict, new_exercise_obj, assistant_message_dict = nodes.generate_new_exercise(
                cast(Dict[str, Any], current_state)
            )
            updated_state = cast(LessonState, updated_state_dict) # Cast result back

            # 3. Process generated exercise or failure message
            validated_exercise: Optional[Exercise] = None
            assistant_message_content: Optional[str] = None
            message_type: str = "SYSTEM_INFO" # Default type

            if isinstance(new_exercise_obj, Exercise):
                validated_exercise = new_exercise_obj
            elif isinstance(new_exercise_obj, dict):
                 try:
                     validated_exercise = Exercise.model_validate(new_exercise_obj)
                 except ValidationError:
                     logger.error("Failed to validate exercise dict returned from node.")

            if validated_exercise:
                # Format and save exercise prompt
                assistant_message_content = _format_exercise_for_chat_history(validated_exercise)
                message_type = "EXERCISE_PROMPT"
                logger.info(f"Generated exercise {validated_exercise.id} for progress {progress_id}")
            else:
                # Exercise generation failed or returned invalid object
                error_msg_from_state = updated_state.get("error_message")
                if error_msg_from_state:
                     assistant_message_content = error_msg_from_state
                     logger.warning(f"Exercise generation failed for progress {progress_id}. Using error message from state: {assistant_message_content}")
                else:
                     logger.warning(f"Exercise generation failed for progress {progress_id}, and no error message found in state.")
                     assistant_message_content = "Sorry, I couldn't generate an exercise right now." # Generic fallback
                message_type = "ERROR"


            # 4. Save the assistant message (exercise or failure) to history
            if assistant_message_content:
                try:
                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="assistant",
                        message_type=message_type,
                        content=assistant_message_content,
                        metadata={"exercise_id": validated_exercise.id} if validated_exercise else None
                    )
                except Exception as save_err:
                    logger.error(f"Failed to save exercise/failure message to history: {save_err}", exc_info=True)
                    # Continue, but the history record is missing

            # 5. Save the updated state (without history)
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                if lesson_db_id is not None and not isinstance(lesson_db_id, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_db_id)}) before saving exercise state.")
                     lesson_db_id = None

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
                    f"Saved updated state after exercise generation for user {user_id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to save state after exercise generation: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    "Failed to save state after exercise generation."
                ) from e

            # 6. Return the generated exercise object and the message content in a dict
            return {
                 "exercise": validated_exercise.model_dump(mode='json') if validated_exercise else None,
                 "message": assistant_message_content # Return the message determined earlier
            }

        except ValueError as e: # Specific exception first
             logger.error(f"Value error during exercise generation: {e}", exc_info=True)
             # Return dict indicating failure
             return {"exercise": None, "message": str(e)}
        except Exception as e: # Generic exception last
            logger.error(
                f"Unexpected error during exercise generation: {e}", exc_info=True
            )
            # Return dict indicating failure
            return {"exercise": None, "message": "An internal server error occurred while generating the exercise."}

    async def generate_assessment_question(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Dict[str, Any]: # Changed return type to Dict
        """
        Handles the request to generate a new assessment question on demand.
        Returns a dictionary containing the question object (if successful) and the message content.
        """
        logger.info(
            f"Generating assessment question for user {user_id}, lesson "
            f"{syllabus_id}/{module_index}/{lesson_index}"
        )
        try:
            # 1. Load current state and progress_id
            current_state, _, progress_id = await self._load_or_initialize_state(
                user_id, syllabus_id, module_index, lesson_index
            )
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")
            if not progress_id:
                 logger.error(f"Failed to retrieve progress_id for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}.")
                 raise RuntimeError("Failed to retrieve progress ID. Cannot generate assessment.")

            # 2. Call the generation node (cast state to Dict)
            # TODO: Ideally, modify node to not add messages to state directly
            updated_state_dict, new_question_obj, assistant_message_dict = nodes.generate_new_assessment(
                cast(Dict[str, Any], current_state)
            )
            updated_state = cast(LessonState, updated_state_dict) # Cast result back

            # 3. Process generated question object
            validated_question: Optional[AssessmentQuestion] = None
            if isinstance(new_question_obj, AssessmentQuestion):
                validated_question = new_question_obj
            elif isinstance(new_question_obj, dict):
                 try:
                     validated_question = AssessmentQuestion.model_validate(new_question_obj)
                 except ValidationError:
                     logger.error("Failed to validate assessment dict returned from node.")

            # 4. Determine message content and type from node's return
            assistant_message_content: Optional[str] = None
            message_type: str = "SYSTEM_INFO" # Default type
            if isinstance(assistant_message_dict, dict):
                assistant_message_content = assistant_message_dict.get("content")
                # Infer type based on success/failure
                if validated_question:
                    message_type = "ASSESSMENT_PROMPT"
                else:
                    # Assume failure message is ERROR type if no question generated
                    message_type = "ERROR"
            else:
                # Fallback if node didn't return a message dict
                logger.warning("Node generate_new_assessment did not return a message dictionary.")
                if validated_question:
                     assistant_message_content = "Generated assessment question." # Generic success
                     message_type = "ASSESSMENT_PROMPT"
                else:
                     assistant_message_content = "Failed to generate assessment question." # Generic failure
                     message_type = "ERROR"


            # 5. Save the assistant message (question prompt or failure) to history
            if assistant_message_content:
                try:
                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="assistant",
                        message_type=message_type,
                        content=assistant_message_content,
                        metadata={"assessment_question_id": validated_question.id} if validated_question else None
                    )
                except Exception as save_err:
                    logger.error(f"Failed to save assessment/failure message to history: {save_err}", exc_info=True)
                    # Continue, but history record is missing

            # 6. Save the updated state (without history)
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                if lesson_db_id is not None and not isinstance(lesson_db_id, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_db_id)}) before saving assessment state.")
                     lesson_db_id = None

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress", # Assuming generating assessment keeps it in progress
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                )
                logger.info(
                    f"Saved updated state after assessment generation attempt for user {user_id}."
                )
            except Exception as e:
                logger.error(f"Failed to save updated lesson state after assessment generation: {e}", exc_info=True)
                # If state save fails, the generated assessment might be lost on next load

            # 7. Return the generated question object (or None) and the message content
            return {
                 "question": validated_question.model_dump(mode='json') if validated_question else None,
                 "message": assistant_message_content # Return the message shown to the user
            }

        except ValueError as e: # Specific exceptions first
             logger.error(f"Value error during assessment generation: {e}", exc_info=True)
             return {"question": None, "message": str(e)}
        except Exception as e: # Generic exception last
            logger.error(f"Unexpected error during assessment generation: {e}", exc_info=True)
            return {"question": None, "message": "An internal server error occurred while generating the assessment question."}
            if not current_state:
                raise RuntimeError("Failed to load or initialize lesson state.")
            if not progress_id:
                 logger.error(f"Failed to retrieve progress_id for user {user_id}, lesson {syllabus_id}/{module_index}/{lesson_index}.")
                 raise RuntimeError("Failed to retrieve progress ID. Cannot generate assessment.")

            # 2. Call the generation node (cast state to Dict)
            # TODO: Ideally, modify node to not add messages to state directly
            updated_state_dict, new_question_obj, assistant_message_dict = nodes.generate_new_assessment(
                cast(Dict[str, Any], current_state)
            )
            updated_state = cast(LessonState, updated_state_dict) # Cast result back

            # 3. Process generated question or failure message
            # Variables are defined within the if/else blocks below

            if isinstance(new_question_obj, AssessmentQuestion):
                validated_question = new_question_obj
            elif isinstance(new_question_obj, dict):
                 try:
                     validated_question = AssessmentQuestion.model_validate(new_question_obj)
                 except ValidationError:
                     logger.error("Failed to validate assessment dict returned from node.")

            if validated_question:
                # Format and save assessment prompt
                assistant_message_content = _format_assessment_question_for_chat_history(validated_question)
                message_type = "ASSESSMENT_PROMPT"
                logger.info(f"Generated assessment question {validated_question.id} for progress {progress_id}")
            else:
                # Extract failure message added by the node (assuming it adds one)
                # This part is fragile and depends on node implementation
                # We should ideally modify the node to return the message instead of relying on state diff
                original_history = current_state.get("conversation_history", []) # History before node call (will be empty/None now)
                current_history = updated_state.get("conversation_history", []) # History after node call (if node still modifies it)
                if isinstance(current_history, list) and len(current_history) > len(original_history):
                     last_message = current_history[-1]
                     if isinstance(last_message, dict) and last_message.get("role") == "assistant":
                         assistant_message_content = last_message.get("content")
                         message_type = "ERROR"
                         logger.warning(f"Assessment generation failed for progress {progress_id}. Extracted message: {assistant_message_content}")
                     else:
                          logger.warning(f"Assessment generation failed for progress {progress_id}, but no assistant message found in state diff.")
                          assistant_message_content = "Sorry, I encountered an issue generating an assessment question."
                          message_type = "ERROR"
                else:
                     # If node doesn't add to history anymore, check for error message in state
                     error_msg_from_state = updated_state.get("error_message")
                     if error_msg_from_state:
                          assistant_message_content = error_msg_from_state
                          message_type = "ERROR"
                          logger.warning(f"Assessment generation failed for progress {progress_id}. Using error message from state: {assistant_message_content}")
                     else:
                          logger.warning(f"Assessment generation failed for progress {progress_id}, and no message found.")
                          assistant_message_content = "Sorry, I couldn't generate an assessment question right now."
                          message_type = "ERROR"


            # 4. Save the assistant message (question or failure) to history
            if assistant_message_content:
                try:
                    self.db_service.save_conversation_message(
                        progress_id=progress_id,
                        role="assistant",
                        message_type=message_type,
                        content=assistant_message_content,
                        metadata={"assessment_question_id": validated_question.id} if validated_question else None
                    )
                except Exception as save_err:
                    logger.error(f"Failed to save assessment/failure message to history: {save_err}", exc_info=True)
                    # Continue, but history record is missing

            # 5. Save the updated state (without history)
            try:
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                if lesson_db_id is not None and not isinstance(lesson_db_id, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_db_id)}) before saving assessment state.")
                     lesson_db_id = None

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status="in_progress", # Assuming generating assessment keeps it in progress
                    lesson_id=lesson_db_id,
                    lesson_state_json=state_json,
                )
                logger.info(
                    f"Saved updated state after assessment generation attempt for user {user_id}."
                )
            except Exception as e:
                logger.error(f"Failed to save updated lesson state after assessment generation: {e}", exc_info=True)
                # If state save fails, the generated assessment might be lost on next load

            # 6. Return the generated question object (or None) and the message content
            return {
                 "question": validated_question.model_dump(mode='json') if validated_question else None,
                 "message": assistant_message_content # Return the message shown to the user
            }

        except ValueError as e:
             logger.error(f"Value error during assessment generation: {e}", exc_info=True)
             # Return None or raise specific exception? Returning a dict indicates failure.
             return {"question": None, "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error during assessment generation: {e}", exc_info=True)
            return {"question": None, "message": "An internal server error occurred while generating the assessment question."}


            # 4. Save the updated state (which now includes the assessment message)
            try:
                # Cast before serializing
                state_json = serialize_state_data(updated_state)
                lesson_db_id = updated_state.get("lesson_db_id")
                # Ensure lesson_db_id is int or None before saving
                if lesson_db_id is not None and not isinstance(lesson_db_id, int):
                     logger.error(f"Invalid lesson_db_id type ({type(lesson_db_id)}) before saving assessment state.")
                     lesson_db_id = None

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
                    f"Saved updated state after assessment generation for user {user_id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to save state after assessment generation: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    "Failed to save state after assessment generation."
                ) from e

            # 4. Return the generated question object
            if isinstance(new_question_obj, AssessmentQuestion):
                 return new_question_obj
            elif isinstance(new_question_obj, dict):
                 try:
                     return AssessmentQuestion.model_validate(new_question_obj)
                 except ValidationError:
                     logger.error("Failed to validate assessment dict returned from node.")
                     return None
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
            lesson_id_pk = self.db_service.get_lesson_id(
                syllabus_id, module_index, lesson_index
            )
            if lesson_id_pk is None:
                raise ValueError(
                    "Cannot update progress: Lesson primary key not found."
                )

            # Call DB service to update progress, passing the lesson_id PK
            # Also fetch the current state to preserve it if only status is changing
            current_progress = self.db_service.get_lesson_progress(
                user_id, syllabus_id, module_index, lesson_index
            )
            current_state_json = (
                current_progress.get("lesson_state_json") if current_progress else None
            )
            current_score = current_progress.get("score") if current_progress else None

            progress_id = self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=status,
                lesson_id=lesson_id_pk, # Pass the validated int PK
                score=current_score,
                lesson_state_json=current_state_json,
            )

            if progress_id is None:
                raise ValueError("Failed to update progress record in database.")

            logger.info(f"Progress updated successfully for user {user_id}.")
            return {"status": "success", "progress_id": progress_id}

        except ValueError as e: # Specific exception first
            logger.error(f"Value error updating progress: {e}", exc_info=True)
            raise e
        except Exception as e: # Generic exception last
            logger.error(f"Unexpected error updating progress: {e}", exc_info=True)
            raise RuntimeError(
                "Failed to update progress due to an internal error."
            ) from e
