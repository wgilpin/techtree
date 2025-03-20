# pylint: disable=missing-class-docstring,missing-module-docstring

import os
import re
import time
import random
import json
from typing import Dict, List, TypedDict, Optional

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from tavily import TavilyClient
from tinydb import TinyDB, Query

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-pro-exp-02-05")

# Configure Tavily API
tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Initialize the database
db = TinyDB("syllabus_db.json")
syllabi_table = db.table("syllabi")


def call_with_retry(func, *args, max_retries=5, initial_delay=1, **kwargs):
    """Call a function with exponential backoff retry logic for quota errors."""
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            time.sleep(delay)


# --- Define State ---
class SyllabusState(TypedDict):
    topic: str
    user_knowledge_level: (
        str  # 'beginner', 'early learner', 'good knowledge', or 'advanced'
    )
    existing_syllabus: Optional[Dict]
    search_results: List[str]
    generated_syllabus: Optional[Dict]
    user_feedback: Optional[str]
    syllabus_accepted: bool
    iteration_count: int


class SyllabusAI:
    """Encapsulates the Tech Tree syllabus langgraph app."""

    def __init__(self):
        """Initialize the SyllabusAI."""
        self.state: Optional[SyllabusState] = None
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()

    def _create_workflow(self) -> StateGraph:
        """Create the langgraph workflow."""
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
        workflow.add_edge("generate_syllabus", "end")
        workflow.add_edge("update_syllabus", "end")
        workflow.add_edge("save_syllabus", "end")

        workflow.set_entry_point("initialize")
        return workflow

    def _initialize(
        self,
        _: Optional[SyllabusState] = None,
        topic: str = "",
        knowledge_level: str = "beginner",
    ) -> Dict:
        """Initialize the state with the topic and user knowledge level."""
        if not topic:
            raise ValueError("Topic is required")

        # Validate knowledge level
        valid_levels = ["beginner", "early learner", "good knowledge", "advanced"]
        if knowledge_level not in valid_levels:
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
            "user_entered_topic": topic,
        }

    def _search_database(self, state: SyllabusState) -> Dict:
        """Search for existing syllabi in the database."""
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]

        # Search for match on both topic and knowledge level
        syllabus_query = Query()
        existing = syllabi_table.search(
            ((syllabus_query.topic == topic) | (syllabus_query.user_entered_topic == topic))
            & (syllabus_query.level.test(lambda x: x.lower() == knowledge_level.lower()))
        )

        if existing:
            return {"existing_syllabus": existing[0]}
        return {}

    def _should_search_internet(self, state: SyllabusState) -> str:
        """Decide whether to search the internet or use existing syllabus."""
        if state["existing_syllabus"]:
            return "end"
        return "search_internet"

    def _search_internet(self, state: SyllabusState) -> Dict:
        """Search the internet for information about the topic."""
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]

        # Use Tavily to search for information
        search_results = []
        try:
            # Search Wikipedia
            wiki_search = tavily.search(
                query=f"{topic} syllabus curriculum",
                search_depth="advanced",
                include_domains=["wikipedia.org", "edu"],
                max_results=2,
            )
            # Search other sources
            general_search = tavily.search(
                query=f"{topic} course syllabus curriculum for {knowledge_level}",
                search_depth="advanced",
                max_results=3,
            )
            search_results = [
                r.get("content", "") for r in wiki_search.get("results", [])
            ]
            search_results.extend(
                [r.get("content", "") for r in general_search.get("results", [])]
            )
        except Exception as e:
            search_results = [f"Error searching for {topic}: {str(e)}"]

        return {"search_results": search_results}

    def _generate_syllabus(self, state: SyllabusState) -> Dict:
        """Generate a syllabus based on search results and user knowledge level."""
        print("DEBUG:   Generating syllabus")
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        search_results = state["search_results"]

        # Combine search results into a single context
        search_context = "\n\n".join(
            [f"Source {i+1}:\n{result}" for i, result in enumerate(search_results)]
        )

        # Construct the prompt for Gemini
        prompt = f"""
        You are an expert curriculum designer creating a
        comprehensive syllabus for the topic: {topic}.
        
        The user's knowledge level is: {knowledge_level}
        
        Use the following information from internet searches to create
        an accurate and up-to-date syllabus:
        
        {search_context}
        
        Create a syllabus with the following structure:
        1. Topic name
        2. Level (should match or be appropriate for the user's knowledge level: {knowledge_level})
        3. Duration (e.g., "4 weeks")
        4. 3-5 Learning objectives
        5. Modules (organized by week or unit)
        6. Lessons within each module (5-10 lessons per module)
        
        Tailor the syllabus to the user's knowledge level:
        - For 'beginner': Focus on foundational concepts and gentle introduction
        - For 'early learner': Include basic concepts but move more quickly to intermediate topics
        - For 'good knowledge': Focus on intermediate to advanced topics, assuming basic knowledge
        - For 'advanced': Focus on advanced topics, cutting-edge developments, and specialized areas
        
        Format your response as a valid JSON object with the following structure:
        {{
          "topic": "Topic Name",
          "level": "Level",
          "duration": "Duration",
          "learning_objectives": ["Objective 1", "Objective 2", ...],
          "modules": [
            {{
              "week": 1,
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
        """

        response = call_with_retry(model.generate_content, prompt)
        response_text = response.text
        print("DEBUG: Generated syllabus.")

        # Extract JSON from response
        # Try different patterns to extract JSON
        json_patterns = [
            # Pattern for JSON in code blocks
            r"```(?:json)?\s*({.*?})```",
            # Pattern for JSON with outer braces
            r'({[\s\S]*"topic"[\s\S]*"level"[\s\S]*"duration"[\s\S]*"learning_objectives"[\s\S]*"modules"[\s\S]*})',
            # Pattern for just the JSON object
            r"({[\s\S]*})",
        ]

        json_str = None
        for pattern in json_patterns:
            json_match = re.search(pattern, response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # Clean up the JSON string
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)
                # Try to parse it
                try:
                    syllabus = json.loads(json_str)
                    # Validate the structure
                    if all(
                        key in syllabus
                        for key in [
                            "topic",
                            "level",
                            "duration",
                            "learning_objectives",
                            "modules",
                        ]
                    ):
                        return {"generated_syllabus": syllabus}
                except Exception:
                    # Continue to the next pattern if this one fails
                    pass

        # If all patterns fail, create a basic structure
        print(f"Failed to parse JSON from response: {response_text[:200]}...")
        return {
            "generated_syllabus": {
                "topic": topic,
                "level": knowledge_level.capitalize(),
                "duration": "4 weeks",
                "learning_objectives": [
                    "Understand basic concepts of " + topic,
                    "Apply knowledge to real-world scenarios",
                    "Develop critical thinking skills related to " + topic,
                ],
                "modules": [
                    {
                        "week": 1,
                        "title": "Introduction to " + topic,
                        "lessons": [
                            {"title": "Basic concepts and terminology"},
                            {"title": "Historical development"},
                            {"title": "Current applications"},
                        ],
                    },
                    {
                        "week": 2,
                        "title": "Core Principles of " + topic,
                        "lessons": [
                            {"title": "Fundamental theories"},
                            {"title": "Key methodologies"},
                            {"title": "Practical applications"},
                        ],
                    },
                ],
            }
        }

    def _update_syllabus(self, state: SyllabusState, feedback: str) -> Dict:
        """Update the syllabus based on user feedback."""
        topic = state["topic"]
        knowledge_level = state["user_knowledge_level"]
        syllabus = state["generated_syllabus"] or state["existing_syllabus"]

        # Construct the prompt for Gemini
        prompt = f"""
        You are an expert curriculum designer updating a syllabus for the topic: {topic}.
        
        The user's knowledge level is: {knowledge_level}
        
        Here is the current syllabus:
        {json.dumps(syllabus, indent=2)}
        
        The user has provided the following feedback:
        {feedback}
        
        Update the syllabus to address the user's feedback while ensuring it remains
        appropriate for their knowledge level ({knowledge_level}). Maintain the same JSON structure.
        
        Format your response as a valid JSON object with the following structure:
        {{
          "topic": "Topic Name",
          "level": "Level",
          "duration": "Duration",
          "learning_objectives": ["Objective 1", "Objective 2", ...],
          "modules": [
            {{
              "week": 1,
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
        """

        response = call_with_retry(model.generate_content, prompt)
        response_text = response.text

        # Extract JSON from response
        # Try different patterns to extract JSON
        json_patterns = [
            # Pattern for JSON in code blocks
            r"```(?:json)?\s*({.*?})```",
            # Pattern for JSON with outer braces
            r'({[\s\S]*"topic"[\s\S]*"level"[\s\S]*"duration"[\s\S]*"learning_objectives"[\s\S]*"modules"[\s\S]*})',
            # Pattern for just the JSON object
            r"({[\s\S]*})",
        ]

        json_str = None
        for pattern in json_patterns:
            json_match = re.search(pattern, response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # Clean up the JSON string
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)
                # Try to parse it
                try:
                    updated_syllabus = json.loads(json_str)
                    # Validate the structure
                    if all(
                        key in updated_syllabus
                        for key in [
                            "topic",
                            "level",
                            "duration",
                            "learning_objectives",
                            "modules",
                        ]
                    ):
                        return {
                            "generated_syllabus": updated_syllabus,
                            "user_feedback": feedback,
                            "iteration_count": state["iteration_count"] + 1,
                        }
                except Exception:
                    # Continue to the next pattern if this one fails
                    pass

        # If all patterns fail, keep the original syllabus but increment the iteration count
        print(f"Failed to parse JSON from response: {response_text[:200]}...")
        return {
            "user_feedback": feedback,
            "iteration_count": state["iteration_count"] + 1,
        }

    def _save_syllabus(self, state: SyllabusState) -> Dict:
        """Save the syllabus to the database."""
        syllabus = state["generated_syllabus"] or state["existing_syllabus"]
        user_entered_topic = state["user_entered_topic"]

        if isinstance(syllabus, dict):
            # If syllabus is already a dict, use it directly
            syllabus["user_entered_topic"] = user_entered_topic
        else:
            # Convert syllabus (Document object) to a dict
            syllabus = syllabus.to_dict()
            syllabus["user_entered_topic"] = user_entered_topic

        # Add the user-entered topic to the syllabus
        syllabus["user_entered_topic"] = user_entered_topic

        # Check if syllabus already exists with same topic and level
        syllabus_query = Query()
        existing = syllabi_table.search(
            (syllabus_query.topic == syllabus["topic"])
            & (syllabus_query.level.test(
                lambda syllabus_doc: syllabus and syllabus_doc.lower() == syllabus["level"].lower() if syllabus_doc else False
            ))
        )

        if existing:
            # Update existing syllabus
            syllabi_table.update(
                syllabus,
                (syllabus_query.topic == syllabus["topic"])
                & (
                    syllabus_query.level.test(
                        lambda syllabus_doc: syllabus and syllabus_doc.lower() == syllabus["level"].lower() if syllabus_doc else False
                    )
                ),
            )
        else:
            # Insert new syllabus
            syllabi_table.insert(syllabus)

        return {"syllabus_saved": True}

    def _end(self, _: SyllabusState) -> Dict:
        """End the workflow."""
        return {}

    def initialize(self, topic: str, knowledge_level: str) -> Dict:
        """Initialize the agent with a topic and knowledge level."""
        self.state = self._initialize(topic=topic, knowledge_level=knowledge_level)
        return {
            "status": "initialized",
            "topic": topic,
            "knowledge_level": knowledge_level,
        }

    def get_or_create_syllabus(self) -> Dict:
        """Get an existing syllabus or create a new one."""
        if not self.state:
            raise ValueError("Agent not initialized")

        # Search database
        result = self._search_database(self.state)
        self.state.update(result)

        # If syllabus exists, return it
        if self.state["existing_syllabus"]:
            print("DEBUG: Loaded from db")
            return self.state["existing_syllabus"]

        # Otherwise, search internet and generate syllabus
        print("DEBUG: Creating.")
        result = self._search_internet(self.state)
        self.state.update(result)

        result = self._generate_syllabus(self.state)
        self.state.update(result)

        return self.state["generated_syllabus"]

    def update_syllabus(self, feedback: str) -> Dict:
        """Update the syllabus based on user feedback."""
        if not self.state:
            raise ValueError("Agent not initialized")

        result = self._update_syllabus(self.state, feedback)
        self.state.update(result)

        return self.state["generated_syllabus"]

    def save_syllabus(self) -> Dict:
        """Save the syllabus to the database."""
        if not self.state:
            raise ValueError("Agent not initialized")

        # Check if the syllabus has been modified
        if (
            self.state["existing_syllabus"]
            and self.state["generated_syllabus"]
            and self.state["existing_syllabus"] == self.state["generated_syllabus"]
        ):
            # If the syllabus hasn't been modified, skip the save operation
            return {"status": "skipped"}

        result = self._save_syllabus(self.state)
        self.state.update(result)

        return {"status": "saved"}

    def get_syllabus(self) -> Dict:
        """Get the current syllabus."""
        if not self.state:
            raise ValueError("Agent not initialized")

        return self.state["generated_syllabus"] or self.state["existing_syllabus"]

    def delete_syllabus(self) -> Dict:
        """Delete the syllabus from the database."""
        if not self.state:
            raise ValueError("Agent not initialized")

        topic = self.state["topic"]
        knowledge_level = self.state["user_knowledge_level"]

        # Delete syllabus from the database
        syllabus_query = Query()
        syllabi_table.remove(
            ((syllabus_query.topic == topic) | (syllabus_query.user_entered_topic == topic))
            & (syllabus_query.level.test(lambda x: x.lower() == knowledge_level.lower()))
        )

        return {"syllabus_deleted": True}
