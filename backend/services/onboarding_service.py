""" Service for onboarding - new topics and user assessment """

import logging
from typing import Dict, Any, Optional
from backend.ai.app import TechTreeAI
from backend.services.sqlite_db import SQLiteDatabaseService

# Configure logging
logger = logging.getLogger(__name__)

# Import SQLiteDatabaseService for type hinting
from .sqlite_db import SQLiteDatabaseService

class OnboardingService:
    """ Service for onboarding - new topics and user assessment """
    # Require db_service and add type hint
    def __init__(self, db_service: SQLiteDatabaseService):
        logger.info("Initializing OnboardingService")
        self.tech_tree_ai = TechTreeAI()
        # Remove fallback
        self.db_service = db_service
        self.current_session = {}

    def _get_or_create_session(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get or create a session for the current user"""
        if not self.current_session:
            self.current_session = {
                "user_id": user_id,
                "topic": None,
                "questions": [],
                "responses": [],
                "difficulty_history": [],
                "is_complete": False,
                "knowledge_level": None,
                "score": 0
            }
        return self.current_session

    async def start_assessment(self, topic: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Initialize the assessment process"""
        logger.info(f"Starting assessment for topic: {topic}, user_id: {user_id}")
        logs = []
        logs.append(f"Starting assessment for topic: {topic}, user_id: {user_id}")
        try:
            session = self._get_or_create_session(user_id)
            session["topic"] = topic
            session["questions"] = []
            session["responses"] = []
            session["difficulty_history"] = []
            session["is_complete"] = False

            logs.append("Initializing TechTreeAI with topic")
            # Initialize TechTreeAI with the topic
            self.tech_tree_ai.initialize(topic)
            logs.append("TechTreeAI initialized successfully")

            logs.append("Performing search")
            result = self.tech_tree_ai.perform_search()
            logs.append(f"Search result: {result}")

            logs.append("Generating first question")
            # Generate first question
            question_result = self.tech_tree_ai.generate_question()
            logs.append(f"Question result: {question_result}")

            # Store question in session
            session["questions"].append(question_result["question"])
            session["difficulty_history"].append(question_result["difficulty_str"])

            logs.append("Assessment started successfully")
            return {
                "search_status": result["search_status"],
                "question": question_result["question"],
                "difficulty": question_result["difficulty_str"],
                "is_complete": False,
                "logs": logs
            }
        except Exception as e: #pylint: disable=broad-exception-caught
            logger.error(f"Error starting assessment: {str(e)}", exc_info=True)
            logs.append(f"Error starting assessment: {str(e)}")
            return {
                "error": str(e),
                "logs": logs
            }

    async def submit_answer(self, answer: str) -> Dict[str, Any]:
        """Process user's answer and generate next question or complete assessment"""
        session = self._get_or_create_session()

        if session["is_complete"]:
            return {
                "is_complete": True,
                "knowledge_level": session["knowledge_level"],
                "score": session["score"]
            }

        # Store user's response
        session["responses"].append(answer)

        # Process answer with AI
        result = self.tech_tree_ai.process_response(answer)

        # Check if assessment is complete
        if result["completed"]:
            knowledge_result = self.tech_tree_ai.get_final_assessment()

            session["is_complete"] = True
            session["knowledge_level"] = knowledge_result["knowledge_level"]
            session["score"] = knowledge_result.get("weighted_percentage", 0)

            # Save assessment to database if user_id exists
            if session["user_id"]:
                self.db_service.save_assessment(
                    user_id=session["user_id"],
                    topic=session["topic"],
                    knowledge_level=session["knowledge_level"],
                    score=session["score"],
                    questions=session["questions"],
                    responses=session["responses"]
                )

            return {
                "is_complete": True,
                "knowledge_level": session["knowledge_level"],
                "score": session["score"],
                "feedback": result["feedback"]
            }
        else:
            # Generate next question
            question_result = self.tech_tree_ai.generate_question()

            # Store question in session
            session["questions"].append(question_result["question"])
            session["difficulty_history"].append(question_result["difficulty_str"])

            return {
                "is_complete": False,
                "question": question_result["question"],
                "difficulty": question_result["difficulty_str"],
                "feedback": result["feedback"]
            }

    async def get_result(self) -> Dict[str, Any]:
        """Get the result of the completed assessment"""
        session = self._get_or_create_session()

        if not session["is_complete"]:
            raise ValueError("Assessment is not complete yet")

        return {
            "topic": session["topic"],
            "knowledge_level": session["knowledge_level"],
            "score": session["score"],
            "question_count": len(session["questions"])
        }

    def reset(self):
        """Reset the current session"""
        self.current_session = {}
