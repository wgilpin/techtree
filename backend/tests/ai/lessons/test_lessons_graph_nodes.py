# backend/tests/ai/lessons/test_lessons_graph_nodes.py
"""tests for backend/ai/lessons/lessons_graph.py node actions"""
# pylint: disable=protected-access, unused-argument, invalid-name

import json
from unittest.mock import ANY, MagicMock, patch

from google.api_core.exceptions import ResourceExhausted

from backend.ai.lessons.lessons_graph import LessonAI
from backend.models import (
    AssessmentQuestion,
    EvaluationResult,
    Exercise,
    GeneratedLessonContent,
    LessonState,
)


# Mock dependencies that are loaded at module level or used in __init__
# NOTE: Patches moved to individual methods to avoid Pylint confusion
class TestLessonAINodes:
    """Tests for the node action methods in LessonAI."""

    # --- Tests for _generate_chat_response ---

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch("backend.ai.lessons.lessons_graph.call_with_retry")
    @patch(
        "backend.ai.lessons.lessons_graph.llm_model"
    )  # Patch the imported MODEL instance
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_generate_chat_response_success(
        self,
        MockStateGraph,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt,
    ):
        """Test successful chat response generation."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_chat_prompt"
        MockLlmModel_response = MagicMock()
        MockLlmModel_response.text = "This is the AI response."
        MockCallWithRetry.return_value = MockLlmModel_response

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Chat Lesson",
                lesson_topic="Chatting",
                introduction="",
                exposition_content="Some exposition.",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
            # Other fields...
        }

        result = lesson_ai._generate_chat_response(state)

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

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_generate_chat_response_no_user_message(self, MockStateGraph):
        """Test chat response generation when no user message precedes."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state: LessonState = {
            "conversation_history": initial_history,
            # Other fields...
        }

        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            result = lesson_ai._generate_chat_response(state)

            mock_warning.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "specific I can help you with" in new_history[1]["content"]

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch(
        "backend.ai.lessons.lessons_graph.call_with_retry",
        side_effect=ResourceExhausted("Quota exceeded"),
    )
    @patch("backend.ai.lessons.lessons_graph.llm_model")
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_generate_chat_response_resource_exhausted(
        self,
        MockStateGraph,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt,
    ):
        """Test chat response generation handling ResourceExhausted."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_chat_prompt"

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Chat Lesson",
                lesson_topic="Chatting",
                introduction="",
                exposition_content="Some exposition.",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
        }

        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_error:
            result = lesson_ai._generate_chat_response(state)

            mock_error.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I'm having trouble connecting" in new_history[1]["content"]

    @patch(
        "backend.ai.lessons.lessons_graph.load_prompt",
        side_effect=Exception("Prompt loading failed"),
    )
    @patch("backend.ai.lessons.lessons_graph.call_with_retry")
    @patch("backend.ai.lessons.lessons_graph.llm_model")
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_generate_chat_response_generic_exception(
        self,
        MockStateGraph,
        MockLlmModel,
        MockCallWithRetry,
        MockLoadPrompt_exc,
    ):
        """Test chat response generation handling a generic exception."""
        lesson_ai = LessonAI()

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Chat Lesson",
                lesson_topic="Chatting",
                introduction="",
                exposition_content="Some exposition.",
                active_exercises=[],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
        }

        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_error:
            result = lesson_ai._generate_chat_response(state)

            mock_error.assert_called_once()
            # call_with_retry should not have been called if load_prompt failed
            MockCallWithRetry.assert_not_called()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I encountered an error" in new_history[1]["content"]

    # --- Tests for _present_exercise ---

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_exercise_success(self, MockStateGraph):
        """Test presenting the next available exercise."""
        lesson_ai = LessonAI()
        exercise1 = Exercise(
            id="ex1", type="short_answer", question="What is 1+1?", answer="2"
        )
        exercise2 = Exercise(
            id="ex2", type="coding", instructions="Write a print statement."
        )
        initial_history = [{"role": "user", "content": "Gimme exercise"}]
        state: LessonState = {
            "user_id": "ex_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Ex Lesson",
                lesson_topic="Exercises",
                introduction="",
                exposition_content="",
                active_exercises=[exercise1, exercise2],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
            "current_exercise_index": -1,  # Start before the first exercise
            # Other fields...
        }

        result = lesson_ai._present_exercise(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2  # User message + AI exercise presentation
        assert new_history[1]["role"] == "assistant"
        assert "Alright, let's try exercise 1!" in new_history[1]["content"]
        assert "**Type:** Short answer" in new_history[1]["content"]
        assert "**Instructions:**\nWhat is 1+1?" in new_history[1]["content"]
        assert "Please provide your answer." in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "doing_exercise"
        assert result.get("current_exercise_index") == 0  # Index updated to 0

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_exercise_ordering(self, MockStateGraph):
        """Test presenting an ordering exercise includes items."""
        lesson_ai = LessonAI()
        exercise_ord = Exercise(
            id="ex_ord",
            type="ordering",
            instructions="Order these steps:",
            items=["Step A", "Step C", "Step B"],
            correct_order=["Step A", "Step B", "Step C"],
        )
        initial_history = [{"role": "user", "content": "Gimme exercise"}]
        state: LessonState = {
            "user_id": "ex_user_ord",
            "generated_content": GeneratedLessonContent(
                lesson_title="Order Lesson",
                lesson_topic="Ordering",
                introduction="",
                exposition_content="",
                active_exercises=[exercise_ord],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
            "current_exercise_index": -1,
            # Other fields...
        }

        result = lesson_ai._present_exercise(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2
        assert new_history[1]["role"] == "assistant"
        assert "Alright, let's try exercise 1!" in new_history[1]["content"]
        assert "**Type:** Ordering" in new_history[1]["content"]
        assert "**Instructions:**\nOrder these steps:" in new_history[1]["content"]
        assert "**Items to order:**" in new_history[1]["content"]
        assert "- Step A" in new_history[1]["content"]
        assert "- Step C" in new_history[1]["content"]  # Check items are listed
        assert "- Step B" in new_history[1]["content"]
        assert "Please provide your answer." in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "doing_exercise"
        assert result.get("current_exercise_index") == 0

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_exercise_no_more_exercises(self, MockStateGraph):
        """Test behavior when no more exercises are available."""
        lesson_ai = LessonAI()
        exercise1 = Exercise(
            id="ex1", type="short_answer", question="What is 1+1?", answer="2"
        )
        initial_history = [{"role": "user", "content": "Next exercise"}]
        state: LessonState = {
            "user_id": "ex_user_done",
            "generated_content": GeneratedLessonContent(
                lesson_title="Ex Lesson",
                lesson_topic="Exercises",
                introduction="",
                exposition_content="",
                active_exercises=[exercise1],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
            "current_exercise_index": 0,  # Already completed the last exercise (index 0)
            # Other fields...
        }

        result = lesson_ai._present_exercise(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2  # User message + AI completion message
        assert new_history[1]["role"] == "assistant"
        assert (
            "Great job, you've completed all the exercises" in new_history[1]["content"]
        )
        assert "What would you like to do next?" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "chatting"  # Mode reset
        assert (
            result.get("current_exercise_index") == 0
        )  # Index remains at the last completed one

    # --- Tests for _present_quiz_question ---

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_quiz_question_success_mc(self, MockStateGraph):
        """Test presenting the next available multiple-choice quiz question."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(
            id="q1",
            type="multiple_choice",
            question="What is Python?",
            options={"A": "Snake", "B": "Language"},
            correct_answer="B",
        )
        q2 = AssessmentQuestion(
            id="q2", type="true_false", question="Is water wet?", correct_answer="True"
        )
        initial_history = [{"role": "user", "content": "Start quiz"}]
        state: LessonState = {
            "user_id": "quiz_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Quiz Lesson",
                lesson_topic="Quizzes",
                introduction="",
                exposition_content="",
                active_exercises=[],
                knowledge_assessment=[q1, q2],
            ),
            "conversation_history": initial_history,
            "current_quiz_question_index": -1,  # Start before the first question
            # Other fields...
        }

        result = lesson_ai._present_quiz_question(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2  # User message + AI question presentation
        assert new_history[1]["role"] == "assistant"
        assert "Okay, here's quiz question 1:" in new_history[1]["content"]
        assert "What is Python?" in new_history[1]["content"]
        assert "- A) Snake" in new_history[1]["content"]
        assert "- B) Language" in new_history[1]["content"]
        assert "Please respond with the letter/key" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "taking_quiz"
        assert result.get("current_quiz_question_index") == 0  # Index updated to 0

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_quiz_question_success_tf(self, MockStateGraph):
        """Test presenting the next available true/false quiz question."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(
            id="q1",
            type="true_false",
            question="Is the sky blue?",
            correct_answer="True",
        )
        initial_history = [{"role": "user", "content": "Start quiz"}]
        state: LessonState = {
            "user_id": "quiz_user_tf",
            "generated_content": GeneratedLessonContent(
                lesson_title="TF Quiz",
                lesson_topic="Quizzes",
                introduction="",
                exposition_content="",
                active_exercises=[],
                knowledge_assessment=[q1],
            ),
            "conversation_history": initial_history,
            "current_quiz_question_index": -1,
            # Other fields...
        }

        result = lesson_ai._present_quiz_question(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2
        assert new_history[1]["role"] == "assistant"
        assert "Okay, here's quiz question 1:" in new_history[1]["content"]
        assert "Is the sky blue?" in new_history[1]["content"]
        assert "- True" in new_history[1]["content"]
        assert "- False" in new_history[1]["content"]
        assert "Please respond with 'True' or 'False'." in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "taking_quiz"
        assert result.get("current_quiz_question_index") == 0

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_present_quiz_question_no_more_questions(self, MockStateGraph):
        """Test behavior when no more quiz questions are available."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(
            id="q1", type="true_false", question="Is water wet?", correct_answer="True"
        )
        initial_history = [{"role": "user", "content": "Next question"}]
        state: LessonState = {
            "user_id": "quiz_user_done",
            "generated_content": GeneratedLessonContent(
                lesson_title="Quiz Lesson",
                lesson_topic="Quizzes",
                introduction="",
                exposition_content="",
                active_exercises=[],
                knowledge_assessment=[q1],
            ),
            "conversation_history": initial_history,
            "current_quiz_question_index": 0,  # Already completed the last question (index 0)
            # Other fields...
        }

        result = lesson_ai._present_quiz_question(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2  # User message + AI completion message
        assert new_history[1]["role"] == "assistant"
        assert "You've completed the quiz for this lesson!" in new_history[1]["content"]
        assert "What would you like to do now?" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "chatting"  # Mode reset
        assert (
            result.get("current_quiz_question_index") == 0
        )  # Index remains at the last completed one

    # --- Tests for _evaluate_chat_answer ---

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch("backend.ai.lessons.lessons_graph.call_llm_with_json_parsing")
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_exercise_correct(
        self,
        MockStateGraph,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluating a correct exercise answer."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=1.0, is_correct=True, feedback="Spot on!", explanation=""
        )
        mock_call_llm.return_value = mock_eval_result

        exercise = Exercise(
            id="ex_eval", type="short_answer", question="2+2?", answer="4"
        )
        initial_history = [
            {"role": "assistant", "content": "Exercise: 2+2?"},
            {"role": "user", "content": "4"},
        ]
        state: LessonState = {
            "user_id": "eval_user",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(
                lesson_title="Eval Lesson",
                lesson_topic="Eval",
                introduction="",
                exposition_content="",
                active_exercises=[exercise],
                knowledge_assessment=[],
            ),
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        result = lesson_ai._evaluate_chat_answer(state)

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
        # Initial history + AI feedback + AI follow-up
        assert len(new_history) == 4
        assert new_history[2]["role"] == "assistant"
        assert new_history[2]["content"] == "Spot on!"  # Feedback from LLM
        assert new_history[3]["role"] == "assistant"
        assert "next exercise" in new_history[3]["content"]  # Follow-up

        assert result.get("current_interaction_mode") == "chatting"  # Mode reset

        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "ex_eval"
        assert response_record["question_type"] == "exercise"
        assert response_record["response"] == "4"
        assert response_record["evaluation"]["is_correct"] is True
        assert response_record["evaluation"]["score"] == 1.0
        assert "timestamp" in response_record

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch("backend.ai.lessons.lessons_graph.call_llm_with_json_parsing")
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_quiz_incorrect(
        self,
        MockStateGraph,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluating an incorrect quiz answer with explanation."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=0.0,
            is_correct=False,
            feedback="Not quite.",
            explanation="Python is a language.",
        )
        mock_call_llm.return_value = mock_eval_result

        question = AssessmentQuestion(
            id="q_eval",
            type="multiple_choice",
            question="What is Python?",
            options={"A": "Snake", "B": "Language"},
            correct_answer="B",
        )
        initial_history = [
            {
                "role": "assistant",
                "content": "Quiz: What is Python? A) Snake B) Language",
            },
            {"role": "user", "content": "A"},
        ]
        state: LessonState = {
            "user_id": "eval_user_quiz",
            "current_interaction_mode": "taking_quiz",
            "current_quiz_question_index": 0,
            "generated_content": GeneratedLessonContent(
                lesson_title="Eval Lesson",
                lesson_topic="Eval",
                introduction="",
                exposition_content="",
                active_exercises=[],
                knowledge_assessment=[question],
            ),
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        result = lesson_ai._evaluate_chat_answer(state)

        MockLoadPrompt.assert_called_once()
        mock_call_llm.assert_called_once()

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        # Initial history + AI feedback (including explanation)
        assert len(new_history) == 3
        assert new_history[2]["role"] == "assistant"
        assert "Not quite." in new_history[2]["content"]  # Feedback
        assert (
            "*Explanation:* Python is a language." in new_history[2]["content"]
        )  # Explanation

        assert result.get("current_interaction_mode") == "chatting"  # Mode reset

        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "q_eval"
        assert response_record["question_type"] == "assessment"
        assert response_record["response"] == "A"
        assert response_record["evaluation"]["is_correct"] is False
        assert response_record["evaluation"]["explanation"] == "Python is a language."

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_no_user_message(self, MockStateGraph):
        """Test evaluation attempt without a preceding user message."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "assistant", "content": "Question?"}]
        state: LessonState = {
            "user_id": "eval_user_no_msg",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(
                active_exercises=[Exercise(id="ex", type="short_answer")],
                knowledge_assessment=[],
            ),  # Dummy content
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_warning.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2  # Original + AI error message
            assert new_history[1]["role"] == "assistant"
            assert "haven't provided an answer yet" in new_history[1]["content"]
            # Mode should not change
            assert result.get("current_interaction_mode") == "doing_exercise"
            # No response should be recorded
            assert len(result.get("user_responses", [])) == 0

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_question_not_found(self, MockStateGraph):
        """Test evaluation when the current question cannot be found."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "user", "content": "My answer"}]
        state: LessonState = {
            "user_id": "eval_user_no_q",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 99,  # Index out of bounds
            "generated_content": GeneratedLessonContent(
                active_exercises=[], knowledge_assessment=[]
            ),  # No exercises
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_error:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_error.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2  # Original + AI error message
            assert new_history[1]["role"] == "assistant"
            assert "lost track of which question" in new_history[1]["content"]
            assert result.get("current_interaction_mode") == "chatting"  # Mode reset
            assert len(result.get("user_responses", [])) == 0

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch(
        "backend.ai.lessons.lessons_graph.call_llm_with_json_parsing", return_value=None
    )
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_llm_failure(
        self,
        MockStateGraph,
        mock_call_llm,
        MockLoadPrompt,
    ):
        """Test evaluation when the LLM call/parsing fails."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_eval_prompt"

        exercise = Exercise(
            id="ex_eval_fail", type="short_answer", question="?", answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_fail",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(
                active_exercises=[exercise], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_log_error:
            result = lesson_ai._evaluate_chat_answer(state)

            MockLoadPrompt.assert_called_once()
            mock_call_llm.assert_called_once()
            mock_log_error.assert_called_once()  # Logged the failure

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2  # Original + AI fallback message
            assert new_history[1]["role"] == "assistant"
            assert "encountered an error while evaluating" in new_history[1]["content"]

            assert result.get("current_interaction_mode") == "chatting"  # Mode reset

            assert "user_responses" in result
            assert len(result["user_responses"]) == 1
            response_record = result["user_responses"][0]
            assert response_record["question_id"] == "ex_eval_fail"
            assert response_record["response"] == "answer"
            # Check fallback evaluation data
            assert response_record["evaluation"]["is_correct"] is False
            assert response_record["evaluation"]["score"] == 0.0
            assert "encountered an error" in response_record["evaluation"]["feedback"]

    @patch(
        "backend.ai.lessons.lessons_graph.load_prompt",
        side_effect=Exception("LLM Error"),
    )
    @patch("backend.ai.lessons.lessons_graph.call_llm_with_json_parsing")
    # Add the standard patches
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_evaluate_chat_answer_llm_exception(
        self,
        MockStateGraph,
        mock_call_llm,
        MockLoadPrompt_exc,
    ):
        """Test evaluation when an exception occurs during LLM call."""
        lesson_ai = LessonAI()

        exercise = Exercise(
            id="ex_eval_exc", type="short_answer", question="?", answer="!"
        )
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_exc",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(
                active_exercises=[exercise], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_log_error:
            result = lesson_ai._evaluate_chat_answer(state)

            MockLoadPrompt_exc.assert_called_once()  # Prompt load failed
            mock_call_llm.assert_not_called()  # LLM call skipped
            mock_log_error.assert_called_once()  # Logged the exception

            # Check results are same as LLM failure case (fallback applied)
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert "encountered an error while evaluating" in new_history[1]["content"]
            assert result.get("current_interaction_mode") == "chatting"
            assert len(result["user_responses"]) == 1
            assert result["user_responses"][0]["evaluation"]["is_correct"] is False
