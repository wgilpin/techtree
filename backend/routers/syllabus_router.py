""" Router for syllabus endpoints """
#pylint: disable=logging-fstring-interpolation

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from backend.services.syllabus_service import SyllabusService
from backend.models import User
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.services.syllabus_service import SyllabusService
from backend.models import User
from backend.dependencies import get_current_user, get_db # Add get_db
from backend.logger import logger
# Import necessary dependencies
from fastapi import Depends # Add Depends
from backend.services.sqlite_db import SQLiteDatabaseService # Add SQLiteDatabaseService

router = APIRouter()
# Removed direct instantiation of syllabus_service

# Dependency function to get SyllabusService instance
def get_syllabus_service(db: SQLiteDatabaseService = Depends(get_db)) -> SyllabusService:
    return SyllabusService(db_service=db)

# Models
class SyllabusRequest(BaseModel):
    """
    Request model for creating a syllabus.
    """
    topic: str
    knowledge_level: str

class Module(BaseModel):
    """
    Model representing a module within a syllabus.
    """
    title: str
    summary: str
    lessons: List[Dict[str, Any]]

class SyllabusContent(BaseModel):
    """
    Model representing the content of a syllabus.
    """
    title: str
    description: str
    modules: List[Module]

class SyllabusResponse(BaseModel):
    """
    Response model for a syllabus.
    """
    syllabus_id: str
    topic: str
    level: str
    content: Dict[str, Any]
    is_new: bool

class ModuleResponse(BaseModel):
    """
    Response model for a module.
    """
    title: str
    summary: str
    lessons: List[Dict[str, Any]]

class LessonSummary(BaseModel):
    """
    Model for a lesson summary.
    """
    title: str
    summary: Optional[str] = None
    duration: Optional[str] = None

# Routes
@router.post("/create", response_model=SyllabusResponse)
# Inject SyllabusService
async def create_syllabus(
    syllabus_req: SyllabusRequest,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None,
    syllabus_service: SyllabusService = Depends(get_syllabus_service)
):
    """
    Create a new syllabus based on topic and knowledge level.
    """
    logger.info(f"Entering create_syllabus endpoint for topic: {syllabus_req.topic}, level: {syllabus_req.knowledge_level}")
    user_id = current_user.user_id if current_user else None
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"

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
        ) from e

@router.get("/{syllabus_id}", response_model=SyllabusResponse)
# Inject SyllabusService
async def get_syllabus(syllabus_id: str, syllabus_service: SyllabusService = Depends(get_syllabus_service)):
    """
    Get a syllabus by ID.
    """
    logger.info(f"Entering get_syllabus endpoint for syllabus_id: {syllabus_id}")
    try:
        syllabus = await syllabus_service.get_syllabus(syllabus_id)
        # Add is_new field to match response model
        syllabus["is_new"] = False
        return syllabus
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving syllabus: {str(e)}"
        ) from e

@router.get("/topic/{topic}/level/{level}", response_model=SyllabusResponse)
# Inject SyllabusService
async def get_syllabus_by_topic_level(
    topic: str,
    level: str,
    current_user: Optional[User] = Depends(get_current_user),
    response: Response = None,
    syllabus_service: SyllabusService = Depends(get_syllabus_service)
):
    """
    Get a syllabus by topic and level.
    """
    logger.info(f"Entering get_syllabus_by_topic_level endpoint for topic: {topic}, level: {level}")
    user_id = current_user.user_id if current_user else None
    if current_user and current_user.user_id == "no-auth":
        response.headers["X-No-Auth"] = "true"

    try:
        result = await syllabus_service.get_syllabus_by_topic_level(topic, level, user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving syllabus: {str(e)}"
        ) from e

@router.get("/{syllabus_id}/module/{module_index}", response_model=ModuleResponse)
# Inject SyllabusService
async def get_module_details(syllabus_id: str, module_index: int, syllabus_service: SyllabusService = Depends(get_syllabus_service)):
    """
    Get details for a specific module in the syllabus.
    """
    logger.info(f"Entering get_module_details endpoint for syllabus_id: {syllabus_id}, module_index: {module_index}")
    try:
        module = await syllabus_service.get_module_details(syllabus_id, module_index)
        return module
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving module details: {str(e)}"
        ) from e

@router.get(
    "/{syllabus_id}/module/{module_index}/lesson/{lesson_index}",
    response_model=LessonSummary)
# Inject SyllabusService
async def get_lesson_summary(syllabus_id: str, module_index: int, lesson_index: int, syllabus_service: SyllabusService = Depends(get_syllabus_service)):
    """
    Get summary for a specific lesson in the syllabus.
    """
    logger.info("Entering get_lesson_summary endpoint for syllabus_id:"
                f" {syllabus_id}, module_index: {module_index}, lesson_index: {lesson_index}")
    try:
        lesson = await syllabus_service.get_lesson_details(syllabus_id, module_index, lesson_index)
        return lesson
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lesson summary: {str(e)}"
        ) from e
