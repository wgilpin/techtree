"""
Service layer for managing syllabi.

Coordinates between the database service and the Syllabus AI component
to create, retrieve, and manage syllabus data.
"""

import logging  # Import logging
from typing import Any, Dict, Optional

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
        logger.debug(
            f"get_or_generate_syllabus called with topic='{topic}', level='{level}', user_id='{user_id}'"
        )
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            logger.info(
                f"Syllabus not found for topic='{topic}', level='{level}', user_id='{user_id}'. Generating new one."
            )
            # If not found, create a new one
            # create_syllabus needs to return data matching SyllabusResponse
            result = await self.create_syllabus(topic, level, user_id)
            # Ensure create_syllabus returns the correct structure
            return result  # Assuming create_syllabus returns the correct structure

        logger.info(
            f"Found existing syllabus for topic='{topic}', level='{level}', user_id='{user_id}'."
        )
        # If found, ensure the response structure matches SyllabusResponse
        # Extract modules from the nested 'content' dictionary
        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Existing syllabus {syllabus.get('syllabus_id')} found but has no modules in its content."
            )
            # Decide how to handle this - maybe regenerate? For now, return empty modules.

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "modules": modules,  # Use extracted modules list
            # "uid": syllabus.get("uid"), # Not part of SyllabusResponse
            # "is_new": False, # Not part of SyllabusResponse
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
        # Initialize syllabus creation with the AI
        # Pass user_id during initialization
        self.syllabus_ai.initialize(topic, knowledge_level, user_id=user_id)

        # Generate syllabus content (should include modules)
        syllabus_content = (
            self.syllabus_ai.get_or_create_syllabus()
        )  # This returns the content dict

        if not syllabus_content or "modules" not in syllabus_content:
            logger.error("Syllabus AI failed to generate content with modules.")
            raise RuntimeError("Failed to generate syllabus content with modules.")

        # Save to database using the service method which handles UID etc.
        # Pass the original user-entered topic for storage
        syllabus_id = self.db_service.save_syllabus(
            topic=syllabus_content.get(
                "topic", topic
            ),  # Use topic from generated content
            level=syllabus_content.get(
                "level", knowledge_level
            ),  # Use level from generated content
            content=syllabus_content,  # Pass the full generated content for saving
            user_id=user_id,
            user_entered_topic=topic,  # Store the original user-entered topic
        )
        logger.info(f"Syllabus saved with ID: {syllabus_id}")

        # Fetch the newly saved syllabus to ensure it was saved correctly
        # get_syllabus_by_id returns the structure with nested content
        saved_syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not saved_syllabus:
            logger.error(
                f"Failed to retrieve newly saved syllabus with ID {syllabus_id}"
            )
            raise RuntimeError(
                f"Failed to retrieve newly saved syllabus with ID {syllabus_id}"
            )

        # Extract modules from the nested content of the saved syllabus
        modules = saved_syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.error(
                f"Newly saved syllabus {syllabus_id} lacks modules in its content."
            )
            # This indicates a problem either in generation or saving/retrieval logic
            raise RuntimeError(
                f"Newly saved syllabus {syllabus_id} is missing modules."
            )

        # Return data structured for SyllabusResponse
        return {
            "syllabus_id": syllabus_id,
            "topic": saved_syllabus["topic"],
            "level": saved_syllabus["level"],
            "modules": modules,  # Use extracted modules
        }

    async def get_syllabus_by_id(self, syllabus_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific syllabus by its database ID.
        Returns data structured to match the SyllabusResponse model.

        Args:
            syllabus_id: The database ID of the syllabus to retrieve.

        Returns:
            A dictionary representing the syllabus structured for SyllabusResponse, or None if not found.
        """
        logger.debug(f"Getting syllabus by ID: {syllabus_id}")
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            logger.warning(f"Syllabus with ID {syllabus_id} not found in DB.")
            return None

        # Extract modules from the nested 'content' dictionary
        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Syllabus {syllabus_id} found but has no modules in its content."
            )
            # Return syllabus info even if modules are missing? Or return None?
            # For now, return with empty modules list to match response model.

        # Return data structured for SyllabusResponse
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
        logger.debug(
            f"get_syllabus_by_topic_level called with topic='{topic}', level='{level}', user_id='{user_id}'"
        )
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            logger.info(
                f"Syllabus not found for topic='{topic}', level='{level}', user_id='{user_id}'."
            )
            return None  # Explicitly return None if not found

        logger.info(
            f"Found existing syllabus for topic='{topic}', level='{level}', user_id='{user_id}'."
        )
        # If found, ensure the response structure matches SyllabusResponse
        modules = syllabus.get("content", {}).get("modules", [])
        if not modules:
            logger.warning(
                f"Existing syllabus {syllabus.get('syllabus_id')} found but has no modules in its content."
            )
            # Return syllabus info even if modules are missing? Or return None?
            # For now, return with empty modules list to match response model.

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "modules": modules,  # Use extracted modules list
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
        # Use the internal DB service method that returns the nested structure
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        if "content" not in syllabus:
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

        # Fetch the corresponding lesson ID from the lessons table using the new method
        lesson_db_id = self.db_service.get_lesson_id(
            syllabus_id, module_index, lesson_index
        )

        # Add indices and DB ID to the returned dict
        lesson_data["module_index"] = module_index
        lesson_data["lesson_index"] = lesson_index
        lesson_data["lesson_id"] = (
            lesson_db_id  # Can be None if content doesn't exist yet
        )

        return lesson_data
