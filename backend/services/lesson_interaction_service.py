"""
Service responsible for managing the interactive state of a lesson,
including chat, exercises, and assessments.
"""
# pylint: disable=broad-exception-caught

import json
from typing import Any, Dict, Optional

from backend.ai.app import LessonAI
from backend.ai.lessons import nodes  # Needed for generate_exercise/assessment calls
from backend.logger import logger
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
)
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService


class LessonInteractionService:
    """
    Service focused on the user's interactive experience within a lesson.

    This service orchestrates the retrieval or creation of a user's lesson state,
    handles chat interactions by coordinating with the LessonAI component,
    manages the generation of on-demand exercises and assessment questions (potentially
    triggered by LessonAI), and updates the user's progress status. It relies on
    LessonExpositionService to obtain the static lesson content.
    """

    def __init__(
        self,
        db_service: SQLiteDatabaseService,
        syllabus_service: SyllabusService,
        exposition_service: LessonExpositionService,
        lesson_ai: LessonAI,
    ):
        """
        Initializes the service with necessary dependencies.

        Args:
            db_service: Service for database interactions.
            syllabus_service: Service for retrieving syllabus details.
            exposition_service: Service for retrieving static lesson exposition.
            lesson_ai: The AI component handling chat logic.
        """
        self.db_service = db_service
        self.syllabus_service = syllabus_service
        self.exposition_service = exposition_service
        self.lesson_ai = lesson_ai
        # TODO: If LessonAI needs to call generate_exercise/assessment,
        # it might need a reference to this service instance.
        # This could be done via a setter or passing `self` during AI processing.
        # Example: self.lesson_ai.set_interaction_service(self)

    async def _initialize_lesson_state(
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
        lesson_db_id: int,  # Expect non-optional int here
    ) -> Dict[str, Any]:
        """
        Helper function to create and initialize lesson state.

        Args:
            topic: The lesson topic.
            level: The knowledge level.
            syllabus_id: The syllabus ID.
            module_title: The module title.
            lesson_title: The lesson title.
            generated_content: The validated static exposition content.
            user_id: The user ID.
            module_index: The module index.
            lesson_index: The lesson index.
            lesson_db_id: The database ID of the lesson content.

        Returns:
            The initialized lesson state dictionary.
        """
        logger.info(
            f"Initializing lesson state for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index} (lesson_id: {lesson_db_id})"
        )

        initial_state = {
            "topic": topic,
            "knowledge_level": level,
            "syllabus_id": syllabus_id,
            "lesson_title": lesson_title,
            "module_title": module_title,
            "generated_content": generated_content,  # Store the object directly
            "user_id": user_id,
            "lesson_uid": lesson_db_id,  # Use the integer lesson_id as the UID
            "conversation_history": [],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "user_responses": [],
            "user_performance": {},
        }

        if not user_id:  # No need to call AI if no user
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
            ):
                fallback_message = {
                    "role": "assistant",
                    "content": f"Welcome to the lesson on '{lesson_title}'! Let's begin.",
                }
                initial_state["conversation_history"] = [fallback_message]
                initial_state["current_interaction_mode"] = "chatting"
                logger.warning(
                    "Added fallback welcome message as start_chat failed or returned no history."
                )

        return initial_state

    async def get_or_create_lesson_state(
        self,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gets existing lesson state or creates a new one, ensuring exposition exists.

        Args:
            syllabus_id: The ID of the syllabus.
            module_index: The index of the module.
            lesson_index: The index of the lesson.
            user_id: The optional ID of the user.

        Returns:
            A dictionary containing the lesson state, exposition content, and metadata.
            Structure: {
                "lesson_id": int,
                "content": GeneratedLessonContent,
                "lesson_state": Optional[Dict]
            }

        Raises:
            ValueError: If lesson exposition cannot be found or generated.
            RuntimeError: If state initialization or saving fails.
        """
        logger.info(
            f"Getting/Creating lesson state: syllabus={syllabus_id}, mod={module_index},"
            f" lesson={lesson_index}, user={user_id}"
        )

        # 1. Get or Generate Exposition Content and ID
        exposition_content_obj, lesson_db_id = (
            await self.exposition_service.get_or_generate_exposition(
                syllabus_id, module_index, lesson_index
            )
        )

        if exposition_content_obj is None or lesson_db_id is None:
            logger.error(
                "Failed to get or generate exposition for "
                f"{syllabus_id}/{module_index}/{lesson_index}"
            )
            raise ValueError(
                "Could not retrieve or generate lesson exposition content."
            )

        # If no user, just return the content
        if not user_id:
            return {
                "lesson_id": lesson_db_id,
                "content": exposition_content_obj,
                "lesson_state": None,
            }

        # 2. Fetch User Progress & State
        lesson_state = None
        progress_entry = self.db_service.get_lesson_progress(
            user_id, syllabus_id, module_index, lesson_index
        )

        state_needs_saving = False
        if progress_entry:
            # Verify lesson_id consistency
            progress_lesson_id = progress_entry.get("lesson_id")
            if progress_lesson_id != lesson_db_id:
                logger.warning(
                    f"Progress entry lesson_id ({progress_lesson_id}) mismatch with "
                    f"fetched/generated lesson_id ({lesson_db_id}) for user {user_id}, lesson "
                    f"{syllabus_id}/{module_index}/{lesson_index}. Using {lesson_db_id}."
                )
                # Force state re-initialization if IDs mismatch? Or just update progress entry?
                # For now, let's assume we proceed with lesson_db_id and
                # potentially initialize state below.
                # Mark state as needing saving if we load it.

            if "lesson_state" in progress_entry and progress_entry["lesson_state"]:
                lesson_state = progress_entry["lesson_state"]
                logger.info(f"Loaded existing lesson state for user {user_id}")

                # Ensure content object and lesson_uid are up-to-date in loaded state
                if (
                    not isinstance(
                        lesson_state.get("generated_content"), GeneratedLessonContent
                    )
                    or lesson_state.get("generated_content").exposition_content
                    != exposition_content_obj.exposition_content
                ):
                    logger.warning("Updating generated_content in loaded state.")
                    lesson_state["generated_content"] = exposition_content_obj
                    state_needs_saving = True

                if lesson_state.get("lesson_uid") != lesson_db_id:
                    logger.warning(
                        "Updating lesson_uid in loaded state from "
                        f"{lesson_state.get('lesson_uid')} to {lesson_db_id}."
                    )
                    lesson_state["lesson_uid"] = lesson_db_id
                    state_needs_saving = True

            else:
                logger.info(f"Progress entry found but no state for user {user_id}")
        else:
            logger.info(f"No existing progress entry found for user {user_id}")

        # 3. Initialize State if Needed
        if lesson_state is None:
            logger.info(
                f"Initializing new lesson state for user {user_id}, lesson_id {lesson_db_id}."
            )
            try:
                # Fetch necessary details for state initialization
                syllabus = await self.syllabus_service.get_syllabus(syllabus_id)
                module_details = await self.syllabus_service.get_module_details(
                    syllabus_id, module_index
                )
                module_title = module_details.get("title", "Unknown Module")
                lesson_title = (
                    exposition_content_obj.metadata.title
                    if exposition_content_obj.metadata
                    else "Unknown Lesson"
                )
                topic = exposition_content_obj.topic or syllabus.get(
                    "topic", "Unknown Topic"
                )
                level = exposition_content_obj.level or syllabus.get(
                    "level", "beginner"
                )

                # Call the helper function to initialize state
                lesson_state = await self._initialize_lesson_state(
                    topic=topic,
                    level=level,
                    syllabus_id=syllabus_id,
                    module_title=module_title,
                    lesson_title=lesson_title,
                    generated_content=exposition_content_obj,
                    user_id=user_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    lesson_db_id=lesson_db_id,
                )
                state_needs_saving = True  # Newly initialized state needs saving

            except Exception as init_err:
                logger.error(
                    f"Failed to initialize lesson state: {init_err}",
                    exc_info=True,
                )
                raise RuntimeError("Failed to initialize lesson state") from init_err

        # 4. Save State if it was newly initialized or updated
        if state_needs_saving:
            try:
                logger.info(
                    f"Saving lesson state for user {user_id}, lesson_id {lesson_db_id}"
                )
                state_json = json.dumps(
                    lesson_state,
                    default=lambda o: (
                        o.model_dump(mode="json")
                        if isinstance(
                            o, (GeneratedLessonContent, Exercise, AssessmentQuestion)
                        )
                        else o
                    ),
                )
                # Determine status and score (use existing if available, else defaults)
                current_status = (
                    progress_entry.get("status", "in_progress")
                    if progress_entry
                    else "in_progress"
                )
                current_score = progress_entry.get("score") if progress_entry else None

                self.db_service.save_user_progress(
                    user_id=user_id,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    status=current_status,
                    score=current_score,
                    lesson_state_json=state_json,
                    lesson_id=lesson_db_id,
                )
                logger.info(
                    f"Successfully saved lesson state for user {user_id}, lesson_id {lesson_db_id}"
                )
            except Exception as save_err:
                logger.error(f"Failed to save lesson state: {save_err}", exc_info=True)
                # Decide whether to raise or just log
                raise RuntimeError("Failed to save lesson state") from save_err

        # 5. Return the final structure
        return {
            "lesson_id": lesson_db_id,
            "content": exposition_content_obj,
            "lesson_state": lesson_state,
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
            user_id: The ID of the user.
            syllabus_id: The ID of the syllabus.
            module_index: The index of the module.
            lesson_index: The index of the lesson.
            user_message: The message sent by the user.

        Returns:
            Dict[str, Any]: Containing the AI's response message(s) or an error.
            Structure: {"responses": List[Dict]} or {"error": str}
        """
        logger.info(
            f"Handling chat turn for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state using the new orchestrator method
        try:
            lesson_data = await self.get_or_create_lesson_state(
                syllabus_id, module_index, lesson_index, user_id
            )
            current_lesson_state = lesson_data.get("lesson_state")
            lesson_db_id = lesson_data.get("lesson_id")

            if not current_lesson_state or not lesson_db_id:
                # This shouldn't happen if get_or_create_lesson_state
                # works correctly for a given user_id
                logger.error(
                    f"Failed to retrieve valid state or lesson_id for chat turn. User: {user_id}"
                )
                raise ValueError("Could not load lesson state for chat.")

        except (ValueError, RuntimeError) as load_err:
            logger.error(
                f"Error loading state for chat turn: {load_err}", exc_info=True
            )
            return {
                "error": "Sorry, I couldn't load the lesson data to process your message."
            }

        # 2. Call LessonAI.process_chat_turn
        try:
            # LessonAI modifies the state internally
            updated_lesson_state = self.lesson_ai.process_chat_turn(
                current_state=current_lesson_state, user_message=user_message
            )
        except Exception as ai_err:
            logger.error(
                f"Error during LessonAI.process_chat_turn: {ai_err}", exc_info=True
            )
            return {"error": "Sorry, I encountered an error processing your message."}

        # 2.5 Apply Adaptivity Rules (Example - kept from original)
        # This logic might be better placed within LessonAI or a dedicated adaptivity component
        try:
            user_responses = updated_lesson_state.get("user_responses", [])
            # ... (rest of adaptivity logic from original service remains the same) ...
            if len(user_responses) >= 2:
                last_response = user_responses[-1]
                prev_response = user_responses[-2]
                if "evaluation" in last_response and "evaluation" in prev_response:
                    last_eval = last_response["evaluation"]
                    prev_eval = prev_response["evaluation"]
                    last_type = last_response.get("question_type")
                    prev_type = prev_response.get("question_type")
                    if (
                        not last_eval.get("is_correct", True)
                        and not prev_eval.get("is_correct", True)
                        and last_type == prev_type
                        and last_type is not None
                    ):
                        logger.warning(
                            f"Adaptivity Alert: User {user_id} answered 2 consecutive "
                            f"{last_type} questions incorrectly. "
                            f"(Last Q: {last_response.get('question_id', 'unknown')}, "
                            f"Prev Q: {prev_response.get('question_id', 'unknown')})"
                        )
            elif user_responses:
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

        # 3. Serialize and save the updated state
        try:
            updated_state_json = json.dumps(
                updated_lesson_state,
                default=lambda o: (
                    o.model_dump(mode="json")
                    if isinstance(
                        o, (GeneratedLessonContent, Exercise, AssessmentQuestion)
                    )
                    else o
                ),
            )
            current_status = "in_progress"  # Assume still in progress after chat
            current_score = updated_lesson_state.get("user_performance", {}).get(
                "score"
            )

            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id,  # Use the ID confirmed at the start
            )
            logger.info(
                f"Saved updated lesson state for user {user_id}, lesson_id {lesson_db_id}"
            )
        except Exception as db_err:
            logger.error(
                f"Failed to save updated lesson state after chat turn: {db_err}",
                exc_info=True,
            )
            # Log but don't prevent response return

        # 4. Return the AI's response(s)
        # Find messages added in the last turn
        last_user_msg_index = -1
        history = updated_lesson_state.get("conversation_history", [])
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                last_user_msg_index = i
                break
        ai_responses = history[last_user_msg_index + 1 :]

        return {"responses": ai_responses}

    async def generate_exercise(  # Renamed
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[Exercise]:
        """
        Generates a new exercise for the lesson on demand, ensuring novelty.
        Likely called by LessonAI during process_chat_turn.

        Args:
            user_id: The user ID.
            syllabus_id: The syllabus ID.
            module_index: The module index.
            lesson_index: The lesson index.

        Returns:
            The generated Exercise object or None if generation failed.

        Raises:
            ValueError: If lesson state cannot be loaded.
            RuntimeError: If exercise generation via node fails.
        """
        logger.info(
            f"Generating new exercise for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state (using the orchestrator is safer)
        try:
            lesson_data = await self.get_or_create_lesson_state(
                syllabus_id, module_index, lesson_index, user_id
            )
            current_lesson_state = lesson_data.get("lesson_state")
            lesson_db_id = lesson_data.get("lesson_id")

            if not current_lesson_state or not lesson_db_id:
                logger.error(
                    "Failed to retrieve valid state or lesson_id for exercise generation. "
                    f"User: {user_id}"
                )
                raise ValueError("Could not load lesson state for exercise generation.")

        except (ValueError, RuntimeError) as load_err:
            logger.error(
                f"Error loading state for exercise generation: {load_err}",
                exc_info=True,
            )
            # Re-raise or return None? Re-raise for clarity.
            raise ValueError(
                "Failed to load lesson state for exercise generation."
            ) from load_err

        # 2. Call the generation node function (assuming LessonAI doesn't do this)
        # If LessonAI *does* handle this, this method might just be a placeholder
        # or only handle saving if the node returns the exercise object directly.
        # For now, assume this service calls the node as per original structure.
        try:
            # Pass state to the node
            updated_state, new_exercise = await nodes.generate_new_exercise(
                current_lesson_state.copy()  # Pass a copy
            )
            if not new_exercise:
                logger.warning(
                    f"generate_new_exercise node did not return a new exercise for user {user_id}."
                )
                # Need to save the updated_state even if no exercise generated? Yes.
            else:
                # Assuming Exercise model now uses 'id' field
                logger.info(f"Successfully generated exercise: {new_exercise.id}")

        except Exception as gen_err:
            logger.error(
                f"Error during exercise generation node call: {gen_err}", exc_info=True
            )
            raise RuntimeError("Failed to generate new exercise.") from gen_err

        # 3. Save the updated state (returned from the node)
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

            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id,
            )
            logger.info(
                "Saved updated lesson state after generating exercise for user "
                f"{user_id}, lesson_id {lesson_db_id}"
            )
        except Exception as db_err:
            logger.error(
                f"Failed to save updated lesson state after exercise generation: {db_err}",
                exc_info=True,
            )
            # Log but return the exercise if generated

        # 4. Return the newly generated exercise
        return new_exercise

    async def generate_assessment_question(  # Renamed
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Optional[AssessmentQuestion]:
        """
        Generates a new assessment question for the lesson on demand.
        Likely called by LessonAI.

        Args:
            user_id: The user ID.
            syllabus_id: The syllabus ID.
            module_index: The module index.
            lesson_index: The lesson index.

        Returns:
            The generated AssessmentQuestion object or None.

        Raises:
            ValueError: If lesson state cannot be loaded.
            RuntimeError: If question generation via node fails.
        """
        logger.info(
            f"Generating new assessment question for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index}"
        )

        # 1. Load current lesson state (using orchestrator)
        try:
            lesson_data = await self.get_or_create_lesson_state(
                syllabus_id, module_index, lesson_index, user_id
            )
            current_lesson_state = lesson_data.get("lesson_state")
            lesson_db_id = lesson_data.get("lesson_id")

            if not current_lesson_state or not lesson_db_id:
                logger.error(
                    "Failed to retrieve valid state or lesson_id for assessment generation. "
                    f"User: {user_id}"
                )
                raise ValueError(
                    "Could not load lesson state for assessment generation."
                )

        except (ValueError, RuntimeError) as load_err:
            logger.error(
                f"Error loading state for assessment generation: {load_err}",
                exc_info=True,
            )
            raise ValueError(
                "Failed to load lesson state for assessment generation."
            ) from load_err

        # 2. Call the generation node function (assuming this service calls it)
        try:
            updated_state, new_question = await nodes.generate_new_assessment_question(
                current_lesson_state.copy()  # Pass a copy
            )
            if not new_question:
                logger.warning(
                    "generate_new_assessment_question node did not "
                    f"return a new question for user {user_id}."
                )
                # Save updated state anyway
            else:
                # Assuming AssessmentQuestion model now uses 'id' field
                logger.info(
                    f"Successfully generated assessment question: {new_question.id}"
                )

        except Exception as gen_err:
            logger.error(
                f"Error during assessment question generation node call: {gen_err}",
                exc_info=True,
            )
            raise RuntimeError(
                "Failed to generate new assessment question."
            ) from gen_err

        # 3. Save the updated state (returned from the node)
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

            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status=current_status,
                score=current_score,
                lesson_state_json=updated_state_json,
                lesson_id=lesson_db_id,
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
            # Log but return question if generated

        # 4. Return the newly generated question
        return new_question

    async def update_lesson_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
    ) -> Dict[str, Any]:
        """
        Update user's progress status for a specific lesson.

        Args:
            user_id: The user ID.
            syllabus_id: The syllabus ID.
            module_index: The module index.
            lesson_index: The lesson index.
            status: The new progress status ("not_started", "in_progress", "completed").

        Returns:
            A dictionary confirming the update.

        Raises:
            ValueError: If status is invalid or lesson details cannot be found.
        """
        logger.info(
            f"Updating progress for user {user_id}, "
            f"lesson {syllabus_id}/{module_index}/{lesson_index} to {status}"
        )
        # Validate status
        if status not in ["not_started", "in_progress", "completed"]:
            raise ValueError(f"Invalid status: {status}")

        # Fetch lesson_id to ensure it's included in the progress update
        lesson_db_id = None
        progress_entry = None  # Keep track of existing entry
        try:
            # Try getting from existing progress first
            progress_entry = self.db_service.get_lesson_progress(
                user_id, syllabus_id, module_index, lesson_index
            )
            if progress_entry and progress_entry.get("lesson_id"):
                lesson_db_id = progress_entry.get("lesson_id")
                logger.debug(
                    f"Found lesson_id {lesson_db_id} in existing progress for status update."
                )
            else:
                # If not in progress, look up via indices using
                # exposition service (indirectly syllabus service)
                _, lesson_db_id = (
                    await self.exposition_service.get_or_generate_exposition(
                        syllabus_id, module_index, lesson_index
                    )
                )
                if lesson_db_id:
                    logger.debug(
                        f"Determined lesson_id {lesson_db_id} "
                        "via exposition service for status update."
                    )
                else:
                    # This case means exposition couldn't be found/generated either
                    logger.error(
                        "Could not determine lesson_id via exposition service for progress update:"
                        f" {syllabus_id}/{module_index}/{lesson_index}"
                    )
                    raise ValueError(
                        "Could not find lesson details via exposition service for progress update."
                    )

            if not isinstance(lesson_db_id, int):  # Final check
                logger.error(
                    "Failed to determine a valid integer lesson_id "
                    f"for progress update. Found: {lesson_db_id}"
                )
                raise ValueError("Could not determine lesson ID for progress update.")

        except ValueError as e:
            logger.error(f"Failed to get lesson_id for progress update: {e}")
            raise  # Re-raise the ValueError

        # Update the progress, including lesson_id
        # Preserve existing score and state if only status is changing
        current_score = progress_entry.get("score") if progress_entry else None
        current_state_json = (
            json.dumps(progress_entry.get("lesson_state"))
            if progress_entry and progress_entry.get("lesson_state")
            else None
        )

        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            status=status,
            score=current_score,  # Preserve score
            lesson_state_json=current_state_json,  # Preserve state
            lesson_id=lesson_db_id,  # Pass the determined lesson_id
        )
        logger.info(
            f"Progress status updated to {status} for lesson_id {lesson_db_id}, user {user_id}."
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,
        }
