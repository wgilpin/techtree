# backend/services/auth_service.py
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional  # Added cast

import bcrypt
import jwt

from backend.services.sqlite_db import SQLiteDatabaseService

# Settings for JWT
SECRET_KEY = os.environ.get("SECRET_KEY")
# Ensure SECRET_KEY is set at module load time
if SECRET_KEY is None:
    raise ValueError(
        "SECRET_KEY environment variable not set. Cannot start AuthService."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 40320  # 28 days


class AuthService:
    """Provides authentication related services like registration, login, and token verification."""

    def __init__(self, db_service: SQLiteDatabaseService):
        """
        Initializes the AuthService.

        Args:
            db_service: An instance of SQLiteDatabaseService for database interactions.
        """
        self.db_service = db_service

    def _hash_password(self, password: str) -> str:
        """
        Hashes a password for storing securely.

        Args:
            password: The plain text password.

        Returns:
            The hashed password as a string.
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a stored password against a provided password.

        Args:
            plain_password: The password provided by the user.
            hashed_password: The stored hashed password.

        Returns:
            True if the password matches, False otherwise.
        """
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def _create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Creates a JWT access token.

        Args:
            data: The data to encode in the token (typically user identifier).
            expires_delta: Optional timedelta object for token expiry.
                Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

        Returns:
            The encoded JWT token as a string.
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        # Add assertion for mypy
        assert (
            SECRET_KEY is not None
        ), "SECRET_KEY cannot be None here due to initial check."
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt.decode("utf-8")  # Decode bytes to string

    async def register(
        self, email: str, password: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registers a new user in the system.

        Args:
            email: The user's email address.
            password: The user's chosen password.
            name: Optional user's name.

        Returns:
            A dictionary containing user details and access token upon successful registration.

        Raises:
            ValueError: If a user with the given email already exists.
        """
        try:
            print(f"Register method called with email: {email}, name: {name}")

            # Check if user already exists
            existing_user = self.db_service.get_user_by_email(email)
            if existing_user:
                print(f"User with email {email} already exists")
                raise ValueError("User with this email already exists")

            # Hash the password
            hashed_password = self._hash_password(password)
            print("Password hashed successfully")

            # Create the user
            user_id = self.db_service.create_user(email, hashed_password, name)
            print(f"User created with ID: {user_id}")

            # Create access token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self._create_access_token(
                data={"sub": user_id, "email": email},
                expires_delta=access_token_expires,
            )
            print("Access token created")

            result = {
                "user_id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "access_token": access_token,
                "token_type": "bearer",
            }
            print(f"Registration successful: {result}")
            return result
        except Exception as e:
            print(f"Error in register method: {str(e)}")
            raise

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticates a user and returns an access token.

        Args:
            email: The user's email address.
            password: The user's password.

        Returns:
            A dictionary containing user details and access token upon successful login.

        Raises:
            ValueError: If the email or password is incorrect.
        """
        # Get the user
        user = self.db_service.get_user_by_email(email)
        if not user:
            raise ValueError("Incorrect email or password")

        # Verify password
        if not self._verify_password(password, user["password_hash"]):
            raise ValueError("Incorrect email or password")

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self._create_access_token(
            data={"sub": user["user_id"], "email": user["email"]},
            expires_delta=access_token_expires,
        )

        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "access_token": access_token,
            "token_type": "bearer",
        }

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifies a JWT token and returns its payload if valid.

        Args:
            token: The JWT token string.

        Returns:
            The decoded payload of the token as a dictionary.

        Raises:
            ValueError: If the token is invalid, expired, or the user doesn't exist.
        """
        try:
            # Add assertion for mypy
            assert (
                SECRET_KEY is not None
            ), "SECRET_KEY cannot be None here due to initial check."
            # jwt.decode returns Dict[str, Any] if successful
            payload: Dict[str, Any] = jwt.decode(
                token, SECRET_KEY, algorithms=[ALGORITHM]
            )
            user_id = payload.get("sub")
            if user_id is None:
                raise ValueError("Invalid token: Missing 'sub' claim")

            # Additional verification - check if user still exists
            user = self.db_service.get_user_by_id(user_id)
            if not user:
                raise ValueError(f"User with ID {user_id} not found")
            # add the user name to the payload
            payload["name"] = user["name"]

            # Type is already known from line 187
            return payload
        except jwt.ExpiredSignatureError as e:
            print(f"Token expired: {str(e)}")
            raise ValueError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}") from e
        except Exception as e:
            print(f"Error decoding token: {str(e)}")
            # Catch other potential errors during decoding or user lookup
            raise ValueError(f"Token verification failed: {str(e)}") from e
