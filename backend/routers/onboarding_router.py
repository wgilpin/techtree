""" router for oboarding - create syllabus etc """
#pylint: disable=logging-fstring-interpolation

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.services.onboarding_service import OnboardingService
from backend.logger import logger

router = APIRouter()
onboarding_service = OnboardingService()

# Models
class TopicRequest(BaseModel):
    """
    Request model for starting an assessment.
    """
    topic: str

class AnswerRequest(BaseModel):
    """
    Request model for submitting an answer.
    """
    answer: str

class AssessmentQuestion(BaseModel):
    """
    Response model for an assessment question.
    """
    question: str
    difficulty: str
    search_status: Optional[str] = None
    is_complete: bool = False

class AssessmentAnswer(BaseModel):
    """
    Response model for an assessment answer.
    """
    is_complete: bool
    question: Optional[str] = None
    difficulty: Optional[str] = None
    feedback: Optional[str] = None
    knowledge_level: Optional[str] = None
    score: Optional[float] = None

class AssessmentResult(BaseModel):
    """
    Response model for the final assessment result.
    """
    topic: str
    knowledge_level: str
    score: float
    question_count: int

# Routes
@router.post("/assessment", response_model=AssessmentQuestion)
async def start_assessment(
    topic_req: TopicRequest
):
    """
    Start a new assessment on a topic.
    """
    user_id = None  # No authentication required
    logger.info(f"Starting assessment for topic: {topic_req.topic}, user_id: {user_id}")

    try:
        logger.info("Calling onboarding_service.start_assessment")
        result = await onboarding_service.start_assessment(topic_req.topic, user_id)
        logger.info(f"Assessment started successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Error starting assessment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting assessment: {str(e)}"
        ) from e

@router.post("/answer", response_model=AssessmentAnswer)
async def submit_answer(answer_req: AnswerRequest):
    """
    Submit an answer to the current question.
    """
    logger.info(f"Entering submit_answer endpoint with answer: {answer_req.answer}")
    try:
        result = await onboarding_service.submit_answer(answer_req.answer)
        return result
    except Exception as e:
        logger.error(f"Error processing answer. Initial error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing answer: {str(e)}"
        ) from e

@router.get("/result", response_model=AssessmentResult)
async def get_assessment_result():
    """
    Get the final result of the assessment.
    """
    logger.info("Entering get_assessment_result endpoint")
    try:
        result = await onboarding_service.get_result()
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving assessment result: {str(e)}"
        ) from e

@router.post("/reset")
async def reset_assessment():
    """
    Reset the current assessment session.
    """
    logger.info("Entering reset_assessment endpoint")
    onboarding_service.reset()
    return {"detail": "Assessment session reset successfully"}