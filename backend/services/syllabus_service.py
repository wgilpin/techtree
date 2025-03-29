"""
Service layer for managing syllabi.

Coordinates between the database service and the Syllabus AI component
to create, retrieve, and manage syllabus data.
"""
from typing import Any, Dict, Optional

from backend.ai.app import SyllabusAI
from backend.services.sqlite_db import SQLiteDatabaseService


class SyllabusService:
    """
    Provides methods for syllabus creation, retrieval, and management.

    Acts as an intermediary between API routers/other services and the
    underlying database and AI components related to syllabi.
    """
    # Require db_service and add type hint
    def __init__(self, db_service: SQLiteDatabaseService):
        """
        Initializes the SyllabusService.

        Args:
            db_service: An instance of SQLiteDatabaseService for database access.
        """
        # Pass db_service to SyllabusAI constructor
        self.syllabus_ai = SyllabusAI(db_service=db_service)
        # Remove fallback
        self.db_service = db_service

    async def create_syllabus(
        self, topic: str, knowledge_level: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new syllabus using the SyllabusAI and saves it to the database.

        Args:
            topic: The desired topic for the syllabus.
            knowledge_level: The target knowledge level for the syllabus.
            user_id: Optional user ID if creating a user-specific syllabus.

        Returns:
            A dictionary representing the newly created and saved syllabus,
            including its database ID and UID.

        Raises:
            RuntimeError: If the newly saved syllabus cannot be retrieved.
        """
        # Initialize syllabus creation with the AI
        # Pass user_id during initialization
        self.syllabus_ai.initialize(topic, knowledge_level, user_id=user_id)

        # Generate syllabus
        syllabus_result = self.syllabus_ai.get_or_create_syllabus()

        # Save to database using the service method which handles UID etc.
        syllabus_id = self.db_service.save_syllabus(
            topic=syllabus_result.get(
                "topic", topic
            ),  # Use topic from generated content if available
            level=syllabus_result.get(
                "level", knowledge_level
            ),  # Use level from generated content
            content=syllabus_result,
            user_id=user_id,
            user_entered_topic=topic,  # Store the original user-entered topic
        )

        # Fetch the newly saved syllabus to get all details including UID
        saved_syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not saved_syllabus:
            # This should ideally not happen if save was successful
            raise RuntimeError(
                f"Failed to retrieve newly saved syllabus with ID {syllabus_id}"
            )

        return {
            "syllabus_id": syllabus_id,
            "topic": saved_syllabus["topic"],
            "level": saved_syllabus["level"],
            "content": saved_syllabus["content"],
            "uid": saved_syllabus.get("uid"),  # Include UID
            "is_new": True,
        }

    async def get_syllabus(self, syllabus_id: str) -> Dict[str, Any]:
        """
        Retrieves a specific syllabus by its database ID.

        Args:
            syllabus_id: The database ID of the syllabus to retrieve.

        Returns:
            A dictionary representing the syllabus.

        Raises:
            ValueError: If no syllabus is found with the given ID.
        """
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        return syllabus

    async def get_syllabus_by_topic_level(
        self, topic: str, level: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves a syllabus by topic and level, creating one if it doesn't exist.

        Searches first for a user-specific syllabus if user_id is provided,
        then for a master syllabus. If neither exists, triggers the creation
        of a new syllabus.

        Args:
            topic: The topic of the syllabus.
            level: The knowledge level of the syllabus.
            user_id: Optional user ID for user-specific retrieval/creation.

        Returns:
            A dictionary representing the found or newly created syllabus.
        """
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            # If not found, create a new one
            result = await self.create_syllabus(topic, level, user_id)
            # create_syllabus now returns the full saved syllabus details
            return result

        # Ensure the response structure is consistent
        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "content": syllabus["content"],
            "uid": syllabus.get("uid"),  # Include UID
            "is_new": False,
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
        syllabus = await self.get_syllabus(syllabus_id)

        if not syllabus or "content" not in syllabus:
            raise ValueError(f"Invalid syllabus content for ID {syllabus_id}")

        content = syllabus["content"]  # Content should already be a dict

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

        # Add module_index to the returned dict for convenience
        module_data = content["modules"][module_index]
        module_data["module_index"] = module_index
        return module_data

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

        if "lessons" not in module or not isinstance(module["lessons"], list):
            raise ValueError(
                f"Module {module_index} in syllabus {syllabus_id} is missing 'lessons' list."
            )

        if lesson_index < 0 or lesson_index >= len(module["lessons"]):
            raise ValueError(
                f"Lesson index {lesson_index} out of range for module "
                f"{module_index} in syllabus {syllabus_id}"
            )

        lesson_data = module["lessons"][lesson_index]

        # Fetch the corresponding lesson ID from the lessons table
        lesson_db_id = self.db_service.get_lesson_id_by_indices(
            syllabus_id, module_index, lesson_index
        )

        # Add indices and DB ID to the returned dict
        lesson_data["module_index"] = module_index
        lesson_data["lesson_index"] = lesson_index
        lesson_data["lesson_id"] = (
            lesson_db_id  # Can be None if content doesn't exist yet
        )

        return lesson_data
