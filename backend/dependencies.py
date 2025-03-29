# backend/dependencies.py
"""
Manages shared dependencies like database connections and service instances
using FastAPI's dependency injection system.
"""

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError

# Import services and models
# Corrected import: OnboardingAI -> TechTreeAI
from backend.ai.app import LessonAI, TechTreeAI, SyllabusAI
from backend.models import User
from backend.services.auth_service import AuthService
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.lesson_interaction_service import LessonInteractionService
from backend.services.onboarding_service import OnboardingService
from backend.services.sqlite_db import SQLiteDatabaseService
from backend.services.syllabus_service import SyllabusService

# --- Environment Variables ---
SECRET_KEY = os.environ.get("SECRET_KEY", "a_very_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Database Initialization ---
# Use SQLite for simplicity
DB_PATH = "techtree_db.sqlite" # Consider making this configurable
db_service = SQLiteDatabaseService(db_path=DB_PATH)

# --- Service Instantiations (Singleton Pattern) ---
# These instances will be shared across requests via dependency functions.

# Authentication Service
auth_service = AuthService(db_service=db_service)

# Onboarding AI and Service
# Corrected instantiation: OnboardingAI -> TechTreeAI
onboarding_ai = TechTreeAI()
# Corrected OnboardingService instantiation (only needs db_service)
onboarding_service = OnboardingService(db_service=db_service)

# Syllabus AI and Service
# Corrected SyllabusAI instantiation (needs db_service)
syllabus_ai = SyllabusAI(db_service=db_service)
syllabus_service = SyllabusService(db_service=db_service)

# Lesson Exposition Service
exposition_service = LessonExpositionService(
    db_service=db_service, syllabus_service=syllabus_service
)

# Lesson AI Component
lesson_ai = LessonAI()

# Lesson Interaction Service
interaction_service = LessonInteractionService(  # Needs DB, Exposition, AI
    db_service=db_service,
    # syllabus_service=syllabus_service, # Removed unexpected argument
    exposition_service=exposition_service,
    lesson_ai=lesson_ai,
)

logger = logging.getLogger(__name__)

# --- Dependency Functions ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> Optional[User]:
    """
    Dependency function to get the current authenticated user from the JWT token.
    Handles token decoding and user retrieval.
    Returns None if token is invalid or user not found (allows optional auth).
    """
    # Special case for no-auth mode (e.g., during development/testing)
    if token == "no-auth-token":
        logger.warning("Using 'no-auth' user.")
        return User(user_id="no-auth", email="no-auth@example.com", name="No Auth User")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            logger.warning("Token payload missing 'sub' (user_id).")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT Error: {e}", exc_info=True)
        raise credentials_exception from e
    except Exception as e: # Catch other potential errors during decoding
        logger.error(f"Token decoding error: {e}", exc_info=True)
        raise credentials_exception from e


    # Corrected user lookup: Use db_service directly
    user_dict = db_service.get_user_by_id(user_id)
    if user_dict is None:
        logger.warning(f"User ID {user_id} from token not found in database.")
        raise credentials_exception
    # Convert dict to User model
    try:
        user = User(**user_dict)
    except ValidationError as e:
        logger.error(f"Failed to validate user data from DB for user {user_id}: {e}")
        # Treat validation error as auth failure
        raise credentials_exception from e
    return user


# --- Service Dependency Getters ---
# These functions simply return the pre-initialized service instances.


def get_db_service() -> SQLiteDatabaseService:
    """Dependency function to get the database service instance."""
    return db_service


def get_auth_service() -> AuthService:
    """Dependency function to get the authentication service instance."""
    return auth_service


def get_onboarding_service() -> OnboardingService:
    """Dependency function to get the onboarding service instance."""
    return onboarding_service


def get_syllabus_service() -> SyllabusService:
    """Dependency function to get the syllabus service instance."""
    return syllabus_service


def get_exposition_service() -> LessonExpositionService:
    """Dependency function to get the lesson exposition service instance."""
    return exposition_service


def get_interaction_service() -> LessonInteractionService:
    """Dependency function to get the lesson interaction service instance."""
    return interaction_service
