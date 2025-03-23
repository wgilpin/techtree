import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.services.auth_service import AuthService
from backend.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
auth_service = AuthService()
logger = logging.getLogger(__name__)

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