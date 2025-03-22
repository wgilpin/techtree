from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.syllabus_service import SyllabusService
from routers.auth_router import User, get_current_user

router = APIRouter()
syllabus_service = SyllabusService()

# Models
class SyllabusRequest(BaseModel):
    topic: str
    knowledge_level: str

class Module(BaseModel):
    title: str
    summary: str
    lessons: List[Dict[str, Any]]

class SyllabusContent(BaseModel):
    title: str
    description: str
    modules: List[Module]

class SyllabusResponse(BaseModel):
    syllabus_id: str
    topic: str
    level: str
    content: Dict[str, Any]
    is_new: bool

class ModuleResponse(BaseModel):
    title: str
    summary: str
    lessons: List[Dict[str, Any]]

class LessonSummary(BaseModel):
    title: str
    summary: Optional[str] = None
    duration: Optional[str] = None

# Routes
@router.post("/create", response_model=SyllabusResponse)
async def create_syllabus(
    syllabus_req: SyllabusRequest,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Create a new syllabus based on topic and knowledge level"""
    user_id = current_user.user_id if current_user else None

    try:
        result = await syllabus_service.create_syllabus(
            syllabus_req.topic,
            syllabus_req.knowledge_level,
            user_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating syllabus: {str(e)}"
        )

@router.get("/{syllabus_id}", response_model=SyllabusResponse)
async def get_syllabus(syllabus_id: str):
    """Get a syllabus by ID"""
    try:
        syllabus = await syllabus_service.get_syllabus(syllabus_id)
        # Add is_new field to match response model
        syllabus["is_new"] = False
        return syllabus
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving syllabus: {str(e)}"
        )

@router.get("/topic/{topic}/level/{level}", response_model=SyllabusResponse)
async def get_syllabus_by_topic_level(
    topic: str,
    level: str,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get a syllabus by topic and level"""
    user_id = current_user.user_id if current_user else None

    try:
        result = await syllabus_service.get_syllabus_by_topic_level(topic, level, user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving syllabus: {str(e)}"
        )

@router.get("/{syllabus_id}/module/{module_index}", response_model=ModuleResponse)
async def get_module_details(syllabus_id: str, module_index: int):
    """Get details for a specific module in the syllabus"""
    try:
        module = await syllabus_service.get_module_details(syllabus_id, module_index)
        return module
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving module details: {str(e)}"
        )

@router.get("/{syllabus_id}/module/{module_index}/lesson/{lesson_index}", response_model=LessonSummary)
async def get_lesson_summary(syllabus_id: str, module_index: int, lesson_index: int):
    """Get summary for a specific lesson in the syllabus"""
    try:
        lesson = await syllabus_service.get_lesson_details(syllabus_id, module_index, lesson_index)
        return lesson
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson summary: {str(e)}"
        )