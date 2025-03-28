# backend/tests/ai/lessons/test_lessons_graph.py
"""tests for the core process and placeholders in backend/ai/lessons/lessons_graph.py"""
# pylint: disable=protected-access, unused-argument

from unittest.mock import MagicMock, patch

import pytest

from backend.ai.lessons.lessons_graph import LessonAI
from backend.models import GeneratedLessonContent, LessonState


# Mock dependencies that are loaded at module level or used in __init__
# Mock load_dotenv before it's called
@patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
# Mock StateGraph and its compile method
@patch("backend.ai.lessons.lessons_graph.StateGraph")
# Mock logger to avoid actual logging during tests
@patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
class TestLessonAICore:
    """Tests for the core graph process and placeholders in LessonAI."""

    # --- Core Process Tests ---
    def test_init_compiles_graph(self, mock_state_graph):
        """Test that __init__ creates and compiles the StateGraph."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow

        lesson_ai = LessonAI()

        mock_state_graph.assert_called_once_with(LessonState)
        assert mock_workflow.add_node.call_count > 0
        assert mock_workflow.add_edge.call_count > 0
        assert mock_workflow.add_conditional_edges.call_count > 0
        mock_workflow.set_entry_point.assert_called_once_with("process_user_message")
        mock_workflow.compile.assert_called_once()
        assert lesson_ai.chat_graph is mock_workflow.compile.return_value

    def test_start_chat_success(self, mock_state_graph):
        """Test the start_chat method for successful initial message generation."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        initial_state: LessonState = {
            "lesson_topic": "Test Topic",
            "lesson_title": "Test Lesson Title",
            "user_id": "test_user_123",
            "generated_content": GeneratedLessonContent(
                lesson_title="Test Lesson Title",
                lesson_topic="Test Topic",
                introduction="Intro text",
                exposition_content="Exposition text",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": [],
            "current_interaction_mode": None,
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "errors": [],
        }

        final_state = lesson_ai.start_chat(initial_state)

        assert isinstance(final_state, dict)
        assert "conversation_history" in final_state
        assert len(final_state["conversation_history"]) == 1
        first_message = final_state["conversation_history"][0]
        assert first_message["role"] == "assistant"
        assert (
            "Welcome to the lesson on **'Test Lesson Title'**!"
            in first_message["content"]
        )
        assert final_state["current_interaction_mode"] == "chatting"
        assert final_state["user_id"] == "test_user_123"

    def test_start_chat_with_existing_history(self, mock_state_graph):
        """Test that start_chat doesn't add a welcome message if history exists."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        initial_state: LessonState = {
            "lesson_topic": "Test Topic",
            "lesson_title": "Test Lesson Title",
            "user_id": "test_user_123",
            "generated_content": GeneratedLessonContent(
                lesson_title="Test Lesson Title",
                lesson_topic="Test Topic",
                introduction="Intro text",
                exposition_content="Exposition text",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": [{"role": "user", "content": "Hello"}],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "errors": [],
        }

        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            final_state = lesson_ai.start_chat(initial_state)
            assert final_state == initial_state
            mock_warning.assert_called_once()  # Check warning was logged

    # --- New tests for placeholders and process_chat_turn ---

    def test_process_user_message_placeholder(self, mock_state_graph):
        """Test the _process_user_message placeholder node."""
        lesson_ai = LessonAI()
        # This node doesn't really use the state currently
        result = lesson_ai._process_user_message({})
        # pylint: disable=use-implicit-booleaness-not-comparison
        assert result == {}  # Placeholder returns empty dict

    def test_update_progress_placeholder(self, mock_state_graph):
        """Test the _update_progress placeholder node."""
        lesson_ai = LessonAI()
        # This node doesn't really use the state currently
        result = lesson_ai._update_progress({})
        # pylint: disable=use-implicit-booleaness-not-comparison
        assert result == {}  # Placeholder returns empty dict

    def test_process_chat_turn_success(self, mock_state_graph):
        """Test the main process_chat_turn method."""
        # Setup mocks for __init__
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        # Mock the output of the compiled graph's invoke method
        graph_output_state_changes = {
            "conversation_history": [
                {"role": "assistant", "content": "Initial"},
                {"role": "user", "content": "Hello there"},
                {"role": "assistant", "content": "General Kenobi!"},  # Added by graph
            ],
            "current_interaction_mode": "chatting",  # Assume graph ended in chatting
        }
        mock_compiled_graph.invoke.return_value = graph_output_state_changes

        # Define the state *before* the user message is added
        current_state: LessonState = {
            "lesson_topic": "Turn Topic",
            "lesson_title": "Turn Lesson",
            "user_id": "turn_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Turn Lesson",
                lesson_topic="Turn Topic",
                introduction="",
                exposition_content="",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": [{"role": "assistant", "content": "Initial"}],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "errors": [],
        }
        user_message = "Hello there"

        final_state = lesson_ai.process_chat_turn(current_state, user_message)

        # Verify the input state passed to invoke includes the new user message
        expected_input_state_to_graph = {
            **current_state,
            "conversation_history": [
                {"role": "assistant", "content": "Initial"},
                {"role": "user", "content": "Hello there"},
            ],
        }
        mock_compiled_graph.invoke.assert_called_once_with(
            expected_input_state_to_graph
        )

        # Verify the final state merges the original state, the added user message,
        # and the changes from the graph output
        expected_final_state = {
            **current_state,  # Start with original state
            **graph_output_state_changes,  # Apply graph changes (overwrites history, mode)
        }
        # The user message was added *before* invoke, so the graph output history is the final one
        assert final_state == expected_final_state
        assert len(final_state["conversation_history"]) == 3
        assert final_state["conversation_history"][-1]["role"] == "assistant"
        assert final_state["conversation_history"][-1]["content"] == "General Kenobi!"

    def test_process_chat_turn_no_state(self, mock_state_graph):
        """Test that process_chat_turn raises ValueError if no state is provided."""
        lesson_ai = LessonAI()
        with pytest.raises(ValueError, match="Current state must be provided"):
            lesson_ai.process_chat_turn(None, "A message")  # type: ignore

    # --- End of tests ---
