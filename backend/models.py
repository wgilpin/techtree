""" models for the ai backend """
from typing import List, Dict, Optional, Union, Any, TypedDict
from pydantic import BaseModel


# pylint: disable=too-few-public-methods
class User(BaseModel):
    """
    Model for user information.
    """

    user_id: str
    email: str
    name: str


# --- Chat Model ---


# pylint: disable=too-few-public-methods
class ChatMessage(BaseModel):
    """Model for a single message in the conversation history."""

    role: str
    content: str


# --- Lesson Content Models ---


# pylint: disable=too-few-public-methods
class Metadata(BaseModel):
    """Model for lesson metadata."""

    title: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None
    related_topics: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    # Add any other metadata fields observed


# pylint: disable=too-few-public-methods
class ExpositionContentItem(BaseModel):
    """Represents a single item within structured exposition content
        (e.g., heading, paragraph, list)."""

    # Based on format_exposition_to_markdown logic
    type: str
    text: Optional[str] = None
    level: Optional[int] = None  # For headings
    items: Optional[List[str]] = None  # For lists
    question: Optional[str] = None  # For thought questions


# pylint: disable=too-few-public-methods
class ExpositionContent(BaseModel):
    """Model for the main explanatory content of a lesson, can be simple string or structured."""

    # Assuming it might be a string OR a structured list
    content: Optional[Union[str, List[ExpositionContentItem]]] = None


# pylint: disable=too-few-public-methods
class Option(BaseModel):
    """Model for a single option in a multiple-choice question."""

    id: str
    text: str


# pylint: disable=too-few-public-methods
class Exercise(BaseModel):
    """Model representing a single active learning exercise within a lesson."""

    id: str  # LLM might not consistently provide this, make optional or generate later
    type: str
    question: Optional[str] = None  # Use instructions if question is missing
    instructions: Optional[str] = None
    items: Optional[List[str]] = None  # For ordering exercises
    options: Optional[List[Option]] = None  # For multiple_choice
    correct_answer_id: Optional[str] = None  # For multiple_choice
    expected_solution_format: Optional[str] = None  # For non-MC
    correct_answer: Optional[Union[str, List[str]]] = None  # For non-MC or ordering
    hints: Optional[List[str]] = None
    explanation: Optional[str] = None
    misconception_corrections: Optional[Dict[str, str]] = (
        None  # Map incorrect option ID to correction
    )
    # Add any other exercise fields observed


# pylint: disable=too-few-public-methods
class AssessmentQuestion(BaseModel):
    """Model representing a single question in the knowledge assessment quiz."""

    id: str  # LLM might not consistently provide this, make optional or generate later
    type: str
    question_text: str  # Renamed from 'question' to match prompt
    options: Optional[List[Option]] = None  # For multiple_choice/true_false
    correct_answer_id: Optional[str] = None  # For multiple_choice/true_false
    correct_answer: Optional[str] = None  # For short_answer
    explanation: Optional[str] = None
    confidence_check: Optional[bool] = False  # Added from prompt
    # Add any other assessment fields observed


# Main model for the generated content
# pylint: disable=too-few-public-methods
class GeneratedLessonContent(BaseModel):
    """Overall model for the AI-generated content of a single lesson."""

    topic: Optional[str] = None  # Or retrieve from syllabus context
    level: Optional[str] = None  # Or retrieve from syllabus context
    # Making exposition_content optional for flexibility during initial parsing,
    # but ideally the LLM should always provide it.
    exposition_content: Optional[Union[str, ExpositionContent, Dict[str, Any]]] = None
    metadata: Optional[Metadata] = None  # Make metadata optional initially


# --- LLM Interaction Models ---


# pylint: disable=too-few-public-methods
class IntentClassificationResult(BaseModel):
    """Pydantic model for the result of intent classification."""

    intent: str


# pylint: disable=too-few-public-methods
class EvaluationResult(BaseModel):
    """Pydantic model for the result of answer evaluation."""

    score: float
    is_correct: bool
    feedback: str
    explanation: Optional[str] = None


# --- LangGraph State ---


class LessonState(TypedDict, total=False): # Allow partial states
    """State dictionary structure for the lessons LangGraph workflow."""

    topic: str
    knowledge_level: str
    syllabus: Optional[Dict[str, Any]] # Added type parameters
    lesson_title: Optional[str]
    module_title: Optional[str]
    generated_content: Optional[
        GeneratedLessonContent
    ]
    user_responses: List[
        Dict[str, Any] # Added type parameters
    ]
    user_performance: Optional[Dict[str, Any]] # Added type parameters
    user_id: Optional[str]
    lesson_uid: Optional[
        str
    ]
    created_at: Optional[str]
    updated_at: Optional[str]
    # Conversational flow fields (History moved to separate table)
    current_interaction_mode: str
    current_exercise_index: Optional[int]
    current_quiz_question_index: Optional[int]
    # Fields for on-demand generated items
    generated_exercises: Optional[List[Exercise]]
    generated_assessment_questions: Optional[List[AssessmentQuestion]]
    generated_exercise_ids: Optional[
        List[str]
    ]
    generated_assessment_question_ids: Optional[
        List[str]
    ]
    # Potentially add fields for error handling or feedback messages
    error_message: Optional[str]
    # Fields added for interaction flow
    active_exercise: Optional[Exercise]
    active_assessment: Optional[AssessmentQuestion]
    potential_answer: Optional[str]
    # Added field to store the lesson's DB primary key
    lesson_db_id: Optional[int]
    # Temporary key to pass history context during graph invocation
    history_context: Optional[List[Dict[str, Any]]]
    # Temporary key to hold message generated by chat node before service saves it
    new_assistant_message: Optional[Dict[str, Any]]
