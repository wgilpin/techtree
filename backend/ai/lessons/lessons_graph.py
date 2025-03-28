"""Langgraph code for the lessons AI"""

# pylint: disable=broad-exception-caught,singleton-comparison

from typing import Any, Dict, List  # Added Union

from dotenv import load_dotenv
from langgraph.graph import StateGraph


from backend.logger import logger  # Ensure logger is available

# Import LessonState and other models from backend.models
from backend.models import    LessonState

# Import node functions
from backend.ai.lessons import nodes

# Load environment variables
load_dotenv()


class LessonAI:
    """Encapsulates the Tech Tree lesson langgraph app."""

    chat_workflow: StateGraph  # Add type hint for instance variable
    chat_graph: Any  # Compiled graph type might be complex, use Any for now

    def __init__(self) -> None:
        """Initialize the LessonAI."""
        # Compile the chat turn workflow
        self.chat_workflow = self._create_chat_workflow()
        self.chat_graph = self.chat_workflow.compile()

    # --- Node methods removed, logic moved to backend.ai.lessons.nodes ---

    # --- Modified Workflow Creation ---
    def _create_chat_workflow(self) -> StateGraph:
        """Create the langgraph workflow for a single chat turn."""
        workflow = StateGraph(LessonState)

        # Add nodes for the chat turn using functions from nodes.py
        workflow.add_node("process_user_message", nodes.process_user_message)
        workflow.add_node("generate_chat_response", nodes.generate_chat_response)
        workflow.add_node("present_exercise", nodes.present_exercise)
        workflow.add_node("present_quiz_question", nodes.present_quiz_question)
        workflow.add_node("evaluate_chat_answer", nodes.evaluate_chat_answer)
        workflow.add_node(
            "update_progress", nodes.update_progress
        )  # Node to potentially save state

        # Entry point for a chat turn
        workflow.set_entry_point("process_user_message")

        # Conditional routing after processing user message using function from nodes.py
        workflow.add_conditional_edges(
            "process_user_message",
            nodes.route_message_logic,  # Use the imported routing function
            {
                "generate_chat_response": "generate_chat_response",
                "present_exercise": "present_exercise",
                "present_quiz_question": "present_quiz_question",
                # Route directly if mode requires evaluation
                "evaluate_chat_answer": "evaluate_chat_answer",
            },
        )

        # Edges leading to update_progress (and potentially loop or end)
        workflow.add_edge("generate_chat_response", "update_progress")
        workflow.add_edge("present_exercise", "update_progress")
        workflow.add_edge("present_quiz_question", "update_progress")
        workflow.add_edge("evaluate_chat_answer", "update_progress")

        # End the turn after updating progress
        workflow.add_edge("update_progress", "__end__")  # Use built-in end

        return workflow

    # --- Method to Handle Chat Turns (no changes needed here) ---
    def process_chat_turn(
        self, current_state: LessonState, user_message: str
    ) -> LessonState:
        """Processes one turn of the conversation."""
        if not current_state:
            raise ValueError("Current state must be provided for a chat turn.")

        # Add user message to history before invoking graph
        updated_history: List[Dict[str, str]] = current_state.get(
            "conversation_history", []
        ) + [{"role": "user", "content": user_message}]
        # type: ignore
        input_state: LessonState = {
            **current_state,
            "conversation_history": updated_history,
        }

        # Invoke the chat graph
        # Assumes self.chat_graph was compiled in __init__
        output_state: Any = self.chat_graph.invoke(input_state)

        # Merge output state changes back
        final_state: LessonState = {**input_state, **output_state}  # type: ignore
        return final_state

    # --- Method to Start Chat (using imported node function) ---
    def start_chat(self, initial_state: LessonState) -> LessonState:
        """
        Generates the initial welcome message and sets up the state for conversation.
        Assumes initial_state contains necessary context (topic, title, user_id, etc.)
        but has an empty conversation_history.
        """
        # Directly call the logic from the start_conversation node function
        # This avoids running the full graph just for the first message
        try:
            start_result: Dict[str, Any] = nodes.start_conversation(initial_state)
            # Merge the result (history, mode) back into the initial state
            return {**initial_state, **start_result}  # type: ignore
        except Exception as e:
            # Log error, return state with a fallback message
            logger.error(f"Error during start_chat: {e}", exc_info=True)
            fallback_message: Dict[str, str] = {
                "role": "assistant",
                "content": "Welcome! Ready to start the lesson?",
            }
            # Ensure the returned state matches LessonState structure
            return {
                **initial_state,
                "conversation_history": [fallback_message],
                "current_interaction_mode": "chatting",
            }  # type: ignore
