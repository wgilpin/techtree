# backend/tests/ai/lessons/test_lessons_graph.py
"""tests for backend/ai/lessons/lessons_graph.py"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import MagicMock, patch

from backend.ai.app import LessonAI
from backend.models import GeneratedLessonContent, LessonState


# Mock dependencies that are loaded at module level or used in __init__
@patch("backend.ai.lessons.lessons_graph.StateGraph")
@patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())  # Mock dotenv
class TestLessonAICore:
    """Tests for the core initialization and structure of LessonAI."""

    def test_init_compiles_graph(self, mock_state_graph):
        """Test that __init__ creates and compiles the StateGraph."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow

        lesson_ai = LessonAI()

        mock_state_graph.assert_called_once_with(LessonState)
        assert mock_workflow.add_node.call_count > 0
        assert mock_workflow.add_edge.call_count > 0
        assert mock_workflow.add_conditional_edges.call_count > 0
        # Corrected entry point assertion
        mock_workflow.set_entry_point.assert_called_once_with("classify_intent")
        mock_workflow.compile.assert_called_once()
        assert lesson_ai.chat_graph is not None

    # Mock the nodes.start_conversation call within start_chat
    # or mock the fallback behavior
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())  # Mock logger
    def test_start_chat_success(self, mock_state_graph):
        """Test the start_chat method for successful initial message generation."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        # Provide a more complete initial state matching LessonState TypedDict
        initial_state: LessonState = {
            "topic": "Test Topic",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Test Lesson Title",
            "module_title": "Test Module",
            "generated_content": GeneratedLessonContent(
                exposition_content="Intro text"
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "test_user_123",
            "lesson_uid": "test_uid",
            "created_at": "t",
            "updated_at": "t",
            "conversation_history": [],  # Start with empty history
            "current_interaction_mode": "chatting",  # Initial mode
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        final_state = lesson_ai.start_chat(initial_state)

        assert "conversation_history" in final_state
        assert len(final_state["conversation_history"]) == 1
        first_message = final_state["conversation_history"][0]
        assert first_message["role"] == "assistant"
        # Assert the generic welcome message from the refactored start_chat
        assert "Welcome to your lesson!" in first_message["content"]
        assert final_state["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())  # Mock logger
    def test_start_chat_with_existing_history(self, mock_state_graph):
        """Test start_chat when initial state unexpectedly has history (should still work)."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        initial_state: LessonState = {
            "topic": "Test Topic",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Test Lesson Title",
            "module_title": "Test Module",
            "generated_content": GeneratedLessonContent(
                exposition_content="Intro text"
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "test_user_123",
            "lesson_uid": "test_uid",
            "created_at": "t",
            "updated_at": "t",
            "conversation_history": [{"role": "system", "content": "Existing message"}],
            "current_interaction_mode": "chatting",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        final_state = lesson_ai.start_chat(initial_state)

        # Should still add the welcome message
        assert len(final_state["conversation_history"]) == 1  # It replaces history now
        first_message = final_state["conversation_history"][0]
        assert first_message["role"] == "assistant"
        assert "Welcome to your lesson!" in first_message["content"]
        assert final_state["current_interaction_mode"] == "chatting"

    # Test process_chat_turn (requires mocking the compiled graph invoke)
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_process_chat_turn(self, mock_state_graph):
        """Test the process_chat_turn method."""
        mock_workflow = MagicMock()
        mock_state_graph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph
        # Simulate graph output (e.g., adding an assistant message)
        mock_graph_output = {
            "conversation_history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "current_interaction_mode": "chatting",
        }
        mock_compiled_graph.invoke.return_value = mock_graph_output

        lesson_ai = LessonAI()

        initial_state: LessonState = {
            "topic": "Test",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Test",
            "module_title": "Test",
            "generated_content": GeneratedLessonContent(exposition_content="Test"),
            "user_responses": [],
            "user_performance": {},
            "user_id": "test",
            "lesson_uid": "test",
            "created_at": "t",
            "updated_at": "t",
            "conversation_history": [],  # Start empty for this turn
            "current_interaction_mode": "chatting",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }
        user_message = "Hello"

        final_state = lesson_ai.process_chat_turn(initial_state, user_message)

        # Check that invoke was called with the state including the new user message
        expected_input_state = {
            **initial_state,
            "conversation_history": [{"role": "user", "content": user_message}],
        }
        mock_compiled_graph.invoke.assert_called_once_with(expected_input_state)

        # Check that the final state includes the original state, the user message,
        # and the output from the graph invoke
        assert (
            final_state["conversation_history"]
            == mock_graph_output["conversation_history"]
        )
        assert (
            final_state["current_interaction_mode"]
            == mock_graph_output["current_interaction_mode"]
        )
        assert (
            final_state["topic"] == initial_state["topic"]
        )  # Check original state preserved
