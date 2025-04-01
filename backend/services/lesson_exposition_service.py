"""
Service responsible for generating and retrieving static lesson exposition content.
"""

# pylint: disable=broad-exception-caught

import json
from typing import Any, Dict, Optional, Tuple

from google.api_core.exceptions import ResourceExhausted

from backend.ai.llm_utils import MODEL as llm_model
from backend.ai.llm_utils import call_with_retry
from backend.ai.prompt_loader import load_prompt
from backend.exceptions import (log_and_propagate, log_and_raise_new,
                                validate_internal_model)
from backend.logger import logger
from backend.models import GeneratedLessonContent, Metadata
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService


class LessonExpositionService:
    """
    Service focused on the static exposition part of a lesson.

    Handles the generation of initial lesson text content using an LLM,
    saving this content to the database, and retrieving existing content
    based on syllabus/module/lesson indices or by the lesson's database ID.
    It does not manage user state or interactive elements like chat or exercises.
    """

    def __init__(
        self, db_service: SQLiteDatabaseService, syllabus_service: SyllabusService
    ) -> None:  # Added return type hint
        """
        Initializes the service with database and syllabus access.

        Args:
            db_service: Service for database interactions.
            syllabus_service: Service for retrieving syllabus details.
        """
        self.db_service = db_service
        self.syllabus_service = syllabus_service

    async def _generate_and_save_exposition(
        self,
        syllabus: Dict[str, Any],  # Added type parameters
        lesson_title: str,
        knowledge_level: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
    ) -> Tuple[GeneratedLessonContent, int]:
        """
        Generates lesson exposition using the LLM, validates it, saves it to the DB,
        and returns the validated content object along with the lesson's database ID.

        Args:
            syllabus: The syllabus dictionary (matching SyllabusResponse).
            lesson_title: The title of the lesson.
            knowledge_level: The target knowledge level.
            syllabus_id: The ID of the syllabus.
            module_index: The index of the module.
            lesson_index: The index of the lesson.

        Returns:
            A tuple containing the generated content object and the lesson's database ID.

        Raises:
            RuntimeError: If content generation or saving fails.
        """
        logger.info(
            f"Generating new exposition for {syllabus_id}/{module_index}/{lesson_index}"
        )

        # Previous performance is not relevant for static exposition generation
        previous_performance: Dict[str, Any] = {}  # Added type parameters

        response_text: str
        try:
            prompt = load_prompt(
                "generate_lesson_content",
                topic=syllabus.get("topic", "Unknown Topic"),
                syllabus_json=json.dumps(
                    {"modules": syllabus.get("modules", [])}, indent=2
                ),
                lesson_name=lesson_title,
                user_level=knowledge_level,
                previous_performance_json=json.dumps(previous_performance, indent=2),
                time_constraint="5 minutes",
            )
            if llm_model is None:
                raise RuntimeError(
                    "LLM model not configured for exposition generation."
                )
            response = call_with_retry(llm_model.generate_content, prompt)
            response_text = response.text
        except ResourceExhausted:
            log_and_raise_new(
                exception_type=RuntimeError,
                exception_message="LLM exposition generation failed due to resource limits.",
                break_chain=True,  # Explicitly break chain as original did 'from None'
                exc_info=False,  # Original didn't log stack trace for this specific case
            )
        except Exception as e:  # Keep general Exception catch
            log_and_propagate(
                RuntimeError, "LLM call failed during exposition generation", e
            )

        try:
            lesson_metadata = Metadata(title=lesson_title)

            generated_content_object = GeneratedLessonContent(
                topic=syllabus.get("topic", "Unknown Topic"),
                level=knowledge_level,
                exposition_content=response_text.strip(),
                metadata=lesson_metadata,
            )

        except Exception as construct_err:
            # Log the response text as an extra detail
            log_and_propagate(
                new_exception_type=RuntimeError,
                new_exception_message="Failed to construct lesson content object from LLM response.",
                original_exception=construct_err,
                llm_response_snippet=response_text[:500],  # Add extra context to log
            )

        try:
            lesson_db_id_int = self.db_service.save_lesson_content(
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                content=generated_content_object.model_dump(mode="json"),
            )
            if not lesson_db_id_int:
                # Use log_and_raise_new as there's no specific prior exception to chain
                log_and_raise_new(
                    exception_type=RuntimeError,
                    exception_message="Failed to save lesson exposition or retrieve lesson ID.",
                    exc_info=False,  # No stack trace needed for this logic error
                )
            return generated_content_object, lesson_db_id_int
        except Exception as save_err:
            log_and_propagate(
                new_exception_type=RuntimeError,
                new_exception_message="Database error saving lesson exposition",
                original_exception=save_err,
            )

    # pylint: disable=too-many-branches
    async def get_or_generate_exposition(
        self, syllabus_id: str, module_index: int, lesson_index: int
    ) -> Tuple[Optional[GeneratedLessonContent], Optional[int]]:
        """
        Gets existing lesson exposition content or generates new content if needed.

        Args:
            syllabus_id: The ID of the syllabus.
            module_index: The index of the module.
            lesson_index: The index of the lesson.

        Returns:
            A tuple containing the validated content object (or None if not found/generated)
            and the lesson's database ID (or None).
        """
        existing_content_obj: Optional[GeneratedLessonContent] = None
        lesson_db_id: Optional[int] = None

        content_data_dict = self.db_service.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )

        if content_data_dict:
            # Use helper to validate and raise specific internal error
            existing_content_obj = validate_internal_model(
                GeneratedLessonContent,
                content_data_dict,
                context_message="Failed to validate existing lesson exposition from DB",
            )
            # Nested try for lesson_id lookup remains
            try:
                retrieved_id = self.db_service.get_lesson_id(
                    syllabus_id, module_index, lesson_index
                )
                if isinstance(retrieved_id, int):
                    lesson_db_id = retrieved_id
            except Exception as e:
                logger.error(
                    f"Content found, but error looking up lesson_id via indices: {e}",
                    exc_info=True,
                )

        if existing_content_obj and lesson_db_id is not None:
            if not existing_content_obj.topic or not existing_content_obj.level:
                try:
                    syllabus = await self.syllabus_service.get_syllabus_by_id(
                        syllabus_id
                    )
                    if syllabus:
                        if not existing_content_obj.topic:
                            existing_content_obj.topic = syllabus.get(
                                "topic", "Unknown Topic"
                            )
                        if not existing_content_obj.level:
                            existing_content_obj.level = syllabus.get(
                                "level", "beginner"
                            )
                except Exception as syllabus_err:
                    logger.warning(
                        f"Could not fetch syllabus to populate missing topic/level: {syllabus_err}"
                    )

            return existing_content_obj, lesson_db_id

        logger.info(
            "Existing lesson exposition not found, invalid, or missing ID. Generating new content."
        )
        try:
            syllabus = await self.syllabus_service.get_syllabus_by_id(syllabus_id)
            if not syllabus:
                log_and_raise_new(
                    exception_type=ValueError,
                    exception_message=f"Syllabus not found for generation: {syllabus_id}",
                )

            lesson_details = await self.syllabus_service.get_lesson_details(
                syllabus_id, module_index, lesson_index
            )
            lesson_title = lesson_details.get("title", "Unknown Lesson")
            knowledge_level = syllabus.get("level", "beginner")

        except ValueError as e:
            log_and_propagate(
                new_exception_type=ValueError,  # Re-raise
                new_exception_message=(
                    f"Could not find details for syllabus {syllabus_id},"
                    f" mod {module_index}, lesson {lesson_index}"
                ),
                original_exception=e,
            )

        try:
            assert syllabus is not None  # Tell mypy syllabus cannot be None here
            generated_content_obj, new_lesson_db_id = (
                await self._generate_and_save_exposition(
                    syllabus=syllabus,
                    lesson_title=lesson_title,
                    knowledge_level=knowledge_level,
                    syllabus_id=syllabus_id,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
            )
            return generated_content_obj, new_lesson_db_id
        except Exception as gen_err:
            logger.error(
                f"Failed to generate and save exposition: {gen_err}", exc_info=True
            )
            return None, None

    async def get_exposition_by_id(
        self, lesson_id: int
    ) -> Optional[GeneratedLessonContent]:
        """
        Retrieve lesson exposition content by its database ID.

        Args:
            lesson_id: The primary key (integer) of the lesson in the database.

        Returns:
            The validated GeneratedLessonContent object or None if not found/invalid.
        """
        content_data_dict = self.db_service.get_lesson_content_by_lesson_pk(lesson_id)

        if not content_data_dict:
            return None

        try:
            # Use helper to validate and raise specific internal error
            # Note: Changes behavior from returning None to raising an error
            content_obj = validate_internal_model(
                GeneratedLessonContent,
                content_data_dict,
                context_message=f"Failed to validate lesson content from DB for lesson_id {lesson_id}",
            )
            return content_obj
        except Exception as e:
            logger.error(
                f"Unexpected error validating content for lesson_id {lesson_id}: {e}",
                exc_info=True,
            )
            return None
