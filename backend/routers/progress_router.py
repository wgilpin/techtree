from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from services.db import DatabaseService
from routers.auth_router import User, get_current_user

router = APIRouter()
db_service = DatabaseService()

# Models
class CourseProgress(BaseModel):
    syllabus_id: str
    topic: str
    level: str
    progress_percentage: float
    completed_lessons: int
    total_lessons: int

class DetailedProgress(BaseModel):
    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str
    score: Optional[float] = None
    created_at: str
    updated_at: str

# Routes
@router.get("/courses", response_model=List[CourseProgress])
async def get_in_progress_courses(current_user: User = Depends(get_current_user)):
    """Get all courses in progress for the current user"""
    try:
        courses = db_service.get_user_in_progress_courses(current_user.user_id)
        return courses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving courses: {str(e)}"
        )

@router.get("/syllabus/{syllabus_id}", response_model=List[DetailedProgress])
async def get_syllabus_progress(syllabus_id: str, current_user: User = Depends(get_current_user)):
    """Get detailed progress for a specific syllabus"""
    try:
        progress = db_service.get_user_syllabus_progress(current_user.user_id, syllabus_id)
        return progress
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress: {str(e)}"
        )

@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_activity(current_user: User = Depends(get_current_user)):
    """Get recent activity for the current user"""
    try:
        # Get all user progress entries
        Progress = db_service.User  # Use the Query class from TinyDB
        progress_entries = db_service.user_progress.search(Progress.user_id == current_user.user_id)

        # Sort by updated_at in descending order and limit to 10 entries
        recent_entries = sorted(progress_entries, key=lambda x: x["updated_at"], reverse=True)[:10]

        # Enrich with syllabus and lesson information
        enriched_entries = []
        for entry in recent_entries:
            syllabus = db_service.get_syllabus_by_id(entry["syllabus_id"])
            lesson = db_service.get_lesson_content(
                entry["syllabus_id"],
                entry["module_index"],
                entry["lesson_index"]
            )

            module_title = ""
            lesson_title = ""
            if syllabus and "content" in syllabus:
                content = syllabus["content"]
                if "modules" in content and len(content["modules"]) > entry["module_index"]:
                    module = content["modules"][entry["module_index"]]
                    module_title = module["title"]

                    if "lessons" in module and len(module["lessons"]) > entry["lesson_index"]:
                        lesson_title = module["lessons"][entry["lesson_index"]]["title"]

            enriched_entries.append({
                "progress_id": entry["progress_id"],
                "syllabus_id": entry["syllabus_id"],
                "topic": syllabus["topic"] if syllabus else "Unknown Topic",
                "module_index": entry["module_index"],
                "module_title": module_title,
                "lesson_index": entry["lesson_index"],
                "lesson_title": lesson_title,
                "status": entry["status"],
                "score": entry["score"],
                "updated_at": entry["updated_at"]
            })

        return enriched_entries
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recent activity: {str(e)}"
        )

@router.get("/summary", response_model=Dict[str, Any])
async def get_progress_summary(current_user: User = Depends(get_current_user)):
    """Get summary statistics of user's learning progress"""
    try:
        # Get all user progress entries
        Progress = db_service.User  # Use the Query class from TinyDB
        progress_entries = db_service.user_progress.search(Progress.user_id == current_user.user_id)

        # Get all user assessments
        assessments = db_service.get_user_assessments(current_user.user_id)

        # Calculate statistics
        total_lessons = len(progress_entries)
        completed_lessons = len([p for p in progress_entries if p["status"] == "completed"])
        in_progress_lessons = len([p for p in progress_entries if p["status"] == "in_progress"])

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

        avg_lesson_score = sum(lesson_scores) / len(lesson_scores) if lesson_scores else 0
        avg_assessment_score = sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0

        return {
            "total_topics": len(topics),
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "in_progress_lessons": in_progress_lessons,
            "avg_lesson_score": avg_lesson_score,
            "avg_assessment_score": avg_assessment_score,
            "assessments_taken": len(assessments)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress summary: {str(e)}"
        )