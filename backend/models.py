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

class Option(BaseModel):
    """Model for a single option in a multiple-choice question."""
    id: str
    text: str

class Exercise(BaseModel):
    """Model representing a single active learning exercise within a lesson."""
    id: str # LLM might not consistently provide this, make optional or generate later
    type: str
    question: Optional[str] = None # Use instructions if question is missing
    instructions: Optional[str] = None
    items: Optional[List[str]] = None # For ordering exercises
    options: Optional[List[Option]] = None # For multiple_choice
    correct_answer_id: Optional[str] = None # For multiple_choice
    expected_solution_format: Optional[str] = None # For non-MC
    correct_answer: Optional[Union[str, List[str]]] = None # For non-MC or ordering
    hints: Optional[List[str]] = None
    explanation: Optional[str] = None
    misconception_corrections: Optional[Dict[str, str]] = None # Map incorrect option ID to correction
    # Add any other exercise fields observed

class AssessmentQuestion(BaseModel):
    """Model representing a single question in the knowledge assessment quiz."""
    id: str # LLM might not consistently provide this, make optional or generate later
    type: str
    question_text: str # Renamed from 'question' to match prompt
    options: Optional[List[Option]] = None # For multiple_choice/true_false
    correct_answer_id: Optional[str] = None # For multiple_choice/true_false
    correct_answer: Optional[str] = None # For short_answer
    explanation: Optional[str] = None
    confidence_check: Optional[bool] = False # Added from prompt
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
    # Fields for on-demand generated items
    generated_exercises: Optional[List[Exercise]]
    generated_assessment_questions: Optional[List[AssessmentQuestion]]
    generated_exercise_ids: Optional[List[str]] # To track generated items and prevent repeats
    generated_assessment_question_ids: Optional[List[str]] # To track generated items and prevent repeats
    # Potentially add fields for error handling or feedback messages
    error_message: Optional[str] = None