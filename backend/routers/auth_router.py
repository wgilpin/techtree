""" router for auth endpoints """

import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from backend.services.auth_service import AuthService
from backend.models import User
from backend.dependencies import get_current_user
from backend.logger import logger

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
auth_service = AuthService()

# Models
class UserCreate(BaseModel):
    """
    Model for user creation.
    """
    email: str  # Changed from EmailStr to str to avoid validation issues
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    """
    Model for user login.
    """
    email: str  # Changed from EmailStr to str to avoid validation issues
    password: str

class Token(BaseModel):
    """
    Model for authentication tokens.
    """
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str

# Routes
@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    """
    Register a new user.
    """
    logger.info(f"Entering register endpoint with data: {user}")
    try:
        print(f"Registration request received: {user}")

        # Validate email format manually
        if "@" not in user.email or "." not in user.email:
            e = ValueError("Invalid email format")
            raise e from e

        # Validate password length
        if len(user.password) < 8:
            e = ValueError("Password must be at least 8 characters long")
            raise e from e

        result = await auth_service.register(user.email, user.password, user.name)
        print(f"Registration successful: {result}")
        return result
    except ValueError as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        print(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) from e

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Log in an existing user.
    """
    logger.info(f"Entering login endpoint with username: {form_data.username}")
    try:
        result = await auth_service.login(form_data.username, form_data.password)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

@router.post("/logout")
async def logout():
    """
    Log out the current user (stateless, client-side token removal).
    """
    logger.info("Entering logout endpoint")
    # In a stateless JWT approach, the client simply discards the token
    # Here we return a success response for compatibility
    return {"detail": "Successfully logged out"}

@router.get("/me", response_model=User)
async def get_user_me(current_user: User = Depends(get_current_user)):
    logger.info(f"Entering get_user_me endpoint, current user: {current_user.email}")
    """
    Get the current user's information.
    """
    return current_user
