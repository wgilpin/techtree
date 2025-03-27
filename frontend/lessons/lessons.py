# frontend/lessons/lessons.py
"""blueprint for lesson handling in the flask app"""

import logging

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
from frontend.auth.auth import login_required  # Import the centralized decorator

# Configure logging for the blueprint
logger = logging.getLogger(__name__)

# Define Blueprint
# Using url_prefix='/lesson' might simplify routes later, but let's keep it explicit for now
lessons_bp = Blueprint("lessons", __name__, template_folder="../templates")

# API_URL is now accessed via current_app.config['API_URL']


# --- Helper function to format exposition (Copied from app.py) ---
def format_exposition_to_markdown(exposition_data):
    """
    Converts the structured exposition content from the API
    into a single markdown string.
    """
    logger.debug(f"DEBUG_FORMAT: Received exposition_data type: {type(exposition_data)}") # DEBUG LOG
    logger.debug(f"DEBUG_FORMAT: Received exposition_data type: {type(exposition_data)}") # DEBUG LOG
    logger.debug(f"DEBUG_FORMAT: Received exposition_data keys: {list(exposition_data.keys()) if isinstance(exposition_data, dict) else 'N/A'}") # DEBUG LOG
    # Check for the 'content' key which contains the list of content items
    has_content = isinstance(exposition_data, dict) and "content" in exposition_data
    logger.debug(f"DEBUG_FORMAT: 'content' key found: {has_content}") # DEBUG LOG

    markdown_parts = []
    # Check for the 'content' key which contains the list of content items
    if has_content:
        logger.debug("DEBUG_FORMAT: Processing 'content' block.") # DEBUG LOG
        content_list = exposition_data.get("content", []) # Get the list from 'content'
        if isinstance(content_list, list):
            for item in content_list: # Iterate through items in 'content' list
                if isinstance(item, dict):
                    # Process based on 'type' key within each item
                    item_type = item.get("type")
                    text = item.get("text", "") # Common field

                    if item_type == "paragraph":
                        markdown_parts.append(text)
                    elif item_type == "heading":
                        level = item.get("level", 2) # Default to level 2 if not specified
                        markdown_parts.append(f"{'#' * level} {text}")
                    elif item_type == "list": # Handle lists if they appear
                         list_items = item.get("items", [])
                         md_list = "\n".join([f"- {li}" for li in list_items])
                         markdown_parts.append(md_list)
                    elif item_type == "thought_question": # Handle thought questions if they appear
                         question = item.get("question", "")
                         markdown_parts.append(f"> *Thought Question: {question}*")
                    else: # Fallback for unknown dict types
                        if text:
                            markdown_parts.append(text)

                elif isinstance(item, str): # Fallback if an item in the list is just a string
                    markdown_parts.append(item)
        else:
            logger.warning(
                f"Exposition 'content' field is not a list: {type(content_list)}"
            )
            return ""
    elif isinstance(exposition_data, str):
        logger.debug("DEBUG_FORMAT: Processing as plain string.") # DEBUG LOG
        logger.info("Exposition data is a plain string.")
        return exposition_data
    else:
        logger.warning(
            f"Unexpected exposition_data format: {type(exposition_data)}. Returning empty string."
        )
        return ""
    return "\n\n".join(markdown_parts)


# --- Lesson Helper Functions (Copied from app.py) ---


def _fetch_lesson_data(syllabus_id, module, lesson_id):
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
            lesson_data = response.json()
            # --- ADDED LOGGING ---
            logger.info(f"Raw lesson data received from backend: {lesson_data}")
            # --- END LOGGING ---
            logger.info("Successfully fetched lesson data.")
            return lesson_data
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


def _process_lesson_content(lesson_data):
    """Processes raw lesson data into the format needed for the template."""
    logger.info("Processing lesson content.")
    content_data = lesson_data.get("content")
    if not isinstance(content_data, dict):
        logger.error(f"Lesson 'content' is not a dictionary: {type(content_data)}")
        return None

    # Format exercises
    formatted_exercises = []
    active_exercises = content_data.get("active_exercises", [])
    if isinstance(active_exercises, list):
        for exercise in active_exercises:
            if isinstance(exercise, dict):
                exercise_type = exercise.get("type", "open_ended")
                formatted_exercise = {
                    "question": exercise.get("instructions", ""),
                    "type": exercise_type,
                    "answer": exercise.get("correct_answer", ""),
                }
                # Add 'items' if it's an ordering exercise
                if exercise_type == 'ordering':
                    formatted_exercise["ordering_items"] = exercise.get("items", []) # Renamed key
                formatted_exercises.append(formatted_exercise)
    else:
        logger.warning(f"active_exercises is not a list: {type(active_exercises)}")

    # Format exposition
    exposition_markdown = format_exposition_to_markdown(
        content_data.get("exposition_content", {})
    )

    # Format summary (knowledge assessment)
    summary_list = content_data.get("knowledge_assessment", [])
    if not isinstance(summary_list, list):
        logger.warning(f"knowledge_assessment is not a list: {type(summary_list)}")
        summary_list = []

    template_data = {
        "module_index": lesson_data.get("module_index"),
        "lesson_index": lesson_data.get("lesson_index"),
        "lesson_id": lesson_data.get("lesson_id"),
        "topic": content_data.get("topic", ""),
        "level": content_data.get("level", ""),
        "title": content_data.get("metadata", {}).get("title", ""),
        "exposition": exposition_markdown, # Keep processed exposition
        "exercises": formatted_exercises, # Keep processed exercises
        "raw_summary": summary_list, # Pass the raw summary list under a new key
        "summary": [], # Keep summary key but make it empty, as it's processed in template now
    }
    logger.info("Lesson content processed (exposition only).")

    # Return only the processed content dict, not the full template_data structure
    processed_content = {
        "topic": content_data.get("topic", ""),
        "level": content_data.get("level", ""),
        "metadata": content_data.get("metadata", {}),
        "exposition": markdown.markdown(exposition_markdown), # Convert exposition here
        # Exercises and summary are no longer processed here
        "active_exercises": content_data.get("active_exercises", []), # Pass raw definitions
        "knowledge_assessment": content_data.get("knowledge_assessment", []) # Pass raw definitions
    }
    return processed_content

# _render_lesson function is removed as processing is simplified or moved


# --- Lesson Routes ---


@lessons_bp.route("/<syllabus_id>/<module>/<lesson_id>") # Assuming module/lesson_id are indices
@login_required
def lesson(syllabus_id, module, lesson_id):
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
        lesson_index = int(lesson_id) # Assuming lesson_id route param is the index
    except ValueError:
        logger.error(f"Invalid module/lesson index in route: module={module}, lesson_id={lesson_id}")
        flash("Invalid lesson URL.")
        # Redirect to syllabus or dashboard?
        return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)

    try:
        # Fetch the combined data (content + state) from the backend
        # Pass integer indices to the fetch function
        backend_response = _fetch_lesson_data(syllabus_id, module_index, lesson_index)
        if backend_response is None:
            # _fetch_lesson_data already flashes a message
            return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)

        # Extract state and raw content
        lesson_state = backend_response.get("lesson_state")
        # Use "content" key, which should now be correctly populated by the backend router
        raw_content = backend_response.get("content")

        if raw_content is None:
             logger.error("Backend response missing 'content'.")
             flash("Failed to load lesson content structure.")
             return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)

        # Process the raw content (e.g., format exposition markdown)
        # Pass raw_content directly, _process_lesson_content expects dict with 'content' key
        processed_content = _process_lesson_content({"content": raw_content})
        if processed_content is None:
            logger.error("Failed to process lesson content.")
            flash("An error occurred while processing the lesson content.")
            return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)

        # Prepare data for the template
        lesson_data_for_template = {
            "lesson_id": backend_response.get("lesson_id"), # Actual lesson PK/ID from backend
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": processed_content, # Pass the processed content dict
            # is_new is also available in backend_response if needed
        }

        # Render the template directly, passing both content data and state
        return render_template(
            "lesson.html",
            user=session.get("user"),
            syllabus_id=syllabus_id, # Pass for JS URL construction
            lesson_data=lesson_data_for_template, # Contains processed content and indices
            lesson_state=lesson_state # Pass the conversational state
        )

    except ValueError as e: # Catch specific errors like invalid indices from conversion
         logger.error(f"Value error in lesson route: {e}", exc_info=True)
         flash(str(e))
         # Redirect? Show error page? For now, render template with None
         return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)
    except Exception as e: #pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error in lesson route: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return render_template("lesson.html", user=session.get("user"), lesson_data=None, lesson_state=None)


# --- NEW Chat POST Route ---
@lessons_bp.route("/chat/<syllabus_id>/<int:module_index>/<int:lesson_index>", methods=["POST"])
@login_required
def lesson_chat(syllabus_id, module_index, lesson_index):
    """
    Handles incoming chat messages from the frontend, forwards to the backend API,
    and returns the AI's response.
    """
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if 'user' not in session:
         return jsonify({"error": "User not logged in"}), 401

    logger.info(f"Received chat message for lesson {syllabus_id}/{module_index}/{lesson_index}: '{user_message[:50]}...'")

    try:
        api_url = current_app.config["API_URL"]
        backend_chat_url = f"{api_url}/lesson/chat/{syllabus_id}/{module_index}/{lesson_index}"
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}

        # Forward the request to the backend API
        backend_response = requests.post(
            backend_chat_url,
            headers=headers,
            json={"message": user_message},
            timeout=60,  # Set appropriate timeout for potentially long AI responses
        )

        # Check if the backend request was successful
        backend_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

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
            except ValueError: # If response is not JSON
                 error_detail = f"{error_detail} Status: {e.response.status_code}"

        return jsonify({"error": error_detail}), 502 # Bad Gateway or appropriate error
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
    except Exception as e: #pylint: disable=broad-exception-caught
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
    answers = data.get("answers") # Expected format: {"0": "A", "1": "True", ...}
    user_id = session.get("user", {}).get("id")

    logger.info(f"Received assessment submission for lesson_id: {lesson_id} by user_id: {user_id}")
    logger.info(f"Answers: {answers}")

    if not lesson_id or not answers or user_id is None:
        logger.warning("Missing lesson_id, answers, or user_id in assessment submission.")
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
    #         logger.error(f"Failed to record assessment results: {response.status_code} - {response.text}")
    #         # Handle error appropriately
    # except requests.RequestException as e:
    #     logger.error(f"API request failed during assessment recording: {str(e)}")
    #     # Handle error appropriately
    # --- End Placeholder ---

    # For now, just return a success message
    return jsonify({"message": "Assessment submitted successfully.", "received_answers": answers})
