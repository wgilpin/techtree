# backend/tests/routers/test_lesson_router.py
# pylint: disable=missing-function-docstring,missing-module-docstring, redefined-outer-name
# pylint: disable=wrong-import-position

import os
# Adjust the import path based on your project structure and how 'app' is defined
import sys
from unittest.mock import AsyncMock, MagicMock
from typing import Generator, Dict, Any


import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# Import the dependency functions we need to override and the User model
from backend.dependencies import get_exposition_service  # New
from backend.dependencies import get_interaction_service  # New
from backend.dependencies import get_current_user
from backend.main import app
# Import models needed for tests
from backend.models import User, GeneratedLessonContent, Exercise, AssessmentQuestion, Metadata

# Import the new service classes for mocking specs
from backend.services.lesson_exposition_service import LessonExpositionService
from backend.services.lesson_interaction_service import LessonInteractionService

# Removed old imports

# Create a TestClient instance
client = TestClient(app)

# --- Fixtures and Mocks ---


# Mock the dependency get_current_user (remains the same)
@pytest.fixture(autouse=True)
def override_get_current_user() -> Generator[User, None, None]: # Yield User directly
    mock_user = User(
        user_id="test_user_id",
        email="test@example.com",
        name="Test User",
    )

    def mock_dependency() -> User:
        return mock_user

    app.dependency_overrides[get_current_user] = mock_dependency
    yield mock_user # Yield the user object
    app.dependency_overrides = {}


# Mock the LessonInteractionService
@pytest.fixture
def mock_interaction_service() -> Generator[MagicMock, None, None]: # Fixture yields
    print("Setting up mock_interaction_service override")
    mock_service = MagicMock(spec=LessonInteractionService)
    mock_service.get_or_create_lesson_state = AsyncMock()
    mock_service.handle_chat_turn = AsyncMock()
    mock_service.generate_exercise = AsyncMock()
    mock_service.generate_assessment_question = AsyncMock()
    mock_service.update_lesson_progress = AsyncMock()

    def override_get_interaction_service() -> MagicMock:
        print("Using mock get_interaction_service")
        return mock_service

    app.dependency_overrides[get_interaction_service] = override_get_interaction_service
    print(f"Overriding get_interaction_service with {override_get_interaction_service}")
    yield mock_service
    print("Cleaning up interaction_service dependency override")
    if get_interaction_service in app.dependency_overrides:
        del app.dependency_overrides[get_interaction_service]


# Mock the LessonExpositionService
@pytest.fixture
def mock_exposition_service() -> Generator[MagicMock, None, None]: # Fixture yields
    print("Setting up mock_exposition_service override")
    mock_service = MagicMock(spec=LessonExpositionService)
    mock_service.get_exposition_by_id = AsyncMock()

    def override_get_exposition_service() -> MagicMock:
        print("Using mock get_exposition_service")
        return mock_service

    app.dependency_overrides[get_exposition_service] = override_get_exposition_service
    print(f"Overriding get_exposition_service with {override_get_exposition_service}")
    yield mock_service
    print("Cleaning up exposition_service dependency override")
    if get_exposition_service in app.dependency_overrides:
        del app.dependency_overrides[get_exposition_service]


# --- Test Cases ---


# Test GET /{syllabus_id}/{module_index}/{lesson_index}
def test_get_lesson_data_success(mock_interaction_service: MagicMock) -> None:
    """Test successful retrieval of lesson data and state."""
    print("Running test_get_lesson_data_success")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    lesson_db_id = 123
    # Create Metadata object first
    mock_metadata = Metadata(title="Test Lesson")
    mock_content_dict: Dict[str, Any] = { # Add type hint
        "topic": "Test Topic",
        "level": "beginner",
        "exposition_content": "<p>Test Exposition</p>",
        "metadata": mock_metadata, # Use the Metadata object
    }
    # Explicitly pass args to avoid mypy **dict inference issues
    mock_content_obj = GeneratedLessonContent(
        topic=mock_content_dict["topic"],
        level=mock_content_dict["level"],
        exposition_content=mock_content_dict["exposition_content"],
        metadata=mock_content_dict["metadata"],
    )
    mock_state = {
        "conversation_history": [],
        "current_interaction_mode": "chatting",
        "lesson_uid": lesson_db_id,
    }
    mock_interaction_service.get_or_create_lesson_state.return_value = {
        "lesson_id": lesson_db_id,
        "content": mock_content_obj,
        "lesson_state": mock_state,
    }
    print("Mock configured")
    response = client.get(f"/lesson/{syllabus_id}/{module_index}/{lesson_index}")
    print(f"Response status: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    assert data["lesson_id"] == lesson_db_id
    assert data["content"] == mock_content_obj.model_dump(mode="json")
    assert data["lesson_state"] == mock_state
    mock_interaction_service.get_or_create_lesson_state.assert_awaited_once_with(
        syllabus_id, module_index, lesson_index, "test_user_id"
    )
    print("test_get_lesson_data_success finished")


def test_get_lesson_data_not_found(mock_interaction_service: MagicMock) -> None:
    """Test retrieving lesson data when exposition cannot be found/generated."""
    print("Running test_get_lesson_data_not_found")
    syllabus_id = "syllabus_bad"
    module_index = 99
    lesson_index = 99
    mock_interaction_service.get_or_create_lesson_state.side_effect = ValueError(
        "Could not retrieve or generate lesson exposition content."
    )
    response = client.get(f"/lesson/{syllabus_id}/{module_index}/{lesson_index}")
    assert response.status_code == 404
    assert (
        "Could not retrieve or generate lesson exposition content."
        in response.json()["detail"]
    )
    print("test_get_lesson_data_not_found finished")


# --- Tests for POST /chat ---
def test_handle_chat_message_success(mock_interaction_service: MagicMock) -> None:
    """Test successfully sending a chat message and getting a response."""
    print("Running test_handle_chat_message_success")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "What is this lesson about?"
    ai_response = [{"role": "assistant", "content": "This lesson is about..."}]
    mock_interaction_service.handle_chat_turn.return_value = {"responses": ai_response}
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["responses"] == ai_response
    assert data["error"] is None
    mock_interaction_service.handle_chat_turn.assert_awaited_once_with(
        user_id="test_user_id",
        syllabus_id=syllabus_id,
        module_index=module_index,
        lesson_index=lesson_index,
        user_message=user_message,
    )
    print("test_handle_chat_message_success finished")


def test_handle_chat_message_unauthenticated() -> None:
    """Test sending chat message without authentication."""
    print("Running test_handle_chat_message_unauthenticated")
    app.dependency_overrides[get_current_user] = lambda: None
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": "test"},
    )
    assert response.status_code == 401
    app.dependency_overrides = {}
    print("test_handle_chat_message_unauthenticated finished")


def test_handle_chat_message_service_error(mock_interaction_service: MagicMock) -> None:
    """Test handling an error structure returned from the service during chat."""
    print("Running test_handle_chat_message_service_error")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "This will cause an error"
    mock_interaction_service.handle_chat_turn.return_value = {
        "error": "AI processing failed"
    }
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["responses"] == []
    assert data["error"] == "AI processing failed"
    print("test_handle_chat_message_service_error finished")


def test_handle_chat_message_state_not_found(mock_interaction_service: MagicMock) -> None:
    """Test handling ValueError (e.g., state not found) raised by the service."""
    print("Running test_handle_chat_message_state_not_found")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "Where is my state?"
    mock_interaction_service.handle_chat_turn.side_effect = ValueError(
        "Could not load lesson state for chat."
    )
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )
    assert response.status_code == 404
    assert "Could not load lesson state for chat." in response.json()["detail"]
    print("test_handle_chat_message_state_not_found finished")


# --- Tests for POST /exercise/{syllabus_id}/{module_index}/{lesson_index} ---
def test_generate_exercise_success(mock_interaction_service: MagicMock) -> None:
    """Test successfully generating an exercise."""
    print("Running test_generate_exercise_success")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    # FIX: Use 'id' instead of 'exercise_id'
    mock_exercise_obj = Exercise(
        id="ex_gen_1", type="short_answer", instructions="Generated Q"
    )
    # Mock should return a tuple (exercise_obj, message)
    mock_interaction_service.generate_exercise.return_value = (mock_exercise_obj, None)
    response = client.post(
        f"/lesson/exercise/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["error"] is None
    assert data["exercise"] == mock_exercise_obj.model_dump(mode="json")
    mock_interaction_service.generate_exercise.assert_awaited_once_with(
        user_id="test_user_id",
        syllabus_id=syllabus_id,
        module_index=module_index,
        lesson_index=lesson_index,
    )
    print("test_generate_exercise_success finished")


def test_generate_exercise_unauthenticated() -> None:
    """Test generating exercise without authentication."""
    print("Running test_generate_exercise_unauthenticated")
    app.dependency_overrides[get_current_user] = lambda: None
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    response = client.post(
        f"/lesson/exercise/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 401
    app.dependency_overrides = {}
    print("test_generate_exercise_unauthenticated finished")


def test_generate_exercise_not_found(mock_interaction_service: MagicMock) -> None:
    """Test generating exercise when lesson state is not found."""
    print("Running test_generate_exercise_not_found")
    syllabus_id = "syllabus_bad"
    module_index = 99
    lesson_index = 99
    mock_interaction_service.generate_exercise.side_effect = ValueError(
        "Lesson state not found"
    )
    response = client.post(
        f"/lesson/exercise/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 404
    assert "Lesson state not found" in response.json()["detail"]
    print("test_generate_exercise_not_found finished")


def test_generate_exercise_runtime_error(mock_interaction_service: MagicMock) -> None:
    """Test generating exercise when the service raises a runtime error."""
    print("Running test_generate_exercise_runtime_error")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    mock_interaction_service.generate_exercise.side_effect = RuntimeError(
        "LLM generation failed"
    )
    response = client.post(
        f"/lesson/exercise/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 500
    assert "LLM generation failed" in response.json()["detail"]
    print("test_generate_exercise_runtime_error finished")


# --- Tests for POST /assessment/{syllabus_id}/{module_index}/{lesson_index} ---
def test_generate_assessment_question_success(mock_interaction_service: MagicMock) -> None:
    """Test successfully generating an assessment question."""
    print("Running test_generate_assessment_question_success")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    # FIX: Use 'id' instead of 'question_id'
    mock_question_obj = AssessmentQuestion(
        id="q_gen_1", type="true_false", question_text="Generated Q?"
    )
    # Mock should return a tuple (question_obj, message)
    mock_interaction_service.generate_assessment_question.return_value = (
        mock_question_obj, None
    )
    response = client.post(
        f"/lesson/assessment/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["error"] is None
    assert data["question"] == mock_question_obj.model_dump(mode="json")
    mock_interaction_service.generate_assessment_question.assert_awaited_once_with(
        user_id="test_user_id",
        syllabus_id=syllabus_id,
        module_index=module_index,
        lesson_index=lesson_index,
    )
    print("test_generate_assessment_question_success finished")


def test_generate_assessment_question_unauthenticated() -> None:
    """Test generating assessment question without authentication."""
    print("Running test_generate_assessment_question_unauthenticated")
    app.dependency_overrides[get_current_user] = lambda: None
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    response = client.post(
        f"/lesson/assessment/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 401
    app.dependency_overrides = {}
    print("test_generate_assessment_question_unauthenticated finished")


def test_generate_assessment_question_not_found(mock_interaction_service: MagicMock) -> None:
    """Test generating assessment question when lesson state is not found."""
    print("Running test_generate_assessment_question_not_found")
    syllabus_id = "syllabus_bad"
    module_index = 99
    lesson_index = 99
    mock_interaction_service.generate_assessment_question.side_effect = ValueError(
        "Lesson state not found"
    )
    response = client.post(
        f"/lesson/assessment/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 404
    assert "Lesson state not found" in response.json()["detail"]
    print("test_generate_assessment_question_not_found finished")


def test_generate_assessment_question_runtime_error(mock_interaction_service: MagicMock) -> None:
    """Test generating assessment question when the service raises a runtime error."""
    print("Running test_generate_assessment_question_runtime_error")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    mock_interaction_service.generate_assessment_question.side_effect = RuntimeError(
        "LLM generation failed"
    )
    response = client.post(
        f"/lesson/assessment/{syllabus_id}/{module_index}/{lesson_index}"
    )
    assert response.status_code == 500
    assert "LLM generation failed" in response.json()["detail"]
    print("test_generate_assessment_question_runtime_error finished")


# --- Test for GET /by-id/{lesson_id} ---
def test_get_lesson_exposition_by_id_success(mock_exposition_service: MagicMock) -> None:
    """Test successfully retrieving lesson exposition by ID."""
    print("Running test_get_lesson_exposition_by_id_success")
    lesson_db_id = 456
    # Create Metadata object first
    mock_metadata = Metadata(title="Expo Lesson")
    mock_exposition_dict: Dict[str, Any] = { # Add type hint
        "topic": "Expo Topic",
        "level": "intermediate",
        "exposition_content": "Expo Content",
        "metadata": mock_metadata, # Use the Metadata object
        # exercises and assessment_questions are not part of GeneratedLessonContent model
    }
    # Explicitly pass args to avoid mypy **dict inference issues
    mock_exposition_obj = GeneratedLessonContent(
        topic=mock_exposition_dict["topic"],
        level=mock_exposition_dict["level"],
        exposition_content=mock_exposition_dict["exposition_content"],
        metadata=mock_exposition_dict["metadata"],
    )
    mock_exposition_service.get_exposition_by_id.return_value = mock_exposition_obj
    response = client.get(f"/lesson/by-id/{lesson_db_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["error"] is None
    assert data["exposition"] == mock_exposition_obj.model_dump(mode="json")
    mock_exposition_service.get_exposition_by_id.assert_awaited_once_with(lesson_db_id)
    print("test_get_lesson_exposition_by_id_success finished")


def test_get_lesson_exposition_by_id_not_found(mock_exposition_service: MagicMock) -> None:
    """Test retrieving non-existent lesson exposition by ID."""
    print("Running test_get_lesson_exposition_by_id_not_found")
    lesson_db_id = 999
    mock_exposition_service.get_exposition_by_id.return_value = None
    response = client.get(f"/lesson/by-id/{lesson_db_id}")
    # Assert status code first
    assert response.status_code == 404
    # Then assert detail message
    assert (
        f"Lesson exposition with ID {lesson_db_id} not found or invalid"
        in response.json()["detail"]
    )
    print("test_get_lesson_exposition_by_id_not_found finished")


# --- Test for POST /progress/{syllabus_id}/{module_index}/{lesson_index} ---
def test_update_lesson_progress_success(mock_interaction_service: MagicMock) -> None:
    """Test successfully updating lesson progress."""
    print("Running test_update_lesson_progress_success")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    new_status = "completed"
    mock_response = {
        "progress_id": 789,
        "user_id": "test_user_id",
        "syllabus_id": syllabus_id,
        "module_index": module_index,
        "lesson_index": lesson_index,
        "status": new_status,
    }
    mock_interaction_service.update_lesson_progress.return_value = mock_response
    response = client.post(
        f"/lesson/progress/{syllabus_id}/{module_index}/{lesson_index}",
        json={"status": new_status},
    )
    assert response.status_code == 200
    data = response.json()
    assert data == mock_response
    mock_interaction_service.update_lesson_progress.assert_awaited_once_with(
        user_id="test_user_id",
        syllabus_id=syllabus_id,
        module_index=module_index,
        lesson_index=lesson_index,
        status=new_status,
    )
    print("test_update_lesson_progress_success finished")


def test_update_lesson_progress_invalid_status(mock_interaction_service: MagicMock) -> None:
    """Test updating progress with an invalid status."""
    print("Running test_update_lesson_progress_invalid_status")
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    invalid_status = "finished"
    mock_interaction_service.update_lesson_progress.side_effect = ValueError(
        f"Invalid status: {invalid_status}"
    )
    response = client.post(
        f"/lesson/progress/{syllabus_id}/{module_index}/{lesson_index}",
        json={"status": invalid_status},
    )
    assert response.status_code == 400
    assert f"Invalid status: {invalid_status}" in response.json()["detail"]
    print("test_update_lesson_progress_invalid_status finished")


def test_update_lesson_progress_unauthenticated() -> None:
    """Test updating progress without authentication."""
    print("Running test_update_lesson_progress_unauthenticated")
    app.dependency_overrides[get_current_user] = lambda: None
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    response = client.post(
        f"/lesson/progress/{syllabus_id}/{module_index}/{lesson_index}",
        json={"status": "completed"},
    )
    assert response.status_code == 401
    app.dependency_overrides = {}
    print("test_update_lesson_progress_unauthenticated finished")


# Removed test_evaluate_exercise as the endpoint is commented out
