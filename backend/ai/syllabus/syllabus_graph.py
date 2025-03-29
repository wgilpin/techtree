"""
LangGraph implementation for generating and managing syllabi.

This module defines the state graph (`SyllabusState`) and the `SyllabusAI`
class which orchestrates the process of syllabus creation. The process involves:
1. Initializing with topic and user level.
2. Searching the database for existing syllabi (user-specific or master).
3. If not found, searching the internet (using Tavily) for relevant context.
4. Generating a new syllabus using an LLM (Gemini) based on the context.
5. Optionally updating the syllabus based on user feedback.
6. Saving the final syllabus (master or user-specific clone) to the database.
"""

# pylint: disable=broad-exception-caught,singleton-comparison

import copy
import json
import os
import random
import re
import time
import uuid
import traceback

from datetime import datetime
from typing import Dict, List, Optional, TypedDict

import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from langgraph.graph import StateGraph
from requests import RequestException
from tavily import TavilyClient

# from tinydb import TinyDB, Query
from backend.services.sqlite_db import \
    SQLiteDatabaseService  # Keep this import for type hinting

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(os.environ["GEMINI_MODEL"])

# Configure Tavily API
tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Import the shared database service instance - REMOVED to break circular import
# from backend.dependencies import db_service as db # Import and alias as 'db' for minimal changes

# db = TinyDB("syllabus_db.json") # Keep old comments if needed
# syllabi_table = db.table("syllabi")
# Direct instantiation removed


def call_with_retry(func, *args, max_retries=5, initial_delay=1, **kwargs):
    """
    Calls a function with exponential backoff retry logic, specifically for ResourceExhausted errors.

    Args:
        func: The function to call.
        *args: Positional arguments for the function.
        max_retries: Maximum number of retries.
        initial_delay: Initial delay in seconds before the first retry.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function call.

    Raises:
        ResourceExhausted: If the function fails after max_retries.
    """
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                print(f"Max retries ({max_retries}) exceeded for {func.__name__}.")
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            print(
                f"ResourceExhausted error. Retrying {func.__name__} in {delay:.2f} seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(delay)
        except Exception as e:
            # Catch other potential exceptions during the call
            print(f"Non-retryable error during {func.__name__} call: {e}")
            raise  # Re-raise other exceptions immediately


# --- Define State ---
class SyllabusState(TypedDict):
    """TypedDict representing the state of the syllabus generation graph."""

    topic: str
    user_knowledge_level: (
        str  # 'beginner', 'early learner', 'good knowledge', or 'advanced'
    )
    existing_syllabus: Optional[Dict]  # Syllabus loaded from DB
    search_results: List[str]  # Content snippets from web search
    generated_syllabus: Optional[
        Dict
    ]  # Syllabus generated/updated by LLM in current run
    user_feedback: Optional[str]  # User feedback for syllabus revision
    syllabus_accepted: (
        bool  # Flag indicating user acceptance (not currently used by graph logic)
    )
    iteration_count: int  # Number of update iterations based on feedback
    user_id: Optional[str]  # ID of the user requesting the syllabus
    uid: Optional[str]  # Unique ID of the syllabus being worked on/generated
    is_master: Optional[bool]  # Whether the syllabus is a master template
    parent_uid: Optional[str]  # UID of the master syllabus if this is a user copy
    created_at: Optional[str]  # ISO format timestamp
    updated_at: Optional[str]  # ISO format timestamp
    user_entered_topic: Optional[str]  # The original topic string entered by the user


class SyllabusAI:
    """
    Encapsulates the LangGraph application for syllabus generation and management.

    This class defines the nodes and edges of a state graph that handles
    searching for, generating, updating, and saving syllabi based on user
    input (topic, level, feedback) and external information (web search).
    It interacts with the database via an injected `SQLiteDatabaseService`.

    Attributes:
        db_service: An instance of SQLiteDatabaseService.
        workflow: The configured LangGraph StateGraph.
        graph: The compiled LangGraph executable graph.
        state: The current internal state (SyllabusState) of the agent during a run.
    """

    def __init__(self, db_service: SQLiteDatabaseService):  # Accept db_service here
        """
        Initializes the SyllabusAI graph and stores the database service.

        Args:
            db_service: An instance of SQLiteDatabaseService for database interactions.
        """
        self.state: Optional[SyllabusState] = None
        self.db_service = db_service  # Store db_service instance
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()

    def _create_workflow(self) -> StateGraph:
        """
        Defines the structure (nodes and edges) of the syllabus LangGraph workflow.

        Nodes:
            - initialize: Sets up the initial state.
            - search_database: Looks for existing syllabi.
            - search_internet: Performs web search if needed.
            - generate_syllabus: Generates syllabus using LLM.
            - update_syllabus: Updates syllabus based on feedback using LLM.
            - save_syllabus: Persists the syllabus to the database.
            - end: Terminal node.

        Edges:
            - initialize -> search_database
            - search_database -> (conditional)
                - If existing found -> end
                - If not found -> search_internet
            - search_internet -> generate_syllabus
            - generate_syllabus -> end
            - update_syllabus -> end
            - save_syllabus -> end

        Returns:
            The configured (but not compiled) StateGraph object.
        """
        workflow = StateGraph(SyllabusState)

        # Add nodes
        workflow.add_node("initialize", self._initialize)
        workflow.add_node("search_database", self._search_database)
        workflow.add_node("search_internet", self._search_internet)
        workflow.add_node("generate_syllabus", self._generate_syllabus)
        workflow.add_node("update_syllabus", self._update_syllabus)
        workflow.add_node("save_syllabus", self._save_syllabus)
        workflow.add_node("end", self._end)

        # Add edges
        workflow.add_edge("initialize", "search_database")
        workflow.add_conditional_edges(
            "search_database",
            self._should_search_internet,
            {"search_internet": "search_internet", "end": "end"},
        )
        workflow.add_edge("search_internet", "generate_syllabus")
        workflow.add_edge(
            "generate_syllabus", "end"
        )  # Generation leads to end, saving is separate
        workflow.add_edge(
            "update_syllabus", "end"
        )  # Updating leads to end, saving is separate
        workflow.add_edge("save_syllabus", "end")  # Saving leads to end

        workflow.set_entry_point("initialize")
        return workflow

    def _initialize(
        self,
        _: Optional[SyllabusState] = None,
        topic: str = "",
        knowledge_level: str = "beginner",
        user_id: Optional[str] = None,  # New parameter
    ) -> Dict:
        """
        Graph Node: Initializes the graph state with topic, knowledge level, and user ID.

        Args:
            _: The current state (ignored during initialization).
            topic: The syllabus topic entered by the user.
            knowledge_level: The user's self-assessed knowledge level.
            user_id: The optional ID of the user requesting the syllabus.

        Returns:
            A dictionary representing the initial state fields to be updated.

        Raises:
            ValueError: If the topic is empty.
        """
        if not topic:
            raise ValueError("Topic is required")

        # Validate knowledge level
        valid_levels = ["beginner", "early learner", "good knowledge", "advanced"]
        if knowledge_level not in valid_levels:
            print(
                f"Warning: Invalid knowledge level '{knowledge_level}'. Defaulting to 'beginner'."
            )
            knowledge_level = "beginner"  # Default to beginner if invalid

        return {
            "topic": topic,
            "user_knowledge_level": knowledge_level,
            "existing_syllabus": None,
            "search_results": [],
            "generated_syllabus": None,
            "user_feedback": None,
            "syllabus_accepted": False,
            "iteration_count": 0,
            "user_entered_topic": topic,  # Store original topic separately
            "user_id": user_id,
            # Other state fields default to None/initial values
        }

    def _search_database(self, state: SyllabusState) -> Dict:
        """
        Graph Node: Searches the database for an existing syllabus matching the criteria.

        Prioritizes finding a user-specific version if a user ID is present,
        otherwise looks for a master version based on topic and level.

        Args:
            state: The current graph state.

        Returns:
            A dictionary containing `existing_syllabus` (as dict) if found, otherwise empty.
        """
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        user_id = state.get("user_id")
        print(
            f"Searching DB for syllabus: Topic='{topic}', Level='{knowledge_level}', User={user_id}"
        )

        found_syllabus = self.db_service.get_syllabus(topic, knowledge_level, user_id)

        if found_syllabus:
            print(f"Found existing syllabus in DB. UID: {found_syllabus.get('uid')}")
            return {"existing_syllabus": found_syllabus}
        else:
            print("No matching syllabus found in DB.")
            return {}

    def _should_search_internet(self, state: SyllabusState) -> str:
        """
        Conditional Edge Logic: Determines the next step after database search.

        Args:
            state: The current graph state.

        Returns:
            'end' if an existing syllabus was found, 'search_internet' otherwise.
        """
        if state.get("existing_syllabus"):
            print("Conditional Edge: Existing syllabus found, proceeding to 'end'.")
            return "end"
        else:
            print(
                "Conditional Edge: No existing syllabus, proceeding to 'search_internet'."
            )
            return "search_internet"

    def _search_internet(self, state: SyllabusState) -> Dict:
        """
        Graph Node: Performs a web search using Tavily to gather context for syllabus generation.

        Args:
            state: The current graph state.

        Returns:
            A dictionary containing the `search_results` list (strings of content).
        """
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        print(
            f"Searching internet for context: Topic='{topic}', Level='{knowledge_level}'"
        )

        # Use Tavily to search for information
        search_results = []
        try:
            # Search Wikipedia and educational domains
            wiki_query = f"{topic} syllabus curriculum outline learning objectives"
            print(f"Tavily Query (wiki/edu): {wiki_query}")
            wiki_search = tavily.search(
                query=wiki_query,
                search_depth="advanced",
                include_domains=["en.wikipedia.org", "edu"],
                max_results=2,
            )
            wiki_content = [
                r.get("content", "")
                for r in wiki_search.get("results", [])
                if r.get("content")
            ]
            search_results.extend(wiki_content)
            print(f"Found {len(wiki_content)} results from wiki/edu.")
        except RequestException as e:
            print(f"Tavily error searching wiki/edu for {topic}: {e}")
        except Exception as e:  # Catch other potential Tavily errors
            print(f"Unexpected error during Tavily wiki/edu search for {topic}: {e}")

        try:
            # Search other sources
            general_query = (
                f"{topic} course syllabus curriculum for {knowledge_level} students"
            )
            print(f"Tavily Query (general): {general_query}")
            general_search = tavily.search(
                query=general_query,
                search_depth="advanced",  # Basic might be sufficient?
                max_results=3,
            )
            general_content = [
                r.get("content", "")
                for r in general_search.get("results", [])
                if r.get("content")
            ]
            search_results.extend(general_content)
            print(f"Found {len(general_content)} results from general search.")
        except RequestException as e:
            print(f"Tavily error during general search for {topic}: {e}")
            search_results.append(f"Error during general web search: {str(e)}")
        except Exception as e:
            print(f"Unexpected error during Tavily general search for {topic}: {e}")
            search_results.append(
                f"Unexpected error during general web search: {str(e)}"
            )

        print(f"Total search results gathered: {len(search_results)}")
        return {"search_results": search_results}

    def _generate_syllabus(self, state: SyllabusState) -> Dict:
        """
        Graph Node: Generates a new syllabus using the LLM (Gemini) based on search results.

        Args:
            state: The current graph state containing topic, level, and search results.

        Returns:
            A dictionary containing the `generated_syllabus` dictionary, or a
            basic fallback structure if generation or parsing fails.
        """
        print("DEBUG:   Generating syllabus with AI")
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        search_results = state["search_results"]

        # Combine search results into a single context
        search_context = "\n\n---\n\n".join(
            [
                f"Source {i+1}:\n{result}"
                for i, result in enumerate(search_results)
                if result
            ]
        )
        if not search_context:
            search_context = (
                "No specific search results found. Generate based on general knowledge."
            )
        print(f"Context length for LLM: {len(search_context)} chars")

        # Construct the prompt for Gemini
        prompt = f"""
        You are an expert curriculum designer creating a
        comprehensive syllabus for the topic: {topic}.

        The user's knowledge level is: {knowledge_level}

        Use the following information from internet searches to create
        an accurate and up-to-date syllabus:

        {search_context}

        Create a syllabus with the following structure:
        1. Topic name (should accurately reflect '{topic}')
        2. Level (must be one of: 'beginner', 'early learner', 'good knowledge', 'advanced', appropriate for '{knowledge_level}')
        3. Duration (e.g., "4 weeks", "6 sessions")
        4. 3-5 Learning objectives (clear, measurable outcomes starting with action verbs)
        5. Modules (organized logically, e.g., by week or unit, minimum 2 modules)
        6. Lessons within each module (clear titles, minimum 3 lessons per module)

        Tailor the syllabus content and depth to the user's knowledge level:
        - For 'beginner': Focus on foundational concepts and gentle introduction. Avoid jargon where possible or explain it clearly.
        - For 'early learner': Include basic concepts but move more quickly to intermediate topics. Introduce core terminology.
        - For 'good knowledge': Focus on intermediate to advanced topics, assuming basic knowledge. Use standard terminology.
        - For 'advanced': Focus on advanced topics, cutting-edge developments, and specialized areas. Use precise terminology.

        For theoretical topics (like astronomy, physics, ethics, etc.),
            focus learning objectives on understanding, analysis, and theoretical applications
            rather than suggesting direct practical manipulation of objects or phenomena
            that cannot be directly accessed or manipulated.

        Format your response ONLY as a valid JSON object with the following structure:
        {{
          "topic": "Topic Name",
          "level": "Level",
          "duration": "Duration",
          "learning_objectives": ["Objective 1", "Objective 2", ...],
          "modules": [
            {{
              "week": 1, // or "unit": 1
              "title": "Module Title",
              "lessons": [
                {{ "title": "Lesson 1 Title" }},
                {{ "title": "Lesson 2 Title" }},
                ...
              ]
            }},
            ...
          ]
        }}

        Ensure the syllabus is comprehensive, well-structured, and follows a
        logical progression appropriate for the user's knowledge level.
        The JSON output must be valid and complete. Do not include any text before or after the JSON object.
        """

        try:
            print("Sending generation request to LLM...")
            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text
            print("DEBUG: LLM response received.")
        except Exception as e:
            print(f"LLM call failed during syllabus generation: {e}")
            response_text = ""  # Ensure response_text is defined

        # Extract JSON from response
        json_str = None
        try:
            # Attempt to find JSON block, allowing for potential markdown fences
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
                print("Extracted JSON from markdown block.")
            else:
                # If no markdown fences, assume the whole text might be JSON
                json_str = response_text.strip()
                # Basic check if it looks like JSON
                if not (json_str.startswith("{") and json_str.endswith("}")):
                    raise ValueError("Response does not appear to be JSON.")
                print("Assuming entire response is JSON.")

            # Basic cleaning
            json_str = re.sub(r"\\n", "", json_str)  # Remove escaped newlines
            json_str = re.sub(
                r"\\(?![\"\\/bfnrtu])", "", json_str
            )  # Remove unnecessary backslashes

            syllabus = json.loads(json_str)
            print("Successfully parsed JSON.")

            # Basic validation
            if not all(
                key in syllabus
                for key in [
                    "topic",
                    "level",
                    "duration",
                    "learning_objectives",
                    "modules",
                ]
            ):
                raise ValueError("Generated JSON missing required keys.")
            if not isinstance(syllabus["modules"], list) or not syllabus["modules"]:
                raise ValueError("Generated JSON 'modules' must be a non-empty list.")
            for i, module in enumerate(syllabus["modules"]):
                if not all(key in module for key in ["title", "lessons"]):
                    raise ValueError(
                        f"Generated JSON module {i} missing 'title' or 'lessons'."
                    )
                if not isinstance(module["lessons"], list) or not module["lessons"]:
                    raise ValueError(
                        f"Generated JSON module {i} 'lessons' must be a non-empty list."
                    )
                for j, lesson in enumerate(module["lessons"]):
                    if "title" not in lesson or not lesson["title"]:
                        raise ValueError(
                            f"Generated JSON lesson {j} in module {i} missing 'title'."
                        )
            print("Generated JSON passed basic validation.")
            return {"generated_syllabus": syllabus}

        except (json.JSONDecodeError, ValueError, Exception) as e:
            print(f"Failed to parse or validate JSON from response: {e}")
            print(f"Response text was: {response_text[:500]}...")
            # Fallback to a basic structure
            print("Using fallback syllabus structure.")
            return {
                "generated_syllabus": {
                    "topic": topic,
                    "level": knowledge_level.capitalize(),
                    "duration": "4 weeks (estimated)",
                    "learning_objectives": [
                        f"Understand basic concepts of {topic}.",
                        "Identify key components or principles.",
                    ],
                    "modules": [
                        {
                            "unit": 1,
                            "title": f"Introduction to {topic}",
                            "lessons": [
                                {"title": "What is " + topic + "?"},
                                {"title": "Core Terminology"},
                                {"title": "Real-world Examples"},
                            ],
                        },
                        {
                            "unit": 2,
                            "title": f"Fundamental Principles of {topic}",
                            "lessons": [
                                {"title": "Principle A"},
                                {"title": "Principle B"},
                                {"title": "How Principles Interact"},
                            ],
                        },
                    ],
                    "error_generating": True,  # Flag indicating fallback
                }
            }

    def _update_syllabus(self, state: SyllabusState, feedback: str) -> Dict:
        """
        Graph Node: Updates the current syllabus based on user feedback using the LLM.

        Args:
            state: The current graph state containing the syllabus to update.
            feedback: The user's feedback text.

        Returns:
            A dictionary containing the updated `generated_syllabus`, feedback,
            and incremented iteration count. Returns original syllabus if update fails.
        """
        print(
            f"Updating syllabus based on feedback (Iteration {state.get('iteration_count', 0) + 1})"
        )
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        syllabus = state["generated_syllabus"] or state["existing_syllabus"]
        if not syllabus:
            print("Error: Cannot update syllabus as none exists in state.")
            return {
                "iteration_count": state.get("iteration_count", 0) + 1
            }  # Increment count even on error

        # Construct the prompt for Gemini
        prompt = f"""
        You are an expert curriculum designer updating a syllabus for the topic: {topic}.

        The user's knowledge level is: {knowledge_level}

        Here is the current syllabus:
        {json.dumps(syllabus, indent=2)}

        The user has provided the following feedback:
        {feedback}

        Update the syllabus JSON object to address the user's feedback while ensuring it remains
        appropriate for their knowledge level ({knowledge_level}). Maintain the exact same JSON structure as the input.
        Ensure the 'level' field remains one of: 'beginner', 'early learner', 'good knowledge', 'advanced'.
        Ensure 'modules' is a list of objects, each with 'title' and a non-empty list of 'lessons' (each lesson having a 'title').

        Format your response ONLY as the updated, valid JSON object. Do not include any text before or after the JSON object.
        """

        try:
            print("Sending update request to LLM...")
            response = call_with_retry(model.generate_content, prompt)
            response_text = response.text
            print("DEBUG: LLM update response received.")
        except Exception as e:
            print(f"LLM call failed during syllabus update: {e}")
            response_text = ""

        # Extract JSON from response
        json_str = None
        try:
            # Attempt to find JSON block, allowing for potential markdown fences
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
                print("Extracted updated JSON from markdown block.")
            else:
                json_str = response_text.strip()
                if not (json_str.startswith("{") and json_str.endswith("}")):
                    raise ValueError("Response does not appear to be JSON.")
                print("Assuming entire update response is JSON.")

            # Basic cleaning
            json_str = re.sub(r"\\n", "", json_str)
            json_str = re.sub(r"\\(?![\"\\/bfnrtu])", "", json_str)

            updated_syllabus = json.loads(json_str)
            print("Successfully parsed updated JSON.")

            # Basic validation (same as generation)
            if not all(
                key in updated_syllabus
                for key in [
                    "topic",
                    "level",
                    "duration",
                    "learning_objectives",
                    "modules",
                ]
            ):
                raise ValueError("Updated JSON missing required keys.")
            if (
                not isinstance(updated_syllabus["modules"], list)
                or not updated_syllabus["modules"]
            ):
                raise ValueError("Updated JSON 'modules' must be a non-empty list.")
            # Further validation can be added here
            print("Updated JSON passed basic validation.")

            return {
                "generated_syllabus": updated_syllabus,  # Store the update here
                "user_feedback": feedback,
                "iteration_count": state.get("iteration_count", 0) + 1,
            }
        except (json.JSONDecodeError, ValueError, Exception) as e:
            print(f"Failed to parse or validate updated JSON: {e}")
            print(f"Response text was: {response_text[:500]}...")
            # Keep original syllabus if update fails
            print("Update failed, keeping original syllabus.")
            return {
                "user_feedback": feedback,  # Still record feedback was given
                "iteration_count": state.get("iteration_count", 0) + 1,
                # generated_syllabus remains as it was before the update attempt
            }

    def _save_syllabus(self, state: SyllabusState) -> Dict:
        """
        Graph Node: Saves the current syllabus (generated or existing) to the database.

        Handles updating existing records or inserting new ones (both master
        and user-specific versions). Uses the injected `db_service`.

        Args:
            state: The current graph state containing the syllabus to save.

        Returns:
            A dictionary indicating the save status (`syllabus_saved`: True/False)
            and potentially the `saved_uid`.
        """
        syllabus_to_save = state.get("generated_syllabus") or state.get(
            "existing_syllabus"
        )
        if not syllabus_to_save:
            print("Warning: No syllabus found in state to save.")
            return {"syllabus_saved": False}  # Indicate save didn't happen

        user_entered_topic = state.get(
            "user_entered_topic", syllabus_to_save.get("topic")
        )  # Fallback
        user_id = state.get("user_id")
        print(
            f"Attempting to save syllabus. User: {user_id}, Topic: {user_entered_topic}"
        )

        # Ensure syllabus_to_save is a mutable dictionary
        if not isinstance(syllabus_to_save, dict):
            try:
                # Handle potential non-dict types if loaded differently
                syllabus_dict = dict(syllabus_to_save)
            except (TypeError, ValueError):
                print(
                    f"Error: Cannot convert syllabus of type {type(syllabus_to_save)} to dict for saving."
                )
                return {"syllabus_saved": False}
        else:
            syllabus_dict = syllabus_to_save.copy()  # Work with a copy

        # Ensure essential keys exist before saving
        if not all(k in syllabus_dict for k in ["topic", "level"]):
            print(
                f"Error: Syllabus missing 'topic' or 'level', cannot save. Data: {syllabus_dict}"
            )
            return {"syllabus_saved": False}

        # Add/update metadata
        now = datetime.now().isoformat()
        syllabus_dict["updated_at"] = now
        if (
            "created_at" not in syllabus_dict or not syllabus_dict["created_at"]
        ):  # Set created_at only if new/missing
            syllabus_dict["created_at"] = now
        if "uid" not in syllabus_dict or not syllabus_dict["uid"]:  # Ensure UID exists
            syllabus_dict["uid"] = str(uuid.uuid4())
            print(f"Generated new UID for saving: {syllabus_dict['uid']}")

        # Separate content from metadata for saving
        content_to_save = {
            "topic": syllabus_dict["topic"],
            "level": syllabus_dict["level"],
            "duration": syllabus_dict.get("duration"),
            "learning_objectives": syllabus_dict.get("learning_objectives"),
            "modules": syllabus_dict.get("modules"),
        }

        # Determine if it's a master or user syllabus
        is_master_save = not user_id

        try:
            # Use the database service methods which handle insert/update logic
            saved_id = self.db_service.save_syllabus(
                topic=syllabus_dict["topic"],
                level=syllabus_dict["level"],
                content=content_to_save,
                user_id=user_id,
                is_master=is_master_save,  # Pass calculated flag
                uid=syllabus_dict["uid"],  # Pass UID for upsert logic
                created_at=syllabus_dict["created_at"],  # Pass timestamps
                updated_at=now,
                user_entered_topic=user_entered_topic,
                parent_uid=syllabus_dict.get("parent_uid"),  # Pass parent_uid if exists
            )

            if saved_id:
                print(
                    f"Syllabus UID {syllabus_dict['uid']} saved successfully (DB ID: {saved_id})."
                )
                # Update state with potentially updated/confirmed UID and timestamps
                state["uid"] = syllabus_dict["uid"]
                state["created_at"] = syllabus_dict["created_at"]
                state["updated_at"] = now
                return {"syllabus_saved": True, "saved_uid": syllabus_dict["uid"]}
            else:
                # This case implies db_service.save_syllabus failed internally
                print(
                    f"Error: db_service.save_syllabus did not return a valid ID for UID {syllabus_dict['uid']}."
                )
                return {"syllabus_saved": False}

        except Exception as e:
            print(
                f"Error saving syllabus UID {syllabus_dict.get('uid', 'N/A')} via db_service: {e}"
            )
            # Log the exception traceback if possible
            import traceback

            traceback.print_exc()
            return {"syllabus_saved": False}

    def clone_syllabus_for_user(self, user_id: str) -> Dict:
        """
        Clones the current syllabus in the state for a specific user.

        Creates a new database entry marked as user-specific, linking it
        to the master syllabus via `parent_uid`. Uses the injected `db_service`.

        Args:
            user_id: The ID of the user for whom to clone the syllabus.

        Returns:
            A dictionary representing the newly cloned user-specific syllabus.

        Raises:
            ValueError: If the agent is not initialized or no syllabus exists in state.
            RuntimeError: If saving the cloned syllabus fails.
        """
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

        # Ensure it's a dictionary
        if not isinstance(syllabus_to_clone, dict):
            try:
                syllabus_dict = dict(syllabus_to_clone)
            except (TypeError, ValueError):
                print(
                    f"Error: Cannot convert syllabus of type {type(syllabus_to_clone)} to dict for cloning."
                )
                raise ValueError("Invalid syllabus format for cloning.")
        else:
            syllabus_dict = syllabus_to_clone

        # Create a deep copy for the user version
        user_syllabus = copy.deepcopy(syllabus_dict)
        now = datetime.now().isoformat()

        # Update the copy with user-specific information
        new_uid = str(uuid.uuid4())  # New unique ID
        user_syllabus["uid"] = new_uid
        user_syllabus["user_id"] = user_id
        user_syllabus["is_master"] = False
        user_syllabus["created_at"] = now
        user_syllabus["updated_at"] = now
        user_syllabus["user_entered_topic"] = self.state.get(
            "user_entered_topic", user_syllabus.get("topic")
        )

        # Determine the parent UID (should be the UID of the master version)
        master_syllabus = self.db_service.get_syllabus(
            user_syllabus["topic"],
            user_syllabus["level"],
            user_id=None,  # Look for master
        )
        parent_uid = master_syllabus.get("uid") if master_syllabus else None
        user_syllabus["parent_uid"] = parent_uid
        print(f"Setting parent UID for clone {new_uid} to {parent_uid}")

        # Separate content for saving
        content_to_save = {
            "topic": user_syllabus["topic"],
            "level": user_syllabus["level"],
            "duration": user_syllabus.get("duration"),
            "learning_objectives": user_syllabus.get("learning_objectives"),
            "modules": user_syllabus.get("modules"),
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
                raise RuntimeError(
                    "db_service.save_syllabus failed to return an ID for the clone."
                )

            print(
                f"Cloned syllabus UID {new_uid} saved for user {user_id} (DB ID: {saved_id})."
            )

            # Update the agent's state to reflect the newly cloned syllabus
            self.state["generated_syllabus"] = (
                user_syllabus  # Now working with the user copy
            )
            self.state["existing_syllabus"] = None  # Clear existing master from state
            self.state["uid"] = new_uid  # Update state UID

            # Add the database primary key if needed, though UID is primary identifier
            user_syllabus["syllabus_id"] = saved_id

            return user_syllabus
        except Exception as e:
            print(f"Error cloning syllabus UID {new_uid} for user {user_id}: {e}")
            import traceback

            traceback.print_exc()
            raise RuntimeError("Failed to save cloned syllabus.") from e

    def _end(self, _: SyllabusState) -> Dict:
        """Graph Node: Terminal node for the graph."""
        print("Workflow ended.")
        return {}

    # --- Public Methods for Service Interaction ---

    def initialize(
        self, topic: str, knowledge_level: str, user_id: Optional[str] = None
    ) -> Dict:
        """
        Initializes the internal state of the SyllabusAI agent for a new run.

        Args:
            topic: The syllabus topic.
            knowledge_level: The user's knowledge level.
            user_id: Optional user ID.

        Returns:
            A dictionary confirming initialization.
        """
        self.state = self._initialize(
            topic=topic, knowledge_level=knowledge_level, user_id=user_id
        )
        print(
            f"SyllabusAI initialized for topic: '{topic}', level: '{knowledge_level}', user: {user_id}"
        )
        return {
            "status": "initialized",
            "topic": topic,
            "knowledge_level": knowledge_level,
            "user_id": user_id,
        }

    def get_or_create_syllabus(self) -> Dict:
        """
        Retrieves an existing syllabus or orchestrates the creation of a new one via the graph.

        Runs the graph from database search onwards. If a syllabus is found in the DB,
        it's returned. Otherwise, web search and generation nodes are executed.
        The result is stored in the agent's internal state.

        Returns:
            The retrieved or generated syllabus dictionary.

        Raises:
            ValueError: If the agent is not initialized.
            RuntimeError: If the graph execution fails to produce a valid syllabus.
        """
        if not self.state:
            raise ValueError("Agent not initialized. Call initialize() first.")
        print("Starting get_or_create_syllabus graph execution...")

        # Run the graph from the entry point ('initialize' sets state, but we start logic from 'search_database')
        # We invoke with the current state, letting the graph decide the path.
        final_state = {}
        try:
            # Start from the beginning of the logical flow after initialization
            for step in self.graph.stream(self.state, config={"recursion_limit": 10}):
                node_name = list(step.keys())[0]
                print(f"Graph Step: {node_name}")
                final_state.update(step[node_name])  # Accumulate state updates
            # Update internal state with the final accumulated state
            self.state.update(final_state)
        except Exception as e:
            print(f"Error during graph execution in get_or_create_syllabus: {e}")
            import traceback

            traceback.print_exc()
            raise RuntimeError("Syllabus graph execution failed.") from e

        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus:
            # This might happen if generation failed and fallback also failed validation
            print(
                "Error: Graph execution finished but no valid syllabus found in state."
            )
            raise RuntimeError("Failed to get or create a valid syllabus.")

        print(f"Syllabus get/create finished. Result UID: {syllabus.get('uid', 'N/A')}")
        return syllabus

    def update_syllabus(self, feedback: str) -> Dict:
        """
        Updates the current syllabus in the state based on user feedback.

        Directly calls the `_update_syllabus` node logic. Note: This does not
        run the full graph, only the update step. The result is stored in the
        agent's internal state.

        Args:
            feedback: The user's feedback text.

        Returns:
            The updated syllabus dictionary.

        Raises:
            ValueError: If the agent is not initialized or no syllabus exists in state.
            RuntimeError: If the update process results in an invalid syllabus.
        """
        if not self.state:
            raise ValueError("Agent not initialized.")
        if not (
            self.state.get("generated_syllabus") or self.state.get("existing_syllabus")
        ):
            raise ValueError("No syllabus loaded to update.")
        print("Starting syllabus update based on feedback...")

        # Invoke the update node directly
        update_result = self._update_syllabus(self.state, feedback)
        self.state.update(update_result)  # Update internal state

        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus:
            # Should be handled within _update_syllabus, but double-check
            print("Error: Syllabus became invalid after update attempt.")
            raise RuntimeError("Syllabus became invalid after update attempt.")

        print(f"Syllabus update finished. Result UID: {syllabus.get('uid', 'N/A')}")
        return syllabus

    def save_syllabus(self) -> Dict:
        """
        Saves the current syllabus in the state to the database.

        Directly calls the `_save_syllabus` node logic. Checks if the syllabus
        appears to need saving before attempting.

        Returns:
            A dictionary indicating the save status ('saved' or 'skipped' or 'failed').

        Raises:
            ValueError: If the agent is not initialized.
        """
        if not self.state:
            raise ValueError("Agent not initialized")
        print("Starting syllabus save process...")

        current_syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not current_syllabus:
            print("Warning: No syllabus in state to save.")
            return {"status": "skipped", "reason": "No syllabus in state"}

        # Simple check: if generated_syllabus exists (meaning it was generated or updated)
        needs_save = self.state.get("generated_syllabus") is not None

        if not needs_save:
            print("Skipping save, syllabus was likely loaded and not modified.")
            return {
                "status": "skipped",
                "reason": "Syllabus loaded, not generated/modified",
            }

        save_result = self._save_syllabus(self.state)
        # No state update needed here as _save_syllabus doesn't modify graph state fields

        if save_result.get("syllabus_saved"):
            print(
                f"Syllabus save finished. Saved UID: {save_result.get('saved_uid', 'N/A')}"
            )
            return {"status": "saved", "uid": save_result.get("saved_uid")}
        else:
            print("Syllabus save failed.")
            return {"status": "failed"}

    def get_syllabus(self) -> Dict:
        """
        Returns the current syllabus dictionary held in the agent's state.

        Returns:
            The syllabus dictionary currently being worked on.

        Raises:
            ValueError: If the agent is not initialized or no syllabus is loaded.
        """
        if not self.state:
            raise ValueError("Agent not initialized")

        syllabus = self.state.get("generated_syllabus") or self.state.get(
            "existing_syllabus"
        )
        if not syllabus:
            raise ValueError("No syllabus loaded in the current state.")
        return syllabus

    def delete_syllabus(self) -> Dict:
        """
        Deletes the syllabus corresponding to the current state from the database.

        Uses topic, level, and user_id from the state to identify the specific
        syllabus record (user-specific or master) to delete via the `db_service`.

        Returns:
            A dictionary confirming deletion status.

        Raises:
            ValueError: If the agent is not initialized or state lacks topic/level.
        """
        if not self.state:
            raise ValueError("Agent not initialized")

        topic = self.state.get("topic")
        knowledge_level = self.state.get("user_knowledge_level")
        user_id = self.state.get(
            "user_id"
        )  # Get user_id to potentially delete user-specific version

        if not topic or not knowledge_level:
            raise ValueError("State is missing topic or knowledge level for deletion.")

        # Use db_service method which handles finding the correct record
        try:
            deleted = self.db_service.delete_syllabus(topic, knowledge_level, user_id)
            if deleted:
                print(
                    f"Syllabus deleted successfully from DB (Topic: {topic}, Level: {knowledge_level}, User: {user_id})."
                )
                # Clear syllabus from state after deletion
                self.state["existing_syllabus"] = None
                self.state["generated_syllabus"] = None
                self.state["uid"] = None  # Clear UID as well
                return {"syllabus_deleted": True}
            else:
                print(
                    f"Syllabus not found in DB for deletion (Topic: {topic}, Level: {knowledge_level}, User: {user_id})."
                )
                return {"syllabus_deleted": False, "reason": "Not found"}
        except Exception as e:
            print(f"Error deleting syllabus from DB: {e}")

            traceback.print_exc()
            return {"syllabus_deleted": False, "error": str(e)}
