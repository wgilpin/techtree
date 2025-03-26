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

# --- Pydantic Models ---

# ... (existing models: LessonRequest, ExerciseSubmission, etc.) ...

# New models for chat
class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str

class ChatMessage(BaseModel):
    """Model for a single message in the conversation history."""
    role: str # 'user' or 'assistant'
    content: str

class ChatTurnResponse(BaseModel):
    """Response model for a chat turn, containing AI responses."""
    responses: List[ChatMessage]
    error: Optional[str] = None # Include optional error field

# Updated model for GET /lesson to include state
class LessonDataResponse(BaseModel):
    """Response model for lesson data including conversational state."""
    lesson_id: Optional[str] # Can be None if lesson doesn't exist yet?
    syllabus_id: str
    module_index: int
    lesson_index: int
    content: Optional[Dict[str, Any]] # Base content (exposition, exercise defs, etc.)
    lesson_state: Optional[Dict[str, Any]] # Conversational state
    is_new: bool


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
    lesson_id: str # This might need to be syllabus_id/module/lesson indices now
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
@router.get("/{syllabus_id}/{module_index}/{lesson_index}", response_model=LessonDataResponse) # Updated response model
async def get_lesson_data( # Renamed function for clarity
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None # Keep Response for headers if needed
):
    """
    Get or generate lesson content structure and current conversational state.
    """
    logger.info(f"Entering get_lesson_data endpoint for syllabus: {syllabus_id}, mod: {module_index}, lesson: {lesson_index}")
    user_id = current_user.user_id if current_user else None
    # Handle no-auth if necessary
    # if current_user and current_user.user_id == "no-auth":
    #     response.headers["X-No-Auth"] = "true" # Example

    try:
        # This service method now returns content and lesson_state
        result = await lesson_service.get_or_generate_lesson(
            syllabus_id,
            module_index,
            lesson_index,
            user_id
        )
        # Ensure the response matches the LessonDataResponse model
        return LessonDataResponse(**result)
    except ValueError as e:
        logger.error(f"Value error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson data: {str(e)}"
        ) from e

# Add new POST endpoint for chat
@router.post("/chat/{syllabus_id}/{module_index}/{lesson_index}", response_model=ChatTurnResponse)
async def handle_chat_message(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    request_body: ChatMessageRequest,
    current_user: User = Depends(get_current_user), # Require authentication for chat
):
    """
    Process a user's chat message for a specific lesson and return the AI's response.
    """
    # Check authentication first
    if not current_user or current_user.user_id == "no-auth": # Ensure authenticated user
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to chat."
        )

    # Log after confirming user exists
    logger.info(f"Entering handle_chat_message for syllabus: {syllabus_id}, mod: {module_index}, lesson: {lesson_index}, user: {current_user.user_id}")

    try:
        result = await lesson_service.handle_chat_turn(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            user_message=request_body.message
        )
        if "error" in result:
             # If service layer handled an error and returned it
             return ChatTurnResponse(responses=[], error=result["error"])
        else:
             # Map result['responses'] to ChatMessage model if needed, though structure matches
             return ChatTurnResponse(responses=result.get("responses", []))

    except ValueError as e: # Catch errors like "Lesson state not found"
        logger.error(f"Value error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # Or 400 Bad Request?
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat message: {str(e)}"
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
