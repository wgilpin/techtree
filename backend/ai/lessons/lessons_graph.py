"""Langgraph code for the lessons AI"""

# pylint: disable=broad-exception-caught,singleton-comparison

from typing import Any, Dict, List, cast, Tuple, Optional # Added Tuple, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END # Added END import


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
        workflow.add_node("classify_intent", nodes.classify_intent)
        workflow.add_node("generate_chat_response", nodes.generate_chat_response)
        workflow.add_node("generate_new_exercise", nodes.generate_new_exercise)
        workflow.add_node("generate_new_assessment", nodes.generate_new_assessment)
        workflow.add_node("evaluate_answer", nodes.evaluate_answer)

        # Entry point for a chat turn
        workflow.set_entry_point("classify_intent")

        # Conditional routing after classifying intent
        workflow.add_conditional_edges(
            "classify_intent",
            _route_message_logic,
            {
                "generate_chat_response": "generate_chat_response",
                "generate_new_exercise": "generate_new_exercise",
                "generate_new_assessment": "generate_new_assessment",
                "evaluate_answer": "evaluate_answer",
            },
        )

        # Edges leading back to the end after processing
        workflow.add_edge("generate_chat_response", END) # Use END constant
        workflow.add_edge("generate_new_exercise", END) # Use END constant
        workflow.add_edge("generate_new_assessment", END) # Use END constant
        workflow.add_edge("evaluate_answer", END) # Use END constant

        return workflow

    # --- Method to Handle Chat Turns (no changes needed here) ---
    def process_chat_turn(
        self, current_state: LessonState, user_message: str, history: List[Dict[str, Any]] # Added history
    ) -> Tuple[LessonState, Optional[List[Dict[str, Any]]]]: # Return state and new messages
        """Processes one turn of the conversation."""
        if not current_state:
            raise ValueError("Current state must be provided for a chat turn.")

        # History is now passed in, user message is saved by service layer.
        # We need to pass history to the nodes via the state during invocation.
        # Note: This assumes nodes are modified to accept history via state['history_context']
        #       and that LessonState is temporarily updated to include this key.
        # TODO: Define 'history_context' key in LessonState or find alternative LangGraph context passing. # pylint: disable=fixme

        # Prepare input state for the graph, adding history temporarily
        input_state_dict: Dict[str, Any] = cast(Dict[str, Any], {
            **current_state,
            "history_context": history, # Add history under a temporary key
            # Ensure user_message is available if nodes need it directly (e.g., classify_intent)
            # Although classify_intent was modified to use history[-1]
            "last_user_message": user_message # Add last user message explicitly if needed
        })

        # Invoke the chat graph
        # The graph will internally call nodes which now expect 'history_context' in the state dict
        output_state_changes: Any = self.chat_graph.invoke(input_state_dict)

        # Extract potential new messages returned by nodes (if nodes are modified to do so)
        # This part is speculative and depends on how nodes are modified.
        # Let's assume nodes add a 'new_assistant_messages' key to the output state changes.
        new_assistant_messages: Optional[List[Dict[str, Any]]] = \
            output_state_changes.pop('new_assistant_messages', None)

        # Merge output state changes back into the original state (excluding temp history)
        final_state_dict = {**current_state, **output_state_changes}

        # Remove the temporary history key if it exists
        final_state_dict.pop('history_context', None)
        final_state_dict.pop('last_user_message', None) # Clean up temporary keys

        # Cast merged dict back to LessonState
        final_state: LessonState = cast(LessonState, final_state_dict)

        # Return the final state and any new messages extracted
        return final_state, new_assistant_messages

    # --- Method to Start Chat (using imported node function) ---
    def start_chat(self, initial_state: LessonState) -> LessonState:
        """
        Generates the initial welcome message and sets up the state for conversation.
        Assumes initial_state contains necessary context (topic, title, user_id, etc.)
        but has an empty conversation_history.
        """
        logger.info("Starting chat, setting initial state.")
        try:
            welcome_message: Dict[str, str] = {
                 "role": "assistant",
                 "content": "Welcome to your lesson! Feel free to ask questions "
                            "or tell me when you're ready for an exercise.",
            }

            # Cast merged dict to LessonState
            return cast(LessonState, {
                **initial_state,
                "conversation_history": [welcome_message],
                "current_interaction_mode": "chatting",
            })
        except Exception as e:
            logger.error(f"Error during start_chat: {e}", exc_info=True)
            fallback_message: Dict[str, str] = {
                "role": "assistant",
                "content": "Welcome! Ready to start the lesson?",
            }
            # Cast merged dict to LessonState
            return cast(LessonState, {
                **initial_state,
                "conversation_history": [fallback_message],
                "current_interaction_mode": "chatting",
            })
