"""Langgraph code for the lessons AI"""

# pylint: disable=broad-exception-caught,singleton-comparison

from typing import Any, Dict, List, Optional # Added Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph


from backend.logger import logger  # Ensure logger is available

# Import LessonState and other models from backend.models
from backend.models import    LessonState

# Import node functions
from backend.ai.lessons import nodes

# Load environment variables
load_dotenv()


# Helper function for routing based on state
def _route_message_logic(state: LessonState) -> str:
    """Determines the next node based on the current interaction mode."""
    mode = state.get("current_interaction_mode", "chatting")
    logger.debug(f"Routing based on interaction mode: {mode}")
    if mode == "request_exercise":
        return "generate_new_exercise"
    if mode == "request_assessment":
        return "generate_new_assessment"
    if mode == "submit_answer":
        return "evaluate_answer"
    # Default to chatting for 'chatting' or unknown modes
    return "generate_chat_response"


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
        workflow.add_node("classify_intent", nodes.classify_intent) # Corrected node name
        workflow.add_node("generate_chat_response", nodes.generate_chat_response)
        # Add new generation nodes
        workflow.add_node("generate_new_exercise", nodes.generate_new_exercise)
        workflow.add_node(
            "generate_new_assessment", nodes.generate_new_assessment) # Corrected node name
        workflow.add_node("evaluate_answer", nodes.evaluate_answer) # Corrected node name
        # Removed "update_progress" node as its implementation is missing

        # Entry point for a chat turn
        workflow.set_entry_point("classify_intent") # Start by classifying intent

        # Conditional routing after classifying intent
        workflow.add_conditional_edges(
            "classify_intent",
            _route_message_logic,  # Use the local routing helper function
            {
                # Keys match return values of _route_message_logic
                "generate_chat_response": "generate_chat_response",
                "generate_new_exercise": "generate_new_exercise",
                "generate_new_assessment": "generate_new_assessment",
                "evaluate_answer": "evaluate_answer",
            },
        )

        # Edges leading back to the end after processing
        # State saving (like update_progress) should happen outside the graph run
        workflow.add_edge("generate_chat_response", "__end__")
        workflow.add_edge("generate_new_exercise", "__end__")
        workflow.add_edge("generate_new_assessment", "__end__")
        workflow.add_edge("evaluate_answer", "__end__")

        # Removed edges related to "update_progress"

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

        # Ensure input_state matches LessonState structure
        input_state: LessonState = {
            **current_state, # type: ignore
            "conversation_history": updated_history,
        }

        # Invoke the chat graph
        # Assumes self.chat_graph was compiled in __init__
        output_state: Any = self.chat_graph.invoke(input_state)

        # Merge output state changes back
        # Ensure the final state structure matches LessonState
        # Note: LangGraph output might only contain changed fields.
        final_state: LessonState = {**input_state, **output_state} # type: ignore
        return final_state

    # --- Method to Start Chat (using imported node function) ---
    def start_chat(self, initial_state: LessonState) -> LessonState:
        """
        Generates the initial welcome message and sets up the state for conversation.
        Assumes initial_state contains necessary context (topic, title, user_id, etc.)
        but has an empty conversation_history.
        """
        # Logic to generate initial message needs refinement.
        # For now, just set a default welcome message and mode.
        # Removed call to non-existent nodes.start_conversation
        logger.info("Starting chat, setting initial state.")
        try:
            # Option 1: Set a fixed welcome message
            welcome_message: Dict[str, str] = {
                 "role": "assistant",
                 "content": "Welcome to your lesson! Feel free to ask questions or tell me when you're ready for an exercise.",
            }
            # Option 2: Call generate_chat_response with a specific prompt (more complex)
            # initial_prompt_state = {**initial_state, "conversation_history": [{"role": "system", "content": "Start the lesson."}]}
            # welcome_state = nodes.generate_chat_response(initial_prompt_state)
            # welcome_message = welcome_state["conversation_history"][-1] # Get the generated message

            return {
                **initial_state, # type: ignore
                "conversation_history": [welcome_message],
                "current_interaction_mode": "chatting",
            }
        except Exception as e:
            # Log error, return state with a fallback message
            logger.error(f"Error during start_chat: {e}", exc_info=True)
            fallback_message: Dict[str, str] = {
                "role": "assistant",
                "content": "Welcome! Ready to start the lesson?",
            }
            # Ensure the returned state matches LessonState structure
            return {
                **initial_state, # type: ignore
                "conversation_history": [fallback_message],
                "current_interaction_mode": "chatting",
            }
