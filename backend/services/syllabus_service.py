from ai.app import SyllabusAI
from services.db import DatabaseService
from typing import Dict, Any, Optional, List

class SyllabusService:
    def __init__(self, db_service=None):
        self.syllabus_ai = SyllabusAI()
        self.db_service = db_service or DatabaseService()

    async def create_syllabus(self, topic: str, knowledge_level: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new syllabus based on topic and knowledge level"""
        # First, check if we already have this syllabus in the database
        existing_syllabus = self.db_service.get_syllabus(topic, knowledge_level, user_id)

        if existing_syllabus:
            return {
                "syllabus_id": existing_syllabus["syllabus_id"],
                "topic": existing_syllabus["topic"],
                "level": existing_syllabus["level"],
                "content": existing_syllabus["content"],
                "is_new": False
            }

        # Initialize syllabus creation with the AI
        self.syllabus_ai.initialize(topic, knowledge_level)

        # Generate syllabus
        syllabus_result = self.syllabus_ai.generate_syllabus()

        # Save to database
        syllabus_id = self.db_service.save_syllabus(
            topic=topic,
            level=knowledge_level,
            content=syllabus_result,
            user_id=user_id
        )

        return {
            "syllabus_id": syllabus_id,
            "topic": topic,
            "level": knowledge_level,
            "content": syllabus_result,
            "is_new": True
        }

    async def get_syllabus(self, syllabus_id: str) -> Dict[str, Any]:
        """Retrieve a syllabus by ID"""
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        if not syllabus:
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        return syllabus

    async def get_syllabus_by_topic_level(self, topic: str, level: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve a syllabus by topic and level"""
        syllabus = self.db_service.get_syllabus(topic, level, user_id)

        if not syllabus:
            # If not found, create a new one
            result = await self.create_syllabus(topic, level, user_id)
            return result

        return {
            "syllabus_id": syllabus["syllabus_id"],
            "topic": syllabus["topic"],
            "level": syllabus["level"],
            "content": syllabus["content"],
            "is_new": False
        }

    async def get_module_details(self, syllabus_id: str, module_index: int) -> Dict[str, Any]:
        """Get details for a specific module in the syllabus"""
        syllabus = await self.get_syllabus(syllabus_id)

        if not syllabus or "content" not in syllabus:
            raise ValueError(f"Invalid syllabus with ID {syllabus_id}")

        content = syllabus["content"]

        if not content or "modules" not in content or module_index >= len(content["modules"]):
            raise ValueError(f"Module index {module_index} out of range for syllabus {syllabus_id}")

        return content["modules"][module_index]

    async def get_lesson_details(self, syllabus_id: str, module_index: int, lesson_index: int) -> Dict[str, Any]:
        """Get basic details for a specific lesson in the syllabus"""
        module = await self.get_module_details(syllabus_id, module_index)

        if "lessons" not in module or lesson_index >= len(module["lessons"]):
            raise ValueError(f"Lesson index {lesson_index} out of range for module {module_index}")

        return module["lessons"][lesson_index]