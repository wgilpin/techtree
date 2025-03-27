from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any, TypedDict # Added TypedDict

class User(BaseModel):
    """
    Model for user information.
    """
    user_id: str
    email: str
    name: str

# --- Lesson Content Models ---

class Metadata(BaseModel):
    """Model for lesson metadata."""
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None
    related_topics: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    # Add any other metadata fields observed

class ExpositionContentItem(BaseModel):
    """Represents a single item within structured exposition content (e.g., heading, paragraph, list)."""
    # Based on format_exposition_to_markdown logic
    type: str
    text: Optional[str] = None
    level: Optional[int] = None # For headings
    items: Optional[List[str]] = None # For lists
    question: Optional[str] = None # For thought questions

class ExpositionContent(BaseModel):
     """Model for the main explanatory content of a lesson, can be simple string or structured."""
     # Assuming it might be a string OR a structured list
     content: Optional[Union[str, List[ExpositionContentItem]]] = None

class Exercise(BaseModel):
    """Model representing a single active learning exercise within a lesson."""
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
    """Model representing a single question in the knowledge assessment quiz."""
    id: str
    type: str
    question: str
    options: Optional[Union[Dict[str, str], List[str]]] = None # For MC/TF
    correct_answer: str # Should this be optional? LLM might not always provide it reliably. Let's keep required for now.
    explanation: Optional[str] = None
    # Add any other assessment fields observed

# Main model for the generated content
class GeneratedLessonContent(BaseModel):
    """Overall model for the AI-generated content of a single lesson."""
    topic: Optional[str] = None # Or retrieve from syllabus context
    level: Optional[str] = None # Or retrieve from syllabus context
    # Making exposition_content optional for flexibility during initial parsing,
    # but ideally the LLM should always provide it.
    exposition_content: Optional[Union[str, ExpositionContent, Dict[str, Any]]] = None
    # thought_questions: List[str] # This seems to be part of exposition now based on ExpositionContentItem
    active_exercises: List[Exercise] = Field(default_factory=list) # Use default_factory for lists
    knowledge_assessment: List[AssessmentQuestion] = Field(default_factory=list) # Use default_factory for lists
    metadata: Optional[Metadata] = None # Make metadata optional initially

# --- LLM Interaction Models ---

class IntentClassificationResult(BaseModel):
    """Pydantic model for the result of intent classification."""
    intent: str

class EvaluationResult(BaseModel):
    """Pydantic model for the result of answer evaluation."""
    score: float
    is_correct: bool
    feedback: str
    explanation: Optional[str] = None

# --- LangGraph State ---

class LessonState(TypedDict):
    """State dictionary structure for the lessons LangGraph workflow."""
    topic: str
    knowledge_level: str
    syllabus: Optional[Dict]
    lesson_title: Optional[str]
    module_title: Optional[str]
    generated_content: Optional[GeneratedLessonContent] # Use Pydantic model here too? Yes.
    user_responses: List[Dict] # Could potentially be List[UserResponseRecord] if defined
    user_performance: Optional[Dict] # Structure depends on how progress is tracked
    user_id: Optional[str]
    lesson_uid: Optional[str] # Assuming this is relevant for identifying the lesson instance
    created_at: Optional[str] # ISO format string
    updated_at: Optional[str] # ISO format string
    # Conversational flow fields
    conversation_history: List[Dict[str, str]] # Stores {'role': 'user'/'assistant', 'content': '...'}
    current_interaction_mode: str  # e.g., 'chatting', 'doing_exercise', 'taking_quiz'
    current_exercise_index: Optional[int]
    current_quiz_question_index: Optional[int]
    # Potentially add fields for error handling or feedback messages
    error_message: Optional[str] = None