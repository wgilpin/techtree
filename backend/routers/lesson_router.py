from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from backend.services.lesson_service import LessonService
from backend.models import User
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from backend.services.lesson_service import LessonService
from backend.models import User
from backend.dependencies import get_current_user
from backend.logger import logger

router = APIRouter()
lesson_service = LessonService()

# Models
class LessonRequest(BaseModel):
    """
    Request model for retrieving a lesson.
    """
    syllabus_id: str
    module_index: int
    lesson_index: int

class ExerciseSubmission(BaseModel):
    """
    Request model for submitting an exercise answer.
    """
    lesson_id: str
    exercise_index: int
    answer: str

class LessonContent(BaseModel):
    """
    Response model for lesson content.
    """
    lesson_id: str
    syllabus_id: str
    module_index: int
    lesson_index: int
    content: Dict[str, Any]
    is_new: bool

class ExerciseFeedback(BaseModel):
    """
    Response model for exercise feedback.
    """
    is_correct: bool
    score: float
    feedback: str
    explanation: Optional[str] = None

class ProgressUpdate(BaseModel):
    """
    Request model for updating lesson progress.
    """
    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str  # "not_started", "in_progress", "completed"

class ProgressResponse(BaseModel):
    """
    Response model for lesson progress updates.
    """
    progress_id: str
    user_id: str
    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str

# Routes
@router.get("/{syllabus_id}/{module_index}/{lesson_index}", response_model=LessonContent)
async def get_lesson(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None
):
    """
    Get or generate content for a specific lesson.
    """
    logger.info(f"Entering get_lesson endpoint for syllabus_id: {syllabus_id}, module_index: {module_index}, lesson_index: {lesson_index}")
    user_id = current_user.user_id if current_user else None
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"

    try:
        result = await lesson_service.get_or_generate_lesson(
            syllabus_id,
            module_index,
            lesson_index,
            user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson: {str(e)}"
        ) from e

@router.get("/by-id/{lesson_id}", response_model=Dict[str, Any])
async def get_lesson_by_id(lesson_id: str):
    """
    Get a lesson by its ID.
    """
    logger.info(f"Entering get_lesson_by_id endpoint for lesson_id: {lesson_id}")
    try:
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        return lesson
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson: {str(e)}"
        ) from e

@router.post("/exercise/evaluate", response_model=ExerciseFeedback)
async def evaluate_exercise(
    submission: ExerciseSubmission,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None
):
    """
    Evaluate a user's answer to an exercise.
    """
    logger.info(f"Entering evaluate_exercise endpoint for lesson_id: {submission.lesson_id}, exercise_index: {submission.exercise_index}")
    user_id = current_user.user_id if current_user else None
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"

    try:
        result = await lesson_service.evaluate_exercise(
            submission.lesson_id,
            submission.exercise_index,
            submission.answer,
            user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating exercise: {str(e)}"
        ) from e

@router.post("/progress", response_model=ProgressResponse)
async def update_lesson_progress(
    progress: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    response: Response = None
):
    """
    Update user's progress for a specific lesson.
    """
    logger.info(f"Entering update_lesson_progress endpoint for syllabus_id: {progress.syllabus_id}, module_index: {progress.module_index}, lesson_index: {progress.lesson_index}, user: {current_user.email}")
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        result = await lesson_service.update_lesson_progress(
            current_user.user_id,
            progress.syllabus_id,
            progress.module_index,
            progress.lesson_index,
            progress.status
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating progress: {str(e)}"
        ) from e
