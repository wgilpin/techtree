from pydantic import BaseModel

class User(BaseModel):
    """
    Model for user information.
    """
    user_id: str
    email: str
    name: str