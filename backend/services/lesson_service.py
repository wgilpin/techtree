from backend.ai.app import LessonAI
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService
from typing import Dict, Any, Optional, List

class LessonService:
    def __init__(self, db_service=None, syllabus_service=None):
        self.lesson_ai = LessonAI()
        self.db_service = db_service or SQLiteDatabaseService()
        self.syllabus_service = syllabus_service or SyllabusService(self.db_service)

    async def get_or_generate_lesson(self, syllabus_id: str, module_index: int, lesson_index: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get existing lesson content or generate new content for a lesson"""
        # First check if the lesson content already exists in the database
        existing_lesson = self.db_service.get_lesson_content(syllabus_id, module_index, lesson_index)

        if existing_lesson:
            return {
                "lesson_id": existing_lesson["lesson_id"],
                "syllabus_id": existing_lesson["syllabus_id"],
                "module_index": existing_lesson["module_index"],
                "lesson_index": existing_lesson["lesson_index"],
                "content": existing_lesson["content"],
                "is_new": False
            }

        # Get syllabus, module and lesson details
        syllabus = await self.syllabus_service.get_syllabus(syllabus_id)
        module = await self.syllabus_service.get_module_details(syllabus_id, module_index)
        lesson_details = await self.syllabus_service.get_lesson_details(syllabus_id, module_index, lesson_index)

        # Initialize and generate lesson content with the AI
        self.lesson_ai.initialize(
            topic=syllabus["topic"],
            skill_level=syllabus["level"],
            module_title=module["title"],
            lesson_title=lesson_details["title"],
            lesson_summary=lesson_details.get("summary", ""),
            previous_lessons=[] # In a future implementation, we could pass previous lessons
        )

        # Generate the full lesson content
        lesson_content = self.lesson_ai.generate_lesson()

        # Save the lesson content to the database
        lesson_id = self.db_service.save_lesson_content(
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            content=lesson_content
        )

        # If user_id provided, create a progress entry with status "not_started"
        if user_id:
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status="not_started"
            )

        return {
            "lesson_id": lesson_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": lesson_content,
            "is_new": True
        }

    async def get_lesson_by_id(self, lesson_id: str) -> Dict[str, Any]:
        """Retrieve a lesson by ID"""
        lesson = self.db_service.get_lesson_by_id(lesson_id)

        if not lesson:
            raise ValueError(f"Lesson with ID {lesson_id} not found")

        return lesson

    async def evaluate_exercise(self, lesson_id: str, exercise_index: int, user_answer: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate a user's answer to an exercise in a lesson"""
        lesson = await self.get_lesson_by_id(lesson_id)

        if not lesson or "content" not in lesson:
            raise ValueError(f"Invalid lesson with ID {lesson_id}")

        content = lesson["content"]

        if not content or "exercises" not in content or exercise_index >= len(content["exercises"]):
            raise ValueError(f"Exercise index {exercise_index} out of range for lesson {lesson_id}")

        exercise = content["exercises"][exercise_index]

        # Initialize evaluation with the AI
        # Here we use the LessonAI to evaluate the exercise response
        self.lesson_ai.initialize_for_evaluation(
            exercise_question=exercise["question"],
            exercise_type=exercise.get("type", "open_ended"),
            expected_answer=exercise.get("answer", ""),
            skill_level=content["skill_level"]
        )

        # Evaluate the user's answer
        evaluation_result = self.lesson_ai.evaluate_exercise(user_answer)

        # If user_id is provided and this is the final exercise, mark the lesson as completed
        if user_id and exercise_index == len(content["exercises"]) - 1:
            # Update user progress to completed
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=lesson["syllabus_id"],
                module_index=lesson["module_index"],
                lesson_index=lesson["lesson_index"],
                status="completed",
                score=evaluation_result.get("score", 0)
            )

        return {
            "is_correct": evaluation_result["is_correct"],
            "score": evaluation_result["score"],
            "feedback": evaluation_result["feedback"],
            "explanation": evaluation_result.get("explanation", "")
        }

    async def update_lesson_progress(self, user_id: str, syllabus_id: str, module_index: int, lesson_index: int, status: str) -> Dict[str, Any]:
        """Update user's progress for a specific lesson"""
        # Validate status
        if status not in ["not_started", "in_progress", "completed"]:
            raise ValueError(f"Invalid status: {status}")

        # Update the progress
        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            status=status
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status
        }