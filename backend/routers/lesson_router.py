from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.lesson_service import LessonService
from routers.auth_router import User, get_current_user

router = APIRouter()
lesson_service = LessonService()

# Models
class LessonRequest(BaseModel):
    syllabus_id: str
    module_index: int
    lesson_index: int

class ExerciseSubmission(BaseModel):
    lesson_id: str
    exercise_index: int
    answer: str

class LessonContent(BaseModel):
    lesson_id: str
    syllabus_id: str
    module_index: int
    lesson_index: int
    content: Dict[str, Any]
    is_new: bool

class ExerciseFeedback(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    explanation: Optional[str] = None

class ProgressUpdate(BaseModel):
    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str  # "not_started", "in_progress", "completed"

class ProgressResponse(BaseModel):
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
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get or generate content for a specific lesson"""
    user_id = current_user.user_id if current_user else None

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
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson: {str(e)}"
        )

@router.get("/by-id/{lesson_id}", response_model=Dict[str, Any])
async def get_lesson_by_id(lesson_id: str):
    """Get a lesson by its ID"""
    try:
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        return lesson
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson: {str(e)}"
        )

@router.post("/exercise/evaluate", response_model=ExerciseFeedback)
async def evaluate_exercise(
    submission: ExerciseSubmission,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Evaluate a user's answer to an exercise"""
    user_id = current_user.user_id if current_user else None

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
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating exercise: {str(e)}"
        )

@router.post("/progress", response_model=ProgressResponse)
async def update_lesson_progress(
    progress: ProgressUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update user's progress for a specific lesson"""
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
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating progress: {str(e)}"
        )