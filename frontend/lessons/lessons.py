# frontend/lessons/lessons.py
"""blueprint for lesson handling in the flask app"""

import logging
from typing import Optional, Union, Dict, List, Any # Added List, Any
import requests
import markdown
from flask import (
    Blueprint,
    flash,
    jsonify,  # Added for evaluate_exercise
    render_template,
    request,
    session,
    current_app,
)
from pydantic import ValidationError

# Assuming backend models are accessible via PYTHONPATH or similar mechanism
# Adjust the import path if necessary based on project structure
from backend.models import (
    GeneratedLessonContent,
    ExpositionContent,
    ExpositionContentItem,
    Exercise, # Import Exercise model
    AssessmentQuestion, # Import AssessmentQuestion model
)

from frontend.auth.auth import login_required  # Import the centralized decorator

# Configure logging for the blueprint
logger = logging.getLogger(__name__)

# Define Blueprint
# Using url_prefix='/lesson' might simplify routes later, but let's keep it explicit for now
lessons_bp = Blueprint("lessons", __name__, template_folder="../templates")


# --- Custom Jinja Filter for Markdown ---
@lessons_bp.app_template_filter("markdownify")
def markdownify_filter(text):
    """Converts markdown text to HTML."""
    # Use the markdown library with desired extensions if needed
    # e.g., markdown.markdown(text, extensions=['fenced_code', 'tables'])
    return markdown.markdown(text)


# API_URL is now accessed via current_app.config['API_URL']


# --- Helper function to format exposition (Copied from app.py) ---
def format_exposition_to_markdown(
    exposition_input: Optional[Union[str, ExpositionContent, Dict]],
) -> str:
    """
    Converts structured exposition content (Pydantic model, dict, or string)
    into a single markdown string.
    """
    logger.debug(
        f"DEBUG_FORMAT: Received exposition_input type: {type(exposition_input)}"
    )

    markdown_parts: List[str] = []

    # Handle if input is the Pydantic Model
    if isinstance(exposition_input, ExpositionContent):
        logger.debug("DEBUG_FORMAT: Processing ExpositionContent model.")
        content_data = exposition_input.content
        if isinstance(content_data, str):
            logger.debug("DEBUG_FORMAT: ExpositionContent.content is a string.")
            return content_data  # Return string directly
        elif isinstance(content_data, list):
            logger.debug(
                "DEBUG_FORMAT: Processing list from ExpositionContent.content."
            )
            for item in content_data:  # item should be ExpositionContentItem
                if isinstance(item, ExpositionContentItem):
                    item_type = item.type
                    text = item.text or ""  # Use attribute access, handle None

                    if item_type == "paragraph":
                        markdown_parts.append(text)
                    elif item_type == "heading":
                        level = item.level or 2  # Default to level 2 if None
                        markdown_parts.append(f"{'#' * level} {text}")
                    elif item_type == "list":
                        list_items = item.items or []
                        if list_items:  # Avoid adding empty list markers
                            md_list = "\n".join([f"- {li}" for li in list_items])
                            markdown_parts.append(md_list)
                    elif item_type == "thought_question":
                        question = item.question or ""
                        if question:  # Avoid adding empty thought question
                            markdown_parts.append(f"> *Thought Question: {question}*")
                    else:  # Fallback for unknown item types within the model list
                        logger.warning(
                            f"Unknown ExpositionContentItem type: {item_type}"
                        )
                        if text:  # Still append text if available
                            markdown_parts.append(text)
                else:
                    logger.warning(
                        f"Unexpected item type in ExpositionContent list: {type(item)}"
                    )
                    # Optionally try to convert to string or skip
                    markdown_parts.append(str(item))
        elif content_data is None:
            logger.debug("DEBUG_FORMAT: ExpositionContent.content is None.")
            return ""  # Return empty string if content is None
        else:
            logger.warning(
                f"Unexpected type for ExpositionContent.content: {type(content_data)}"
            )
            return ""  # Return empty string for unexpected types

    # Handle if input is a plain string
    elif isinstance(exposition_input, str):
        logger.debug("DEBUG_FORMAT: Processing as plain string.")
        return exposition_input

    # Handle if input is still a dictionary (e.g., validation failed upstream) - Legacy support
    elif isinstance(exposition_input, dict):
        logger.warning(
            "DEBUG_FORMAT: Processing as dictionary (fallback). "
            "Pydantic validation may have failed."
        )
        # Attempt to use the old logic as a fallback
        content_list = exposition_input.get("content", [])
        if isinstance(content_list, list):
            for item_dict in content_list:
                if isinstance(item_dict, dict):
                    item_type = item_dict.get("type")
                    text = item_dict.get("text", "")
                    if item_type == "paragraph":
                        markdown_parts.append(text)
                    elif item_type == "heading":
                        markdown_parts.append(
                            f"{'#' * item_dict.get('level', 2)} {text}"
                        )
                    elif item_type == "list":
                        markdown_parts.append(
                            "\n".join([f"- {li}" for li in item_dict.get("items", [])])
                        )
                    elif item_type == "thought_question":
                        markdown_parts.append(
                            f"> *Thought Question: {item_dict.get('question', '')}*"
                        )
                    elif text:
                        markdown_parts.append(text)
                elif isinstance(item_dict, str):
                    markdown_parts.append(item_dict)
        elif isinstance(
            exposition_input.get("content"), str
        ):  # Check if dict['content'] is string
            return exposition_input.get("content", "")

    # Handle None or other unexpected types
    elif exposition_input is None:
        logger.debug("DEBUG_FORMAT: Received None input.")
        return ""
    else:
        logger.warning(
            f"Unexpected exposition_input format: {type(exposition_input)}. Returning empty string."
        )
        return ""

    # Join the parts for list-based content
    return "\n\n".join(markdown_parts)


# --- Lesson Helper Functions (Copied from app.py) ---


def _fetch_lesson_data(syllabus_id: str, module: int, lesson_id: int) -> Optional[Dict]:
    """Fetches lesson data from the backend API."""
    logger.info(
        "Fetching lesson data for syllabus_id: "
        f"{syllabus_id}, module: {module}, lesson_id: {lesson_id}"
    )
    try:
        api_url = current_app.config["API_URL"]
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{api_url}/lesson/{syllabus_id}/{module}/{lesson_id}",  # Use config value
            headers=headers,
            timeout=300,
        )
        logger.info(f"API response status: {response.status_code}")

        if response.ok:
            lesson_data_dict = response.json()

            # Validate the 'content' part (exposition, metadata) using Pydantic
            raw_content_dict = lesson_data_dict.get("content")
            if raw_content_dict:
                try:
                    # Validate and store the model object within the dictionary
                    lesson_data_dict["content_model"] = (
                        GeneratedLessonContent.model_validate(raw_content_dict)
                    )
                    logger.info("Successfully validated lesson content using Pydantic.")
                except ValidationError as e:
                    logger.error(
                        f"Pydantic validation failed for lesson content: {e}",
                        exc_info=True,
                    )
                    # Decide how to handle validation failure:
                    # Option 1: Flash error and return None (prevents loading broken lesson)
                    flash(
                        "Failed to parse lesson content structure."
                        " The lesson might be displayed incorrectly."
                    )
                    # Option 2: Keep the raw dict but maybe flag it?
                    lesson_data_dict["content_model"] = (
                        None  # Explicitly set to None on failure
                    )
                    # return None # Or return None to prevent loading
            else:
                logger.warning("Backend response missing 'content' dictionary.")
                lesson_data_dict["content_model"] = (
                    None  # Ensure key exists even if content is missing
                )

            # Note: Exercises and assessments are expected to be at the top level
            # of lesson_data_dict (e.g., 'generated_exercises'), not inside 'content'.
            # They are likely generated by separate steps in the backend.

            logger.info("Successfully fetched lesson data dictionary.")
            return lesson_data_dict  # Return the dictionary possibly containing the validated model
        else:
            logger.error(
                f"Failed to load lesson. Status: {response.status_code}, Text: {response.text}"
            )
            flash("Failed to load lesson. Please try again later.")
            return None
    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        flash(f"Error fetching lesson data: {str(e)}")
        return None


def _process_lesson_content(lesson_data_dict: Dict) -> Optional[Dict]:
    """
    Processes lesson data, primarily using the validated Pydantic model for exposition,
    and retrieves exercises/assessments from the main data structure,
    preparing the format needed for the template.
    """
    logger.info("Processing lesson content using Pydantic model for exposition.")

    # Get the validated model for exposition/metadata from the dictionary
    content_model: Optional[GeneratedLessonContent] = lesson_data_dict.get(
        "content_model"
    )

    # Handle cases where validation might have failed or content was missing
    if not content_model:
        logger.error(
            "Validated content model (for exposition) not found in lesson data. Cannot process."
        )
        # Return a default structure or None, depending on how the route handles it
        # Returning None might be safer to prevent rendering errors.
        return None

    # Format exposition using the model
    # Pass the exposition part of the model to the formatting function
    exposition_markdown_str = format_exposition_to_markdown(
        content_model.exposition_content
    )

    # Get exercises and assessments from the main dictionary (lesson_data_dict)
    # These are generated separately from the main exposition content.
    # Use .get() with default empty list for safety
    exercises: List[Exercise] = lesson_data_dict.get("generated_exercises", [])
    assessment_questions: List[AssessmentQuestion] = lesson_data_dict.get(
        "generated_assessment_questions", []
    )

    # Prepare the dictionary to be returned, using data from the model and the main dict
    # This dictionary structure should match what the template expects
    processed_content = {
        "topic": content_model.topic or "",
        "level": content_model.level or "",
        # Access metadata safely
        "metadata": (
            content_model.metadata.model_dump() if content_model.metadata else {}
        ),
        # Convert the formatted exposition markdown string to HTML
        "exposition": markdown.markdown(exposition_markdown_str),
        # Pass the raw exercise and assessment definitions retrieved from the main dict
        # The template (lesson.html) will need to handle rendering these lists of objects
        "active_exercises": [ex.model_dump() for ex in exercises if ex], # Added 'if ex' for safety
        "knowledge_assessment": [
            q.model_dump() for q in assessment_questions if q # Added 'if q' for safety
        ],
    }

    logger.info("Lesson content processed (exposition from model, exercises/assessment from dict).")
    return processed_content


# _render_lesson function is removed as processing is simplified or moved


# --- Lesson Routes ---


@lessons_bp.route(
    "/<syllabus_id>/<module>/<lesson_id>"
)  # Assuming module/lesson_id are indices
@login_required
def lesson(syllabus_id: str, module: str, lesson_id: str):
    """
    Displays a specific lesson, including exposition and chat state.

    Fetches lesson data (content structure + conversational state)
    and renders the template. Requires the user to be logged in.
    """
    logger.info(
        # Route parameters are strings, ensure indices are integers if needed later
        f"Entering lesson route: syllabus_id={syllabus_id}, module={module}, lesson_id={lesson_id}"
    )
    try:
        # Convert route params early
        module_index = int(module)
        lesson_index = int(lesson_id)  # Assuming lesson_id route param is the index
    except ValueError:
        logger.error(
            f"Invalid module/lesson index in route: module={module}, lesson_id={lesson_id}"
        )
        flash("Invalid lesson URL.")
        # Redirect to syllabus or dashboard?
        return render_template(
            "lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None
        )

    try:
        # Fetch the combined data (content + state) from the backend
        # Pass integer indices to the fetch function
        backend_response = _fetch_lesson_data(syllabus_id, module_index, lesson_index)
        if backend_response is None:
            # _fetch_lesson_data already flashes a message
            return render_template(
                "lesson.html",
                user=session.get("user"),
                lesson_data=None,
                lesson_state=None,
            )

        # Extract state and raw content
        lesson_state = backend_response.get("lesson_state")
        # Use "content" key, which should now be correctly populated by the backend router
        raw_content = backend_response.get("content") # This is the exposition/metadata part

        if raw_content is None:
            logger.error("Backend response missing 'content' (exposition/metadata).")
            flash("Failed to load lesson content structure.")
            return render_template(
                "lesson.html",
                user=session.get("user"),
                lesson_data=None,
                lesson_state=None,
            )

        # Process the raw content (e.g., format exposition markdown)
        # Pass the full backend_response which contains the validated 'content_model'
        # and potentially 'generated_exercises'/'generated_assessment_questions'
        processed_content = _process_lesson_content(backend_response)
        if processed_content is None:
            logger.error("Failed to process lesson content.")
            flash("An error occurred while processing the lesson content.")
            return render_template(
                "lesson.html",
                user=session.get("user"),
                lesson_data=None,
                lesson_state=None,
            )

        # Prepare data for the template
        lesson_data_for_template = {
            "lesson_id": backend_response.get(
                "lesson_id"
            ),  # Actual lesson PK/ID from backend
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": processed_content,  # Pass the processed content dict
            # is_new is also available in backend_response if needed
        }

        # Render the template directly, passing both content data and state
        return render_template(
            "lesson.html",
            user=session.get("user"),
            syllabus_id=syllabus_id,  # Pass for JS URL construction
            lesson_data=lesson_data_for_template,  # Contains processed content and indices
            lesson_state=lesson_state,  # Pass the conversational state
        )

    except (
        ValueError
    ) as e:  # Catch specific errors like invalid indices from conversion
        logger.error(f"Value error in lesson route: {e}", exc_info=True)
        flash(str(e))
        # Redirect? Show error page? For now, render template with None
        return render_template(
            "lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error in lesson route: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return render_template(
            "lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None
        )


# --- NEW Chat POST Route ---
@lessons_bp.route(
    "/chat/<syllabus_id>/<int:module_index>/<int:lesson_index>", methods=["POST"]
)
@login_required
def lesson_chat(syllabus_id: str, module_index: int, lesson_index: int):
    """
    Handles incoming chat messages from the frontend, forwards to the backend API,
    and returns the AI's response.
    """
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    logger.info(
        f"Received chat message for lesson {syllabus_id}/{module_index}/{lesson_index}: "
        f"'{user_message[:50]}...'"
    )

    try:
        api_url = current_app.config["API_URL"]
        backend_chat_url = (
            f"{api_url}/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}"
        )
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}

        # Forward the request to the backend API
        backend_response = requests.post(
            backend_chat_url,
            headers=headers,
            json={"message": user_message},
            timeout=60,  # Set appropriate timeout for potentially long AI responses
        )

        # Check if the backend request was successful
        backend_response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        # Return the JSON response from the backend directly to the frontend JS
        response_data = backend_response.json()
        logger.info(f"Received backend response: {response_data}")
        return jsonify(response_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling backend chat API: {e}", exc_info=True)
        # Check if the error response from backend was JSON
        error_detail = "Failed to communicate with the learning assistant."
        if e.response is not None:
            try:
                error_json = e.response.json()
                error_detail = error_json.get("detail", error_detail)
            except ValueError:  # If response is not JSON
                error_detail = f"{error_detail} Status: {e.response.status_code}"

        return jsonify({"error": error_detail}), 502  # Bad Gateway or appropriate error
    except Exception as e:
        logger.exception(f"Unexpected error in lesson_chat route: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@lessons_bp.route("/exercise/evaluate", methods=["POST"])
@login_required
def evaluate_exercise():
    """
    Evaluates a user's answer to an exercise.

    Sends the answer to the backend API for evaluation and returns the result.
    Requires the user to be logged in.
    """
    data = request.json
    lesson_id = data.get("lesson_id")
    exercise_index = data.get("exercise_index")
    answer = data.get("answer")
    logger.info(f"Evaluating exercise: lesson_id={lesson_id}, index={exercise_index}")

    try:
        api_url = current_app.config["API_URL"]
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.post(
            f"{api_url}/lesson/exercise/evaluate",  # Use config value
            json={
                "lesson_id": lesson_id,
                "exercise_index": exercise_index,
                "answer": answer,
            },
            headers=headers,
            timeout=30,
        )

        if response.ok:
            evaluation_result = response.json()
            logger.info(f"Evaluation result: {evaluation_result}")
            return jsonify(evaluation_result)
        else:
            logger.error(
                f"Exercise evaluation failed: {response.status_code} - {response.text}"
            )
            return (
                jsonify({"error": "Failed to evaluate exercise"}),
                response.status_code,
            )

    except requests.RequestException as e:
        logger.error(f"API request failed during evaluation: {str(e)}")
        return jsonify({"error": f"API request failed: {str(e)}"}), 500
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error during exercise evaluation: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@lessons_bp.route("/assessment/submit", methods=["POST"])
@login_required
def submit_assessment():
    """
    Receives and processes submitted answers for the knowledge assessment.
    """
    data = request.json
    lesson_id = data.get("lesson_id")
    answers = data.get("answers")  # Expected format: {"0": "A", "1": "True", ...}
    user_id = session.get("user", {}).get("id")

    logger.info(
        f"Received assessment submission for lesson_id: {lesson_id} by user_id: {user_id}"
    )
    logger.info(f"Answers: {answers}")

    if not lesson_id or not answers or user_id is None:
        logger.warning(
            "Missing lesson_id, answers, or user_id in assessment submission."
        )
        return jsonify({"error": "Missing required data"}), 400

    # --- Placeholder for backend processing ---
    # Here you would typically:
    # 1. Fetch the correct answers for the assessment from the backend/DB.
    # 2. Compare user's answers with correct answers.
    # 3. Calculate a score or provide feedback.
    # 4. Store the results (e.g., in the database associated with the user and lesson).
    # 5. Potentially call the backend API to record completion or score.
    # Example API call (if needed):
    # try:
    #     api_url = current_app.config["API_URL"]
    #     headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
    #     response = requests.post(
    #         f"{api_url}/lesson/assessment/record", # Hypothetical endpoint
    #         json={"lesson_id": lesson_id, "user_id": user_id, "answers": answers},
    #         headers=headers,
    #         timeout=15,
    #     )
    #     if not response.ok:
    #         logger.error(
    #           f"Failed to record assessment results: {response.status_code} - {response.text}")
    #         # Handle error appropriately
    # except requests.RequestException as e:
    #     logger.error(f"API request failed during assessment recording: {str(e)}")
    #     # Handle error appropriately
    # --- End Placeholder ---

    # For now, just return a success message
    return jsonify(
        {"message": "Assessment submitted successfully.", "received_answers": answers}
    )
