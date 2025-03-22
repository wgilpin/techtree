from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.onboarding_service import OnboardingService
from routers.auth_router import User, get_current_user

router = APIRouter()
onboarding_service = OnboardingService()

# Models
class TopicRequest(BaseModel):
    topic: str

class AnswerRequest(BaseModel):
    answer: str

class AssessmentQuestion(BaseModel):
    question: str
    difficulty: str
    search_status: Optional[str] = None
    is_complete: bool = False

class AssessmentAnswer(BaseModel):
    is_complete: bool
    question: Optional[str] = None
    difficulty: Optional[str] = None
    feedback: Optional[str] = None
    knowledge_level: Optional[str] = None
    score: Optional[float] = None

class AssessmentResult(BaseModel):
    topic: str
    knowledge_level: str
    score: float
    question_count: int

# Routes
@router.post("/assessment", response_model=AssessmentQuestion)
async def start_assessment(
    topic_req: TopicRequest,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Start a new assessment on a topic"""
    user_id = current_user.user_id if current_user else None

    try:
        result = await onboarding_service.start_assessment(topic_req.topic, user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting assessment: {str(e)}"
        )

@router.post("/answer", response_model=AssessmentAnswer)
async def submit_answer(answer_req: AnswerRequest):
    """Submit an answer to the current question"""
    try:
        result = await onboarding_service.submit_answer(answer_req.answer)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing answer: {str(e)}"
        )

@router.get("/result", response_model=AssessmentResult)
async def get_assessment_result():
    """Get the final result of the assessment"""
    try:
        result = await onboarding_service.get_result()
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving assessment result: {str(e)}"
        )

@router.post("/reset")
async def reset_assessment():
    """Reset the current assessment session"""
    onboarding_service.reset()
    return {"detail": "Assessment session reset successfully"}