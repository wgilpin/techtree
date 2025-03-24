import bcrypt
import jwt
from datetime import datetime, timedelta
from backend.services.sqlite_db import SQLiteDatabaseService
from typing import Dict, Any, Optional

# Settings for JWT
SECRET_KEY = "your-secret-key"  # In production, this should be an environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 40320  # Increased to 28 days  (28 * 60 * 24)

class AuthService:
    def __init__(self, db_service=None):
        print("Init DB in AuthService")
        self.db_service = db_service or SQLiteDatabaseService()

    def _hash_password(self, password: str) -> str:
        """Hash a password for storing"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a stored password against a provided password"""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    def _create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def register(self, email: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Register a new user"""
        try:
            print(f"Register method called with email: {email}, name: {name}")

            # Check if user already exists
            existing_user = self.db_service.get_user_by_email(email)
            if existing_user:
                print(f"User with email {email} already exists")
                raise ValueError("User with this email already exists")

            # Hash the password
            hashed_password = self._hash_password(password)
            print(f"Password hashed successfully")

            # Create the user
            user_id = self.db_service.create_user(email, hashed_password, name)
            print(f"User created with ID: {user_id}")

            # Create access token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self._create_access_token(
                data={"sub": user_id, "email": email},
                expires_delta=access_token_expires
            )
            print(f"Access token created")

            result = {
                "user_id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "access_token": access_token,
                "token_type": "bearer"
            }
            print(f"Registration successful: {result}")
            return result
        except Exception as e:
            print(f"Error in register method: {str(e)}")
            raise

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate a user and return a token"""
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
            expires_delta=access_token_expires
        )

        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "access_token": access_token,
            "token_type": "bearer"
        }

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise ValueError("Invalid token")

            # Additional verification - check if user still exists
            user = self.db_service.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            # add the user name to the payload
            payload["name"] = user["name"]

            return payload
        except Exception as e:
            print(f"Error decoding token: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}") from e
