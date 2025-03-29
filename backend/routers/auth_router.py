"""fastApi router for authentication"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# Corrected import: get_db -> get_db_service
from backend.dependencies import get_current_user, get_db_service
from backend.models import User
from backend.services.auth_service import AuthService
from backend.services.sqlite_db import SQLiteDatabaseService # Import for type hint

router = APIRouter()

# --- Pydantic Models ---

class Token(BaseModel):
    """Model for the access token response."""
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str

class UserCreate(BaseModel):
    """Model for user registration request."""
    email: str
    password: str
    name: Optional[str] = None

class UserResponse(BaseModel):
    """Model for user information response (excluding password)."""
    user_id: str
    email: str
    name: str

# --- Authentication Routes ---

@router.post("/register", response_model=Token)
async def register_user(
    user_data: UserCreate,
    # Use get_db_service for dependency injection
    db_service: SQLiteDatabaseService = Depends(get_db_service)
) -> Token:
    """
    Registers a new user.
    Hashes the password and stores the user in the database.
    Returns an access token upon successful registration.
    """
    auth_service = AuthService(db_service=db_service) # Instantiate AuthService with db_service
    try:
        # Pass necessary arguments to register method
        result = await auth_service.register(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name
        )
        # Construct the Token response model
        return Token(
            access_token=result["access_token"],
            token_type=result["token_type"],
            user_id=result["user_id"],
            email=result["email"],
            name=result["name"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        # Log the exception details for debugging
        # logger.exception(f"Registration failed: {e}") # Assuming logger is configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an internal error."
        ) from e


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    # Use get_db_service for dependency injection
    db_service: SQLiteDatabaseService = Depends(get_db_service)
) -> Token:
    """
    Authenticates a user using email (username) and password.
    Returns an access token upon successful authentication.
    """
    auth_service = AuthService(db_service=db_service) # Instantiate AuthService with db_service
    try:
        result = await auth_service.login(email=form_data.username, password=form_data.password)
        # Construct the Token response model
        return Token(
            access_token=result["access_token"],
            token_type=result["token_type"],
            user_id=result["user_id"],
            email=result["email"],
            name=result["name"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e), # "Incorrect email or password"
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        # Log the exception details for debugging
        # logger.exception(f"Login failed: {e}") # Assuming logger is configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to an internal error."
        ) from e


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Returns the information for the currently authenticated user.
    """
    # The get_current_user dependency already returns a validated User model
    # No need to fetch again unless more details are needed than in the token
    # If get_current_user raises an exception, FastAPI handles the 401 response.
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name
    )

# Example protected route (optional)
# @router.get("/protected")
# async def read_protected_route(current_user: User = Depends(get_current_user)):
#     """An example protected route requiring authentication."""
#     return {"message": f"Hello {current_user.name}, you are authenticated!"}
