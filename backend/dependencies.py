import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.services.auth_service import AuthService
from backend.services.sqlite_db import SQLiteDatabaseService  # Import the DB service
from backend.models import User

# Create a single instance of the database service
db_service = SQLiteDatabaseService()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
# Pass the shared db_service instance to AuthService
auth_service = AuthService(db_service=db_service)
logger = logging.getLogger(__name__)

# Dependency function to get the shared DB instance
def get_db():
    return db_service

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to get the current user from the JWT token.
    """
    if os.environ.get('NO_AUTH'):
        logger.warning("NO_AUTH is active. Bypassing authentication.")
        return User(user_id="no-auth", email="no-auth", name="No Auth User")
    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return User(user_id=user_id, email=payload.get("email"), name=payload.get("name"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e