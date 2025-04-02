# backend/tests/ai/lessons/test_node_evaluate.py
"""Tests for backend/ai/lessons/nodes.py evaluate_answer node"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import ANY, MagicMock, patch
from typing import Optional, List, Dict, Any, cast  # Added imports


# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
    LessonState,
    Option,
)
from backend.ai.prompt_formatting import LATEX_FORMATTING_INSTRUCTIONS



class TestEvaluateAnswerNode:
    """Tests for the evaluate_answer node action."""

    # Basic state setup helper (copied and adapted)

    def _get_base_state(
        self,
        user_message: Optional[str] = "Test answer",
        history: Optional[List[Dict[str, str]]] = None,  # Use List[Dict[str, str]]
        active_exercise: Optional[Exercise] = None,
        active_assessment: Optional[AssessmentQuestion] = None,
        potential_answer: Optional[str] = "Test answer",
    ) -> LessonState:
        """Creates a base LessonState dictionary for testing evaluation."""
        current_history = list(history) if history is not None else []
        if user_message:  # Usually the answer is the last user message
            current_history.append({"role": "user", "content": user_message})

        # Ensure all keys from LessonState are present
        state: LessonState = {
            "topic": "Evaluation",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval Lesson",
            "module_title": "Module Eval",
            "generated_content": GeneratedLessonContent(
                exposition_content="Some exposition."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "eval_user",
            "lesson_uid": "eval_lesson_uid",
            "created_at": "sometime",
            "updated_at": "sometime",
            "history_context": current_history,  # Use history_context
            "current_interaction_mode": "submit_answer",  # Assume mode is correct
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [active_exercise] if active_exercise else [],
            "generated_assessment_questions": (
                [active_assessment] if active_assessment else []
            ),
            "generated_exercise_ids": [active_exercise.id] if active_exercise else [],
            "generated_assessment_question_ids": (
                [active_assessment.id] if active_assessment else []
            ),
            "error_message": None,
            "active_exercise": active_exercise,
            "active_assessment": active_assessment,
            "potential_answer": potential_answer,
            "lesson_db_id": None,
        }
        return state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_exercise_correct(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None:  # Added return type hint
        """Test evaluating a correct exercise answer."""
        mock_load_prompt.return_value = "mocked_eval_prompt"
        mock_call_llm.return_value = "Spot on!"

        exercise = Exercise(
            id="ex_eval", type="short_answer", question="2+2?", correct_answer="4"
        )
        initial_history = [
            {"role": "assistant", "content": "Exercise: 2+2?"},
            {"role": "user", "content": "4"},
        ]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_exercise=exercise,
            potential_answer="4",
        )

        # Cast state before calling node
        updated_state, feedback_message = nodes.evaluate_answer(
            cast(Dict[str, Any], state)
        )

        mock_load_prompt.assert_called_once_with(
            "evaluate_answer",
            task_type="Exercise",
            task_details=ANY,
            correct_answer_details="Correct Answer/Criteria: 4",
            user_answer="4",
            latex_formatting_instructions=LATEX_FORMATTING_INSTRUCTIONS,
        )
        mock_call_llm.assert_called_once_with("mocked_eval_prompt", max_retries=2)

        # Check the returned feedback message (it's a dict or None)
        assert isinstance(feedback_message, dict)
        assert feedback_message.get("role") == "assistant"
        assert feedback_message.get("content") == "Spot on!"

        # Check the updated state (it's a dict)
        assert isinstance(updated_state, dict)
        assert updated_state.get("current_interaction_mode") == "chatting"
        assert updated_state.get("active_exercise") is None
        assert updated_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_quiz_incorrect(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None:  # Added return type hint
        """Test evaluating an incorrect quiz answer with explanation."""
        mock_load_prompt.return_value = "mocked_eval_prompt"
        mock_call_llm.return_value = "Not quite. *Explanation:* Python is a language."

        question = AssessmentQuestion(
            id="q_eval",
            type="multiple_choice",
            question_text="What is Python?",
            options=[Option(id="A", text="Snake"), Option(id="B", text="Language")],
            correct_answer_id="B",
            correct_answer="Language",
        )
        initial_history = [
            {
                "role": "assistant",
                "content": "Quiz: What is Python? A) Snake B) Language",
            },
            {"role": "user", "content": "A"},
        ]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_assessment=question,
            potential_answer="A",
        )

        # Cast state before calling node
        updated_state, feedback_message = nodes.evaluate_answer(
            cast(Dict[str, Any], state)
        )

        mock_load_prompt.assert_called_once_with(
            "evaluate_answer",
            task_type="Assessment Question",
            task_details=ANY,
            correct_answer_details="Correct Answer: Language", # Match actual call
            user_answer="A",
            latex_formatting_instructions=LATEX_FORMATTING_INSTRUCTIONS,
        )
        mock_call_llm.assert_called_once_with("mocked_eval_prompt", max_retries=2)

        # Check the returned feedback message
        assert isinstance(feedback_message, dict)
        assert feedback_message.get("role") == "assistant"
        assert "Not quite." in feedback_message.get("content", "")
        assert "*Explanation:* Python is a language." in feedback_message.get(
            "content", ""
        )

        # Check the updated state
        assert isinstance(updated_state, dict)
        assert updated_state.get("current_interaction_mode") == "chatting"
        assert updated_state.get("active_assessment") is None
        assert updated_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_no_user_answer(self) -> None:  # Added return type hint
        """Test evaluation attempt without a user answer in state."""
        initial_history = [{"role": "assistant", "content": "Question?"}]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_exercise=Exercise(id="ex", type="short_answer"),
            potential_answer=None,
        )

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node
            updated_state, feedback_message = nodes.evaluate_answer(
                cast(Dict[str, Any], state)
            )

            mock_error.assert_called_once_with(
                f"Cannot evaluate: No user answer found in state for user {state['user_id']}."
            )
            # Check the returned feedback message
            assert isinstance(feedback_message, dict)
            assert feedback_message.get("role") == "assistant"
            assert "Sorry, I couldn't find your answer" in feedback_message.get(
                "content", ""
            )

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_no_active_task(self) -> None:  # Added return type hint
        """Test evaluation when there is no active exercise or assessment."""
        initial_history = [{"role": "user", "content": "My answer"}]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_exercise=None,
            active_assessment=None,
            potential_answer="My answer",
        )

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node
            updated_state, feedback_message = nodes.evaluate_answer(
                cast(Dict[str, Any], state)
            )

            mock_error.assert_called_once_with(
                "Cannot evaluate: No active exercise or assessment"
                f" found for user {state['user_id']}."
            )
            # Check the returned feedback message
            assert isinstance(feedback_message, dict)
            assert feedback_message.get("role") == "assistant"
            assert (
                "There doesn't seem to be an active question"
                in feedback_message.get("content", "")
            )

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"
            # Ensure active tasks are still None
            assert updated_state.get("active_exercise") is None
            assert updated_state.get("active_assessment") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text",
        return_value=None,
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_llm_failure(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None:  # Added return type hint
        """Test evaluation when the LLM call/parsing fails."""
        mock_load_prompt.return_value = "mocked_eval_prompt"
        exercise = Exercise(
            id="ex_eval_fail", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_exercise=exercise,
            potential_answer="answer",
        )

        with patch("backend.ai.lessons.nodes.logger.warning") as mock_log_warning:
            # Cast state before calling node
            updated_state, feedback_message = nodes.evaluate_answer(
                cast(Dict[str, Any], state)
            )

            mock_load_prompt.assert_called_once()
            mock_call_llm.assert_called_once()
            mock_log_warning.assert_called_once_with(
                "LLM returned None for evaluation feedback."
            )

            # Check the returned feedback message
            assert isinstance(feedback_message, dict)
            assert feedback_message.get("role") == "assistant"
            assert (
                "Sorry, I couldn't evaluate your answer properly"
                in feedback_message.get("content", "")
            )  # Check fallback

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"
            assert updated_state.get("active_exercise") is None
            assert (
                updated_state.get("potential_answer") is None
            )  # Also check potential_answer
            assert updated_state.get("potential_answer") is None

    @patch(
        "backend.ai.lessons.nodes.load_prompt",
        side_effect=Exception("LLM Error"),
    )
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_answer_llm_exception(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt_exc: MagicMock,
    ) -> None:  # Added return type hint
        """Test evaluation when an exception occurs during LLM call."""
        exercise = Exercise(
            id="ex_eval_exc", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state = self._get_base_state(
            user_message=None,
            history=initial_history,
            active_exercise=exercise,
            potential_answer="answer",
        )

        with patch("backend.ai.lessons.nodes.logger.error") as mock_log_error:
            # Cast state before calling node
            updated_state, feedback_message = nodes.evaluate_answer(
                cast(Dict[str, Any], state)
            )

            mock_load_prompt_exc.assert_called_once()
            mock_call_llm.assert_not_called()
            mock_log_error.assert_called_once()
            assert (
                "LLM call failed during answer evaluation"
                in mock_log_error.call_args[0][0]
            )

            # Check the returned feedback message
            assert isinstance(feedback_message, dict)
            assert feedback_message.get("role") == "assistant"
            assert (
                "Sorry, I encountered an error while evaluating"
                in feedback_message.get("content", "")
            )  # Check error fallback

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"
            assert updated_state.get("active_exercise") is None
            assert updated_state.get("potential_answer") is None
