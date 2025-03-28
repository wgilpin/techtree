"""fastApi router for lessons"""

from typing import Any, Dict, List, Optional

# Import necessary dependencies
from fastapi import Depends  # Add Depends
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from backend.dependencies import get_current_user, get_db
from backend.logger import logger
# Add Exercise and AssessmentQuestion to imports
from backend.models import User, GeneratedLessonContent, Exercise, AssessmentQuestion
from backend.routers.syllabus_router import get_syllabus_service
from backend.services.lesson_service import LessonService
from backend.services.sqlite_db import SQLiteDatabaseService

# We also need SyllabusService to instantiate LessonService
from backend.services.syllabus_service import SyllabusService

router = APIRouter()
# Removed direct instantiation of lesson_service


def get_lesson_service(
    db: SQLiteDatabaseService = Depends(get_db),
    syllabus_service: SyllabusService = Depends(get_syllabus_service),
) -> LessonService:
    """Dependency function to get LessonService instance"""
    return LessonService(db_service=db, syllabus_service=syllabus_service)


# --- Pydantic Models ---

# ... (existing models: LessonRequest, ExerciseSubmission, etc.) ...


# New models for chat
class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    message: str


class ChatMessage(BaseModel):
    """Model for a single message in the conversation history."""

    role: str  # 'user' or 'assistant'
    content: str


class ChatTurnResponse(BaseModel):
    """Response model for a chat turn, containing AI responses."""

    responses: List[ChatMessage]
    error: Optional[str] = None  # Include optional error field


# Updated model for GET /lesson to include state
class LessonDataResponse(BaseModel):
    """Response model for lesson data including conversational state."""

    lesson_id: Optional[str]  # Can be None if lesson doesn't exist yet?
    syllabus_id: str
    module_index: int
    lesson_index: int
    content: Optional[GeneratedLessonContent]  # Use the specific Pydantic model
    lesson_state: Optional[Dict[str, Any]]  # Conversational state (Keep as dict for now)
    is_new: bool


# Add response models for new endpoints
class ExerciseResponse(BaseModel):
    exercise: Optional[Exercise]
    error: Optional[str] = None

class AssessmentQuestionResponse(BaseModel):
    question: Optional[AssessmentQuestion]
    error: Optional[str] = None


# Existing models (ensure they are still here or adjust if needed)
class LessonRequest(BaseModel):
    """
    Request model for retrieving a lesson. (May not be needed if using path params)
    """

    syllabus_id: str
    module_index: int
    lesson_index: int


class ExerciseSubmission(BaseModel):
    """
    Request model for submitting an exercise answer.
    """

    lesson_id: str  # This might need to be syllabus_id/module/lesson indices now
    exercise_index: int
    answer: str


# LessonContent might be replaced by LessonDataResponse
# class LessonContent(BaseModel):
#     """
#     Response model for lesson content.
#     """
#     lesson_id: str
#     syllabus_id: str
#     module_index: int
#     lesson_index: int
#     content: Dict[str, Any]
#     is_new: bool


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


# --- API Routes ---


# Modify existing GET endpoint
@router.get(
    "/{syllabus_id}/{module_index}/{lesson_index}", response_model=LessonDataResponse
)  # Updated response model
# Inject LessonService
async def get_lesson_data(  # Renamed function for clarity
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: Optional[User] = Depends(get_current_user),
    #pylint: disable=unused-argument
    response: Response = None,  # Keep Response for headers if needed
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Get or generate lesson content structure and current conversational state.
    """
    logger.info(
        "Entering get_lesson_data endpoint for syllabus:"
        f" {syllabus_id}, mod: {module_index}, lesson: {lesson_index}"
    )
    user_id = current_user.user_id if current_user else None
    # Handle no-auth if necessary
    # if current_user and current_user.user_id == "no-auth":
    #     response.headers["X-No-Auth"] = "true" # Example

    try:
        # This service method now returns content and lesson_state
        result = await lesson_service.get_or_generate_lesson(
            syllabus_id, module_index, lesson_index, user_id
        )
        # Ensure the response matches the LessonDataResponse model

        # Ensure the response matches the LessonDataResponse model
        # Convert lesson_id to string if present, as the model expects a string
        if result.get("lesson_id") is not None:
            result["lesson_id"] = str(result["lesson_id"])
        # The service result keys ("content", "lesson_state", etc.) should directly match the model
        return LessonDataResponse(**result)
    except ValueError as e:
        logger.error(f"Value error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson data: {str(e)}",
        ) from e


# Add new POST endpoint for chat
@router.post(
    "/chat/{syllabus_id}/{module_index}/{lesson_index}", response_model=ChatTurnResponse
)
# Inject LessonService
async def handle_chat_message(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    request_body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),  # Require authentication for chat
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Process a user's chat message for a specific lesson and return the AI's response.
    """
    # Check authentication first
    if (
        not current_user or current_user.user_id == "no-auth"
    ):  # Ensure authenticated user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to chat.",
        )

    # Log after confirming user exists
    logger.info(
        "Entering handle_chat_message for syllabus: "
        f"{syllabus_id}, mod: {module_index}, "
        f"lesson: {lesson_index}, user: {current_user.user_id}"
    )

    try:
        result = await lesson_service.handle_chat_turn(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            user_message=request_body.message,
        )
        if "error" in result:
            # If service layer handled an error and returned it
            return ChatTurnResponse(responses=[], error=result["error"])
        else:
            # Map result['responses'] to ChatMessage model if needed, though structure matches
            return ChatTurnResponse(responses=result.get("responses", []))

    except ValueError as e:  # Catch errors like "Lesson state not found"
        logger.error(f"Value error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)  # Or 400 Bad Request?
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat message: {str(e)}",
        ) from e


# Add new POST endpoint for generating exercises
@router.post(
    "/exercise/{syllabus_id}/{module_index}/{lesson_index}", response_model=ExerciseResponse
)
async def generate_exercise(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: User = Depends(get_current_user),  # Require authentication
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Generates a new exercise for the specified lesson on demand.
    """
    if not current_user or current_user.user_id == "no-auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to generate exercises.",
        )

    logger.info(
        "Entering generate_exercise for syllabus: "
        f"{syllabus_id}, mod: {module_index}, "
        f"lesson: {lesson_index}, user: {current_user.user_id}"
    )

    try:
        new_exercise = await lesson_service.generate_exercise_for_lesson(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        if new_exercise:
            return ExerciseResponse(exercise=new_exercise)
        else:
            # If service returns None, it means generation failed gracefully
            return ExerciseResponse(exercise=None, error="Failed to generate a new exercise.")

    except ValueError as e: # Catch errors like "Lesson state not found"
        logger.error(f"Value error in generate_exercise: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e: # Catch errors from generation itself
         logger.error(f"Runtime error in generate_exercise: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in generate_exercise: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating exercise: {str(e)}",
        ) from e


# Add new POST endpoint for generating assessment questions
@router.post(
    "/assessment/{syllabus_id}/{module_index}/{lesson_index}", response_model=AssessmentQuestionResponse
)
async def generate_assessment_question(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: User = Depends(get_current_user),  # Require authentication
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Generates a new assessment question for the specified lesson on demand.
    """
    if not current_user or current_user.user_id == "no-auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to generate assessment questions.",
        )

    logger.info(
        "Entering generate_assessment_question for syllabus: "
        f"{syllabus_id}, mod: {module_index}, "
        f"lesson: {lesson_index}, user: {current_user.user_id}"
    )

    try:
        new_question = await lesson_service.generate_assessment_question_for_lesson(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        if new_question:
            return AssessmentQuestionResponse(question=new_question)
        else:
            return AssessmentQuestionResponse(question=None, error="Failed to generate a new assessment question.")

    except ValueError as e:
        logger.error(f"Value error in generate_assessment_question: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
         logger.error(f"Runtime error in generate_assessment_question: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in generate_assessment_question: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating assessment question: {str(e)}",
        ) from e


@router.get("/by-id/{lesson_id}", response_model=Dict[str, Any])
# Inject LessonService
async def get_lesson_by_id(
    lesson_id: str, lesson_service: LessonService = Depends(get_lesson_service)
):
    """
    Get a lesson by its ID.
    """
    logger.info(f"Entering get_lesson_by_id endpoint for lesson_id: {lesson_id}")
    try:
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        return lesson
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson: {str(e)}",
        ) from e


@router.post("/exercise/evaluate", response_model=ExerciseFeedback)
# Inject LessonService
async def evaluate_exercise(
    submission: ExerciseSubmission,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None,
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Evaluate a user's answer to an exercise.
    """
    logger.info(
        "Entering evaluate_exercise endpoint for lesson_id:"
        f" {submission.lesson_id}, exercise_index: {submission.exercise_index}"
    )
    user_id = current_user.user_id if current_user else None
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"

    try:
        result = await lesson_service.evaluate_exercise(
            submission.lesson_id, submission.exercise_index, submission.answer, user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating exercise: {str(e)}",
        ) from e


@router.post("/progress", response_model=ProgressResponse)
# Inject LessonService
async def update_lesson_progress(
    progress: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    response: Response = None,
    lesson_service: LessonService = Depends(get_lesson_service),
):
    """
    Update user's progress for a specific lesson.
    """
    logger.info(
        "Entering update_lesson_progress endpoint for syllabus_id:"
        f" {progress.syllabus_id}, module_index: {progress.module_index},"
        f" lesson_index: {progress.lesson_index}, user: {current_user.email}"
    )
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"
    try:
        result = await lesson_service.update_lesson_progress(
            current_user.user_id,
            progress.syllabus_id,
            progress.module_index,
            progress.lesson_index,
            progress.status,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating progress: {str(e)}",
        ) from e
