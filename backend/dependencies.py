"""
FastAPI dependency injection setup.

This module initializes shared service instances (like database connections,
AI components, and business logic services) and provides dependency functions
(e.g., `get_db`, `get_current_user`) for use in API route definitions.
This promotes code reuse and testability by managing singleton instances
and handling common tasks like authentication.
"""

import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Import Services
from backend.services.auth_service import AuthService
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.lesson_interaction_service import (
    LessonInteractionService,
)
from backend.ai.app import LessonAI

# Import Models
from backend.models import User

# --- Service Instantiation ---

# Create a single instance of the database service
# This allows sharing the same DB connection pool across the application.
db_service = SQLiteDatabaseService()

# Authentication Service
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
auth_service = AuthService(db_service=db_service)

# Syllabus Service
syllabus_service = SyllabusService(db_service=db_service)

# Lesson Exposition Service
exposition_service = LessonExpositionService(
    db_service=db_service, syllabus_service=syllabus_service
)

# Lesson AI Component
lesson_ai = LessonAI()

# Lesson Interaction Service
interaction_service = LessonInteractionService(  # Needs DB, Syllabus, Exposition, AI
    db_service=db_service,
    syllabus_service=syllabus_service,
    exposition_service=exposition_service,
    lesson_ai=lesson_ai,
)

logger = logging.getLogger(__name__)

# --- Dependency Functions ---


# Dependency function to get the shared DB instance
def get_db() -> SQLiteDatabaseService:
    """
    FastAPI dependency function to provide the shared SQLiteDatabaseService instance.

    Returns:
        The singleton SQLiteDatabaseService instance.
    """
    return db_service


# Dependency function to get the shared Syllabus Service instance
def get_syllabus_service() -> SyllabusService:
    """
    FastAPI dependency function to provide the shared SyllabusService instance.

    Returns:
        The singleton SyllabusService instance.
    """
    return syllabus_service


# Dependency function to get the shared Lesson Exposition Service instance
def get_exposition_service() -> LessonExpositionService:
    """
    FastAPI dependency function to provide the shared LessonExpositionService instance.

    Returns:
        The singleton LessonExpositionService instance.
    """
    return exposition_service


# Dependency function to get the shared Lesson Interaction Service instance
def get_interaction_service() -> LessonInteractionService:
    """
    FastAPI dependency function to provide the shared LessonInteractionService instance.

    Returns:
        The singleton LessonInteractionService instance.
    """
    return interaction_service


# Dependency function to get the current user from the JWT token
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    FastAPI dependency function to get the current authenticated user from the JWT token.

    Verifies the token and returns the corresponding User object.
    Handles the NO_AUTH environment variable for bypassing authentication during development.

    Args:
        token: The bearer token extracted from the Authorization header.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException (401): If authentication credentials are invalid or missing.
        HTTPException (500): If an unexpected error occurs during token verification.
    """
    if os.environ.get("NO_AUTH"):
        logger.warning("NO_AUTH is active. Bypassing authentication.")
        # Return a default User object for no-auth mode
        return User(user_id="no-auth", email="no-auth@example.com", name="No Auth User")
    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials (missing sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Fetch user details from DB or use token payload
        return User(
            user_id=user_id, email=payload.get("email"), name=payload.get("name")
        )
    except ValueError as e:
        logger.error(f"Token verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:  # Catch other potential errors during verification
        logger.error(f"Unexpected error during token verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify authentication credentials",
        ) from e
