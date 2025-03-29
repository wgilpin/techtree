"""Defines and manages the LangGraph workflow for syllabus generation."""

# pylint: disable=broad-exception-caught,singleton-comparison

import copy
import uuid
import traceback
from datetime import datetime
from typing import Dict, Optional
from functools import partial

from langgraph.graph import StateGraph

# Project specific imports
from backend.services.sqlite_db import SQLiteDatabaseService
from .state import SyllabusState
from . import nodes
from .config import (
    MODEL as llm_model,
    TAVILY as tavily_client,
)  # Import configured clients


class SyllabusAI:
    """Orchestrates syllabus generation using a LangGraph workflow."""

    def __init__(self, db_service: SQLiteDatabaseService):
        """Initializes the SyllabusAI graph and stores dependencies."""
        self.state: Optional[SyllabusState] = None
        self.db_service = db_service
        # Store configured clients (or handle None if config failed)
        self.llm_model = llm_model
        self.tavily_client = tavily_client
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()

    def _create_workflow(self) -> StateGraph:
        """Defines the structure (nodes and edges) of the syllabus LangGraph workflow."""
        workflow = StateGraph(SyllabusState)

        # Note: The first argument (state) is passed automatically by LangGraph
        search_db_partial = partial(nodes.search_database, db_service=self.db_service)
        search_internet_partial = partial(
            nodes.search_internet, tavily_client=self.tavily_client
        )
        generate_syllabus_partial = partial(
            nodes.generate_syllabus, llm_model=self.llm_model
        )

        # Add nodes using the standalone functions from nodes.py
        workflow.add_node("search_database", search_db_partial)
        workflow.add_node("search_internet", search_internet_partial)
        workflow.add_node("generate_syllabus", generate_syllabus_partial)
        workflow.add_node("end_node", nodes.end_node)  # Use the simple end node

        # Define edges and entry point
        workflow.set_entry_point("search_database")  # Start flow by searching DB

        workflow.add_conditional_edges(
            "search_database",
            self._should_search_internet,
            {
                "search_internet": "search_internet",
                "end": "end_node",
            },  # Route to end if found
        )
        workflow.add_edge("search_internet", "generate_syllabus")
        workflow.add_edge("generate_syllabus", "end_node")  # Generation leads to end

        return workflow

    def _should_search_internet(self, state: SyllabusState) -> str:
        """Conditional Edge: Determines if web search is needed."""
        if state.get("existing_syllabus"):
            print("Conditional Edge: Existing syllabus found, ending.")
            return "end"
        else:
            print("Conditional Edge: No existing syllabus, searching internet.")
            return "search_internet"

    # --- Public Methods for Service Interaction ---

    def initialize(
        self, topic: str, knowledge_level: str, user_id: Optional[str] = None
    ) -> Dict:
        """Initializes the internal state for a new run."""
        # Use the node function directly to create the initial state dict
        self.state = nodes.initialize_state(
            None,  # Pass None for state as it's initialization
            topic=topic,
            knowledge_level=knowledge_level,
            user_id=user_id,
        )
        print(
            f"SyllabusAI initialized: Topic='{topic}', Level='{knowledge_level}', User={user_id}"
        )
        return {
            "status": "initialized",
            "topic": topic,
            "knowledge_level": knowledge_level,
            "user_id": user_id,
        }

    def get_or_create_syllabus(self) -> Dict:
        """Retrieves an existing syllabus or orchestrates the creation of a new one."""
        if not self.state:
            raise ValueError("Agent not initialized. Call initialize() first.")
        if not self.graph:
            raise RuntimeError("Graph not compiled.")
        print("Starting get_or_create_syllabus graph execution...")

        # Run the graph from the entry point ('search_database')
        final_state_updates = {}
        try:
            # Stream the execution, starting with the current state
            for step in self.graph.stream(self.state, config={"recursion_limit": 10}):
                node_name = list(step.keys())[0]
                print(f"Graph Step: {node_name}")
                # Accumulate all updates from the steps
                final_state_updates.update(step[node_name])

            # Apply accumulated updates to the internal state
            if final_state_updates:
                self.state.update(final_state_updates)

        except Exception as e:
            print(f"Error during graph execution in get_or_create_syllabus: {e}")
            traceback.print_exc()
            raise RuntimeError("Syllabus graph execution failed.") from e

        # The result is the syllabus found or generated, now stored in the updated state
        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )

        if not syllabus:
            print(
                "Error: Graph execution finished but no valid syllabus found in state."
            )
            # Attempt to provide more context if available
            if self.state.get("error_generating"):
                print("Generation fallback structure was used but might be invalid.")
            raise RuntimeError("Failed to get or create a valid syllabus.")

        print(f"Syllabus get/create finished. Result UID: {syllabus.get('uid', 'N/A')}")
        return syllabus  # Return the syllabus from the final state

    def update_syllabus(self, feedback: str) -> Dict:
        """Updates the current syllabus based on user feedback."""
        if not self.state:
            raise ValueError("Agent not initialized.")
        if not (
            self.state.get("generated_syllabus") or self.state.get("existing_syllabus")
        ):
            raise ValueError("No syllabus loaded to update.")
        if not self.llm_model:
            raise RuntimeError("LLM model not configured for updates.")
        print("Starting syllabus update based on feedback...")

        # Call the update node function directly, passing current state and feedback
        update_result = nodes.update_syllabus(self.state, feedback, self.llm_model)
        self.state.update(update_result)  # Update internal state with results

        # Return the syllabus currently in state
        # (which might be the updated one or original if update failed)
        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus:
            print("Error: Syllabus became invalid after update attempt.")
            raise RuntimeError("Syllabus became invalid after update attempt.")

        print(f"Syllabus update finished. Result UID: {syllabus.get('uid', 'N/A')}")
        return syllabus

    def save_syllabus(self) -> Dict:
        """Saves the current syllabus in the state to the database."""
        if not self.state:
            raise ValueError("Agent not initialized")
        print("Starting syllabus save process...")

        current_syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not current_syllabus:
            print("Warning: No syllabus in state to save.")
            return {"status": "skipped", "reason": "No syllabus in state"}

        # Determine if save is needed (e.g., if generated_syllabus is populated)
        needs_save = self.state.get("generated_syllabus") is not None

        if not needs_save:
            # Check if it's an existing syllabus that might have been modified outside generation
            # For now, only save if explicitly generated/updated in this session.
            print(
                "Skipping save, syllabus was likely loaded and not modified in this session."
            )
            return {
                "status": "skipped",
                "reason": "Syllabus loaded, not generated/modified",
            }

        # Call the save node function directly
        save_result = nodes.save_syllabus(self.state, self.db_service)
        # Update state with any potential changes from saving (like UID, timestamps)
        if save_result.get("syllabus_saved"):
            # Selectively update state fields returned by save_syllabus
            state_updates = {k: v for k, v in save_result.items() if k in self.state}
            self.state.update(state_updates)
            print(
                f"Syllabus save finished. Saved UID: {save_result.get('saved_uid', 'N/A')}"
            )
            return {"status": "saved", "uid": save_result.get("saved_uid")}
        else:
            print("Syllabus save failed.")
            return {"status": "failed"}

    def get_syllabus(self) -> Dict:
        """Returns the current syllabus dictionary held in the agent's state."""
        if not self.state:
            raise ValueError("Agent not initialized")
        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus:
            raise ValueError("No syllabus loaded in the current state.")
        return syllabus

    def clone_syllabus_for_user(self, user_id: str) -> Dict:
        """Clones the current syllabus in the state for a specific user."""
        if not self.state:
            raise ValueError("Agent not initialized")

        syllabus_to_clone = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus_to_clone:
            raise ValueError("No syllabus to clone")

        print(
            f"Cloning syllabus for user {user_id}. Source UID: {syllabus_to_clone.get('uid')}"
        )

        try:
            syllabus_dict = dict(syllabus_to_clone)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid syllabus format for cloning: {type(syllabus_to_clone)}"
            ) from e

        # Create a deep copy for the user version
        user_syllabus = copy.deepcopy(syllabus_dict)
        now = datetime.now().isoformat()
        new_uid = str(uuid.uuid4())

        # Update the copy with user-specific information
        user_syllabus["uid"] = new_uid
        user_syllabus["user_id"] = user_id
        user_syllabus["is_master"] = False
        user_syllabus["created_at"] = now
        user_syllabus["updated_at"] = now
        user_syllabus["user_entered_topic"] = self.state.get(
            "user_entered_topic", user_syllabus.get("topic")
        )

        # Determine the parent UID (should be the UID of the master version)
        # Ensure we look up the master based on the *cloned* topic/level
        master_syllabus = self.db_service.get_syllabus(
            user_syllabus["topic"],
            user_syllabus["level"],
            user_id=None,  # Look for master
        )
        parent_uid = master_syllabus.get("uid") if master_syllabus else syllabus_to_clone.get("uid")
        user_syllabus["parent_uid"] = parent_uid
        print(f"Setting parent UID for clone {new_uid} to {parent_uid}")

        # Separate content for saving
        content_to_save = {
            k: user_syllabus.get(k)
            for k in ["topic", "level", "duration", "learning_objectives", "modules"]
        }

        try:
            # Save the new user-specific syllabus using the db_service method
            saved_id = self.db_service.save_syllabus(
                topic=user_syllabus["topic"],
                level=user_syllabus["level"],
                content=content_to_save,
                user_id=user_id,
                is_master=False,
                parent_uid=parent_uid,
                uid=new_uid,
                created_at=now,
                updated_at=now,
                user_entered_topic=user_syllabus["user_entered_topic"],
            )

            if not saved_id:
                raise RuntimeError("db_service.save_syllabus failed for the clone.")

            print(
                f"Cloned syllabus UID {new_uid} saved for user {user_id} (DB ID: {saved_id})."
            )

            # Update the agent's state to reflect the newly cloned syllabus
            self.state["generated_syllabus"] = (
                user_syllabus  # Now working with the user copy
            )
            self.state["existing_syllabus"] = None  # Clear existing master from state
            self.state["uid"] = new_uid
            self.state["user_id"] = user_id  # Ensure state reflects the user
            self.state["is_master"] = False
            self.state["parent_uid"] = parent_uid
            self.state["created_at"] = now
            self.state["updated_at"] = now

            # Add the database primary key if needed, though UID is primary identifier
            user_syllabus["syllabus_id"] = saved_id

            return user_syllabus
        except Exception as e:
            print(f"Error cloning syllabus UID {new_uid} for user {user_id}: {e}")
            traceback.print_exc()
            raise RuntimeError("Failed to save cloned syllabus.") from e

    def delete_syllabus(self) -> Dict:
        """Deletes the syllabus corresponding to the current state from the database."""
        if not self.state:
            raise ValueError("Agent not initialized")

        topic = self.state.get("topic")
        knowledge_level = self.state.get("user_knowledge_level")
        user_id = self.state.get("user_id")  # Use state's user_id

        if not topic or not knowledge_level:
            raise ValueError("State is missing topic or knowledge level for deletion.")

        print(
            f"Attempting deletion: Topic='{topic}', Level='{knowledge_level}', User={user_id}"
        )
        try:
            deleted = self.db_service.delete_syllabus(topic, knowledge_level, user_id)
            if deleted:
                print("Syllabus deleted successfully from DB.")
                # Clear syllabus from state after deletion
                self.state["existing_syllabus"] = None
                self.state["generated_syllabus"] = None
                self.state["uid"] = None
                self.state["parent_uid"] = None
                self.state["created_at"] = None
                self.state["updated_at"] = None
                # Keep topic, level, user_id etc. as they defined what was deleted
                return {"syllabus_deleted": True}
            else:
                print("Syllabus not found in DB for deletion.")
                return {"syllabus_deleted": False, "reason": "Not found"}
        except Exception as e:
            print(f"Error deleting syllabus from DB: {e}")
            traceback.print_exc()
            return {"syllabus_deleted": False, "error": str(e)}
