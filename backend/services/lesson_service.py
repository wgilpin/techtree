"""Lesson logic, for generation and evaluation"""

import json
import re
from typing import Any, Dict, Optional

# Import necessary components from lessons_graph
from backend.ai.lessons.lessons_graph import model, call_with_retry
from backend.ai.app import LessonAI
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService
from backend.logger import logger  # Import the configured logger


class LessonService:
    """Service for managing and generating lesson content."""

    def __init__(self, db_service=None, syllabus_service=None):
        # LessonAI is still needed for generation
        self.lesson_ai = LessonAI()
        self.db_service = db_service or SQLiteDatabaseService()
        self.syllabus_service = syllabus_service or SyllabusService(self.db_service)

    async def get_or_generate_lesson(
        self,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get existing lesson content or generate new content for a lesson"""
        # First check if the lesson content already exists in the database
        # Get syllabus details first, as we need topic and level regardless
        syllabus = await self.syllabus_service.get_syllabus(syllabus_id)
        if not syllabus:
            raise ValueError(f"Syllabus with ID {syllabus_id} not found")

        # Check if the lesson content already exists in the database
        existing_lesson = self.db_service.get_lesson_content(
            syllabus_id, module_index, lesson_index
        )

        if existing_lesson:
            # Ensure topic and level are in the content
            if "topic" not in existing_lesson["content"]:
                existing_lesson["content"]["topic"] = syllabus["topic"]
            if "level" not in existing_lesson["content"]:
                existing_lesson["content"]["level"] = syllabus["level"]

            return {
                "lesson_id": existing_lesson["lesson_id"],
                "syllabus_id": existing_lesson["syllabus_id"],
                "module_index": existing_lesson["module_index"],
                "lesson_index": existing_lesson["lesson_index"],
                "content": existing_lesson["content"],
                "is_new": False,
            }

        # Lesson doesn't exist, proceed with generation
        # Get module and lesson details
        module = await self.syllabus_service.get_module_details(
            syllabus_id, module_index
        )
        lesson_details = await self.syllabus_service.get_lesson_details(
            syllabus_id, module_index, lesson_index
        )

        # Initialize and generate lesson content with the AI
        self.lesson_ai.initialize(
            topic=syllabus["topic"],
            knowledge_level=syllabus["level"],
            module_title=module["title"],
            lesson_title=lesson_details["title"],
            user_id=user_id,
            # lesson_summary=lesson_details.get("summary", ""),
            # previous_lessons=[] # In a future implementation, we could pass previous lessons
        )

        # Generate the full lesson content
        lesson_content = self.lesson_ai.get_lesson_content()

        # Save the lesson content to the database
        lesson_id = self.db_service.save_lesson_content(
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            content=lesson_content,
        )

        # If user_id provided, create a progress entry with status "not_started"
        if user_id:
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=syllabus_id,
                module_index=module_index,
                lesson_index=lesson_index,
                status="not_started",
            )

        return {
            "lesson_id": lesson_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            # Ensure topic and level are in the newly generated content
            "content": {
                **lesson_content,
                "topic": syllabus["topic"],
                "level": syllabus["level"],
            },
            "is_new": True,
        }

    async def get_lesson_by_id(self, lesson_id: str) -> Dict[str, Any]:
        """Retrieve a lesson by ID"""
        lesson = self.db_service.get_lesson_by_id(lesson_id)

        if not lesson:
            raise ValueError(f"Lesson with ID {lesson_id} not found")

        return lesson

    async def evaluate_exercise(
        self,
        lesson_id: str,
        exercise_index: int,
        user_answer: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a user's answer to an exercise in a lesson"""
        lesson = await self.get_lesson_by_id(lesson_id)

        if not lesson or "content" not in lesson:
            raise ValueError(f"Invalid lesson with ID {lesson_id}")

        content = lesson["content"]

        # Determine the correct key for exercises and get the list
        exercises_list = None
        if "exercises" in content and isinstance(content.get("exercises"), list):
            exercises_list = content["exercises"]
            logger.debug(f"Using 'exercises' key for lesson {lesson_id}")
        elif "active_exercises" in content and isinstance(
            content.get("active_exercises"), list
        ):
            exercises_list = content["active_exercises"]
            logger.debug(f"Using 'active_exercises' key for lesson {lesson_id}")
        else:
            logger.warning(
                "Neither 'exercises' nor 'active_exercises' key found"
                f" or valid list in content for lesson {lesson_id}"
            )

        # Check if exercises list is valid and index is within bounds
        # Added check for exercises_list being None
        if exercises_list is None or exercise_index >= len(exercises_list):
            raise ValueError(
                f"Exercise index {exercise_index} out of range or"
                f" exercises not found/invalid for lesson {lesson_id}"
            )

        exercise = exercises_list[exercise_index]
        # Log specific fields instead of the entire exercise data to avoid encoding issues
        logger.debug(f"Exercise index: {exercise_index}, type: {exercise.get('type', 'unknown')}")
        logger.debug(f"Exercise ID: {exercise.get('id', 'unknown')}")

        # Check for different possible field names that might contain the question text
        instructions = exercise.get('instructions', None)
        question = exercise.get('question', None)

        logger.debug(f"Found 'instructions' field: {instructions is not None}")
        logger.debug(f"Found 'question' field: {question is not None}")

        # Use instructions if available, otherwise fall back to question
        question_text = question if question is not None else (instructions if instructions is not None else 'Error: Question text not found.')
        logger.debug(f"Using question_text: '{question_text[:100]}...' (truncated)")

        exercise_type = exercise.get("type", "open_ended") # Determine type for prompt
        user_answer_str = str(user_answer) # Ensure user answer is a string

        # Construct specific prompt content based on exercise type
        prompt_content = ""
        if exercise_type == 'ordering':
            # Ensure items are strings for joining
            items_to_order = [str(item) for item in exercise.get('items', [])]
            # Assuming correct_answer is stored as a list or string representing the sequence
            correct_sequence = exercise.get('correct_answer', 'N/A')
            prompt_content = f"""
Question: {question_text}

Items to order:
{chr(10).join([f'- {item}' for item in items_to_order])}

Expected correct order: {correct_sequence}

User's submitted order: {user_answer_str}

Please evaluate if the user's submitted order matches the expected correct order.
"""
        else:
            # For other types, look for different possible field names for the expected answer
            expected_solution = (
                exercise.get('answer') or
                exercise.get('expected_solution') or
                exercise.get('correct_answer') or
                exercise.get('correct_answer_explanation', 'N/A')
            )

            logger.debug(f"Using expected_solution: '{str(expected_solution)[:100]}...' (truncated)")

            prompt_content = f"""
Question: {question_text}

Expected solution or correct answer: {expected_solution}

User's response: {user_answer_str}

Please evaluate the user's response.
"""

        # Construct the full prompt for Gemini
        prompt = f"""
You are evaluating a user's response to a {exercise_type} exercise.

{prompt_content}

Provide your evaluation as a JSON object with the following structure:
1. "score": A score between 0 (incorrect) and 1 (correct). For ordering, 1 if the order is exactly correct, 0 otherwise. For other types, grade appropriately.
2. "feedback": A brief explanation of the evaluation (e.g., "Correct order", "Incorrect order", or feedback on partial correctness for other types).
3. "explanation": An optional brief explanation of the correct answer, especially if the user was incorrect.
4. "is_correct": A boolean (true if score is 1.0 for ordering, true if score >= 0.8 for other types, false otherwise).

Example JSON format:
{{
  "score": 1.0,
  "feedback": "The sequence is correct.",
  "explanation": "The correct order is B, D, G, A, F, E, C because...",
  "is_correct": true
}}
"""

        # Call the Gemini model directly
        try:
            evaluation_response = call_with_retry(model.generate_content, prompt)
            evaluation_text = evaluation_response.text
            logger.debug(f"Raw evaluation response: {evaluation_text}")

            # Extract JSON from response (using patterns from _evaluate_response)
            json_patterns = [
                r"```(?:json)?\s*({.*?})```",
                r'({[\s\S]*"score"[\s\S]*"feedback"[\s\S]*"explanation"[\s\S]*"is_correct"[\s\S]*})',
                r"({[\s\S]*})",
            ]

            evaluation_result = None
            for pattern in json_patterns:
                json_match = re.search(pattern, evaluation_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    # Basic cleanup
                    json_str = re.sub(r"\\n", "", json_str)
                    json_str = re.sub(r"\\", "", json_str) # Be careful with this one
                    try:
                        evaluation_result = json.loads(json_str)
                        # Basic validation
                        if all(
                            key in evaluation_result
                            for key in ["score", "feedback", "is_correct"]
                        ):
                            # Ensure explanation is present, even if empty
                            evaluation_result.setdefault("explanation", "")
                            logger.debug(f"Parsed evaluation result: {evaluation_result}")
                            break # Successfully parsed
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parsing failed for pattern {pattern}: {e}")
                        logger.warning(f"Problematic JSON string: {json_str}")
                        evaluation_result = None # Reset on failure

            if evaluation_result is None:
                 logger.error(f"Failed to parse evaluation JSON from response: {evaluation_text}")
                 # Provide a default error response
                 evaluation_result = {
                     "score": 0.0,
                     "feedback": "Sorry, I couldn't evaluate your answer at this time.",
                     "explanation": "",
                     "is_correct": False,
                 }

        except Exception as e:
            logger.error(f"Error during exercise evaluation: {e}", exc_info=True)
            evaluation_result = {
                "score": 0.0,
                "feedback": "An error occurred during evaluation.",
                "explanation": "",
                "is_correct": False,
            }


        # If user_id is provided and this is the final exercise, mark the lesson as completed
        if (
            user_id
            and exercises_list is not None
            and exercise_index == len(exercises_list) - 1
        ):  # Use exercises_list here
            # Update user progress to completed
            self.db_service.save_user_progress(
                user_id=user_id,
                syllabus_id=lesson["syllabus_id"],
                module_index=lesson["module_index"],
                lesson_index=lesson["lesson_index"],
                status="completed",
                score=evaluation_result.get("score", 0), # Use score from parsed result
            )

        # Return the structured evaluation result
        return {
            "is_correct": evaluation_result["is_correct"],
            "score": evaluation_result["score"],
            "feedback": evaluation_result["feedback"],
            "explanation": evaluation_result["explanation"],
        }

    async def update_lesson_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
    ) -> Dict[str, Any]:
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
            status=status,
            # Score is only updated during evaluation, pass None here
            score=None
        )

        return {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,
        }
