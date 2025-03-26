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
    markdown_parts = []
    if isinstance(exposition_data, dict) and "content" in exposition_data:
        content_list = exposition_data.get("content", [])
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    text = item.get("text", "")
                    if item_type == "paragraph":
                        markdown_parts.append(text)
                    elif item_type == "heading":
                        level = item.get("level", 2)
                        markdown_parts.append(f"{'#' * level} {text}")
                    elif item_type == "thought_question":
                        question = item.get("question", "")
                        markdown_parts.append(f"> *Thought Question: {question}*")
                    else:
                        if text:
                            markdown_parts.append(text)
                elif isinstance(item, str):
                    markdown_parts.append(item)
        else:
            logger.warning(
                f"Exposition 'content' field is not a list: {type(content_list)}"
            )
            return ""
    elif isinstance(exposition_data, str):
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
            timeout=30,
        )
        logger.info(f"API response status: {response.status_code}")

        if response.ok:
            lesson_data = response.json()
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
    logger.info("Lesson content processed, passing raw summary.")
    return template_data


def _render_lesson(template_data, syllabus_id, module, lesson_id):
    """Renders the lesson template with processed data, converting markdown."""
    logger.info("Rendering lesson template.")

    # Convert exposition markdown to HTML
    exposition_markdown = template_data.get("exposition", "")
    if not isinstance(exposition_markdown, str):
        logger.error(
            "Processed exposition is not a string: "
            f"{type(exposition_markdown)}. Defaulting to empty."
        )
        exposition_markdown = ""
    template_data["exposition"] = markdown.markdown(exposition_markdown)

    # Convert exercise questions markdown to HTML
    for exercise in template_data.get("exercises", []):
        question_content = exercise.get("question", "")
        if not isinstance(question_content, str):
            logger.warning(
                f"Exercise question is not a string: {type(question_content)}. Defaulting."
            )
            question_content = ""
        exercise["question"] = markdown.markdown(question_content)

    # Summary processing is now handled in the template using the 'raw_summary' data
    logger.debug(f"Raw summary data being passed to template: {template_data.get('raw_summary')}")

    # Use the blueprint's template folder context
    try:
        return render_template(
            "lesson.html",
            user=session["user"],
            syllabus_id=syllabus_id,
            module=module,
            lesson_id=lesson_id,
            lesson_data=template_data,
        )
    except Exception as render_error:
        logger.error(f"Error during render_template: {render_error}", exc_info=True)
        logger.error(f"Data passed to template: {template_data}") # Log data on error
        raise # Re-raise the exception after logging


# --- Lesson Routes ---


@lessons_bp.route("/<syllabus_id>/<module>/<lesson_id>")
@login_required
def lesson(syllabus_id, module, lesson_id):
    """
    Displays a specific lesson.

    Fetches lesson data, processes it, and renders the template.
    Requires the user to be logged in.
    """
    logger.info(
        f"Entering lesson route: syllabus_id={syllabus_id}, module={module}, lesson_id={lesson_id}"
    )
    try:
        lesson_data = _fetch_lesson_data(syllabus_id, module, lesson_id)
        if lesson_data is None:
            return render_template(
                "lesson.html", user=session["user"], lesson_data=None
            )

        template_data = _process_lesson_content(lesson_data)
        if template_data is None:
            logger.error("Failed to process lesson content.")
            flash("An error occurred while processing the lesson content.")
            return render_template(
                "lesson.html", user=session["user"], lesson_data=None
            )

        return _render_lesson(template_data, syllabus_id, module, lesson_id)

    except Exception as e: #pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error in lesson route: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return render_template("lesson.html", user=session["user"], lesson_data=None)


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
