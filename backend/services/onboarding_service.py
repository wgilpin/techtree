# backend/services/onboarding_service.py
""" Service for onboarding - new topics and user assessment """

import logging
from typing import Dict, Any, Optional, List, TypedDict # Added List, TypedDict
# Import TechTreeAI for type hinting
from backend.ai.onboarding.onboarding_graph import TechTreeAI # Keep TechTreeAI import
from backend.services.sqlite_db import SQLiteDatabaseService

# Configure logging
logger = logging.getLogger(__name__)

# Define TypedDict for the structure held in self.current_session_state
class OnboardingSessionState(TypedDict):
    user_id: Optional[str]
    topic: Optional[str]
    questions: List[str]
    responses: List[str]
    difficulty_history: List[str] # Storing difficulty string representation
    is_complete: bool
    knowledge_level: Optional[str]
    score: float # Final percentage score

class OnboardingService:
    """ Service for onboarding - new topics and user assessment """
    # Require db_service and add type hint
    def __init__(self, db_service: SQLiteDatabaseService):
        logger.info("Initializing OnboardingService")
        # Each service instance manages one TechTreeAI instance.
        # If concurrency is needed, this AI instance management needs rethinking.
        self.tech_tree_ai_instance = TechTreeAI()
        self.db_service = db_service
        # This holds the state for the *single* active assessment managed by this service instance.
        # Add type hint here
        self.current_session_state: Optional[OnboardingSessionState] = None

    def _get_or_create_session(self, user_id: Optional[str] = None) -> OnboardingSessionState:
        """Get or create the single active session state for this service instance."""
        if self.current_session_state is None:
            logger.info(f"Creating new onboarding session state for user_id: {user_id}")
            # Ensure the created dictionary matches OnboardingSessionState
            self.current_session_state = {
                "user_id": user_id,
                "topic": None,
                "questions": [],
                "responses": [],
                "difficulty_history": [],
                "is_complete": False,
                "knowledge_level": None,
                "score": 0.0
            }
        # Ensure the return type matches the annotation
        return self.current_session_state

    async def start_assessment(self, topic: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Initialize the assessment process"""
        logger.info(f"Starting assessment for topic: {topic}, user_id: {user_id}")
        logs = []
        logs.append(f"Starting assessment for topic: {topic}, user_id: {user_id}")
        try:
            # Reset session state and AI instance for a new assessment
            self.current_session_state = None
            session = self._get_or_create_session(user_id)
            session["topic"] = topic
            self.tech_tree_ai_instance = TechTreeAI() # Create a fresh AI instance

            logs.append("Initializing TechTreeAI with topic")
            self.tech_tree_ai_instance.initialize(topic)
            logs.append("TechTreeAI initialized successfully")

            logs.append("Performing search")
            search_result = self.tech_tree_ai_instance.perform_search()
            logs.append(f"Search result: {search_result}")

            logs.append("Generating first question")
            question_result = self.tech_tree_ai_instance.generate_question()
            logs.append(f"Question result: {question_result}")

            # Store question in session state
            session["questions"].append(question_result["question"])
            session["difficulty_history"].append(question_result["difficulty_str"])

            logs.append("Assessment started successfully")
            return {
                "search_status": search_result.get("search_status", "Unknown"),
                "question": question_result["question"],
                "difficulty": question_result["difficulty_str"],
                "is_complete": False,
                "logs": logs
            }
        except Exception as e: #pylint: disable=broad-exception-caught
            logger.error(f"Error starting assessment: {str(e)}", exc_info=True)
            logs.append(f"Error starting assessment: {str(e)}")
            # Reset state on error?
            self.current_session_state = None
            return {
                "error": str(e),
                "logs": logs
            }

    async def submit_answer(self, answer: str) -> Dict[str, Any]:
        """Process user's answer and generate next question or complete assessment"""
        session = self._get_or_create_session() # Gets the current session state

        if session["is_complete"]:
            logger.info("Attempted to submit answer to already completed assessment.")
            return {
                "is_complete": True,
                "knowledge_level": session["knowledge_level"],
                "score": session["score"]
            }

        # Store user's response in session state
        session["responses"].append(answer)

        # Process answer with AI instance
        eval_result = self.tech_tree_ai_instance.evaluate_answer(answer)

        # Check if assessment is complete (AI instance tracks this)
        if self.tech_tree_ai_instance.is_complete():
            knowledge_result = self.tech_tree_ai_instance.get_final_assessment()

            # Update session state with final results
            session["is_complete"] = True
            session["knowledge_level"] = knowledge_result["knowledge_level"]
            session["score"] = knowledge_result.get("weighted_percentage", 0.0)

            # Save assessment to database if user_id exists
            user_id_to_save = session.get("user_id")
            if user_id_to_save:
                logger.info(f"Saving completed assessment for user {user_id_to_save}")
                try:
                    self.db_service.save_assessment(
                        user_id=user_id_to_save,
                        topic=session["topic"] or "Unknown",
                        knowledge_level=session["knowledge_level"] or "Unknown",
                        score=session["score"],
                        questions=session["questions"],
                        responses=session["responses"]
                    )
                    logger.info("Assessment saved successfully.")
                except Exception as db_err:
                    logger.error(f"Failed to save assessment to DB: {db_err}", exc_info=True)
            else:
                 logger.info("Assessment completed but not saved (no user_id).")

            return {
                "is_complete": True,
                "knowledge_level": session["knowledge_level"],
                "score": session["score"],
                "feedback": eval_result["feedback"]
            }
        else:
            # Generate next question using the AI instance
            question_result = self.tech_tree_ai_instance.generate_question()

            # Store question in session state
            session["questions"].append(question_result["question"])
            session["difficulty_history"].append(question_result["difficulty_str"])

            return {
                "is_complete": False,
                "question": question_result["question"],
                "difficulty": question_result["difficulty_str"],
                "feedback": eval_result["feedback"]
            }

    async def get_result(self) -> Dict[str, Any]:
        """Get the result of the completed assessment"""
        session = self._get_or_create_session() # Gets the current session state

        if not session["is_complete"]:
            raise ValueError("Assessment is not complete yet")

        # Return results stored in the session state
        return {
            "topic": session["topic"],
            "knowledge_level": session["knowledge_level"],
            "score": session["score"],
            "question_count": len(session["questions"])
        }

    # Added return type hint
    def reset(self) -> None:
        """Reset the current session state and the AI instance"""
        logger.info("Resetting onboarding session.")
        self.current_session_state = None
        self.tech_tree_ai_instance = TechTreeAI()
