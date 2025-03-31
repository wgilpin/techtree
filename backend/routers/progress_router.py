# backend/routers/progress_router.py
"""fastApi router for user progress"""

import logging # Added logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

# Corrected import: get_db -> get_db_service
from backend.dependencies import get_current_user, get_db_service
from backend.models import User
from backend.services.sqlite_db import SQLiteDatabaseService # Import for type hint

router = APIRouter()
logger = logging.getLogger(__name__) # Added logger instance

# --- Pydantic Models ---

# pylint: disable=too-few-public-methods
class CourseProgress(BaseModel):
    """Model representing progress summary for a course (syllabus)."""
    syllabus_id: str
    topic: str
    level: str
    completed_lessons: int
    total_lessons: int
    progress_percentage: float = Field(..., ge=0, le=100)
    last_accessed: str # ISO format timestamp

# pylint: disable=too-few-public-methods
class CourseListResponse(BaseModel):
    """Response model for listing courses the user has progress in."""
    courses: List[CourseProgress]

# --- Progress Routes ---

@router.get("/courses", response_model=CourseListResponse)
async def get_user_courses( # Added return type hint
    current_user: User = Depends(get_current_user),
    db_service: SQLiteDatabaseService = Depends(get_db_service)
) -> CourseListResponse:
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

        # --- DEBUG LOGGING ---
        # Log the raw data received from the database service
        logger.info(f"Data received from DB service (get_user_in_progress_courses): {courses_data}")
        # --- END DEBUG LOGGING ---

        # Format the data into CourseProgress models
        # This will now include progress_percentage due to the updated model
        courses_list = [CourseProgress(**course) for course in courses_data]

        return CourseListResponse(courses=courses_list)

    except Exception as e:
        # Log the exception including the original error type
        logger.exception(f"Error fetching user courses for {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course progress.",
        ) from e

# Note: Routes for updating progress are currently in lesson_router.py
# They could potentially be moved here if desired, but require interaction service.
# Example:
# @router.post("/{syllabus_id}/{module_index}/{lesson_index}")
# async def update_progress(...): ...
