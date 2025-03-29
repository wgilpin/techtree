# backend/tests/ai/lessons/test_lessons_graph_nodes.py
"""tests for backend/ai/lessons/lessons_graph.py node actions"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import ANY, MagicMock, patch, AsyncMock  # Import AsyncMock
import pytest  # Need pytest for async tests

from google.api_core.exceptions import ResourceExhausted

# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
    Exercise,
    GeneratedLessonContent,
    LessonState,
    Option,  # Added Option import
)


# Mock dependencies that are loaded at module level or used in __init__
# NOTE: Patches moved to individual methods to avoid Pylint confusion
# Removed @pytest.mark.asyncio from class level
class TestLessonAINodes:
    """Tests for the node action methods in LessonAI."""

    # --- Tests for generate_chat_response ---

    # Patches updated to target the 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text", new_callable=AsyncMock
    )  # Patch plain text call
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Patch logger in nodes
    async def test_generate_chat_response_success(
        self,
        mock_call_llm,
        mock_load_prompt,
    ):
        """Test successful chat response generation."""
        mock_load_prompt.return_value = "mocked_chat_prompt"
        mock_call_llm.return_value = (
            "This is the AI response."  # Plain text returns string
        )

        initial_history = [{"role": "user", "content": "Tell me more."}]
        # Use a simplified state structure matching LessonState TypedDict
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
            "conversation_history": initial_history,
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

        # Call the node function directly
        result = await nodes.generate_chat_response(state)  # Await the async node

        mock_load_prompt.assert_called_once_with(
            "chat_response",
            user_message="Tell me more.",
            conversation_history="",  # History before last message is empty
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
        assert new_history[0] == initial_history[0]  # Original message preserved
        assert new_history[1]["role"] == "assistant"
        assert new_history[1]["content"] == "This is the AI response."
        assert result["current_interaction_mode"] == "chatting"  # Mode should be set

    # Remove LessonAI init patches, update logger patch target
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_generate_chat_response_no_user_message(self):
        """Test chat response generation when no user message precedes."""
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state: LessonState = {
            "conversation_history": initial_history,
            "generated_content": GeneratedLessonContent(),  # Provide minimal valid content
            # Fill in other required LessonState fields
            "topic": "Test",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Test",
            "module_title": "Test",
            "user_responses": [],
            "user_performance": {},
            "user_id": "test",
            "lesson_uid": "test",
            "created_at": "t",
            "updated_at": "t",
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

        # Patch logger warning where it's used
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            result = await nodes.generate_chat_response(state)

            # Check only for the specific warning about no user message
            mock_warning.assert_called_once_with(
                f"Cannot generate chat response: No user message found for user {state['user_id']}."
            )
            # State should remain unchanged if no user message
            assert result == state

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text",  # Target nodes, plain text call
        new_callable=AsyncMock,
        side_effect=ResourceExhausted("Quota exceeded"),
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Target nodes
    async def test_generate_chat_response_resource_exhausted(
        self,
        mock_call_llm,
        mock_load_prompt,
    ):
        """Test chat response generation handling ResourceExhausted."""
        mock_load_prompt.return_value = "mocked_chat_prompt"

        initial_history = [{"role": "user", "content": "Tell me more."}]
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
            "created_at": "t",
            "updated_at": "t",
            "conversation_history": initial_history,
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

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = await nodes.generate_chat_response(state)

            mock_error.assert_called_once()
            assert "LLM call failed" in mock_error.call_args[0][0]
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            # Corrected Assertion: Expect the fallback from the except Exception block
            assert (
                "Sorry, I'm having trouble understanding right now."
                in new_history[1]["content"]
            )

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch(
        "backend.ai.lessons.nodes.load_prompt",  # Target nodes
        side_effect=Exception("Prompt loading failed"),
    )
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text", new_callable=AsyncMock
    )  # Target nodes
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Target nodes
    async def test_generate_chat_response_generic_exception(
        self,
        mock_call_llm,
        mock_load_prompt_exc,
    ):
        """Test chat response generation handling a generic exception."""
        initial_history = [{"role": "user", "content": "Tell me more."}]
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
            "created_at": "t",
            "updated_at": "t",
            "conversation_history": initial_history,
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

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = await nodes.generate_chat_response(state)

            mock_error.assert_called_once()
            assert (
                "LLM call failed" in mock_error.call_args[0][0]
            )  # Error is now in LLM call block
            mock_call_llm.assert_not_called()  # LLM call shouldn't happen if prompt load fails
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert (
                "Sorry, I'm having trouble understanding right now."
                in new_history[1]["content"]
            )  # Default fallback

    # --- Tests for evaluate_answer --- # Corrected function name

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text", new_callable=AsyncMock
    )  # Use plain text call
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Patch logger
    async def test_evaluate_answer_exercise_correct(  # Corrected function name
        self,
        mock_call_llm,
        mock_load_prompt,
    ):
        """Test evaluating a correct exercise answer."""
        mock_load_prompt.return_value = "mocked_eval_prompt"
        # Plain text call returns string feedback
        mock_call_llm.return_value = "Spot on!"

        exercise = Exercise(  # Use correct_answer
            id="ex_eval", type="short_answer", question="2+2?", correct_answer="4"
        )
        initial_history = [
            {"role": "assistant", "content": "Exercise: 2+2?"},
            {"role": "user", "content": "4"},
        ]
        state: LessonState = {
            "user_id": "eval_user",
            "current_interaction_mode": "submit_answer",  # Mode should be submit
            "active_exercise": exercise,  # Set active exercise directly
            "active_assessment": None,
            "potential_answer": "4",  # Answer stored in state
            "generated_content": GeneratedLessonContent(),  # Minimal content
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval",
            "module_title": "Eval",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [exercise],
            "generated_assessment_questions": [],
            "generated_exercise_ids": ["ex_eval"],
            "generated_assessment_question_ids": [],
            "error_message": None,
        }

        # Call node function directly
        result = await nodes.evaluate_answer(state)  # Corrected function name

        mock_load_prompt.assert_called_once_with(
            "evaluate_answer",
            task_type="Exercise",
            task_details=ANY,  # Context is complex, just check it was called
            correct_answer_details="Correct Answer/Criteria: 4",
            user_answer="4",
        )
        mock_call_llm.assert_called_once_with("mocked_eval_prompt", max_retries=2)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 3  # Original + User Answer + AI Feedback
        assert new_history[-1]["role"] == "assistant"  # Feedback is last
        assert new_history[-1]["content"] == "Spot on!"

        assert (
            result.get("current_interaction_mode") == "chatting"
        )  # Mode reset after eval
        assert result.get("active_exercise") is None  # Active task cleared
        assert result.get("potential_answer") is None  # Answer cleared

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text", new_callable=AsyncMock
    )  # Use plain text call
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Patch logger
    async def test_evaluate_answer_quiz_incorrect(  # Corrected function name
        self,
        mock_call_llm,
        mock_load_prompt,
    ):
        """Test evaluating an incorrect quiz answer with explanation."""
        mock_load_prompt.return_value = "mocked_eval_prompt"
        # Simulate LLM feedback including explanation
        mock_call_llm.return_value = "Not quite. *Explanation:* Python is a language."

        question = (
            AssessmentQuestion(  # Use question_text, List[Option], correct_answer_id
                id="q_eval",
                type="multiple_choice",
                question_text="What is Python?",
                options=[Option(id="A", text="Snake"), Option(id="B", text="Language")],
                correct_answer_id="B",
                correct_answer="Language",  # Add correct answer text for prompt context
            )
        )
        initial_history = [
            {
                "role": "assistant",
                "content": "Quiz: What is Python? A) Snake B) Language",
            },
            {"role": "user", "content": "A"},  # Incorrect answer
        ]
        state: LessonState = {
            "user_id": "eval_user_quiz",
            "current_interaction_mode": "submit_answer",  # Mode should be submit
            "active_exercise": None,
            "active_assessment": question,  # Set active assessment
            "potential_answer": "A",  # Answer stored in state
            "generated_content": GeneratedLessonContent(),  # Minimal content
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval Quiz",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval Quiz",
            "module_title": "Eval Quiz",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval_q",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [question],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": ["q_eval"],
            "error_message": None,
        }

        # Call node function directly
        result = await nodes.evaluate_answer(state)  # Corrected function name

        mock_load_prompt.assert_called_once_with(
            "evaluate_answer",
            task_type="Assessment Question",
            task_details=ANY,
            correct_answer_details="Correct Answer/Criteria: Language",
            user_answer="A",
        )
        mock_call_llm.assert_called_once_with("mocked_eval_prompt", max_retries=2)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 3  # Original + User Answer + AI Feedback
        assert new_history[-1]["role"] == "assistant"
        assert "Not quite." in new_history[-1]["content"]
        assert "*Explanation:* Python is a language." in new_history[-1]["content"]

        assert result.get("current_interaction_mode") == "chatting"
        assert result.get("active_assessment") is None  # Active task cleared
        assert result.get("potential_answer") is None  # Answer cleared

    # Remove LessonAI init patches, update logger patch target
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_evaluate_answer_no_user_answer(self):  # Corrected function name
        """Test evaluation attempt without a user answer in state."""
        initial_history = [{"role": "assistant", "content": "Question?"}]
        state: LessonState = {
            "user_id": "eval_user_no_ans",
            "current_interaction_mode": "submit_answer",  # Mode is submit
            "active_exercise": Exercise(id="ex", type="short_answer"),  # Active task
            "active_assessment": None,
            "potential_answer": None,  # No answer in state
            "generated_content": GeneratedLessonContent(),  # Minimal content
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval",
            "module_title": "Eval",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [Exercise(id="ex", type="short_answer")],
            "generated_assessment_questions": [],
            "generated_exercise_ids": ["ex"],
            "generated_assessment_question_ids": [],
            "error_message": None,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = await nodes.evaluate_answer(state)  # Corrected function name

            # Check that the specific error about no answer was logged
            mock_error.assert_called_once_with(
                f"Cannot evaluate: No user answer found in state for user {state['user_id']}."
            )
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2  # Original + Error message
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I couldn't find your answer" in new_history[1]["content"]
            # Mode should revert to chatting on error
            assert result.get("current_interaction_mode") == "chatting"

    # Remove LessonAI init patches, update logger patch target
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_evaluate_answer_no_active_task(self):  # Corrected function name
        """Test evaluation when there is no active exercise or assessment."""
        initial_history = [{"role": "user", "content": "My answer"}]
        state: LessonState = {
            "user_id": "eval_user_no_task",
            "current_interaction_mode": "submit_answer",  # Mode is submit
            "active_exercise": None,  # No active task
            "active_assessment": None,
            "potential_answer": "My answer",  # User provided answer
            "generated_content": GeneratedLessonContent(),
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval",
            "module_title": "Eval",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = await nodes.evaluate_answer(state)  # Corrected function name

            mock_error.assert_called_once_with(
                "Cannot evaluate: No active exercise or assessment"
                f" found for user {state['user_id']}."
            )
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2  # User answer + Error message
            assert new_history[1]["role"] == "assistant"
            assert (
                "There doesn't seem to be an active question"
                in new_history[1]["content"]
            )
            assert (
                result.get("current_interaction_mode") == "chatting"
            )  # Mode reset on error

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text",
        new_callable=AsyncMock,
        return_value=None,  # Target nodes, plain text
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Patch logger
    async def test_evaluate_answer_llm_failure(  # Corrected function name
        self,
        mock_call_llm,
        mock_load_prompt,
    ):
        """Test evaluation when the LLM call/parsing fails."""
        mock_load_prompt.return_value = "mocked_eval_prompt"

        exercise = Exercise(  # Use correct_answer
            id="ex_eval_fail", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_fail",
            "current_interaction_mode": "submit_answer",  # Mode is submit
            "active_exercise": exercise,  # Active task
            "active_assessment": None,
            "potential_answer": "answer",  # User answer
            "generated_content": GeneratedLessonContent(),  # Minimal content
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval",
            "module_title": "Eval",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [exercise],
            "generated_assessment_questions": [],
            "generated_exercise_ids": ["ex_eval_fail"],
            "generated_assessment_question_ids": [],
            "error_message": None,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_log_warning:
            # Call node function directly
            result = await nodes.evaluate_answer(state)  # Corrected function name

            mock_load_prompt.assert_called_once()
            mock_call_llm.assert_called_once()
            # Check if the specific warning for LLM failure was logged
            mock_log_warning.assert_called_once_with(
                "LLM returned None for evaluation feedback."
            )

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            # Corrected Assertion: History length should be 2 (user + fallback)
            assert len(new_history) == 2
            assert new_history[-1]["role"] == "assistant"
            assert (
                "Sorry, I couldn't evaluate your answer" in new_history[-1]["content"]
            )

            assert result.get("current_interaction_mode") == "chatting"
            assert result.get("active_exercise") is None  # Task cleared even on error
            assert result.get("potential_answer") is None  # Answer cleared

    # Update patches to target 'nodes' module
    @pytest.mark.asyncio # Added decorator
    @patch(
        "backend.ai.lessons.nodes.load_prompt",  # Target nodes
        side_effect=Exception("LLM Error"),
    )
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text", new_callable=AsyncMock
    )  # Target nodes, plain text
    @patch("backend.ai.lessons.nodes.logger", MagicMock())  # Patch logger
    async def test_evaluate_answer_llm_exception(  # Corrected function name
        self,
        mock_call_llm,
        mock_load_prompt_exc,
    ):
        """Test evaluation when an exception occurs during LLM call."""
        exercise = Exercise(  # Use correct_answer
            id="ex_eval_exc", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_exc",
            "current_interaction_mode": "submit_answer",  # Mode is submit
            "active_exercise": exercise,  # Active task
            "active_assessment": None,
            "potential_answer": "answer",  # User answer
            "generated_content": GeneratedLessonContent(),  # Minimal content
            "conversation_history": initial_history,
            # Fill other required fields
            "topic": "Eval",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Eval",
            "module_title": "Eval",
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "eval",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [exercise],
            "generated_assessment_questions": [],
            "generated_exercise_ids": ["ex_eval_exc"],
            "generated_assessment_question_ids": [],
            "error_message": None,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_log_error:
            # Call node function directly
            result = await nodes.evaluate_answer(state)  # Corrected function name

            mock_load_prompt_exc.assert_called_once()  # Prompt load failed
            mock_call_llm.assert_not_called()  # LLM call shouldn't happen
            # Check if the specific error for prompt loading failure was logged
            mock_log_error.assert_called_once()
            assert (
                "LLM call failed during answer evaluation"
                in mock_log_error.call_args[0][0]
            )

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            # Corrected Assertion: History length should be 2 (user + fallback)
            assert len(new_history) == 2
            assert new_history[-1]["role"] == "assistant"
            assert (
                "Sorry, I couldn't evaluate your answer" in new_history[-1]["content"]
            )

            assert result.get("current_interaction_mode") == "chatting"
            assert result.get("active_exercise") is None  # Task cleared
            assert result.get("potential_answer") is None  # Answer cleared

    # --- Tests for generate_new_exercise ---

    # Removed @pytest.mark.asyncio - This function is synchronous
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")  # No AsyncMock needed
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_success(self, mock_call_llm, mock_load_prompt):
        """Test successful generation of a new exercise."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        mock_new_exercise = Exercise(
            id="ex_new_1",
            type="short_answer",
            instructions="New exercise?",
            correct_answer="Yes",
        )
        mock_call_llm.return_value = mock_new_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "generated_exercises": [],
            "generated_exercise_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",  # Assume user just requested
            # Fill other required fields
            "syllabus": None,
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "gen_ex",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_assessment_questions": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        updated_state, generated_exercise = nodes.generate_new_exercise(
            state
        )  # No await

        mock_load_prompt.assert_called_once_with(
            "generate_exercises",
            topic="Generation",
            lesson_title="Gen Ex",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            syllabus_context="Module: Module Gen, Lesson: Gen Ex",
            existing_exercise_descriptions_json="[]",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_gen_ex_prompt", validation_model=Exercise, max_retries=2
        )

        assert generated_exercise == mock_new_exercise
        assert (
            updated_state["active_exercise"] == mock_new_exercise
        )  # Check active exercise
        assert updated_state["generated_exercise_ids"] == ["ex_new_1"]
        assert (
            updated_state["current_interaction_mode"] == "awaiting_answer"
        )  # Mode updated
        # assert updated_state["current_exercise_id"] == "ex_new_1" # ID tracking removed from state
        assert len(updated_state["conversation_history"]) == 2  # Initial + Presentation
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert (
            "Okay, I've generated a new"
            in updated_state["conversation_history"][-1]["content"]
        )
        # Corrected assertion: check for space instead of underscore
        assert (
            "short answer exercise"
            in updated_state["conversation_history"][-1]["content"]
        )

    # Removed @pytest.mark.asyncio - This function is synchronous
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", return_value=None
    )  # No AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_llm_failure(self, mock_call_llm, mock_load_prompt):
        """Test failure during LLM call for exercise generation."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_fail_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex Fail",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "generated_exercises": [],
            "generated_exercise_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
            # Fill other required fields
            "syllabus": None,
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "gen_ex_fail",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_assessment_questions": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        updated_state, generated_exercise = nodes.generate_new_exercise(
            state
        )  # No await

        mock_call_llm.assert_called_once()
        assert generated_exercise is None
        assert updated_state["active_exercise"] is None  # Should not be updated
        assert updated_state["generated_exercise_ids"] == []
        assert updated_state["current_interaction_mode"] == "chatting"  # Mode reset
        # assert "current_exercise_id" not in updated_state # ID tracking removed
        assert (
            len(updated_state["conversation_history"]) == 2
        )  # Initial + Error message
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert (
            "Sorry, I wasn't able to generate an exercise"
            in updated_state["conversation_history"][-1]["content"]
        )
        assert updated_state["error_message"] == "Exercise generation failed."

    # Removed @pytest.mark.asyncio - This function is synchronous
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")  # No AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_duplicate_id(self, mock_call_llm, mock_load_prompt):
        """Test discarding exercise if LLM returns a duplicate ID."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        # Simulate LLM returning an exercise with an ID that already exists
        mock_duplicate_exercise = Exercise(
            id="ex_existing",
            type="short_answer",
            instructions="Duplicate?",
            correct_answer="No",
        )
        mock_call_llm.return_value = mock_duplicate_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_dup_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex Dup",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "generated_exercises": [],  # Start empty
            "generated_exercise_ids": ["ex_existing"],  # Pre-populate with the ID
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
            # Fill other required fields
            "syllabus": None,
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "gen_ex_dup",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_assessment_questions": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        updated_state, generated_exercise = nodes.generate_new_exercise(
            state
        )  # No await

        mock_call_llm.assert_called_once()
        assert generated_exercise is None  # Exercise should be discarded
        assert updated_state["active_exercise"] is None  # List remains empty
        assert updated_state["generated_exercise_ids"] == [
            "ex_existing"
        ]  # ID list unchanged
        assert updated_state["current_interaction_mode"] == "chatting"
        # assert "current_exercise_id" not in updated_state # ID tracking removed
        assert (
            len(updated_state["conversation_history"]) == 2
        )  # Initial + Error message
        # Correct assertion to match the actual error message in the node
        assert (
            "Sorry, I couldn't come up with a new exercise"
            in updated_state["conversation_history"][-1]["content"]
        )

    # --- Tests for generate_new_assessment --- # Corrected function name

    # Removed @pytest.mark.asyncio - This function is synchronous
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")  # No AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_assessment_success(
        self, mock_call_llm, mock_load_prompt
    ):  # Corrected function name
        """Test successful generation of a new assessment question."""
        mock_load_prompt.return_value = "mocked_gen_q_prompt"
        mock_new_question = AssessmentQuestion(
            id="q_new_1",
            type="true_false",
            question_text="Is this new?",
            correct_answer_id="True",
        )
        mock_call_llm.return_value = mock_new_question

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_q_user",
            "topic": "Generation",
            "lesson_title": "Gen Q",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "generated_assessment_questions": [],
            "generated_assessment_question_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
            # Fill other required fields
            "syllabus": None,
            "user_responses": [],
            "user_performance": {},
            "lesson_uid": "gen_q",
            "created_at": "t",
            "updated_at": "t",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_exercise_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
        }

        updated_state, generated_question = nodes.generate_new_assessment(
            state
        )  # Corrected function name, no await

        mock_load_prompt.assert_called_once_with(
            "generate_assessment",
            topic="Generation",
            lesson_title="Gen Q",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            # syllabus_context="Module: Module Gen, Lesson: Gen Q", # Removed from prompt call
            existing_question_descriptions_json="[]",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_gen_q_prompt", validation_model=AssessmentQuestion, max_retries=2
        )

        assert generated_question == mock_new_question
        assert (
            updated_state["active_assessment"] == mock_new_question
        )  # Check active assessment
        # Corrected assertion: Check the ID list update
        assert updated_state["generated_assessment_question_ids"] == ["q_new_1"]
        assert (
            updated_state["current_interaction_mode"] == "awaiting_answer"
        )  # Mode updated
        # assert updated_state["current_assessment_question_id"] == "q_new_1" # ID tracking removed
        assert len(updated_state["conversation_history"]) == 2  # Initial + Presentation
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert (
            "Okay, here's an assessment question"
            in updated_state["conversation_history"][-1]["content"]
        )
        assert (
            "true false" in updated_state["conversation_history"][-1]["content"]
        )  # Check space, not underscore

    # Add similar failure/duplicate tests for generate_new_assessment if desired...
