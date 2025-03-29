"""fastApi router for lessons"""

from typing import Any, Dict, List, Optional

# Import necessary dependencies
from fastapi import Depends
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

# Import new dependency functions and User model
from backend.dependencies import (
    get_current_user,
    get_interaction_service,  # New
    get_exposition_service,  # New
)
from backend.logger import logger
# Import ChatMessage from models now
from backend.models import User, GeneratedLessonContent, Exercise, AssessmentQuestion, ChatMessage

# Import the new service types for type hinting
from backend.services.lesson_interaction_service import LessonInteractionService
from backend.services.lesson_exposition_service import LessonExpositionService

router = APIRouter()

# --- Pydantic Models ---


# Models for chat
class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str


# REMOVED local ChatMessage definition (lines 34-37)


class ChatTurnResponse(BaseModel):
    """Response model for a chat turn, containing AI responses."""
    responses: List[ChatMessage] # This now refers to the imported ChatMessage
    error: Optional[str] = None


# Updated model for GET /lesson to include state
class LessonDataResponse(BaseModel):
    """Response model for lesson data including conversational state."""
    lesson_id: Optional[int]
    content: Optional[GeneratedLessonContent]
    lesson_state: Optional[Dict[str, Any]]


# Response models for new generation endpoints
class ExerciseResponse(BaseModel):
    """Response model for generating an exercise."""
    exercise: Optional[Exercise]
    error: Optional[str] = None


class AssessmentQuestionResponse(BaseModel):
    """Response model for generating an assessment question."""
    question: Optional[AssessmentQuestion]
    error: Optional[str] = None


# Model for getting exposition by ID
class LessonExpositionResponse(BaseModel):
    """Response model for retrieving lesson exposition by ID."""
    exposition: Optional[GeneratedLessonContent]
    error: Optional[str] = None


class ProgressUpdate(BaseModel):
    """Request model for updating lesson progress status."""
    status: str


class ProgressResponse(BaseModel):
    """Response model for lesson progress updates."""
    progress_id: Optional[int]
    user_id: str
    syllabus_id: str
    module_index: int
    lesson_index: int
    status: str


# --- API Routes ---


@router.get(
    "/{syllabus_id}/{module_index}/{lesson_index}", response_model=LessonDataResponse
)
async def get_lesson_data(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: Optional[User] = Depends(get_current_user),
    interaction_service: LessonInteractionService = Depends(get_interaction_service),
):
    """
    Retrieves or generates lesson data, including static content and user state.

    If a user is authenticated, it fetches or initializes their specific lesson state.
    If no user is authenticated, it only fetches or generates the static lesson content.

    Args:
        syllabus_id: The ID of the parent syllabus.
        module_index: The index of the parent module within the syllabus.
        lesson_index: The index of the lesson within the module.
        current_user: The authenticated user (optional).
        interaction_service: Dependency-injected LessonInteractionService instance.

    Returns:
        LessonDataResponse containing the lesson ID, content, and state (if user).

    Raises:
        HTTPException (404): If the lesson exposition cannot be found or generated.
        HTTPException (500): If there's an internal server error during state handling.
    """
    logger.info(
        "Entering get_lesson_data endpoint for syllabus:"
        f" {syllabus_id}, mod: {module_index}, lesson: {lesson_index}"
    )
    user_id = current_user.user_id if current_user else None
    try:
        result = await interaction_service.get_or_create_lesson_state(
            syllabus_id, module_index, lesson_index, user_id
        )
        return LessonDataResponse(**result)
    except ValueError as e:
        logger.error(f"Value error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(f"Runtime error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in get_lesson_data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson data: {str(e)}",
        ) from e


@router.post(
    "/chat/{syllabus_id}/{module_index}/{lesson_index}", response_model=ChatTurnResponse
)
async def handle_chat_message(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    request_body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    interaction_service: LessonInteractionService = Depends(get_interaction_service),
):
    """
    Processes one turn of a user's chat conversation within a specific lesson.

    Requires user authentication. Loads the current lesson state, passes the user's
    message to the interaction service (which coordinates with the AI), saves the
    updated state, and returns the AI's response messages.

    Args:
        syllabus_id: The ID of the parent syllabus.
        module_index: The index of the parent module.
        lesson_index: The index of the lesson.
        request_body: Contains the user's chat message.
        current_user: The authenticated user.
        interaction_service: Dependency-injected LessonInteractionService instance.

    Returns:
        ChatTurnResponse containing a list of AI response messages or an error message.

    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (404): If the lesson state cannot be found.
        HTTPException (500): If an internal server error occurs.
    """
    if not current_user or current_user.user_id == "no-auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to chat.",
        )
    logger.info(
        "Entering handle_chat_message for syllabus: "
        f"{syllabus_id}, mod: {module_index}, "
        f"lesson: {lesson_index}, user: {current_user.user_id}"
    )
    try:
        result = await interaction_service.handle_chat_turn(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            user_message=request_body.message,
        )
        if "error" in result:
            return ChatTurnResponse(responses=[], error=result["error"])
        else:
            # Ensure the response structure matches ChatTurnResponse
            # The service should return a dict with a 'responses' key containing a list of dicts
            # that match the ChatMessage structure.
            responses_list = result.get("responses", [])
            # Validate/convert if necessary, though Pydantic handles it if types match
            return ChatTurnResponse(responses=responses_list)
    except ValueError as e:
        logger.error(f"Value error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in handle_chat_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat message: {str(e)}",
        ) from e


@router.post(
    "/exercise/{syllabus_id}/{module_index}/{lesson_index}",
    response_model=ExerciseResponse,
)
async def generate_exercise(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: User = Depends(get_current_user),
    interaction_service: LessonInteractionService = Depends(get_interaction_service),
):
    """
    Generates a new, unique exercise for the specified lesson on demand.

    Requires user authentication. Calls the interaction service to generate
    and save the exercise within the user's lesson state.

    Args:
        syllabus_id: The ID of the parent syllabus.
        module_index: The index of the parent module.
        lesson_index: The index of the lesson.
        current_user: The authenticated user.
        interaction_service: Dependency-injected LessonInteractionService instance.

    Returns:
        ExerciseResponse containing the generated Exercise object or an error message.

    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (404): If the lesson state cannot be found.
        HTTPException (500): If exercise generation fails or an internal error occurs.
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
        new_exercise = await interaction_service.generate_exercise(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        if new_exercise:
            return ExerciseResponse(exercise=new_exercise)
        else:
            # If service returns None, indicate failure gracefully
            return ExerciseResponse(
                exercise=None, error="Failed to generate a new exercise."
            )
    except ValueError as e:
        logger.error(f"Value error in generate_exercise: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(f"Runtime error in generate_exercise: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in generate_exercise: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating exercise: {str(e)}",
        ) from e


@router.post(
    "/assessment/{syllabus_id}/{module_index}/{lesson_index}",
    response_model=AssessmentQuestionResponse,
)
async def generate_assessment_question(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    current_user: User = Depends(get_current_user),
    interaction_service: LessonInteractionService = Depends(get_interaction_service),
):
    """
    Generates a new, unique assessment question for the specified lesson on demand.

    Requires user authentication. Calls the interaction service to generate
    and save the assessment question within the user's lesson state.

    Args:
        syllabus_id: The ID of the parent syllabus.
        module_index: The index of the parent module.
        lesson_index: The index of the lesson.
        current_user: The authenticated user.
        interaction_service: Dependency-injected LessonInteractionService instance.

    Returns:
        AssessmentQuestionResponse containing the generated question or an error.

    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (404): If the lesson state cannot be found.
        HTTPException (500): If question generation fails or an internal error occurs.
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
        new_question = await interaction_service.generate_assessment_question(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        if new_question:
            return AssessmentQuestionResponse(question=new_question)
        else:
            # If service returns None, indicate failure gracefully
            return AssessmentQuestionResponse(
                question=None, error="Failed to generate a new assessment question."
            )
    except ValueError as e:
        logger.error(f"Value error in generate_assessment_question: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(
            f"Runtime error in generate_assessment_question: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error in generate_assessment_question: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating assessment question: {str(e)}",
        ) from e


@router.get("/by-id/{lesson_id}", response_model=LessonExpositionResponse)
async def get_lesson_exposition_by_id(
    lesson_id: int,
    exposition_service: LessonExpositionService = Depends(get_exposition_service),
):
    """
    Retrieves the static exposition content for a lesson using its database ID.

    Does not require user authentication as it fetches static content.

    Args:
        lesson_id: The integer primary key of the lesson in the database.
        exposition_service: Dependency-injected LessonExpositionService instance.

    Returns:
        LessonExpositionResponse containing the lesson's static content.

    Raises:
        HTTPException (404): If no lesson exposition is found for the given ID.
        HTTPException (500): If an internal server error occurs.
    """
    logger.info(
        f"Entering get_lesson_exposition_by_id endpoint for lesson_id: {lesson_id}"
    )
    try:
        exposition = await exposition_service.get_exposition_by_id(lesson_id)
        if exposition is None:
            logger.warning(
                f"Lesson exposition with ID {lesson_id} not found by service."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lesson exposition with ID {lesson_id} not found or invalid.",
            )
        return LessonExpositionResponse(exposition=exposition)
    except HTTPException as http_exc:
        raise http_exc
    except ValueError as e: # Should not happen if service handles None return
        logger.error(f"Value error in get_lesson_exposition_by_id: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Unexpected error in get_lesson_exposition_by_id: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson exposition: {str(e)}",
        ) from e


# Comment out evaluate_exercise endpoint
# @router.post("/exercise/evaluate", response_model=ExerciseFeedback) ...


@router.post(
    "/progress/{syllabus_id}/{module_index}/{lesson_index}",
    response_model=ProgressResponse,
)
async def update_lesson_progress(
    syllabus_id: str,
    module_index: int,
    lesson_index: int,
    progress: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    interaction_service: LessonInteractionService = Depends(get_interaction_service),
):
    """
    Updates the progress status for a specific lesson for the authenticated user.

    Allowed statuses are "not_started", "in_progress", "completed".

    Args:
        syllabus_id: The ID of the parent syllabus.
        module_index: The index of the parent module.
        lesson_index: The index of the lesson.
        progress: Request body containing the new status.
        current_user: The authenticated user.
        interaction_service: Dependency-injected LessonInteractionService instance.

    Returns:
        ProgressResponse confirming the updated progress details.

    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (400): If the provided status is invalid.
        HTTPException (404): If the lesson details cannot be found (implicitly via service).
        HTTPException (500): If an internal server error occurs.
    """
    if not current_user or current_user.user_id == "no-auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to update progress.",
        )
    logger.info(
        "Entering update_lesson_progress endpoint for syllabus_id:"
        f" {syllabus_id}, module_index: {module_index},"
        f" lesson_index: {lesson_index}, status: {progress.status}, user: {current_user.user_id}"
    )
    try:
        result = await interaction_service.update_lesson_progress(
            user_id=current_user.user_id,
            syllabus_id=syllabus_id,
            module_index=module_index,
            lesson_index=lesson_index,
            status=progress.status,
        )
        return ProgressResponse(**result)
    except ValueError as e: # Catches invalid status or lesson not found from service
        logger.error(f"Value error in update_lesson_progress: {e}", exc_info=True)
        # Determine if it's a 404 or 400 based on error message?
        # For now, assume 400 for invalid status.
        status_code = status.HTTP_400_BAD_REQUEST if "Invalid status" in str(e) \
            else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in update_lesson_progress: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating progress: {str(e)}",
        ) from e
