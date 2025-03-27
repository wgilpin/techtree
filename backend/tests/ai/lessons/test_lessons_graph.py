# backend/tests/ai/lessons/test_lessons_graph.py
import json
from unittest.mock import ANY, MagicMock, patch

import pytest
from google.api_core.exceptions import \
    ResourceExhausted  # Import for testing exception

from backend.ai.lessons.lessons_graph import LessonAI
from backend.models import (AssessmentQuestion, EvaluationResult, Exercise,
                            GeneratedLessonContent, IntentClassificationResult,
                            LessonState)


# Mock dependencies that are loaded at module level or used in __init__
# Mock load_dotenv before it's called
@patch('backend.ai.lessons.lessons_graph.load_dotenv', MagicMock())
# Mock StateGraph and its compile method
@patch('backend.ai.lessons.lessons_graph.StateGraph')
# Mock logger to avoid actual logging during tests
@patch('backend.ai.lessons.lessons_graph.logger', MagicMock())
class TestLessonAI:
    """Tests for the LessonAI class."""

    # --- Existing tests from previous step ---
    def test_init_compiles_graph(self, MockStateGraph):
        """Test that __init__ creates and compiles the StateGraph."""
        mock_workflow = MagicMock()
        MockStateGraph.return_value = mock_workflow

        lesson_ai = LessonAI()

        MockStateGraph.assert_called_once_with(LessonState)
        assert mock_workflow.add_node.call_count > 0
        assert mock_workflow.add_edge.call_count > 0
        assert mock_workflow.add_conditional_edges.call_count > 0
        mock_workflow.set_entry_point.assert_called_once_with("process_user_message")
        mock_workflow.compile.assert_called_once()
        assert lesson_ai.chat_graph is mock_workflow.compile.return_value

    def test_start_chat_success(self, MockStateGraph):
        """Test the start_chat method for successful initial message generation."""
        mock_workflow = MagicMock()
        MockStateGraph.return_value = mock_workflow
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
                knowledge_assessment=[]
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
        assert "Welcome to the lesson on **'Test Lesson Title'**!" in first_message["content"]
        assert final_state["current_interaction_mode"] == "chatting"
        assert final_state["user_id"] == "test_user_123"

    def test_start_chat_with_existing_history(self, MockStateGraph):
        """Test that start_chat doesn't add a welcome message if history exists."""
        mock_workflow = MagicMock()
        MockStateGraph.return_value = mock_workflow
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
                knowledge_assessment=[]
            ),
            "conversation_history": [{"role": "user", "content": "Hello"}],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1,
            "current_quiz_question_index": -1,
            "user_responses": [],
            "errors": [],
        }

        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            final_state = lesson_ai.start_chat(initial_state)
            assert final_state == initial_state
            mock_warning.assert_called_once() # Check warning was logged

    # --- New tests for _route_message_logic ---

    @pytest.mark.parametrize("mode", ["doing_exercise", "taking_quiz"])
    def test_route_message_logic_evaluation_mode(self, MockStateGraph, mode):
        """Test routing when mode requires evaluation."""
        lesson_ai = LessonAI() # Instantiation needed to access the method
        state: LessonState = {
            "current_interaction_mode": mode,
            "conversation_history": [{"role": "user", "content": "My answer"}],
            # Other state fields...
        }
        route = lesson_ai._route_message_logic(state)
        assert route == "evaluate_chat_answer"

    def test_route_message_logic_chatting_no_user_message(self, MockStateGraph):
        """Test routing in chatting mode with no preceding user message."""
        lesson_ai = LessonAI()
        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [{"role": "assistant", "content": "Hi there!"}],
            # Other state fields...
        }
        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing')
    @pytest.mark.parametrize("intent, expected_route", [
        ("request_exercise", "present_exercise"),
        ("request_quiz", "present_quiz_question"),
        ("ask_question", "generate_chat_response"),
        ("other_chat", "generate_chat_response"),
        ("unknown_intent", "generate_chat_response"), # Test default for unknown
    ])
    def test_route_message_logic_chatting_intent_classification(
        self, mock_call_llm, mock_load_prompt, MockStateGraph, intent, expected_route
    ):
        """Test routing based on LLM intent classification."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Give me an exercise"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }

        route = lesson_ai._route_message_logic(state)

        mock_load_prompt.assert_called_once_with(
            "intent_classification",
            history_json=json.dumps(state["conversation_history"], indent=2),
            user_input="Give me an exercise",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_prompt", validation_model=IntentClassificationResult
        )
        assert route == expected_route
        # Check warning for unknown intent
        if intent == "unknown_intent":
             with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
                 lesson_ai._route_message_logic(state) # Call again to check warning
                 mock_warning.assert_called_once()


    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing')
    def test_route_message_logic_chatting_intent_failure(
        self, mock_call_llm, mock_load_prompt, MockStateGraph
    ):
        """Test routing default when intent classification fails."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_prompt"
        mock_call_llm.return_value = None # Simulate LLM/parsing failure

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Something weird"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response" # Default route
            mock_warning.assert_called_once()

    @patch('backend.ai.lessons.lessons_graph.load_prompt', side_effect=Exception("LLM Error"))
    def test_route_message_logic_chatting_intent_exception(
        self, mock_load_prompt, MockStateGraph
    ):
        """Test routing default when an exception occurs during intent classification."""
        lesson_ai = LessonAI()

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Something weird"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_error:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response" # Default route
            mock_error.assert_called_once()

    def test_route_message_logic_unexpected_mode(self, MockStateGraph):
        """Test routing default for an unexpected interaction mode."""
        lesson_ai = LessonAI()
        state: LessonState = {
            "current_interaction_mode": "unexpected_mode",
            "conversation_history": [{"role": "user", "content": "My answer"}],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()

    # --- New tests for _generate_chat_response ---

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_with_retry')
    @patch('backend.ai.lessons.lessons_graph.llm_model') # Patch the imported MODEL instance
    def test_generate_chat_response_success(
        self, mock_llm, mock_call_retry, mock_load_prompt, MockStateGraph
    ):
        """Test successful chat response generation."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_chat_prompt"
        mock_llm_response = MagicMock()
        mock_llm_response.text = "This is the AI response."
        mock_call_retry.return_value = mock_llm_response

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson",
            "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Chat Lesson", lesson_topic="Chatting", introduction="",
                exposition_content="Some exposition.", active_exercises=[], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            # Other fields...
        }

        result = lesson_ai._generate_chat_response(state)

        mock_load_prompt.assert_called_once_with(
            "chat_response",
            lesson_title="Chat Lesson",
            exposition="Some exposition.",
            history_json=json.dumps(initial_history, indent=2),
        )
        # Check that call_with_retry was called with the model's method and the prompt
        mock_call_retry.assert_called_once_with(mock_llm.generate_content, "mocked_chat_prompt")

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2
        assert new_history[0] == initial_history[0] # Original message preserved
        assert new_history[1]["role"] == "assistant"
        assert new_history[1]["content"] == "This is the AI response."

    def test_generate_chat_response_no_user_message(self, MockStateGraph):
        """Test chat response generation when no user message precedes."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state: LessonState = {
            "conversation_history": initial_history,
            # Other fields...
        }

        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            result = lesson_ai._generate_chat_response(state)

            mock_warning.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "specific I can help you with" in new_history[1]["content"]

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_with_retry', side_effect=ResourceExhausted("Quota exceeded"))
    @patch('backend.ai.lessons.lessons_graph.llm_model')
    def test_generate_chat_response_resource_exhausted(
        self, mock_llm, mock_call_retry, mock_load_prompt, MockStateGraph
    ):
        """Test chat response generation handling ResourceExhausted."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_chat_prompt"

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson", "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(lesson_title="Chat Lesson", lesson_topic="Chatting", introduction="", exposition_content="Some exposition.", active_exercises=[], knowledge_assessment=[]),
            "conversation_history": initial_history,
        }

        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_error:
            result = lesson_ai._generate_chat_response(state)

            mock_error.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I'm having trouble connecting" in new_history[1]["content"]

    @patch('backend.ai.lessons.lessons_graph.load_prompt', side_effect=Exception("Prompt loading failed"))
    @patch('backend.ai.lessons.lessons_graph.call_with_retry')
    @patch('backend.ai.lessons.lessons_graph.llm_model')
    def test_generate_chat_response_generic_exception(
        self, mock_llm, mock_call_retry, mock_load_prompt, MockStateGraph
    ):
        """Test chat response generation handling a generic exception."""
        lesson_ai = LessonAI()

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state: LessonState = {
            "lesson_title": "Chat Lesson", "user_id": "chat_user",
            "generated_content": GeneratedLessonContent(lesson_title="Chat Lesson", lesson_topic="Chatting", introduction="", exposition_content="Some exposition.", active_exercises=[], knowledge_assessment=[]),
            "conversation_history": initial_history,
        }

        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_error:
            result = lesson_ai._generate_chat_response(state)

            mock_error.assert_called_once()
            # call_with_retry should not have been called if load_prompt failed
            mock_call_retry.assert_not_called()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert new_history[1]["role"] == "assistant"
            assert "Sorry, I encountered an error" in new_history[1]["content"]

    # --- New tests for _present_exercise ---

    def test_present_exercise_success(self, MockStateGraph):
        """Test presenting the next available exercise."""
        lesson_ai = LessonAI()
        exercise1 = Exercise(id="ex1", type="short_answer", question="What is 1+1?", answer="2")
        exercise2 = Exercise(id="ex2", type="coding", instructions="Write a print statement.")
        initial_history = [{"role": "user", "content": "Gimme exercise"}]
        state: LessonState = {
            "user_id": "ex_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Ex Lesson", lesson_topic="Exercises", introduction="", exposition_content="",
                active_exercises=[exercise1, exercise2], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            "current_exercise_index": -1, # Start before the first exercise
            # Other fields...
        }

        result = lesson_ai._present_exercise(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2 # User message + AI exercise presentation
        assert new_history[1]["role"] == "assistant"
        assert "Alright, let's try exercise 1!" in new_history[1]["content"]
        assert "**Type:** Short answer" in new_history[1]["content"]
        assert "**Instructions:**\nWhat is 1+1?" in new_history[1]["content"]
        assert "Please provide your answer." in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "doing_exercise"
        assert result.get("current_exercise_index") == 0 # Index updated to 0

    def test_present_exercise_ordering(self, MockStateGraph):
        """Test presenting an ordering exercise includes items."""
        lesson_ai = LessonAI()
        exercise_ord = Exercise(
            id="ex_ord", type="ordering", instructions="Order these steps:",
            items=["Step A", "Step C", "Step B"], correct_order=["Step A", "Step B", "Step C"]
        )
        initial_history = [{"role": "user", "content": "Gimme exercise"}]
        state: LessonState = {
            "user_id": "ex_user_ord",
            "generated_content": GeneratedLessonContent(
                lesson_title="Order Lesson", lesson_topic="Ordering", introduction="", exposition_content="",
                active_exercises=[exercise_ord], knowledge_assessment=[]
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
        assert "- Step C" in new_history[1]["content"] # Check items are listed
        assert "- Step B" in new_history[1]["content"]
        assert "Please provide your answer." in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "doing_exercise"
        assert result.get("current_exercise_index") == 0

    def test_present_exercise_no_more_exercises(self, MockStateGraph):
        """Test behavior when no more exercises are available."""
        lesson_ai = LessonAI()
        exercise1 = Exercise(id="ex1", type="short_answer", question="What is 1+1?", answer="2")
        initial_history = [{"role": "user", "content": "Next exercise"}]
        state: LessonState = {
            "user_id": "ex_user_done",
            "generated_content": GeneratedLessonContent(
                lesson_title="Ex Lesson", lesson_topic="Exercises", introduction="", exposition_content="",
                active_exercises=[exercise1], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            "current_exercise_index": 0, # Already completed the last exercise (index 0)
            # Other fields...
        }

        result = lesson_ai._present_exercise(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2 # User message + AI completion message
        assert new_history[1]["role"] == "assistant"
        assert "Great job, you've completed all the exercises" in new_history[1]["content"]
        assert "What would you like to do next?" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "chatting" # Mode reset
        assert result.get("current_exercise_index") == 0 # Index remains at the last completed one

    # --- New tests for _present_quiz_question ---

    def test_present_quiz_question_success_mc(self, MockStateGraph):
        """Test presenting the next available multiple-choice quiz question."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(
            id="q1", type="multiple_choice", question="What is Python?",
            options={"A": "Snake", "B": "Language"}, correct_answer="B"
        )
        q2 = AssessmentQuestion(id="q2", type="true_false", question="Is water wet?", correct_answer="True")
        initial_history = [{"role": "user", "content": "Start quiz"}]
        state: LessonState = {
            "user_id": "quiz_user",
            "generated_content": GeneratedLessonContent(
                lesson_title="Quiz Lesson", lesson_topic="Quizzes", introduction="", exposition_content="",
                active_exercises=[], knowledge_assessment=[q1, q2]
            ),
            "conversation_history": initial_history,
            "current_quiz_question_index": -1, # Start before the first question
            # Other fields...
        }

        result = lesson_ai._present_quiz_question(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2 # User message + AI question presentation
        assert new_history[1]["role"] == "assistant"
        assert "Okay, here's quiz question 1:" in new_history[1]["content"]
        assert "What is Python?" in new_history[1]["content"]
        assert "- A) Snake" in new_history[1]["content"]
        assert "- B) Language" in new_history[1]["content"]
        assert "Please respond with the letter/key" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "taking_quiz"
        assert result.get("current_quiz_question_index") == 0 # Index updated to 0

    def test_present_quiz_question_success_tf(self, MockStateGraph):
        """Test presenting the next available true/false quiz question."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(id="q1", type="true_false", question="Is the sky blue?", correct_answer="True")
        initial_history = [{"role": "user", "content": "Start quiz"}]
        state: LessonState = {
            "user_id": "quiz_user_tf",
            "generated_content": GeneratedLessonContent(
                lesson_title="TF Quiz", lesson_topic="Quizzes", introduction="", exposition_content="",
                active_exercises=[], knowledge_assessment=[q1]
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

    def test_present_quiz_question_no_more_questions(self, MockStateGraph):
        """Test behavior when no more quiz questions are available."""
        lesson_ai = LessonAI()
        q1 = AssessmentQuestion(id="q1", type="true_false", question="Is water wet?", correct_answer="True")
        initial_history = [{"role": "user", "content": "Next question"}]
        state: LessonState = {
            "user_id": "quiz_user_done",
            "generated_content": GeneratedLessonContent(
                lesson_title="Quiz Lesson", lesson_topic="Quizzes", introduction="", exposition_content="",
                active_exercises=[], knowledge_assessment=[q1]
            ),
            "conversation_history": initial_history,
            "current_quiz_question_index": 0, # Already completed the last question (index 0)
            # Other fields...
        }

        result = lesson_ai._present_quiz_question(state)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        assert len(new_history) == 2 # User message + AI completion message
        assert new_history[1]["role"] == "assistant"
        assert "You've completed the quiz for this lesson!" in new_history[1]["content"]
        assert "What would you like to do now?" in new_history[1]["content"]

        assert result.get("current_interaction_mode") == "chatting" # Mode reset
        assert result.get("current_quiz_question_index") == 0 # Index remains at the last completed one

    # --- New tests for _evaluate_chat_answer ---

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing')
    def test_evaluate_chat_answer_exercise_correct(
        self, mock_call_llm, mock_load_prompt, MockStateGraph
    ):
        """Test evaluating a correct exercise answer."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=1.0, is_correct=True, feedback="Spot on!", explanation=""
        )
        mock_call_llm.return_value = mock_eval_result

        exercise = Exercise(id="ex_eval", type="short_answer", question="2+2?", answer="4")
        initial_history = [
            {"role": "assistant", "content": "Exercise: 2+2?"},
            {"role": "user", "content": "4"},
        ]
        state: LessonState = {
            "user_id": "eval_user",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(
                lesson_title="Eval Lesson", lesson_topic="Eval", introduction="", exposition_content="",
                active_exercises=[exercise], knowledge_assessment=[]
            ),
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        result = lesson_ai._evaluate_chat_answer(state)

        mock_load_prompt.assert_called_once_with(
            "evaluate_answer",
            question_type="exercise",
            prompt_context=ANY # Context is complex, just check it was called
        )
        mock_call_llm.assert_called_once_with("mocked_eval_prompt", validation_model=EvaluationResult)

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        # Initial history + AI feedback + AI follow-up
        assert len(new_history) == 4
        assert new_history[2]["role"] == "assistant"
        assert new_history[2]["content"] == "Spot on!" # Feedback from LLM
        assert new_history[3]["role"] == "assistant"
        assert "next exercise" in new_history[3]["content"] # Follow-up

        assert result.get("current_interaction_mode") == "chatting" # Mode reset

        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "ex_eval"
        assert response_record["question_type"] == "exercise"
        assert response_record["response"] == "4"
        assert response_record["evaluation"]["is_correct"] is True
        assert response_record["evaluation"]["score"] == 1.0
        assert "timestamp" in response_record

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing')
    def test_evaluate_chat_answer_quiz_incorrect(
        self, mock_call_llm, mock_load_prompt, MockStateGraph
    ):
        """Test evaluating an incorrect quiz answer with explanation."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_eval_prompt"
        mock_eval_result = EvaluationResult(
            score=0.0, is_correct=False, feedback="Not quite.", explanation="Python is a language."
        )
        mock_call_llm.return_value = mock_eval_result

        question = AssessmentQuestion(
            id="q_eval", type="multiple_choice", question="What is Python?",
            options={"A": "Snake", "B": "Language"}, correct_answer="B"
        )
        initial_history = [
            {"role": "assistant", "content": "Quiz: What is Python? A) Snake B) Language"},
            {"role": "user", "content": "A"},
        ]
        state: LessonState = {
            "user_id": "eval_user_quiz",
            "current_interaction_mode": "taking_quiz",
            "current_quiz_question_index": 0,
            "generated_content": GeneratedLessonContent(
                lesson_title="Eval Lesson", lesson_topic="Eval", introduction="", exposition_content="",
                active_exercises=[], knowledge_assessment=[question]
            ),
            "conversation_history": initial_history,
            "user_responses": [],
            # Other fields...
        }

        result = lesson_ai._evaluate_chat_answer(state)

        mock_load_prompt.assert_called_once()
        mock_call_llm.assert_called_once()

        assert "conversation_history" in result
        new_history = result["conversation_history"]
        # Initial history + AI feedback (including explanation)
        assert len(new_history) == 3
        assert new_history[2]["role"] == "assistant"
        assert "Not quite." in new_history[2]["content"] # Feedback
        assert "*Explanation:* Python is a language." in new_history[2]["content"] # Explanation

        assert result.get("current_interaction_mode") == "chatting" # Mode reset

        assert "user_responses" in result
        assert len(result["user_responses"]) == 1
        response_record = result["user_responses"][0]
        assert response_record["question_id"] == "q_eval"
        assert response_record["question_type"] == "assessment"
        assert response_record["response"] == "A"
        assert response_record["evaluation"]["is_correct"] is False
        assert response_record["evaluation"]["explanation"] == "Python is a language."

    def test_evaluate_chat_answer_no_user_message(self, MockStateGraph):
        """Test evaluation attempt without a preceding user message."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "assistant", "content": "Question?"}]
        state: LessonState = {
            "user_id": "eval_user_no_msg",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(active_exercises=[Exercise(id="ex", type="short_answer")], knowledge_assessment=[]), # Dummy content
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch('backend.ai.lessons.lessons_graph.logger.warning') as mock_warning:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_warning.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2 # Original + AI error message
            assert new_history[1]["role"] == "assistant"
            assert "haven't provided an answer yet" in new_history[1]["content"]
            # Mode should not change
            assert result.get("current_interaction_mode") == "doing_exercise"
            # No response should be recorded
            assert len(result.get("user_responses", [])) == 0

    def test_evaluate_chat_answer_question_not_found(self, MockStateGraph):
        """Test evaluation when the current question cannot be found."""
        lesson_ai = LessonAI()
        initial_history = [{"role": "user", "content": "My answer"}]
        state: LessonState = {
            "user_id": "eval_user_no_q",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 99, # Index out of bounds
            "generated_content": GeneratedLessonContent(active_exercises=[], knowledge_assessment=[]), # No exercises
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_error:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_error.assert_called_once()
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2 # Original + AI error message
            assert new_history[1]["role"] == "assistant"
            assert "lost track of which question" in new_history[1]["content"]
            assert result.get("current_interaction_mode") == "chatting" # Mode reset
            assert len(result.get("user_responses", [])) == 0

    @patch('backend.ai.lessons.lessons_graph.load_prompt')
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing', return_value=None)
    def test_evaluate_chat_answer_llm_failure(
        self, mock_call_llm, mock_load_prompt, MockStateGraph
    ):
        """Test evaluation when the LLM call/parsing fails."""
        lesson_ai = LessonAI()
        mock_load_prompt.return_value = "mocked_eval_prompt"

        exercise = Exercise(id="ex_eval_fail", type="short_answer", question="?", answer="!")
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_fail",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(active_exercises=[exercise], knowledge_assessment=[]),
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_log_error:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_load_prompt.assert_called_once()
            mock_call_llm.assert_called_once()
            mock_log_error.assert_called_once() # Logged the failure

            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2 # Original + AI fallback message
            assert new_history[1]["role"] == "assistant"
            assert "encountered an error while evaluating" in new_history[1]["content"]

            assert result.get("current_interaction_mode") == "chatting" # Mode reset

            assert "user_responses" in result
            assert len(result["user_responses"]) == 1
            response_record = result["user_responses"][0]
            assert response_record["question_id"] == "ex_eval_fail"
            assert response_record["response"] == "answer"
            # Check fallback evaluation data
            assert response_record["evaluation"]["is_correct"] is False
            assert response_record["evaluation"]["score"] == 0.0
            assert "encountered an error" in response_record["evaluation"]["feedback"]

    @patch('backend.ai.lessons.lessons_graph.load_prompt', side_effect=Exception("LLM Error"))
    @patch('backend.ai.lessons.lessons_graph.call_llm_with_json_parsing')
    def test_evaluate_chat_answer_llm_exception(
        self, mock_call_llm, mock_load_prompt, MockStateGraph
    ):
        """Test evaluation when an exception occurs during LLM call."""
        lesson_ai = LessonAI()

        exercise = Exercise(id="ex_eval_exc", type="short_answer", question="?", answer="!")
        initial_history = [{"role": "user", "content": "answer"}]
        state: LessonState = {
            "user_id": "eval_user_exc",
            "current_interaction_mode": "doing_exercise",
            "current_exercise_index": 0,
            "generated_content": GeneratedLessonContent(active_exercises=[exercise], knowledge_assessment=[]),
            "conversation_history": initial_history,
            "user_responses": [],
        }

        with patch('backend.ai.lessons.lessons_graph.logger.error') as mock_log_error:
            result = lesson_ai._evaluate_chat_answer(state)

            mock_load_prompt.assert_called_once() # Prompt load failed
            mock_call_llm.assert_not_called() # LLM call skipped
            mock_log_error.assert_called_once() # Logged the exception

            # Check results are same as LLM failure case (fallback applied)
            assert "conversation_history" in result
            new_history = result["conversation_history"]
            assert len(new_history) == 2
            assert "encountered an error while evaluating" in new_history[1]["content"]
            assert result.get("current_interaction_mode") == "chatting"
            assert len(result["user_responses"]) == 1
            assert result["user_responses"][0]["evaluation"]["is_correct"] is False

    # --- New tests for placeholders and process_chat_turn ---

    def test_process_user_message_placeholder(self, MockStateGraph):
        """Test the _process_user_message placeholder node."""
        lesson_ai = LessonAI()
        # This node doesn't really use the state currently
        result = lesson_ai._process_user_message({})
        assert result == {} # Placeholder returns empty dict

    def test_update_progress_placeholder(self, MockStateGraph):
        """Test the _update_progress placeholder node."""
        lesson_ai = LessonAI()
        # This node doesn't really use the state currently
        result = lesson_ai._update_progress({})
        assert result == {} # Placeholder returns empty dict

    def test_process_chat_turn_success(self, MockStateGraph):
        """Test the main process_chat_turn method."""
        # Setup mocks for __init__
        mock_workflow = MagicMock()
        MockStateGraph.return_value = mock_workflow
        mock_compiled_graph = MagicMock()
        mock_workflow.compile.return_value = mock_compiled_graph

        lesson_ai = LessonAI()

        # Mock the output of the compiled graph's invoke method
        graph_output_state_changes = {
            "conversation_history": [
                {"role": "assistant", "content": "Initial"},
                {"role": "user", "content": "Hello there"},
                {"role": "assistant", "content": "General Kenobi!"}, # Added by graph
            ],
            "current_interaction_mode": "chatting", # Assume graph ended in chatting
        }
        mock_compiled_graph.invoke.return_value = graph_output_state_changes

        # Define the state *before* the user message is added
        current_state: LessonState = {
            "lesson_topic": "Turn Topic", "lesson_title": "Turn Lesson", "user_id": "turn_user",
            "generated_content": GeneratedLessonContent(lesson_title="Turn Lesson", lesson_topic="Turn Topic", introduction="", exposition_content="", active_exercises=[], knowledge_assessment=[]),
            "conversation_history": [{"role": "assistant", "content": "Initial"}],
            "current_interaction_mode": "chatting",
            "current_exercise_index": -1, "current_quiz_question_index": -1,
            "user_responses": [], "errors": [],
        }
        user_message = "Hello there"

        final_state = lesson_ai.process_chat_turn(current_state, user_message)

        # Verify the input state passed to invoke includes the new user message
        expected_input_state_to_graph = {
            **current_state,
            "conversation_history": [
                {"role": "assistant", "content": "Initial"},
                {"role": "user", "content": "Hello there"},
            ]
        }
        mock_compiled_graph.invoke.assert_called_once_with(expected_input_state_to_graph)

        # Verify the final state merges the original state, the added user message,
        # and the changes from the graph output
        expected_final_state = {
            **current_state, # Start with original state
            **graph_output_state_changes # Apply graph changes (overwrites history, mode)
        }
        # The user message was added *before* invoke, so the graph output history is the final one
        assert final_state == expected_final_state
        assert len(final_state["conversation_history"]) == 3
        assert final_state["conversation_history"][-1]["role"] == "assistant"
        assert final_state["conversation_history"][-1]["content"] == "General Kenobi!"

    def test_process_chat_turn_no_state(self, MockStateGraph):
        """Test that process_chat_turn raises ValueError if no state is provided."""
        lesson_ai = LessonAI()
        with pytest.raises(ValueError, match="Current state must be provided"):
            lesson_ai.process_chat_turn(None, "A message") # type: ignore


    # --- End of tests ---