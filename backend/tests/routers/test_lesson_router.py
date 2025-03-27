# backend/tests/routers/test_lesson_router.py
# pylint: disable=missing-function-docstring,missing-module-docstring
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

# Adjust the import path based on your project structure and how 'app' is defined
# Assuming 'app' is the FastAPI instance in backend.main
# Need to make sure sys.path is correct for tests or use relative imports
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.main import app
from backend.models import User
from backend.services.lesson_service import LessonService
from backend.dependencies import get_current_user  # Import the dependency function
# Import the dependency getter function we need to override
from backend.routers.lesson_router import get_lesson_service

# Create a TestClient instance
client = TestClient(app)

# --- Fixtures and Mocks ---


# Mock the dependency get_current_user
@pytest.fixture(autouse=True)
def override_get_current_user():
    mock_user = User(
        user_id="test_user_id",
        email="test@example.com",
        name="Test User",
        password_hash="hashed",
    )

    def mock_dependency():
        print("Using mock get_current_user")  # Debug print
        return mock_user

    app.dependency_overrides[get_current_user] = mock_dependency
    print(
        f"Overriding get_current_user: {get_current_user} with {mock_dependency}"
    )  # Debug print
    yield
    # Clean up overrides after test
    print("Cleaning up dependency overrides")  # Debug print
    app.dependency_overrides = {}





# Mock the LessonService by overriding the dependency
@pytest.fixture
def mock_lesson_service():
    print("Setting up mock_lesson_service override")  # Debug print
    # Create a MagicMock instance that adheres to the LessonService spec
    mock_service = MagicMock(spec=LessonService)
    # Configure async methods on the mock
    mock_service.get_or_generate_lesson = AsyncMock()
    mock_service.handle_chat_turn = AsyncMock()
    # Add other methods used in tests if necessary, e.g., evaluate_exercise, update_lesson_progress
    mock_service.get_lesson_by_id = AsyncMock()
    mock_service.evaluate_exercise = AsyncMock()
    mock_service.update_lesson_progress = AsyncMock()

    # Define the override function
    def override_get_lesson_service():
        print("Using mock get_lesson_service")  # Debug print
        return mock_service

    # Apply the override
    app.dependency_overrides[get_lesson_service] = override_get_lesson_service
    print(
        f"Overriding get_lesson_service: {get_lesson_service} with {override_get_lesson_service}"
    )  # Debug print

    yield mock_service  # Yield the mock for use in tests

    # Clean up the override after the test
    print("Cleaning up lesson_service dependency override")  # Debug print
    del app.dependency_overrides[get_lesson_service]


# --- Test Cases ---

#pylint: disable=redefined-outer-name
def test_get_lesson_data_success(mock_lesson_service):
    """Test successful retrieval of lesson data and state."""
    print("Running test_get_lesson_data_success")  # Debug print
    # Arrange
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    mock_content = {"metadata": {"title": "Test Lesson"}, "exposition": "<p>Test</p>"}
    mock_state = {"conversation_history": [], "current_interaction_mode": "chatting"}
    mock_lesson_service.get_or_generate_lesson.return_value = {
        "lesson_id": "lesson_db_id_1",
        "syllabus_id": syllabus_id,
        "module_index": module_index,
        "lesson_index": lesson_index,
        "content": mock_content,
        "lesson_state": mock_state,
        "is_new": False,
    }
    print("Mock configured")  # Debug print

    # Act
    print("Making GET request")  # Debug print
    response = client.get(f"/lesson/{syllabus_id}/{module_index}/{lesson_index}")
    print(f"Response status: {response.status_code}")  # Debug print
    # print(f"Response JSON: {response.json()}") # Debug print

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["syllabus_id"] == syllabus_id
    assert data["module_index"] == module_index
    assert data["lesson_index"] == lesson_index
    assert data["content"] == mock_content
    assert data["lesson_state"] == mock_state
    assert data["is_new"] is False
    mock_lesson_service.get_or_generate_lesson.assert_awaited_once_with(
        syllabus_id, module_index, lesson_index, "test_user_id"
    )
    print("test_get_lesson_data_success finished")  # Debug print


def test_get_lesson_data_not_found(mock_lesson_service):
    """Test retrieving a non-existent lesson."""
    print("Running test_get_lesson_data_not_found")  # Debug print
    # Arrange
    syllabus_id = "syllabus_bad"
    module_index = 99
    lesson_index = 99
    mock_lesson_service.get_or_generate_lesson.side_effect = ValueError(
        "Lesson not found"
    )

    # Act
    response = client.get(f"/lesson/{syllabus_id}/{module_index}/{lesson_index}")

    # Assert
    assert response.status_code == 404
    assert "Lesson not found" in response.json()["detail"]
    print("test_get_lesson_data_not_found finished")  # Debug print


# --- Tests for POST /chat ---


def test_handle_chat_message_success(mock_lesson_service):
    """Test successfully sending a chat message and getting a response."""
    print("Running test_handle_chat_message_success")  # Debug print
    # Arrange
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "What is this lesson about?"
    ai_response = [{"role": "assistant", "content": "This lesson is about..."}]
    mock_lesson_service.handle_chat_turn.return_value = {"responses": ai_response}

    # Act
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["responses"] == ai_response
    assert data["error"] is None
    mock_lesson_service.handle_chat_turn.assert_awaited_once_with(
        user_id="test_user_id",
        syllabus_id=syllabus_id,
        module_index=module_index,
        lesson_index=lesson_index,
        user_message=user_message,
    )
    print("test_handle_chat_message_success finished")  # Debug print


def test_handle_chat_message_unauthenticated():
    """Test sending chat message without authentication."""
    print("Running test_handle_chat_message_unauthenticated")  # Debug print
    # Arrange
    # Override dependency to simulate no user
    app.dependency_overrides[get_current_user] = lambda: None
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1

    # Act
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": "test"},
    )

    # Assert
    assert response.status_code == 401  # FastAPI default for failed dependency
    # Detail might vary based on how get_current_user signals failure
    # assert "Authentication required" in response.json()["detail"] # Check if detail matches

    # Clean up override
    app.dependency_overrides = {}
    print("test_handle_chat_message_unauthenticated finished")  # Debug print


def test_handle_chat_message_service_error(mock_lesson_service):
    """Test handling an error from the lesson service during chat."""
    print("Running test_handle_chat_message_service_error")  # Debug print
    # Arrange
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "This will cause an error"
    # Simulate service layer returning an error structure
    mock_lesson_service.handle_chat_turn.return_value = {
        "error": "AI processing failed"
    }

    # Act
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )

    # Assert
    assert response.status_code == 200  # Endpoint handles the error gracefully
    data = response.json()
    assert data["responses"] == []
    assert data["error"] == "AI processing failed"
    print("test_handle_chat_message_service_error finished")  # Debug print


def test_handle_chat_message_state_not_found(mock_lesson_service):
    """Test handling ValueError (e.g., state not found) from service."""
    print("Running test_handle_chat_message_state_not_found")  # Debug print
    # Arrange
    syllabus_id = "syllabus1"
    module_index = 0
    lesson_index = 1
    user_message = "Where is my state?"
    mock_lesson_service.handle_chat_turn.side_effect = ValueError(
        "Lesson state not found"
    )

    # Act
    response = client.post(
        f"/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}",
        json={"message": user_message},
    )

    # Assert
    assert (
        response.status_code == 404
    )  # Based on router's exception handling for ValueError
    assert "Lesson state not found" in response.json()["detail"]
    print("test_handle_chat_message_state_not_found finished")  # Debug print
