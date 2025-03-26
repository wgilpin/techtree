from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.models import User
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.models import User
# Import Depends and get_db, keep get_current_user
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from fastapi import Depends # Ensure Depends is imported

router = APIRouter()
# Removed direct DB instantiation and print statement


# Models
class CourseProgress(BaseModel):
    """
    Model for representing a user's progress in a course.
    """

    syllabus_id: str
    topic: str
    level: str
    progress_percentage: float
    completed_lessons: int
    total_lessons: int


class DetailedProgress(BaseModel):
    """
    Model for representing detailed progress information for a lesson.
    """

    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str
    score: Optional[float] = None
    created_at: str
    updated_at: str


# Routes
@router.get("/courses", response_model=List[CourseProgress])
async def get_in_progress_courses(
    current_user: User = Depends(get_current_user), response: Response = None
):
    """
    Get all courses in progress for the current user.
    """
    logger.info(f"Entering get_in_progress_courses endpoint for user: {current_user.email}")
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        courses = db_service.get_user_in_progress_courses(current_user.user_id)
        return courses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving courses: {str(e)}",
        ) from e


@router.get("/syllabus/{syllabus_id}", response_model=List[DetailedProgress])
async def get_syllabus_progress(
    syllabus_id: str,
    current_user: User = Depends(get_current_user),
    response: Response = None,
):
    """
    Get detailed progress for a specific syllabus.
    """
    logger.info(f"Entering get_syllabus_progress endpoint for syllabus_id: {syllabus_id}, user: {current_user.email}")
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        progress = db_service.get_user_syllabus_progress(
            current_user.user_id, syllabus_id
        )
        return progress
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress: {str(e)}",
        ) from e


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_activity(
    current_user: User = Depends(get_current_user), response: Response = None
):
    """
    Get recent activity for the current user.

    Returns:
        A list of dictionaries, each representing a recent activity entry.
        Each entry includes syllabus and lesson information, as well as progress details.
    """
    logger.info(f"Entering get_recent_activity endpoint for user: {current_user.email}")
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        # Get all user progress entries
        query = """
            SELECT * FROM user_progress
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 10
        """
        recent_entries = db_service.execute_read_query(query, (current_user.user_id,))

        # Enrich with syllabus and lesson information
        enriched_entries = []
        for entry in recent_entries:
            entry_dict = dict(entry)
            syllabus = db_service.get_syllabus_by_id(entry_dict["syllabus_id"])
            # lesson = db_service.get_lesson_content(
            #     entry_dict["syllabus_id"],
            #     entry_dict["module_index"],
            #     entry_dict["lesson_index"]
            # )

            module_title = ""
            # lesson_title = ""  # No longer needed
            if syllabus and "content" in syllabus:
                content = syllabus["content"]
                if (
                    "modules" in content
                    and len(content["modules"]) > entry_dict["module_index"]
                ):
                    module = content["modules"][entry_dict["module_index"]]
                    module_title = module["title"]

                    # if "lessons" in module and
                    #   len(module["lessons"]) > entry_dict["lesson_index"]:  # No longer needed
                    #     lesson_title = module["lessons"]\
                        # [entry_dict["lesson_index"]]["title"]  # No longer needed

            enriched_entries.append(
                {
                    "progress_id": entry_dict["progress_id"],
                    "syllabus_id": entry_dict["syllabus_id"],
                    "topic": syllabus["topic"] if syllabus else "Unknown Topic",
                    "module_index": entry_dict["module_index"],
                    "module_title": module_title,
                    "lesson_index": entry_dict["lesson_index"],
                    "lesson_title": "",  #  entry_dict["lesson_index"],
                    "status": entry_dict["status"],
                    "score": entry_dict["score"],
                    "updated_at": entry_dict["updated_at"],
                }
            )

        return enriched_entries
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recent activity: {str(e)}",
        ) from e


@router.get("/summary", response_model=Dict[str, Any])
async def get_progress_summary(
    current_user: User = Depends(get_current_user), response: Response = None
):
    """
    Get summary statistics of user's learning progress.

    Returns:
        A dictionary containing summary statistics, including:
        - total_topics: The number of unique topics the user has engaged with.
        - total_lessons: The total number of lessons the user has interacted with.
        - completed_lessons: The number of lessons the user has completed.
        - in_progress_lessons: The number of lessons the user is currently working on.
        - avg_lesson_score: The average score across all lessons.
        - avg_assessment_score: The average score across all assessments.
        - assessments_taken: The total number of assessments taken.
    """
    logger.info(f"Entering get_progress_summary endpoint for user: {current_user.email}")
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        # Get all user progress entries
        progress_query = """
            SELECT * FROM user_progress
            WHERE user_id = ?
        """
        progress_entries = db_service.execute_read_query(
            progress_query, (current_user.user_id,)
        )
        progress_entries = [dict(entry) for entry in progress_entries]

        # Get all user assessments
        assessments = db_service.get_user_assessments(current_user.user_id)

        # Calculate statistics
        total_lessons = len(progress_entries)
        completed_lessons = len(
            [p for p in progress_entries if p["status"] == "completed"]
        )
        in_progress_lessons = len(
            [p for p in progress_entries if p["status"] == "in_progress"]
        )

        # Get unique topics
        syllabus_ids = set(entry["syllabus_id"] for entry in progress_entries)
        topics = set()
        for sid in syllabus_ids:
            syllabus = db_service.get_syllabus_by_id(sid)
            if syllabus:
                topics.add(syllabus["topic"])

        # Calculate average scores
        lesson_scores = [p["score"] for p in progress_entries if p["score"] is not None]
        assessment_scores = [a["score"] for a in assessments if a["score"] is not None]

        avg_lesson_score = (
            sum(lesson_scores) / len(lesson_scores) if lesson_scores else 0
        )
        avg_assessment_score = (
            sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0
        )

        return {
            "total_topics": len(topics),
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "in_progress_lessons": in_progress_lessons,
            "avg_lesson_score": avg_lesson_score,
            "avg_assessment_score": avg_assessment_score,
            "assessments_taken": len(assessments),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress summary: {str(e)}",
        ) from e
