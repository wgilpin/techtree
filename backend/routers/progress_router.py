"""fastApi router for user progress"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

# Corrected import: get_db -> get_db_service
from backend.dependencies import get_current_user, get_db_service
from backend.models import User
from backend.services.sqlite_db import SQLiteDatabaseService # Import for type hint

router = APIRouter()

# --- Pydantic Models ---

class CourseProgress(BaseModel):
    """Model representing progress summary for a course (syllabus)."""
    syllabus_id: str
    topic: str
    level: str
    completed_lessons: int
    total_lessons: int
    last_accessed: str # ISO format timestamp

class CourseListResponse(BaseModel):
    """Response model for listing courses the user has progress in."""
    courses: List[CourseProgress]

# --- Progress Routes ---

@router.get("/courses", response_model=CourseListResponse)
async def get_user_courses(
    current_user: User = Depends(get_current_user),
    # Use get_db_service for dependency injection
    db_service: SQLiteDatabaseService = Depends(get_db_service)
):
    """
    Retrieves a list of courses (syllabi) the user has made progress on.
    """
    if not current_user or current_user.user_id == "no-auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view progress.",
        )

    try:
        # Call the DB service method to get in-progress courses
        courses_data = db_service.get_user_in_progress_courses(current_user.user_id)

        # Format the data into CourseProgress models
        courses_list = [CourseProgress(**course) for course in courses_data]

        return CourseListResponse(courses=courses_list)

    except Exception as e:
        # Log the exception
        # logger.exception(f"Error fetching user courses for {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course progress.",
        ) from e

# Note: Routes for updating progress are currently in lesson_router.py
# They could potentially be moved here if desired, but require interaction service.
# Example:
# @router.post("/{syllabus_id}/{module_index}/{lesson_index}")
# async def update_progress(...): ...
