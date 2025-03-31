# backend/services/lesson_state_utils.py
"""Utility functions for serializing, deserializing, and formatting lesson state data."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar, cast

from pydantic import BaseModel, ValidationError

# Assuming models are defined in backend.models
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
    LessonState,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# --- Serialization Helpers ---


def _serialize_value(value: Any) -> Any:
    """Serialize a single value, handling Pydantic models and datetimes."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list) and value and isinstance(value[0], BaseModel):
        return [item.model_dump(mode="json") for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_state_data(state: LessonState) -> str:
    """
    Converts the LessonState TypedDict, potentially containing Pydantic models,
    to a JSON string.

    Args:
        state: The LessonState dictionary.

    Returns:
        A JSON string representation of the state.
    """
    serializable_dict = {key: _serialize_value(value) for key, value in state.items()}
    return json.dumps(serializable_dict)


def prepare_state_for_response(
    state: Optional[LessonState],
) -> Optional[Dict[str, Any]]:
    """
    Prepares the LessonState dictionary for an API response by serializing
    nested Pydantic models and datetimes.

    Args:
        state: The LessonState dictionary, or None.

    Returns:
        A dictionary suitable for JSON serialization in the response, or None.
    """
    if state is None:
        return None
    # Use the existing _serialize_value helper
    return {key: _serialize_value(value) for key, value in state.items()}


# --- Deserialization Helpers ---


def _deserialize_model(
    data: Optional[Any], model_cls: Type[T], field_name: str
) -> Optional[T]:
    """Safely deserialize data into a Pydantic model instance."""
    if not isinstance(data, dict):
        if data is not None:  # Log if data exists but isn't a dict
            logger.warning(
                f"Expected dict for {field_name}, got {type(data)}. Skipping."
            )
        return None
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        logger.error(f"Validation failed for {field_name}: {e}. Data: {data}")
        return None


def _deserialize_model_list(
    data: Optional[Any], model_cls: Type[T], field_name: str
) -> List[T]:
    """Safely deserialize a list of dictionaries into Pydantic model instances."""
    if not isinstance(data, list):
        if data is not None:  # Log if data exists but isn't a list
            logger.warning(
                f"Expected list for {field_name}, got {type(data)}. Skipping."
            )
        return []

    validated_items: List[T] = []
    for i, item_data in enumerate(data):
        if not isinstance(item_data, dict):
            logger.warning(
                f"Expected dict for item {i} in {field_name}, got {type(item_data)}. Skipping item."
            )
            continue
        try:
            validated_items.append(model_cls.model_validate(item_data))
        except ValidationError as e:
            logger.error(
                f"Validation failed for item {i} in {field_name}: {e}. Data: {item_data}"
            )
            # Skip invalid items
    return validated_items


def deserialize_state_data(state_dict: Dict[str, Any]) -> LessonState:
    """
    Converts a dictionary (from DB) back into a LessonState structure
    with Pydantic models, handling potential validation errors gracefully.

    Args:
        state_dict: The dictionary loaded from the database.

    Returns:
        A LessonState TypedDict with nested models validated.
    """
    deserialized_state = state_dict.copy()  # Start with a copy

    # Deserialize complex fields using helpers
    deserialized_state["generated_content"] = _deserialize_model(
        state_dict.get("generated_content"), GeneratedLessonContent, "generated_content"
    )
    deserialized_state["active_exercise"] = _deserialize_model(
        state_dict.get("active_exercise"), Exercise, "active_exercise"
    )
    deserialized_state["active_assessment"] = _deserialize_model(
        state_dict.get("active_assessment"), AssessmentQuestion, "active_assessment"
    )
    deserialized_state["generated_exercises"] = _deserialize_model_list(
        state_dict.get("generated_exercises"), Exercise, "generated_exercises"
    )
    deserialized_state["generated_assessment_questions"] = _deserialize_model_list(
        state_dict.get("generated_assessment_questions"),
        AssessmentQuestion,
        "generated_assessment_questions",
    )

    # Ensure other fields expected by LessonState are present or defaulted if needed
    # (Example: ensure user_responses is a list)
    if not isinstance(deserialized_state.get("user_responses"), list):
        deserialized_state["user_responses"] = []
    # Add similar checks/defaults for other LessonState fields as necessary

    # Cast the final dictionary to LessonState for type hinting purposes
    # MyPy will check if the structure matches the TypedDict definition
    return cast(LessonState, deserialized_state)


# --- Formatting Helpers ---


def format_exercise_for_chat_history(exercise: Exercise) -> str:
    """Formats an Exercise object into an HTML string for chat history."""
    if not exercise:
        return "<p><em>Error: Could not format exercise.</em></p>"

    # Use model_dump to get a dictionary, handling potential None values
    exercise_dict = exercise.model_dump(mode="json")

    exercise_type = exercise_dict.get("type", "unknown").replace("_", " ")
    instructions = (
        exercise_dict.get("instructions") or exercise_dict.get("question") or "N/A"
    )
    options = exercise_dict.get("options", [])
    items = exercise_dict.get("items", [])

    content_html = '<div class="generated-item exercise-item">'
    content_html += f"<h3>Exercise ({exercise_type})</h3>"
    content_html += f"<p><strong>Instructions:</strong> {instructions}</p>"

    if exercise_dict.get("type") == "multiple_choice" and options:
        content_html += "<ul>"
        for opt in options:
            opt_id = opt.get("id", "?")
            opt_text = opt.get("text", "")
            content_html += f"<li><strong>{opt_id})</strong> {opt_text}</li>"
        content_html += "</ul>"
        content_html += (
            '<p><small><em>Submit your answer (e.g., "A") in the chat.</em></small></p>'
        )
    elif exercise_dict.get("type") == "ordering" and items:
        content_html += "<p><strong>Items to order:</strong></p><ul>"
        for item in items:
            content_html += f"<li>{item}</li>"
        content_html += "</ul>"
        content_html += '<p><small><em>'
        content_html += 'Submit your ordered list (e.g., "Item B, Item A, Item C") in the chat.</em></small></p>'
    else:
        content_html += "<p><small><em>Submit your answer in the chat.</em></small></p>"

    content_html += "</div>"
    return content_html


def format_assessment_question_for_chat_history(question: AssessmentQuestion) -> str:
    """Formats an AssessmentQuestion object into an HTML string for chat history."""
    if not question:
        return "<p><em>Error: Could not format assessment question.</em></p>"

    question_dict = question.model_dump(mode="json")

    q_type = question_dict.get("type", "unknown").replace("_", " ")
    q_text = question_dict.get("question_text", "N/A")
    options = question_dict.get("options", [])

    content_html = '<div class="generated-item assessment-item">'
    content_html += f"<h3>Assessment Question ({q_type})</h3>"
    content_html += f"<p>{q_text}</p>"

    if (
        question_dict.get("type") == "multiple_choice"
        or question_dict.get("type") == "true_false"
    ) and options:
        content_html += "<ul>"
        for opt in options:
            opt_id = opt.get("id", "?")
            opt_text = opt.get("text", "")
            content_html += f"<li><strong>{opt_id})</strong> {opt_text}</li>"
        content_html += "</ul>"
        if question_dict.get("type") == "multiple_choice":
            content_html += '<p><small><em>Submit your answer (e.g., "A") in the chat.</em></small></p>'
        else:  # true_false
            content_html += '<p><small><em>Submit your answer ("True" or "False") in the chat.</em></small></p>'
    else:  # short_answer
        content_html += "<p><small><em>Submit your answer in the chat.</em></small></p>"

    content_html += "</div>"
    return content_html
