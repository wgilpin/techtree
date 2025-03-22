from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from services.auth_service import AuthService

# Debug imports
import sys
print(f"Python version: {sys.version}")
print(f"Modules: {sys.modules.keys()}")

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
auth_service = AuthService()

# Models
class UserCreate(BaseModel):
    email: str  # Changed from EmailStr to str to avoid validation issues
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: str  # Changed from EmailStr to str to avoid validation issues
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str

class User(BaseModel):
    user_id: str
    email: str
    name: str

# Dependencies
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return User(user_id=user_id, email=payload.get("email"), name="User")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Routes
@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    try:
        print(f"Registration request received: {user}")

        # Validate email format manually
        if "@" not in user.email or "." not in user.email:
            raise ValueError("Invalid email format")

        # Validate password length
        if len(user.password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        result = await auth_service.register(user.email, user.password, user.name)
        print(f"Registration successful: {result}")
        return result
    except ValueError as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        result = await auth_service.login(form_data.username, form_data.password)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout():
    # In a stateless JWT approach, the client simply discards the token
    # Here we return a success response for compatibility
    return {"detail": "Successfully logged out"}

@router.get("/me", response_model=User)
async def get_user_me(current_user: User = Depends(get_current_user)):
    return current_user