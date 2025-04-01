"""
Service layer for managing syllabi.

Coordinates between the database service and the Syllabus AI component
to create, retrieve, and manage syllabus data.
"""

import logging
from typing import Any, Dict, Optional, cast  # Added cast
from backend.exceptions import log_and_raise_new

from backend.ai.app import SyllabusAI
from backend.services.sqlite_db import SQLiteDatabaseService

# Get logger instance
logger = logging.getLogger(__name__)


class SyllabusService:
    """
    Provides methods for syllabus creation, retrieval, and management.

    Acts as an intermediary between API routers/other services and the
    underlying database and AI components related to syllabi.
    """

    def __init__(self, db_service: SQLiteDatabaseService):
        """
        Initializes the SyllabusService.

        Args:
            db_service: An instance of SQLiteDatabaseService for database access.
        """
        self.syllabus_ai = SyllabusAI(db_service=db_service)
        self.db_service = db_service

    async def get_or_generate_syllabus(
        self, topic: str, level: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves a syllabus by topic and level, creating one if it doesn't exist.
        This method is intended to be called by endpoints that need to ensure a
        syllabus exists, like the POST /generate endpoint.

        Args:
            topic: The topic of the syllabus.
            level: The knowledge level of the syllabus.
            user_id: Optional user ID for user-specific retrieval/creation.

        Returns:
            A dictionary representing the found or newly created syllabus,
            structured to match the SyllabusResponse model.
        """
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            logger.info(
                f"Syllabus not found for topic='{topic}', level='{level}', user_id='{user_id}'. "
                "Generating new one."
            )
            result = await self.create_syllabus(topic, level, user_id)
            return result

        logger.info(
            f"Found existing syllabus for topic='{topic}', level='{level}', user_id='{user_id}'."
        )
        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Existing syllabus {syllabus.get('syllabus_id')} found but "
                "has no modules in its content."
            )

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "modules": modules,
        }

    async def create_syllabus(
        self, topic: str, knowledge_level: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new syllabus using the SyllabusAI and saves it to the database.
        Returns data structured to match the SyllabusResponse model.

        Args:
            topic: The desired topic for the syllabus.
            knowledge_level: The target knowledge level for the syllabus.
            user_id: Optional user ID if creating a user-specific syllabus.

        Returns:
            A dictionary representing the newly created and saved syllabus,
            structured to match the SyllabusResponse model.

        Raises:
            RuntimeError: If the newly saved syllabus cannot be retrieved or lacks modules.
        """
        logger.info(
            f"Creating syllabus for topic='{topic}', level='{knowledge_level}', user_id='{user_id}'"
        )
        self.syllabus_ai.initialize(topic, knowledge_level, user_id=user_id)

        syllabus_content = self.syllabus_ai.get_or_create_syllabus()

        if not syllabus_content or "modules" not in syllabus_content:
            log_and_raise_new(
                exception_type=RuntimeError,
                exception_message="Failed to generate syllabus content with modules.",
                exc_info=False # Original log didn't include stack trace
            )

        syllabus_id = self.db_service.save_syllabus(
            topic=str(syllabus_content.get("topic", topic)),  # Ensure topic is str
            level=str(
                syllabus_content.get("level", knowledge_level)
            ),  # Ensure level is str
            content=cast(Dict[str, Any], syllabus_content),  # Cast content to Dict
            user_id=user_id,
            user_entered_topic=topic,
        )
        logger.info(f"Syllabus saved with ID: {syllabus_id}")

        saved_syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not saved_syllabus:
            logger.error(
                f"Failed to retrieve newly saved syllabus with ID {syllabus_id}"
            )
            raise RuntimeError(
                f"Failed to retrieve newly saved syllabus with ID {syllabus_id}"
            )

        modules = saved_syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.error(
                f"Newly saved syllabus {syllabus_id} lacks modules in its content."
            )
            raise RuntimeError(
                f"Newly saved syllabus {syllabus_id} is missing modules."
            )

        return {
            "syllabus_id": syllabus_id,
            "topic": saved_syllabus["topic"],
            "level": saved_syllabus["level"],
            "modules": modules,
        }

    async def get_syllabus_by_id(self, syllabus_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific syllabus by its database ID.
        Returns data structured to match the SyllabusResponse model.

        Args:
            syllabus_id: The database ID of the syllabus to retrieve.

        Returns:
            A dictionary representing the syllabus structured for SyllabusResponse,
                or None if not found.
        """
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            logger.warning(f"Syllabus with ID {syllabus_id} not found in DB.")
            return None

        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Syllabus {syllabus_id} found but has no modules in its content."
            )

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "modules": modules,
        }

    async def get_syllabus_by_topic_level(
        self, topic: str, level: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves a syllabus by topic and level. Does NOT create one if it doesn't exist.
        This method is intended for endpoints that specifically need to fetch an existing
        syllabus, like the GET /topic/{topic}/level/{level} endpoint.
        Returns data structured to match the SyllabusResponse model.

        Args:
            topic: The topic of the syllabus.
            level: The knowledge level of the syllabus.
            user_id: Optional user ID for user-specific retrieval.

        Returns:
            A dictionary representing the found syllabus structured for SyllabusResponse, or None.
        """
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            logger.info(
                f"Syllabus not found for topic='{topic}', level='{level}', user_id='{user_id}'."
            )
            return None

        logger.info(
            f"Found existing syllabus for topic='{topic}', level='{level}', user_id='{user_id}'."
        )
        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Existing syllabus {syllabus.get('syllabus_id')} found but "
                "has no modules in its content."
            )

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "modules": modules,
        }

    async def get_module_details(
        self, syllabus_id: str, module_index: int
    ) -> Dict[str, Any]:
        """
        Retrieves details for a specific module within a syllabus.

        Args:
            syllabus_id: The database ID of the syllabus.
            module_index: The zero-based index of the module within the syllabus content.

        Returns:
            A dictionary containing the module's details (title, lessons, etc.),
            including the 'module_index'.

        Raises:
            ValueError: If the syllabus is invalid, content is missing, or the
                        module index is out of range.
        """
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        if "content" not in syllabus:
            raise ValueError(f"Invalid syllabus content for ID {syllabus_id}")

        content = syllabus["content"]

        if (
            not isinstance(content, dict)
            or "modules" not in content
            or not isinstance(content["modules"], list)
        ):
            raise ValueError(
                f"Syllabus {syllabus_id} content is missing 'modules' list."
            )

        if module_index < 0 or module_index >= len(content["modules"]):
            raise ValueError(
                f"Module index {module_index} out of range for syllabus {syllabus_id}"
            )

        module_data = content["modules"][module_index]
        module_data["module_index"] = module_index
        # Cast before returning
        return cast(Dict[str, Any], module_data)

    async def get_lesson_details(
        self, syllabus_id: str, module_index: int, lesson_index: int
    ) -> Dict[str, Any]:
        """
        Retrieves details for a specific lesson within a syllabus module.

        Also fetches the corresponding lesson's database ID if it exists.

        Args:
            syllabus_id: The database ID of the syllabus.
            module_index: The zero-based index of the module.
            lesson_index: The zero-based index of the lesson within the module.

        Returns:
            A dictionary containing the lesson's details (title, etc.), including
            'module_index', 'lesson_index', and 'lesson_id' (which may be None).

        Raises:
            ValueError: If the syllabus or module is invalid, content is missing,
                        or the lesson index is out of range.
        """
        module = await self.get_module_details(syllabus_id, module_index)

        # Access lessons via module['content']['lessons'] based on _build_syllabus_dict
        module_content = module.get("content", {})
        if (
            not isinstance(module_content, dict)
            or "lessons" not in module_content
            or not isinstance(module_content["lessons"], list)
        ):
            raise ValueError(
                f"Module {module_index} in syllabus {syllabus_id} "
                "is missing 'lessons' list in its content."
            )

        lessons = module_content["lessons"]
        if lesson_index < 0 or lesson_index >= len(lessons):
            raise ValueError(
                f"Lesson index {lesson_index} out of range for module "
                f"{module_index} in syllabus {syllabus_id}"
            )

        lesson_data = lessons[lesson_index]

        lesson_db_id = self.db_service.get_lesson_id(
            syllabus_id, module_index, lesson_index
        )

        lesson_data["module_index"] = module_index
        lesson_data["lesson_index"] = lesson_index
        lesson_data["lesson_id"] = lesson_db_id

        # Cast before returning
        return cast(Dict[str, Any], lesson_data)
