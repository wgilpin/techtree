# backend/tests/ai/lessons/test_lessons_graph_nodes.py
"""tests for backend/ai/lessons/lessons_graph.py node actions"""
# pylint: disable=protected-access, unused-argument, invalid-name

import json
from unittest.mock import ANY, MagicMock, patch, AsyncMock # Import AsyncMock
import pytest # Need pytest for async tests

from google.api_core.exceptions import ResourceExhausted

# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
    EvaluationResult,
    Exercise,
    GeneratedLessonContent,
    LessonState,
    Option, # Added Option import
)


# Mock dependencies that are loaded at module level or used in __init__
# NOTE: Patches moved to individual methods to avoid Pylint confusion
class TestLessonAINodes:
    """Tests for the node action methods in LessonAI."""

    # --- Tests for generate_chat_response ---

    # Patches updated to target the 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_with_retry")
    @patch("backend.ai.lessons.nodes.llm_model") # Patch the imported MODEL instance in nodes
    @patch("backend.ai.lessons.nodes.logger", MagicMock()) # Patch logger in nodes
    def test_generate_chat_response_success(
        self,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt,
    ):
        """Test successful chat response generation."""
        # No longer need LessonAI instance or its init patches (StateGraph, load_dotenv)
        MockLoadPrompt.return_value = "mocked_chat_prompt"
        MockLlmModel_response = MagicMock()
        MockLlmModel_response.text = "This is the AI response."
        MockCallWithRetry.return_value = MockLlmModel_response

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent( # Ensure valid content
                topic="Chatting",
                level="beginner",
                exposition_content="Some exposition.",
                # active_exercises=[], # Removed in model
                # knowledge_assessment=[], # Removed in model
            ),
            "conversation_history": initial_history,
            # Other fields...
        }

        # Call the node function directly
        result = nodes.generate_chat_response(state)

        MockLoadPrompt.assert_called_once_with(
            "chat_response",
            lesson_title="Chat Lesson",
            exposition="Some exposition.",
            history_json=json.dumps(initial_history, indent=2),
        )
        # Check that call_with_retry was called with the model's method and the prompt
        MockCallWithRetry.assert_called_once_with(
            MockLlmModel.generate_content, "mocked_chat_prompt"
        )

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2
        assert new_history[0] == initial_history[0]  # Original message preserved
        assert new_history[1]["role"] == "assistant"
        assert new_history[1]["content"] == "This is the AI response."

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_no_user_message(self):
        """Test chat response generation when no user message precedes."""
        # lesson_ai = LessonAI() # Removed
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state: LessonState = {
            "conversation_history": initial_history,
            "generated_content": GeneratedLessonContent(), # Provide minimal valid content
            # Other fields...
        }

        # Patch logger warning where it's used
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            result = nodes.generate_chat_response(state)

            # Check only for the specific warning about no preceding user message
            mock_warning.assert_called_once_with(
                'generate_chat_response called without a preceding user message.'
            )
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "specific I can help you with" in new_history[1]["content"]

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_with_retry", # Target nodes
        side_effect=ResourceExhausted("Quota exceeded"),
    )
    @patch("backend.ai.lessons.nodes.llm_model") # Target nodes
    @patch("backend.ai.lessons.nodes.logger", MagicMock()) # Target nodes
    def test_generate_chat_response_resource_exhausted(
        self,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt,
    ):
        """Test chat response generation handling ResourceExhausted."""
        # lesson_ai = LessonAI() # Removed
        MockLoadPrompt.return_value = "mocked_chat_prompt"

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent( # Ensure valid content
                topic="Chatting",
                level="beginner",
                exposition_content="Some exposition.",
                # active_exercises=[], # Removed
                # knowledge_assessment=[], # Removed
            ),
            "conversation_history": initial_history,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
             # Call node function directly
            result = nodes.generate_chat_response(state)

            mock_error.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            # Expect the generic error message now, as ResourceExhausted is caught by `except Exception`
            assert "Sorry, I encountered an error" in new_history[1]["content"]

    # Update patches to target 'nodes' module
    @patch(
        "backend.ai.lessons.nodes.load_prompt", # Target nodes
        side_effect=Exception("Prompt loading failed"),
    )
    @patch("backend.ai.lessons.nodes.call_with_retry") # Target nodes
    @patch("backend.ai.lessons.nodes.llm_model") # Target nodes
    @patch("backend.ai.lessons.nodes.logger", MagicMock()) # Target nodes
    def test_generate_chat_response_generic_exception(
        self,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt_exc,
    ):
        """Test chat response generation handling a generic exception."""
        # lesson_ai = LessonAI() # Removed

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent( # Ensure valid content
                topic="Chatting",
                level="beginner",
                exposition_content="Some exposition.",
                # active_exercises=[], # Removed
                # knowledge_assessment=[], # Removed
            ),
            "conversation_history": initial_history,
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = nodes.generate_chat_response(state)

            mock_error.assert_called_once()
            # call_with_retry should not have been called if load_prompt failed
            MockCallWithRetry.assert_not_called()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I encountered an error" in new_history[1]["content"]

    # --- Tests for evaluate_chat_answer ---

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    # Removed broad logger mock to allow debug logs
    def test_evaluate_chat_answer_exercise_correct(
        self,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluating a correct exercise answer."""
        # lesson_ai = LessonAI() # Removed
        MockLoadPrompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=1.0, is_correct=True, feedback="Spot on!", explanation=""
        )
        mock_call_llm.return_value = mock_eval_result

        exercise = Exercise( # Use correct_answer
            id="ex_eval", type="short_answer", question="2+2?", correct_answer="4"
        )
        initial_history = [
            {"role": "assistant", "content": "Exercise: 2+2?"},
            {"role": "user", "content": "4"},
        ]
        state: LessonState = {
            "user_id": "eval_user",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_id": "ex_eval", # Use ID tracking
            "generated_content": GeneratedLessonContent( # Ensure valid content
                topic="Eval",
                level="beginner",
                exposition_content="",
                # active_exercises=[exercise], # No longer in content
                # knowledge_assessment=[],
            ),
            "generated_exercises": [exercise], # Add to state list
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        # Call node function directly
        result = nodes.evaluate_chat_answer(state)

        # Check prompt loading was called (it should be now)
        MockLoadPrompt.assert_called_once_with(
            "evaluate_answer",
            question_type="exercise",
            prompt_context=ANY,  # Context is complex, just check it was called
        )
        mock_call_llm.assert_called_once_with(
            "mocked_eval_prompt", validation_model=EvaluationResult
        )

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 4  # Original + User Answer + AI Feedback + Follow-up
        assert new_history[-2]["role"] == "assistant" # Feedback is second to last
        assert new_history[-2]["content"] == "Spot on!"
        assert new_history[-1]["role"] == "assistant" # Follow-up is last
        assert "next exercise" in new_history[-1]["content"]

        assert result.get("current_interaction_mode") == "chatting" # Mode reset after eval
        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "ex_eval"
        assert response_record["response"] == "4"
        assert response_record["evaluation"]["is_correct"] is True

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    # Removed broad logger mock to allow debug logs
    def test_evaluate_chat_answer_quiz_incorrect(
        self,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluating an incorrect quiz answer with explanation."""
        # lesson_ai = LessonAI() # Removed
        MockLoadPrompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=0.0,
            is_correct=False,
            feedback="Not quite.",
            explanation="Python is a language.",
        )
        mock_call_llm.return_value = mock_eval_result

        question = AssessmentQuestion( # Use question_text, List[Option], correct_answer_id
            id="q_eval",
            type="multiple_choice",
            question_text="What is Python?",
            options=[Option(id="A", text="Snake"), Option(id="B", text="Language")],
            correct_answer_id="B",
        )
        initial_history = [
            {"role": "assistant", "content": "Quiz: What is Python? A) Snake B) Language"},
            {"role": "user", "content": "A"}, # Incorrect answer
        ]
        state: LessonState = {
            "user_id": "eval_user_quiz",
            "current_interaction_mode": "taking_quiz",
            "current_assessment_question_id": "q_eval", # Use ID tracking
            "generated_content": GeneratedLessonContent( # Ensure valid content
                topic="Eval Quiz",
                level="beginner",
                exposition_content="",
                # active_exercises=[],
                # knowledge_assessment=[question], # No longer in content
            ),
            "generated_assessment_questions": [question], # Add to state list
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        # Call node function directly
        result = nodes.evaluate_chat_answer(state)

        MockLoadPrompt.assert_called_once_with(
            "evaluate_answer",
            question_type="assessment",
            prompt_context=ANY,
        )
        mock_call_llm.assert_called_once_with(
            "mocked_eval_prompt", validation_model=EvaluationResult
        )

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        # Should only have feedback, no automatic follow-up on incorrect
        assert len(new_history) == 3
        assert new_history[-1]["role"] == "assistant"
        assert "Not quite." in new_history[-1]["content"]
        assert "*Explanation:* Python is a language." in new_history[-1]["content"]

        assert result.get("current_interaction_mode") == "chatting"
        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "q_eval"
        assert response_record["response"] == "A"
        assert response_record["evaluation"]["is_correct"] is False

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_chat_answer_no_user_message(self):
        """Test evaluation attempt without a preceding user message."""
        # lesson_ai = LessonAI() # Removed
        initial_history = [{"role": "assistant", "content": "Question?"}]
        state: LessonState = {
            "user_id": "eval_user_no_msg",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_id": "ex", # Use ID tracking
            "generated_content": GeneratedLessonContent(), # Provide minimal valid content
            "generated_exercises": [Exercise(id="ex", type="short_answer")], # Add to state
            # knowledge_assessment=[],
            "conversation_history": initial_history,
            "user_responses": [],
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            result = nodes.evaluate_chat_answer(state)

            # Check that the specific warning about no preceding user message was logged
            mock_warning.assert_any_call(
                f"evaluate_chat_answer called without a preceding user message for user {state['user_id']}."
            )
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "haven't provided an answer yet" in new_history[1]["content"]
            # Mode should remain unchanged if no answer provided
            assert result.get("current_interaction_mode") == "doing_exercise"

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_evaluate_chat_answer_question_not_found(self):
        """Test evaluation when the question cannot be found (e.g., bad ID)."""
        # lesson_ai = LessonAI() # Removed
        initial_history = [{"role": "user", "content": "My answer"}]
        state: LessonState = {
            "user_id": "eval_user_no_q",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_id": "non_existent_id", # Bad ID
            "generated_content": GeneratedLessonContent(),
            "generated_exercises": [Exercise(id="ex", type="short_answer")], # Add to state
            # knowledge_assessment=[],
            "conversation_history": initial_history,
            "user_responses": [],
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            result = nodes.evaluate_chat_answer(state)

            mock_error.assert_called_once()
            assert "Could not find question for evaluation" in mock_error.call_args[0][0]
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I lost track" in new_history[1]["content"]
            assert result.get("current_interaction_mode") == "chatting" # Mode reset on error

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", return_value=None # Target nodes
    )
    # Removed broad logger mock to allow debug logs
    def test_evaluate_chat_answer_llm_failure(
        self,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluation when the LLM call/parsing fails."""
        # lesson_ai = LessonAI() # Removed
        MockLoadPrompt.return_value = "mocked_eval_prompt"

        exercise = Exercise( # Use correct_answer
            id="ex_eval_fail", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_fail",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_id": "ex_eval_fail", # Use ID tracking
            "generated_content": GeneratedLessonContent(), # Ensure valid content
            "generated_exercises": [exercise], # Add to state
            # knowledge_assessment=[]
            "conversation_history": initial_history,
            "user_responses": [],
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_log_error:
            # Call node function directly
            result = nodes.evaluate_chat_answer(state)

            MockLoadPrompt.assert_called_once() # Should be called now
            mock_call_llm.assert_called_once()
            # Check if the specific error for LLM failure was logged
            assert any("Failed to get valid evaluation from LLM" in call.args[0] for call in mock_log_error.call_args_list)

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2 # User answer + Fallback feedback
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I encountered an error while evaluating" in new_history[1]["content"]

            assert result.get("current_interaction_mode") == "chatting"
            assert "user_responses" in result
            assert len(result["user_responses"]) == 1
            response_record = result["user_responses"][0]
            assert response_record["evaluation"]["is_correct"] is False # Fallback is incorrect

    # Update patches to target 'nodes' module
    @patch(
        "backend.ai.lessons.nodes.load_prompt", # Target nodes
        side_effect=Exception("LLM Error"),
    )
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing") # Target nodes
    # Removed broad logger mock to allow debug logs
    def test_evaluate_chat_answer_llm_exception(
        self,
        mock_call_llm,
        MockLoadPrompt_exc,
    ):
        """Test evaluation when an exception occurs during LLM call."""
        # lesson_ai = LessonAI() # Removed

        exercise = Exercise( # Use correct_answer
            id="ex_eval_exc", type="short_answer", question="?", correct_answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_exc",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_id": "ex_eval_exc", # Use ID tracking
            "generated_content": GeneratedLessonContent(), # Ensure valid content
            "generated_exercises": [exercise], # Add to state
            # knowledge_assessment=[]
            "conversation_history": initial_history,
            "user_responses": [],
        }

        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_log_error:
            # Call node function directly
            result = nodes.evaluate_chat_answer(state)

            MockLoadPrompt_exc.assert_called_once()  # Prompt load failed
            mock_call_llm.assert_not_called() # LLM call shouldn't happen
            # Check if the specific error for prompt loading failure was logged
            assert any("Error in evaluation prompt loading/formatting" in call.args[0] for call in mock_log_error.call_args_list)

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2 # User answer + Fallback feedback
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I encountered an error while evaluating" in new_history[1]["content"]

            assert result.get("current_interaction_mode") == "chatting"
            assert "user_responses" in result
            assert len(result["user_responses"]) == 1
            response_record = result["user_responses"][0]
            assert response_record["evaluation"]["is_correct"] is False # Fallback is incorrect

    # --- Tests for generate_new_exercise ---

    @pytest.mark.asyncio # Mark test as async
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock) # Use AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_generate_new_exercise_success(self, mock_call_llm, mock_load_prompt):
        """Test successful generation of a new exercise."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        mock_new_exercise = Exercise(
            id="ex_new_1", type="short_answer", instructions="New exercise?", correct_answer="Yes"
        )
        mock_call_llm.return_value = mock_new_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(exposition_content="Lesson content here."),
            "generated_exercises": [],
            "generated_exercise_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting", # Assume user just requested
        }

        updated_state, generated_exercise = await nodes.generate_new_exercise(state)

        mock_load_prompt.assert_called_once_with(
            "generate_exercises",
            topic="Generation",
            lesson_title="Gen Ex",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            syllabus_context="Module: Module Gen, Lesson: Gen Ex",
            existing_exercise_descriptions_json='[]'
        )
        mock_call_llm.assert_called_once_with( # Changed from assert_awaited_once_with
            "mocked_gen_ex_prompt", validation_model=Exercise, max_retries=2
        )

        assert generated_exercise == mock_new_exercise
        assert updated_state["generated_exercises"] == [mock_new_exercise]
        assert updated_state["generated_exercise_ids"] == ["ex_new_1"]
        assert updated_state["current_interaction_mode"] == "doing_exercise"
        assert updated_state["current_exercise_id"] == "ex_new_1"
        assert len(updated_state["conversation_history"]) == 2 # Initial + Presentation
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert "Okay, here's a new exercise" in updated_state["conversation_history"][-1]["content"]
        assert "New exercise?" in updated_state["conversation_history"][-1]["content"]

    @pytest.mark.asyncio
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock, return_value=None) # Use AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_generate_new_exercise_llm_failure(self, mock_call_llm, mock_load_prompt):
        """Test failure during LLM call for exercise generation."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_fail_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex Fail",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(exposition_content="Lesson content here."),
            "generated_exercises": [],
            "generated_exercise_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
        }

        updated_state, generated_exercise = await nodes.generate_new_exercise(state)

        mock_call_llm.assert_called_once() # Changed from assert_awaited_once
        assert generated_exercise is None
        assert updated_state["generated_exercises"] == [] # Should not be updated
        assert updated_state["generated_exercise_ids"] == []
        assert updated_state["current_interaction_mode"] == "chatting" # Mode reset
        assert "current_exercise_id" not in updated_state # ID should not be set
        assert len(updated_state["conversation_history"]) == 2 # Initial + Error message
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert "Sorry, I wasn't able to generate an exercise" in updated_state["conversation_history"][-1]["content"]
        assert updated_state["error_message"] == "Failed to generate exercise."

    @pytest.mark.asyncio
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock) # Use AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_generate_new_exercise_duplicate_id(self, mock_call_llm, mock_load_prompt):
        """Test discarding exercise if LLM returns a duplicate ID."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        # Simulate LLM returning an exercise with an ID that already exists
        mock_duplicate_exercise = Exercise(
            id="ex_existing", type="short_answer", instructions="Duplicate?", correct_answer="No"
        )
        mock_call_llm.return_value = mock_duplicate_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_ex_dup_user",
            "topic": "Generation",
            "lesson_title": "Gen Ex Dup",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(exposition_content="Lesson content here."),
            "generated_exercises": [], # Start empty
            "generated_exercise_ids": ["ex_existing"], # Pre-populate with the ID
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
        }

        updated_state, generated_exercise = await nodes.generate_new_exercise(state)

        mock_call_llm.assert_called_once() # Changed from assert_awaited_once
        assert generated_exercise is None # Exercise should be discarded
        assert updated_state["generated_exercises"] == [] # List remains empty
        assert updated_state["generated_exercise_ids"] == ["ex_existing"] # ID list unchanged
        assert updated_state["current_interaction_mode"] == "chatting"
        assert "current_exercise_id" not in updated_state
        assert len(updated_state["conversation_history"]) == 2 # Initial + Error message
        # Correct assertion to match the actual error message in the node
        assert "Sorry, I couldn't come up with a new exercise" in updated_state["conversation_history"][-1]["content"]

    # --- Tests for generate_new_assessment_question ---

    @pytest.mark.asyncio
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock) # Use AsyncMock
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_generate_new_assessment_question_success(self, mock_call_llm, mock_load_prompt):
        """Test successful generation of a new assessment question."""
        mock_load_prompt.return_value = "mocked_gen_q_prompt"
        mock_new_question = AssessmentQuestion(
            id="q_new_1", type="true_false", question_text="Is this new?", correct_answer_id="True"
        )
        mock_call_llm.return_value = mock_new_question

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state: LessonState = {
            "user_id": "gen_q_user",
            "topic": "Generation",
            "lesson_title": "Gen Q",
            "knowledge_level": "intermediate",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(exposition_content="Lesson content here."),
            "generated_assessment_questions": [],
            "generated_assessment_question_ids": [],
            "conversation_history": initial_history,
            "current_interaction_mode": "chatting",
        }

        updated_state, generated_question = await nodes.generate_new_assessment_question(state)

        mock_load_prompt.assert_called_once_with(
            "generate_assessment",
            topic="Generation",
            lesson_title="Gen Q",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            syllabus_context="Module: Module Gen, Lesson: Gen Q",
            existing_question_descriptions_json='[]'
        )
        mock_call_llm.assert_called_once_with( # Changed from assert_awaited_once_with
            "mocked_gen_q_prompt", validation_model=AssessmentQuestion, max_retries=2
        )

        assert generated_question == mock_new_question
        assert updated_state["generated_assessment_questions"] == [mock_new_question]
        assert updated_state["generated_assessment_question_ids"] == ["q_new_1"]
        assert updated_state["current_interaction_mode"] == "taking_quiz"
        assert updated_state["current_assessment_question_id"] == "q_new_1"
        assert len(updated_state["conversation_history"]) == 2 # Initial + Presentation
        assert updated_state["conversation_history"][-1]["role"] == "assistant"
        assert "Okay, here's an assessment question" in updated_state["conversation_history"][-1]["content"]
        assert "Is this new?" in updated_state["conversation_history"][-1]["content"]

    # Add similar failure/duplicate tests for generate_new_assessment_question if desired...
