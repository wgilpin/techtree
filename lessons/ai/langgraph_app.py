# pylint: disable=missing-class-docstring,missing-module-docstring

import os
import re
import time
import random
import json
from typing import Dict, List, TypedDict, Optional
from datetime import datetime
import uuid

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from tinydb import TinyDB, Query

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-pro-exp-02-05")

# Initialize the database
db = TinyDB("syllabus_db.json")
syllabi_table = db.table("syllabi")
user_progress_table = db.table("user_progress")


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
class LessonState(TypedDict):
    topic: str
    knowledge_level: str
    syllabus: Optional[Dict]
    lesson_title: Optional[str]
    module_title: Optional[str]
    generated_content: Optional[Dict]
    user_responses: List[Dict]
    user_performance: Optional[Dict]
    user_email: Optional[str]
    lesson_uid: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class LessonAI:
    """Encapsulates the Tech Tree lesson langgraph app."""

    def __init__(self):
        """Initialize the LessonAI."""
        self.state: Optional[LessonState] = None
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()

    def _create_workflow(self) -> StateGraph:
        """Create the langgraph workflow."""
        workflow = StateGraph(LessonState)

        # Add nodes
        workflow.add_node("initialize", self._initialize)
        workflow.add_node("retrieve_syllabus", self._retrieve_syllabus)
        workflow.add_node("generate_lesson_content", self._generate_lesson_content)
        workflow.add_node("evaluate_response", self._evaluate_response)
        workflow.add_node("provide_feedback", self._provide_feedback)
        workflow.add_node("save_progress", self._save_progress)
        workflow.add_node("end", self._end)

        # Add edges
        workflow.add_edge("initialize", "retrieve_syllabus")
        workflow.add_edge("retrieve_syllabus", "generate_lesson_content")
        workflow.add_edge("generate_lesson_content", "end")
        workflow.add_edge("evaluate_response", "provide_feedback")
        workflow.add_edge("provide_feedback", "save_progress")
        workflow.add_edge("save_progress", "end")

        workflow.set_entry_point("initialize")
        return workflow

    def _initialize(
        self,
        state: Optional[LessonState] = None,
        topic: str = "",
        knowledge_level: str = "beginner",
        user_email: Optional[str] = None,
    ) -> Dict:
        """Initialize the state with the topic, user knowledge level, and user email."""
        # Debug print to see what's being passed
        print(f"_initialize called with state: {state}, topic: {topic}, knowledge_level: {knowledge_level}, user_email: {user_email}")

        # Check if topic is in state (which might be the case when called through the graph)
        if state and isinstance(state, dict) and "topic" in state and not topic:
            topic = state["topic"]
            knowledge_level = state.get("knowledge_level", knowledge_level)
            user_email = state.get("user_email", user_email)
            print(f"Using topic from state: {topic}")

        if not topic:
            raise ValueError("Topic is required")

        # Validate knowledge level
        valid_levels = ["beginner", "early learner", "good knowledge", "advanced"]
        if knowledge_level not in valid_levels:
            knowledge_level = "beginner"  # Default to beginner if invalid

        return {
            "topic": topic,
            "knowledge_level": knowledge_level,
            "syllabus": None,
            "lesson_title": None,
            "module_title": None,
            "generated_content": None,
            "user_responses": [],
            "user_performance": {},
            "user_email": user_email,
        }

    def _retrieve_syllabus(self, state: LessonState) -> Dict:
        """Retrieve the syllabus for the specified topic and knowledge level."""
        topic = state["topic"]
        knowledge_level = state["knowledge_level"]
        user_email = state.get("user_email")

        # Preserve module_title and lesson_title if they're in the inputs
        module_title = state.get("module_title")
        lesson_title = state.get("lesson_title")

        # Debug print
        print(f"_retrieve_syllabus: module_title={module_title}, lesson_title={lesson_title}")

        # Search for match on topic and knowledge level
        syllabus_query = Query()

        if user_email:
            # First try to find a user-specific version
            user_specific = syllabi_table.search(
                ((syllabus_query.topic == topic) | (syllabus_query.user_entered_topic == topic))
                & (syllabus_query.level.test(lambda x: x.lower() == knowledge_level.lower()))
                & (syllabus_query.user_id == user_email)
            )

            if user_specific:
                return {
                    "syllabus": user_specific[0],
                    "module_title": module_title,
                    "lesson_title": lesson_title
                }

        # If no user-specific version or no user_email provided, look for master version
        master_version = syllabi_table.search(
            ((syllabus_query.topic == topic) | (syllabus_query.user_entered_topic == topic))
            & (syllabus_query.level.test(lambda x: x.lower() == knowledge_level.lower()))
            & (syllabus_query.is_master == True)
        )

        if master_version:
            return {
                "syllabus": master_version[0],
                "module_title": module_title,
                "lesson_title": lesson_title
            }

        # If no syllabus found, return an error
        raise ValueError(f"No syllabus found for topic '{topic}' at level '{knowledge_level}'")

    def _generate_lesson_content(self, state: LessonState) -> Dict:
        """Generate lesson content based on the syllabus, module title, and lesson title."""
        # Access values from self.state instead of state parameter
        syllabus = self.state["syllabus"]
        lesson_title = self.state.get("lesson_title")
        module_title = self.state.get("module_title")
        knowledge_level = self.state["knowledge_level"]
        user_email = self.state.get("user_email")

        # Debug print
        print(f"_generate_lesson_content: module_title={module_title}, lesson_title={lesson_title}")

        # Check if module_title and lesson_title are provided
        if not module_title or not lesson_title:
            raise ValueError("Module title and lesson title are required")

        # Find the lesson in the syllabus
        lesson_found = False
        for module in syllabus["modules"]:
            if module["title"] == module_title:
                for lesson in module["lessons"]:
                    if lesson["title"] == lesson_title:
                        lesson_found = True
                        break
                if lesson_found:
                    break

        if not lesson_found:
            raise ValueError(f"Lesson '{lesson_title}' not found in module '{module_title}'")

        # Check if we already have generated content for this lesson
        lesson_uid = f"{syllabus['uid']}_{module_title}_{lesson_title}"
        lesson_query = Query()
        existing_content = db.table("lesson_content").search(lesson_query.lesson_uid == lesson_uid)

        if existing_content:
            return {"generated_content": existing_content[0]["content"], "lesson_uid": lesson_uid}

        # Read the system prompt
        with open("lessons/system_prompt.txt", "r", encoding="utf-8") as f:
            system_prompt = f.read()

        # Get user's previous performance if available
        previous_performance = {}
        if user_email:
            user_progress = user_progress_table.search(lesson_query.user_email == user_email)
            if user_progress:
                previous_performance = user_progress[0].get("performance", {})

        # Construct the prompt for Gemini
        prompt = f"""
        {system_prompt}

        ## Input Parameters
        - topic: {syllabus['topic']}
        - syllabus: {json.dumps(syllabus, indent=2)}
        - lesson_name: {lesson_title}
        - user_level: {knowledge_level}
        - previous_performance: {json.dumps(previous_performance, indent=2)}
        - time_constraint: 5 minutes

        Please generate the lesson content following the output format specified in the system prompt.
        """

        response = call_with_retry(model.generate_content, prompt)
        response_text = response.text

        # Extract JSON from response
        json_patterns = [
            # Pattern for JSON in code blocks
            r"```(?:json)?\s*({.*?})```",
            # Pattern for JSON with outer braces
            r'({[\s\S]*"exposition_content"[\s\S]*"thought_questions"[\s\S]*"active_exercises"[\s\S]*"knowledge_assessment"[\s\S]*"metadata"[\s\S]*})',
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
                    content = json.loads(json_str)
                    # Validate the structure
                    if all(
                        key in content
                        for key in [
                            "exposition_content",
                            "thought_questions",
                            "active_exercises",
                            "knowledge_assessment",
                            "metadata",
                        ]
                    ):
                        # Save the content to the database
                        now = datetime.now().isoformat()
                        lesson_content = {
                            "lesson_uid": lesson_uid,
                            "content": content,
                            "created_at": now,
                            "updated_at": now,
                        }
                        db.table("lesson_content").insert(lesson_content)

                        return {"generated_content": content, "lesson_uid": lesson_uid}
                except Exception as e:
                    # Continue to the next pattern if this one fails
                    print(f"Failed to parse JSON: {e}")

        # If all patterns fail, create a basic structure
        print(f"Failed to parse JSON from response: {response_text[:200]}...")
        basic_content = {
            "exposition_content": f"# {lesson_title}\n\nThis is a placeholder for the lesson content.",
            "thought_questions": [
                "What do you think about this topic?",
                "How might this apply to real-world scenarios?",
            ],
            "active_exercises": [
                {
                    "id": "ex1",
                    "type": "scenario",
                    "question": "Consider the following scenario...",
                    "expected_solution": "The correct approach would be...",
                    "hints": ["Think about...", "Consider..."],
                    "explanation": "This works because...",
                    "misconceptions": {
                        "common_error_1": "This is incorrect because...",
                        "common_error_2": "This approach fails because...",
                    },
                }
            ],
            "knowledge_assessment": [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "question": "Which of the following best describes...?",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": "Option B",
                    "explanation": "Option B is correct because...",
                }
            ],
            "metadata": {
                "tags": ["placeholder"],
                "difficulty": 3,
                "related_topics": ["Related Topic 1", "Related Topic 2"],
                "prerequisites": ["Prerequisite 1"],
            },
        }

        # Save the basic content to the database
        now = datetime.now().isoformat()
        lesson_content = {
            "lesson_uid": lesson_uid,
            "content": basic_content,
            "created_at": now,
            "updated_at": now,
        }
        db.table("lesson_content").insert(lesson_content)

        return {"generated_content": basic_content, "lesson_uid": lesson_uid}

    def _evaluate_response(self, state: LessonState, response: str, question_id: str) -> Dict:
        """Evaluate a user's response to a question."""
        generated_content = state["generated_content"]

        # Find the question in the content
        question = None
        question_type = None

        # Check active exercises
        for exercise in generated_content["active_exercises"]:
            if exercise["id"] == question_id:
                question = exercise
                question_type = "exercise"
                break

        # Check knowledge assessment
        if not question:
            for assessment in generated_content["knowledge_assessment"]:
                if assessment["id"] == question_id:
                    question = assessment
                    question_type = "assessment"
                    break

        if not question:
            raise ValueError(f"Question with ID '{question_id}' not found")

        # Construct the prompt for Gemini
        prompt = f"""
        You are evaluating a user's response to a {question_type}.

        Question: {question['question']}

        Expected solution or correct answer: {question.get('expected_solution') or question.get('correct_answer')}

        User's response: {response}

        Please evaluate the user's response and provide:
        1. A score between 0 and 1, where 1 is completely correct and 0 is completely incorrect
        2. Feedback explaining what was correct and what could be improved
        3. Whether the user has any misconceptions that should be addressed

        Format your response as a JSON object with the following structure:
        {
          "score": 0.75,
          "feedback": "Your feedback here...",
          "misconceptions": ["Misconception 1", "Misconception 2"]
        }
        """

        evaluation_response = call_with_retry(model.generate_content, prompt)
        evaluation_text = evaluation_response.text

        # Extract JSON from response
        json_patterns = [
            r"```(?:json)?\s*({.*?})```",
            r'({[\s\S]*"score"[\s\S]*"feedback"[\s\S]*"misconceptions"[\s\S]*})',
            r"({[\s\S]*})",
        ]

        for pattern in json_patterns:
            json_match = re.search(pattern, evaluation_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                json_str = re.sub(r"\\n", "", json_str)
                json_str = re.sub(r"\\", "", json_str)
                try:
                    evaluation = json.loads(json_str)
                    if all(key in evaluation for key in ["score", "feedback", "misconceptions"]):
                        # Add the response and evaluation to the user_responses list
                        user_response = {
                            "question_id": question_id,
                            "question_type": question_type,
                            "response": response,
                            "evaluation": evaluation,
                            "timestamp": datetime.now().isoformat(),
                        }

                        return {
                            "user_responses": state["user_responses"] + [user_response],
                        }
                except Exception:
                    pass

        # If all patterns fail, create a basic evaluation
        basic_evaluation = {
            "score": 0.5,
            "feedback": "I couldn't properly evaluate your response. Please try again.",
            "misconceptions": [],
        }

        user_response = {
            "question_id": question_id,
            "question_type": question_type,
            "response": response,
            "evaluation": basic_evaluation,
            "timestamp": datetime.now().isoformat(),
        }

        return {
            "user_responses": state["user_responses"] + [user_response],
        }

    def _provide_feedback(self, state: LessonState) -> Dict:
        """Provide feedback based on the user's responses."""
        user_responses = state["user_responses"]

        if not user_responses:
            return {}

        # Get the most recent response
        latest_response = user_responses[-1]

        # Return the evaluation as feedback
        return {
            "feedback": latest_response["evaluation"]["feedback"],
            "misconceptions": latest_response["evaluation"]["misconceptions"],
        }

    def _save_progress(self, state: LessonState) -> Dict:
        """Save the user's progress to the database."""
        user_email = state.get("user_email")

        if not user_email:
            return {}

        topic = state["topic"]
        syllabus = state["syllabus"]
        lesson_title = state["lesson_title"]
        module_title = state["module_title"]
        user_responses = state["user_responses"]

        # Calculate the overall score for this lesson
        assessment_scores = []
        for response in user_responses:
            if response["question_type"] == "assessment":
                assessment_scores.append(response["evaluation"]["score"])

        lesson_score = sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0

        # Get existing user progress
        user_query = Query()
        existing_progress = user_progress_table.search(user_query.user_email == user_email)

        now = datetime.now().isoformat()

        if existing_progress:
            progress = existing_progress[0]

            # Update the progress for this topic
            topic_progress = progress.get(topic, {})

            # Update completed lessons
            completed_lessons = topic_progress.get("completed_lessons", [])
            if lesson_title not in completed_lessons:
                completed_lessons.append(lesson_title)

            # Update performance
            performance = topic_progress.get("performance", {})
            performance[lesson_title] = {
                "score": lesson_score,
                "completed_at": now,
            }

            # Update the topic progress
            topic_progress["completed_lessons"] = completed_lessons
            topic_progress["current_lesson"] = lesson_title
            topic_progress["performance"] = performance

            # Calculate overall progress
            total_lessons = sum(len(module["lessons"]) for module in syllabus["modules"])
            overall_progress = len(completed_lessons) / total_lessons if total_lessons > 0 else 0

            # Calculate overall performance
            overall_performance = sum(perf["score"] for perf in performance.values()) / len(performance) if performance else 0

            topic_progress["overall_progress"] = overall_progress
            topic_progress["overall_performance"] = overall_performance

            # Update the progress object
            progress[topic] = topic_progress
            progress["updated_at"] = now

            # Update in the database
            user_progress_table.update(progress, user_query.user_email == user_email)

            return {"user_performance": performance[lesson_title]}
        else:
            # Create new progress entry
            performance = {
                lesson_title: {
                    "score": lesson_score,
                    "completed_at": now,
                }
            }

            # Calculate overall progress
            total_lessons = sum(len(module["lessons"]) for module in syllabus["modules"])
            overall_progress = 1 / total_lessons if total_lessons > 0 else 0

            topic_progress = {
                "completed_lessons": [lesson_title],
                "current_lesson": lesson_title,
                "performance": performance,
                "overall_progress": overall_progress,
                "overall_performance": lesson_score,
            }

            new_progress = {
                "user_email": user_email,
                "created_at": now,
                "updated_at": now,
                topic: topic_progress,
            }

            # Insert into the database
            user_progress_table.insert(new_progress)

            return {"user_performance": performance[lesson_title]}

    def _end(self, _: LessonState) -> Dict:
        """End the workflow."""
        return {}

    def initialize(self, topic: str, knowledge_level: str, user_email: Optional[str] = None) -> Dict:
        """Initialize the LessonAI with a topic, knowledge level, and user email."""
        inputs = {"topic": topic, "knowledge_level": knowledge_level, "user_email": user_email}
        self.state = self.graph.invoke(inputs)
        return self.state

    def get_lesson_content(self, module_title: str, lesson_title: str) -> Dict:
        """Get or generate content for a specific lesson."""
        if not self.state:
            raise ValueError("LessonAI not initialized. Call initialize() first.")

        # Update the state directly with module_title and lesson_title
        self.state["module_title"] = module_title
        self.state["lesson_title"] = lesson_title

        # Debug print
        print(f"get_lesson_content: module_title={module_title}, lesson_title={lesson_title}")
        print(f"Current state before invoke: {self.state}")

        # Invoke the graph starting at generate_lesson_content
        self.state = self.graph.invoke({}, {"current": "generate_lesson_content"})

        # Debug print
        print(f"State after invoke: {self.state}")

        return self.state["generated_content"]

    def evaluate_response(self, response: str, question_id: str) -> Dict:
        """Evaluate a user's response to a question."""
        if not self.state:
            raise ValueError("LessonAI not initialized. Call initialize() first.")

        inputs = {
            "response": response,
            "question_id": question_id,
        }

        self.state = self.graph.invoke(inputs, {"current": "evaluate_response"})
        return self.state["feedback"]

    def save_progress(self) -> Dict:
        """Save the user's progress."""
        if not self.state:
            raise ValueError("LessonAI not initialized. Call initialize() first.")

        self.state = self.graph.invoke({}, {"current": "save_progress"})
        return self.state["user_performance"]

    def get_user_progress(self, user_email: str, topic: Optional[str] = None) -> Dict:
        """Get the user's progress for a topic or all topics."""
        user_query = Query()
        progress = user_progress_table.search(user_query.user_email == user_email)

        if not progress:
            return {}

        if topic:
            return progress[0].get(topic, {})

        return progress[0]