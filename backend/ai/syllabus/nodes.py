"""Implements the node functions for the syllabus generation LangGraph."""

# pylint: disable=broad-exception-caught

import json
import re
import uuid
import traceback
from datetime import datetime
from typing import Dict, Optional

from requests import RequestException
from tavily import TavilyClient
import google.generativeai as genai

# Project specific imports
from backend.services.sqlite_db import SQLiteDatabaseService
from .state import SyllabusState
from .prompts import GENERATION_PROMPT_TEMPLATE, UPDATE_PROMPT_TEMPLATE
from .utils import call_with_retry

# --- Node Functions ---


def initialize_state(
    _: Optional[SyllabusState],  # LangGraph passes state, but we ignore it here
    topic: str = "",
    knowledge_level: str = "beginner",
    user_id: Optional[str] = None,
) -> Dict:
    """Initializes the graph state with topic, knowledge level, and user ID."""
    if not topic:
        raise ValueError("Topic is required")

    valid_levels = ["beginner", "early learner", "good knowledge", "advanced"]
    if knowledge_level not in valid_levels:
        print(f"Warning: Invalid level '{knowledge_level}'. Defaulting to 'beginner'.")
        knowledge_level = "beginner"

    return {
        "topic": topic,
        "user_knowledge_level": knowledge_level,
        "existing_syllabus": None,
        "search_results": [],
        "generated_syllabus": None,
        "user_feedback": None,
        "syllabus_accepted": False,
        "iteration_count": 0,
        "user_entered_topic": topic,
        "user_id": user_id,
        "uid": None,
        "is_master": None,
        "parent_uid": None,
        "created_at": None,
        "updated_at": None,
    }


def search_database(state: SyllabusState, db_service: SQLiteDatabaseService) -> Dict:
    """Searches the database for an existing syllabus matching the criteria."""
    topic = state["topic"]
    knowledge_level = state["user_knowledge_level"]
    user_id = state.get("user_id")
    print(f"DB Search: Topic='{topic}', Level='{knowledge_level}', User={user_id}")

    found_syllabus = db_service.get_syllabus(topic, knowledge_level, user_id)

    if found_syllabus:
        print(f"Found existing syllabus in DB. UID: {found_syllabus.get('uid')}")
        # Ensure all state fields are present from the loaded syllabus
        return {
            "existing_syllabus": found_syllabus,
            "uid": found_syllabus.get("uid"),
            "is_master": found_syllabus.get("is_master"),
            "parent_uid": found_syllabus.get("parent_uid"),
            "created_at": found_syllabus.get("created_at"),
            "updated_at": found_syllabus.get("updated_at"),
            # Keep user_entered_topic from initial state if different
            "user_entered_topic": state.get("user_entered_topic", topic),
        }
    else:
        print("No matching syllabus found in DB.")
        return {"existing_syllabus": None}  # Explicitly return None


def search_internet(state: SyllabusState, tavily_client: TavilyClient) -> Dict:
    """Performs a web search using Tavily to gather context."""
    if not tavily_client:
        print("Warning: Tavily client not configured. Skipping internet search.")
        return {"search_results": ["Tavily client not available."]}

    topic = state["topic"]
    knowledge_level = state["user_knowledge_level"]
    print(f"Internet Search: Topic='{topic}', Level='{knowledge_level}'")

    search_results = []
    queries = [
        (
            f"{topic} syllabus curriculum outline learning objectives",
            {"include_domains": ["en.wikipedia.org", "edu"], "max_results": 2},
        ),
        (
            f"{topic} course syllabus curriculum for {knowledge_level} students",
            {"max_results": 3},
        ),
    ]

    for query, params in queries:
        try:
            print(f"Tavily Query: {query} (Params: {params})")
            search = tavily_client.search(
                query=query, search_depth="advanced", **params
            )
            content = [
                r.get("content", "")
                for r in search.get("results", [])
                if r.get("content")
            ]
            search_results.extend(content)
            print(f"Found {len(content)} results.")
        except RequestException as e:
            print(f"Tavily request error for query '{query}': {e}")
            search_results.append(f"Error during web search: {str(e)}")
        except Exception as e:
            print(f"Unexpected error during Tavily search for query '{query}': {e}")
            search_results.append(f"Unexpected error during web search: {str(e)}")

    print(f"Total search results gathered: {len(search_results)}")
    return {"search_results": search_results}


def _parse_llm_json_response(response_text: str) -> Optional[Dict]:
    """Attempts to parse a JSON object from the LLM response text."""
    json_str = None
    try:
        match = re.search(r"```(?:json)?\s*({.*?})\s*```", response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            print("Extracted JSON from markdown block.")
        else:
            json_str = response_text.strip()
            if not (json_str.startswith("{") and json_str.endswith("}")):
                # If it doesn't look like JSON, maybe it's just the raw content?
                # Or maybe the LLM failed completely. Let validation handle it.
                print("Response does not appear to be JSON or markdown block.")
                return None  # Indicate parsing failure early

            print("Assuming entire response is JSON.")

        # Basic cleaning
        json_str = re.sub(r"\\n", "", json_str)
        json_str = re.sub(r"\\(?![\"\\/bfnrtu])", "", json_str)

        parsed_json = json.loads(json_str)
        print("Successfully parsed JSON.")
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from response: {e}")
        print(f"Response text was: {response_text[:500]}...")
        return None
    except Exception as e:
        print(f"Unexpected error during JSON parsing: {e}")
        print(f"Response text was: {response_text[:500]}...")
        return None


def _validate_syllabus_structure(syllabus: Dict, context: str = "Generated") -> bool:
    """Performs basic validation on the syllabus dictionary structure."""
    required_keys = ["topic", "level", "duration", "learning_objectives", "modules"]
    if not all(key in syllabus for key in required_keys):
        print(f"Error: {context} JSON missing required keys ({required_keys}).")
        return False
    if not isinstance(syllabus["modules"], list) or not syllabus["modules"]:
        print(f"Error: {context} JSON 'modules' must be a non-empty list.")
        return False
    for i, module in enumerate(syllabus["modules"]):
        if not all(key in module for key in ["title", "lessons"]):
            print(f"Error: {context} JSON module {i} missing 'title' or 'lessons'.")
            return False
        if not isinstance(module["lessons"], list) or not module["lessons"]:
            print(
                f"Error: {context} JSON module {i} 'lessons' must be a non-empty list."
            )
            return False
        for j, lesson in enumerate(module["lessons"]):
            if "title" not in lesson or not lesson["title"]:
                print(
                    f"Error: {context} JSON lesson {j} in module {i} missing 'title'."
                )
                return False
    print(f"{context} JSON passed basic validation.")
    return True


def generate_syllabus(state: SyllabusState, llm_model: genai.GenerativeModel) -> Dict:
    """Generates a new syllabus using the LLM based on search results."""
    if not llm_model:
        print("Warning: LLM model not configured. Cannot generate syllabus.")
        # Return a very basic fallback immediately
        return {
            "generated_syllabus": {
                "topic": state["topic"],
                "level": state["user_knowledge_level"],
                "duration": "N/A",
                "learning_objectives": ["Generation failed"],
                "modules": [{"title": "Generation Failed", "lessons": []}],
                "error_generating": True,
            }
        }

    print("Generating syllabus with AI...")
    topic = state["topic"]
    knowledge_level = state["user_knowledge_level"]
    search_results = state["search_results"]

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

    prompt = GENERATION_PROMPT_TEMPLATE.format(
        topic=topic, knowledge_level=knowledge_level, search_context=search_context
    )

    response_text = ""
    try:
        print("Sending generation request to LLM...")
        response = call_with_retry(llm_model.generate_content, prompt)
        response_text = response.text
        print("LLM response received.")
    except Exception as e:
        print(f"LLM call failed during syllabus generation: {e}")
        # Fall through to parsing/validation which will likely fail

    syllabus = _parse_llm_json_response(response_text)

    if syllabus and _validate_syllabus_structure(syllabus, "Generated"):
        return {"generated_syllabus": syllabus}
    else:
        print(
            "Using fallback syllabus structure due to generation/parsing/validation error."
        )
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
                "error_generating": True,
            }
        }


def update_syllabus(
    state: SyllabusState, feedback: str, llm_model: genai.GenerativeModel
) -> Dict:
    """Updates the current syllabus based on user feedback using the LLM."""
    if not llm_model:
        print("Warning: LLM model not configured. Cannot update syllabus.")
        return {  # Return minimal update indicating failure
            "user_feedback": feedback,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    iteration = state.get("iteration_count", 0) + 1
    print(f"Updating syllabus based on feedback (Iteration {iteration})")
    topic = state["topic"]
    knowledge_level = state["user_knowledge_level"]
    # Prioritize generated/updated syllabus, fallback to existing if needed
    current_syllabus = state.get("generated_syllabus") or state.get("existing_syllabus")

    if not current_syllabus:
        print("Error: Cannot update syllabus as none exists in state.")
        return {"iteration_count": iteration}  # Increment count even on error

    try:
        syllabus_json = json.dumps(current_syllabus, indent=2)
    except TypeError as e:
        print(f"Error serializing current syllabus to JSON for update: {e}")
        return {"iteration_count": iteration}

    prompt = UPDATE_PROMPT_TEMPLATE.format(
        topic=topic,
        knowledge_level=knowledge_level,
        syllabus_json=syllabus_json,
        feedback=feedback,
    )

    response_text = ""
    try:
        print("Sending update request to LLM...")
        response = call_with_retry(llm_model.generate_content, prompt)
        response_text = response.text
        print("LLM update response received.")
    except Exception as e:
        print(f"LLM call failed during syllabus update: {e}")
        # Fall through

    updated_syllabus = _parse_llm_json_response(response_text)

    if updated_syllabus and _validate_syllabus_structure(updated_syllabus, "Updated"):
        return {
            "generated_syllabus": updated_syllabus,  # Overwrite with the update
            "user_feedback": feedback,
            "iteration_count": iteration,
        }
    else:
        print("Update failed (parsing/validation), keeping original syllabus.")
        # Return feedback and iteration count, but don't change generated_syllabus
        return {
            "user_feedback": feedback,
            "iteration_count": iteration,
        }


def save_syllabus(state: SyllabusState, db_service: SQLiteDatabaseService) -> Dict:
    """Saves the current syllabus (generated or existing) to the database."""
    syllabus_to_save = state.get("generated_syllabus") or state.get("existing_syllabus")
    if not syllabus_to_save:
        print("Warning: No syllabus found in state to save.")
        return {"syllabus_saved": False}

    user_entered_topic = state.get("user_entered_topic", syllabus_to_save.get("topic"))
    user_id = state.get("user_id")
    print(f"Save Attempt: User={user_id}, Topic='{user_entered_topic}'")

    # Ensure mutable dict and copy
    try:
        syllabus_dict = dict(syllabus_to_save).copy()
    except (TypeError, ValueError):
        print(f"Error: Cannot convert syllabus type {type(syllabus_to_save)} to dict.")
        return {"syllabus_saved": False}

    if not all(k in syllabus_dict for k in ["topic", "level"]):
        print(f"Error: Syllabus missing 'topic' or 'level'. Data: {syllabus_dict}")
        return {"syllabus_saved": False}

    # Add/update metadata
    now = datetime.now().isoformat()
    syllabus_dict["updated_at"] = now
    if not syllabus_dict.get("created_at"):
        syllabus_dict["created_at"] = now
    if not syllabus_dict.get("uid"):
        syllabus_dict["uid"] = str(uuid.uuid4())
        print(f"Generated new UID for saving: {syllabus_dict['uid']}")

    # Content vs Metadata separation
    content_to_save = {
        k: syllabus_dict.get(k)
        for k in ["topic", "level", "duration", "learning_objectives", "modules"]
    }

    is_master_save = not user_id

    try:
        saved_id = db_service.save_syllabus(
            topic=syllabus_dict["topic"],
            level=syllabus_dict["level"],
            content=content_to_save,
            user_id=user_id,
            is_master=is_master_save,
            uid=syllabus_dict["uid"],
            created_at=syllabus_dict["created_at"],
            updated_at=now,
            user_entered_topic=user_entered_topic,
            parent_uid=syllabus_dict.get("parent_uid"),
        )

        if saved_id:
            print(f"Syllabus UID {syllabus_dict['uid']} saved (DB ID: {saved_id}).")
            # Return updates to state based on saved data
            return {
                "syllabus_saved": True,
                "saved_uid": syllabus_dict["uid"],
                "uid": syllabus_dict["uid"],  # Ensure state uid matches saved uid
                "created_at": syllabus_dict["created_at"],
                "updated_at": now,
                "is_master": is_master_save,  # Reflect saved status
            }
        else:
            print(
                f"Error: db_service.save_syllabus failed for UID {syllabus_dict['uid']}."
            )
            return {"syllabus_saved": False}

    except Exception as e:
        print(f"Error saving syllabus UID {syllabus_dict.get('uid', 'N/A')}: {e}")
        traceback.print_exc()
        return {"syllabus_saved": False}


def end_node(_: SyllabusState) -> Dict:
    """Terminal node for the graph."""
    print("Workflow ended.")
    return {}  # No state change
