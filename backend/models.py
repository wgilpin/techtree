from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any

class User(BaseModel):
    """
    Model for user information.
    """
    user_id: str
    email: str
    name: str

# --- Lesson Content Models ---

class Metadata(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None
    related_topics: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    # Add any other metadata fields observed

class ExpositionContentItem(BaseModel):
    # Based on format_exposition_to_markdown logic
    type: str
    text: Optional[str] = None
    level: Optional[int] = None # For headings
    items: Optional[List[str]] = None # For lists
    question: Optional[str] = None # For thought questions

class ExpositionContent(BaseModel):
     # Assuming it might be a string OR a structured list
     content: Optional[Union[str, List[ExpositionContentItem]]] = None

class Exercise(BaseModel):
    id: str
    type: str
    question: Optional[str] = None
    instructions: Optional[str] = None # Use alias if needed
    items: Optional[List[str]] = None # For ordering
    options: Optional[Union[Dict[str, str], List[str]]] = None # For MC
    expected_solution: Optional[str] = None
    correct_answer: Optional[str] = None # Use alias if needed
    hints: Optional[List[str]] = None
    explanation: Optional[str] = None
    misconceptions: Optional[Dict[str, str]] = None
    # Add any other exercise fields observed

class AssessmentQuestion(BaseModel):
    id: str
    type: str
    question: str
    options: Optional[Union[Dict[str, str], List[str]]] = None # For MC/TF
    correct_answer: str # Should this be optional? LLM might not always provide it reliably. Let's keep required for now.
    explanation: Optional[str] = None
    # Add any other assessment fields observed

# Main model for the generated content
class GeneratedLessonContent(BaseModel):
    topic: Optional[str] = None # Or retrieve from syllabus context
    level: Optional[str] = None # Or retrieve from syllabus context
    # Making exposition_content optional for flexibility during initial parsing,
    # but ideally the LLM should always provide it.
    exposition_content: Optional[Union[str, ExpositionContent, Dict[str, Any]]] = None
    # thought_questions: List[str] # This seems to be part of exposition now based on ExpositionContentItem
    active_exercises: List[Exercise] = Field(default_factory=list) # Use default_factory for lists
    knowledge_assessment: List[AssessmentQuestion] = Field(default_factory=list) # Use default_factory for lists
    metadata: Optional[Metadata] = None # Make metadata optional initially