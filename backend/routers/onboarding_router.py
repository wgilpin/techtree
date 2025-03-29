"""fastApi router for onboarding"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

# Corrected import: get_db -> get_db_service
# Import get_onboarding_service explicitly
from backend.dependencies import get_db_service, get_onboarding_service
from backend.services.onboarding_service import OnboardingService
from backend.services.sqlite_db import SQLiteDatabaseService # Import for type hint
from backend.logger import logger # Import logger

router = APIRouter()

# --- Pydantic Models ---

class OnboardingRequest(BaseModel):
    """Request model for starting the onboarding process."""
    topic: str
    user_id: Optional[str] = None # Optional user ID

class OnboardingResponse(BaseModel):
    """Response model for the initial onboarding state."""
    session_id: str # Or some identifier for the onboarding session
    initial_questions: List[Dict] # List of initial assessment questions

class AnswerRequest(BaseModel):
    """Request model for submitting answers during onboarding."""
    session_id: str
    answers: Dict[str, str] # Question ID -> User Answer mapping

class AssessmentResult(BaseModel):
    """Response model for the final assessment result."""
    session_id: str
    knowledge_level: str
    recommendations: Optional[List[str]] = None # Optional recommendations

# --- Onboarding Routes ---

@router.post("/start", response_model=OnboardingResponse)
async def start_onboarding(
    request_body: OnboardingRequest,
    # Use get_db_service for dependency injection
    db_service: SQLiteDatabaseService = Depends(get_db_service),
    # Inject OnboardingService explicitly using the getter function
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    """
    Starts the onboarding process for a given topic.
    Generates initial assessment questions.
    """
    logger.info(f"Starting onboarding for topic: {request_body.topic}, user: {request_body.user_id}")
    try:
        # Call the service method to start onboarding
        session_data = await onboarding_service.start_assessment(
            topic=request_body.topic, user_id=request_body.user_id
        )
        # Expecting session_data to contain session_id and initial_questions
        if not session_data or "session_id" not in session_data or "questions" not in session_data:
             logger.error("Onboarding service did not return expected data structure.")
             raise HTTPException(status_code=500, detail="Failed to initialize onboarding session.")

        return OnboardingResponse(
            session_id=session_data["session_id"],
            initial_questions=session_data["questions"]
        )
    except ValueError as e:
        logger.error(f"Value error starting onboarding: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error starting onboarding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during onboarding.") from e


@router.post("/submit", response_model=AssessmentResult)
async def submit_onboarding_answers(
    request_body: AnswerRequest,
    # Use get_db_service for dependency injection
    db_service: SQLiteDatabaseService = Depends(get_db_service),
    # Inject OnboardingService explicitly using the getter function
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    """
    Submits user answers for the onboarding assessment and gets the result.
    """
    logger.info(f"Submitting answers for onboarding session: {request_body.session_id}")
    try:
        # Call the service method to process answers and get results
        result_data = await onboarding_service.process_answers_and_get_level(
            session_id=request_body.session_id, answers=request_body.answers
        )

        if not result_data or "knowledge_level" not in result_data:
            logger.error("Onboarding service did not return expected result structure.")
            raise HTTPException(status_code=500, detail="Failed to finalize onboarding assessment.")

        return AssessmentResult(
            session_id=request_body.session_id, # Return the session ID back
            knowledge_level=result_data["knowledge_level"],
            recommendations=result_data.get("recommendations") # Optional field
        )
    except ValueError as e:
        logger.error(f"Value error submitting onboarding answers: {e}", exc_info=True)
        # Could be 400 for bad answers or 404 for bad session ID
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error submitting onboarding answers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during assessment submission.") from e