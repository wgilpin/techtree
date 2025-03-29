"""fastApi router for onboarding"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# Corrected import: get_db -> get_db_service
# Import get_onboarding_service explicitly
from backend.dependencies import get_onboarding_service
from backend.services.onboarding_service import OnboardingService
from backend.logger import logger # Import logger

router = APIRouter()

# --- Pydantic Models ---

class OnboardingRequest(BaseModel):
    """Request model for starting the onboarding process."""
    topic: str
    user_id: Optional[str] = None # Optional user ID

# Updated response model for starting onboarding
class OnboardingResponse(BaseModel):
    """Response model for the initial onboarding state."""
    question: str
    difficulty: str
    search_status: Optional[str] = None
    is_complete: bool = False # Should always be false initially
    logs: Optional[List[str]] = None # For debugging

# Updated request model for submitting an answer
class AnswerRequest(BaseModel):
    """Request model for submitting an answer during onboarding."""
    answer: str # Expect a single answer string

# New response model for submitting an answer
class AnswerResponse(BaseModel):
    """Response model after submitting an answer."""
    is_complete: bool
    knowledge_level: Optional[str] = None # Only present if complete
    score: Optional[float] = None # Only present if complete
    feedback: str
    next_question: Optional[str] = None # Only present if not complete
    next_difficulty: Optional[str] = None # Only present if not complete


# --- Onboarding Routes ---

@router.post("/start", response_model=OnboardingResponse)
async def start_onboarding( # Added return type hint
    request_body: OnboardingRequest,
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
) -> OnboardingResponse:
    """
    Starts the onboarding process for a given topic.
    Generates the first assessment question.
    """
    logger.info(f"Starting onboarding for topic: {request_body.topic}, user: {request_body.user_id}")
    try:
        # Call the service method to start onboarding
        session_data = await onboarding_service.start_assessment(
            topic=request_body.topic, user_id=request_body.user_id
        )

        if session_data.get("error"):
             logger.error(f"Onboarding service returned error: {session_data['error']}")
             # Include logs in the error detail if available
             error_detail = f"Failed to initialize onboarding: {session_data['error']}"
             if session_data.get("logs"):
                 error_detail += f" Logs: {'; '.join(session_data['logs'])}"
             raise HTTPException(status_code=500, detail=error_detail)

        if "question" not in session_data or "difficulty" not in session_data:
             logger.error("Onboarding service did not return expected question data.")
             raise HTTPException(status_code=500, detail="Failed to initialize onboarding session.")

        return OnboardingResponse(
            question=session_data["question"],
            difficulty=session_data["difficulty"],
            search_status=session_data.get("search_status"),
            logs=session_data.get("logs") # Include logs if present
        )
    except ValueError as e:
        logger.error(f"Value error starting onboarding: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error starting onboarding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during onboarding.") from e


@router.post("/submit", response_model=AnswerResponse)
async def submit_onboarding_answer( # Added return type hint
    request_body: AnswerRequest,
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
) -> AnswerResponse:
    """
    Submits a user answer for the current onboarding question and gets feedback/next question or result.
    """
    logger.info("Submitting onboarding answer...") # Avoid logging the answer itself
    try:
        # Call the service method to process the single answer
        result_data = await onboarding_service.submit_answer(
            answer=request_body.answer
        )

        if result_data.get("is_complete"):
            # Assessment is finished
            logger.info("Onboarding assessment complete.")
            return AnswerResponse(
                is_complete=True,
                knowledge_level=result_data.get("knowledge_level"),
                score=result_data.get("score"),
                feedback=result_data.get("feedback", "")
            )
        else:
            # Assessment continues
            logger.info("Onboarding assessment continues, returning next question.")
            return AnswerResponse(
                is_complete=False,
                feedback=result_data.get("feedback", ""),
                next_question=result_data.get("question"),
                next_difficulty=result_data.get("difficulty")
            )

    except ValueError as e:
        logger.error(f"Value error submitting onboarding answer: {e}", exc_info=True)
        # Could be 400 for bad answers or 404 if session wasn't started
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error submitting onboarding answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during answer submission.") from e