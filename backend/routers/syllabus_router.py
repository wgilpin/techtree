# Improved code for backend/routers/syllabus_router.py
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status # Use status constants
from pydantic import BaseModel, Field # Field can be used for better validation/docs

# Assuming get_db_service is NOT directly needed here if SyllabusService handles it
from backend.dependencies import get_current_user, get_syllabus_service
# Removed unused get_db_service import
from backend.models import User
# Removed unused SQLiteDatabaseService import
from backend.services.syllabus_service import SyllabusService

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Pydantic Models ---

# Consider adding example values or more specific field constraints if applicable
class SyllabusRequest(BaseModel):
    """Request model for generating a syllabus."""
    topic: str = Field(..., json_schema_extra={"example": "Introduction to Python"})
    level: str = Field(..., json_schema_extra={"example": "Beginner"})
    user_id: Optional[str] = Field(None, json_schema_extra={"example": "user_abc_123"}) # Optional user ID

class Module(BaseModel):
    """Represents a single module within a syllabus."""
    # Define structure more explicitly if known, e.g.:
    module_id: str = Field(..., json_schema_extra={"example": "mod_1"})
    title: str = Field(..., json_schema_extra={"example": "Module 1: Getting Started"})
    content: Dict[str, Any] # Or a more specific model

class SyllabusResponse(BaseModel):
    """Response model for a generated syllabus."""
    syllabus_id: str = Field(..., json_schema_extra={"example": "sy_xyz_789"})
    topic: str = Field(..., json_schema_extra={"example": "Introduction to Python"})
    level: str = Field(..., json_schema_extra={"example": "Beginner"})
    # Use the specific Module model for better type safety and documentation
    modules: List[Module]

class SyllabusSummary(BaseModel):
    """Summary model for listing syllabi."""
    syllabus_id: str = Field(..., json_schema_extra={"example": "sy_xyz_789"})
    topic: str = Field(..., json_schema_extra={"example": "Introduction to Python"})
    level: str = Field(..., json_schema_extra={"example": "Beginner"})

class SyllabusListResponse(BaseModel):
    """Response model for listing available syllabi."""
    syllabi: List[SyllabusSummary]


# --- Helper Functions (Optional) ---
# If validation logic becomes complex, extract it to helper functions

# --- Syllabus Routes ---

@router.post(
    "/generate",
    response_model=SyllabusResponse,
    status_code=status.HTTP_201_CREATED, # Use 201 for resource creation
    summary="Generate a new syllabus", # Add summary for docs
    description="Generates a new syllabus based on topic and level, optionally personalized.", # Add description
)
async def generate_syllabus( # Added return type hint
    request_body: SyllabusRequest,
    syllabus_service: SyllabusService = Depends(get_syllabus_service),
    current_user: User = Depends(get_current_user)
) -> SyllabusResponse:
    """
    Generates a new syllabus based on the topic and level.
    Optionally personalizes based on user ID if provided.
    """
    logger.info(
        "Generating syllabus request received",
        extra={
            "topic": request_body.topic,
            "level": request_body.level,
            "user_id": current_user.user_id,
        },
    )
    try:
        syllabus_data = await syllabus_service.get_or_generate_syllabus(
            topic=request_body.topic,
            level=request_body.level,
            user_id=current_user.user_id,
        )

        if not syllabus_data:
             logger.error("Syllabus service returned empty data.")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail="Failed to generate syllabus data.",
             )

        # Pydantic will validate the structure when creating SyllabusResponse
        return SyllabusResponse(**syllabus_data)

    except ValueError as e:
        logger.warning(f"Validation error generating syllabus: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {e}"
        ) from e
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error generating syllabus: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred during syllabus generation.",
        ) from e


@router.get(
    "/{syllabus_id}",
    response_model=SyllabusResponse,
    summary="Get syllabus by ID",
    description="Retrieves a specific syllabus by its unique ID.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Syllabus not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    }
)
async def get_syllabus_by_id( # Added return type hint
    syllabus_id: str,
    syllabus_service: SyllabusService = Depends(get_syllabus_service),
    current_user: User = Depends(get_current_user)
) -> SyllabusResponse:
    """
    Retrieves a specific syllabus by its unique ID.
    """
    logger.info(f"Retrieving syllabus with ID: {syllabus_id} for user: {current_user.user_id}")
    try:
        syllabus_data = await syllabus_service.get_syllabus_by_id(syllabus_id)

        if syllabus_data is None:
            logger.warning(f"Syllabus with ID '{syllabus_id}' not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Syllabus with ID '{syllabus_id}' not found.",
            )

        return SyllabusResponse(**syllabus_data)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving syllabus {syllabus_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while retrieving the syllabus.",
        ) from e

# --- NEW ROUTE ---
@router.get(
    "/topic/{topic}/level/{level}",
    response_model=SyllabusResponse,
    summary="Get syllabus by topic and level",
    description="Retrieves a specific syllabus by its topic and level, considering the logged-in user.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Syllabus not found for this topic/level"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    }
)
async def get_syllabus_by_topic_level( # Added return type hint
    topic: str,
    level: str,
    syllabus_service: SyllabusService = Depends(get_syllabus_service),
    current_user: User = Depends(get_current_user)
) -> SyllabusResponse:
    """
    Retrieves a specific syllabus by its topic and level for the current user.
    """
    logger.info(f"Retrieving syllabus for topic: {topic}, level: {level}, user: {current_user.user_id}")
    try:
        syllabus_data = await syllabus_service.get_syllabus_by_topic_level(
            topic=topic,
            level=level,
            user_id=current_user.user_id
        )

        if syllabus_data is None:
            logger.warning(f"Syllabus not found for topic '{topic}', level '{level}', user '{current_user.user_id}'.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Syllabus not found for topic '{topic}', level '{level}'.",
            )

        return SyllabusResponse(**syllabus_data)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving syllabus for topic {topic}, level {level}, user {current_user.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while retrieving the syllabus.",
        ) from e


# Optional: Add a route to list available syllabi if needed
# @router.get(
#     "/",
#     response_model=SyllabusListResponse,
#     summary="List available syllabi",
# )
# async def list_syllabi(
#     syllabus_service: SyllabusService = Depends(get_syllabus_service),
#     # Add pagination parameters if needed: skip: int = 0, limit: int = 100
# ):
#     """Lists available syllabi summaries."""
#     logger.info("Listing available syllabi")
#     try:
#         # Assuming service method exists and returns list of dicts/objects
#         syllabi_data = await syllabus_service.list_syllabi_summaries() # Example method
#         return SyllabusListResponse(syllabi=[SyllabusSummary(**s) for s in syllabi_data])
#     except Exception as e:
#         logger.error(f"Unexpected error listing syllabi: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An internal server error occurred while listing syllabi.",
#         ) from e
