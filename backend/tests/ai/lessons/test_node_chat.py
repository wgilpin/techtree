# backend/tests/ai/lessons/test_node_chat.py
"""Tests for backend/ai/lessons/nodes.py generate_chat_response node"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import MagicMock, patch
from typing import Optional, List, Dict, Any, cast # Added Optional, List, Dict, Any, cast


from google.api_core.exceptions import ResourceExhausted

# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    GeneratedLessonContent,
    LessonState,
)


class TestGenerateChatResponse:
    """Tests for the generate_chat_response node action."""

    # Basic state setup helper (copied and adapted)
    def _get_base_state(
        self,
        user_message: Optional[str] = "Test message", # Allow None
        history: Optional[List[Dict[str, str]]] = None # Use List[Dict[str, str]]
    ) -> LessonState:
        """Creates a base LessonState dictionary for testing chat response."""
        current_history = list(history) if history is not None else []
        if user_message:
            current_history.append({"role": "user", "content": user_message})

        # Ensure all keys from LessonState are present
        state: LessonState = {
            "topic": "Chatting",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Chat Lesson",
            "module_title": "Module Chat",
            "generated_content": GeneratedLessonContent(
                exposition_content="Some exposition."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "chat_user",
            "lesson_uid": "chat_lesson_uid",
            "created_at": "sometime",
            "updated_at": "sometime",
            "conversation_history": current_history,
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
            "lesson_db_id": None,
        }
        return state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_success(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None: # Added return type hint
        """Test successful chat response generation."""
        mock_load_prompt.return_value = "mocked_chat_prompt"
        mock_call_llm.return_value = "This is the AI response."

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        # Cast state before calling node
        result = nodes.generate_chat_response(cast(Dict[str, Any], state))

        mock_load_prompt.assert_called_once_with(
            "chat_response",
            user_message="Tell me more.",
            conversation_history="",
            topic="Chatting",
            lesson_title="Chat Lesson",
            user_level="beginner",
            exposition_summary="Some exposition.",
            active_task_context="None",
        )
        mock_call_llm.assert_called_once_with("mocked_chat_prompt", max_retries=3)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2
        assert new_history[0] == initial_history[0]
        assert new_history[1]["role"] == "assistant"
        assert new_history[1]["content"] == "This is the AI response."
        assert result["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_no_user_message(self) -> None: # Added return type hint
        """Test chat response generation when no user message precedes."""
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Cast state before calling node
            result = nodes.generate_chat_response(cast(Dict[str, Any], state))

            mock_warning.assert_called_once_with(
                f"Cannot generate chat response: No user message found for user {state['user_id']}."
            )
            assert result == state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text",
        side_effect=ResourceExhausted("Quota exceeded"), # type: ignore[no-untyped-call]
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_resource_exhausted(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None: # Added return type hint
        """Test chat response generation handling ResourceExhausted."""
        mock_load_prompt.return_value = "mocked_chat_prompt"
        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node
            result = nodes.generate_chat_response(cast(Dict[str, Any], state))

            mock_error.assert_called_once()
            assert "LLM call failed" in mock_error.call_args[0][0]
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert (
                "Sorry, I'm having trouble understanding right now."
                in new_history[1]["content"]
            )

    @patch(
        "backend.ai.lessons.nodes.load_prompt",
        side_effect=Exception("Prompt loading failed"),
    )
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text"
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_generic_exception(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt_exc: MagicMock,
    ) -> None: # Added return type hint
        """Test chat response generation handling a generic exception."""
        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node
            result = nodes.generate_chat_response(cast(Dict[str, Any], state))

            mock_error.assert_called_once()
            assert (
                "LLM call failed" in mock_error.call_args[0][0]
            )
            mock_call_llm.assert_not_called()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert (
                "Sorry, I'm having trouble understanding right now."
                in new_history[1]["content"]
            )