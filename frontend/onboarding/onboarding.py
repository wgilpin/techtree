# frontend/onboarding/onboarding.py
""" Blueprint for onboarding - syllabus creation and user level testing """

import logging
from typing import Any, Dict, Optional, cast, Union
import requests
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,  # Import current_app
)
from werkzeug.wrappers import Response as WerkzeugResponse # type: ignore[import-not-found]

# Configure logging for the blueprint
logger = logging.getLogger(__name__)

# Define Blueprint
onboarding_bp = Blueprint("onboarding", __name__, template_folder="../templates")

# API_URL is now accessed via current_app.config['API_URL']


# --- Onboarding API Helper Functions ---


def _start_assessment(topic: str) -> Optional[Dict[str, Any]]:
    """Calls the backend API to start a new assessment."""
    logger.info(f"Starting assessment for topic: {topic}")
    try:
        api_url = current_app.config["API_URL"]
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.post(
            f"{api_url}/onboarding/assessment",  # Use config value
            json={"topic": topic},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        # Cast the response to the expected type using typing.cast
        return cast(Optional[Dict[str, Any]], response.json())
    except requests.RequestException as e:
        logger.error(f"API error starting assessment: {str(e)}")
        flash(f"Error starting assessment: {str(e)}")
        return None
    except Exception as e: #pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error starting assessment: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return None


def _submit_answer(answer: Optional[str]) -> Optional[Dict[str, Any]]:
    """Calls the backend API to submit an assessment answer."""
    logger.info("Submitting assessment answer.")
    try:
        api_url = current_app.config["API_URL"]
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.post(
            f"{api_url}/onboarding/answer",  # Use config value
            json={"answer": answer},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        # Cast the response to the expected type using typing.cast
        return cast(Optional[Dict[str, Any]], response.json())
    except requests.RequestException as e:
        logger.error(f"API error submitting answer: {str(e)}")
        flash(f"Error processing answer: {str(e)}")
        return None
    except Exception as e: #pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error submitting answer: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return None
# --- Route Handlers ---


def _handle_onboarding_get(topic: Optional[str]) -> Union[WerkzeugResponse, str]:
    """Handles GET requests for the onboarding route."""
    if not topic:
        # Render a page to select a topic if none is provided
        logger.info("No topic provided for onboarding GET request.")
        return render_template("onboarding.html", user=session.get("user"), topic=None)

    # Check if user is logged in to start assessment
    if "user" not in session:
        flash("Please log in to start the assessment.")
        return redirect(url_for("auth.login"))

    result = _start_assessment(topic)
    if result:
        return render_template(
            "onboarding.html",
            user=session["user"],
            topic=topic,
            question=result.get("question"),
            difficulty=result.get("difficulty"),
        )
    else:
        # Error flash handled in _start_assessment
        return render_template("onboarding.html", user=session.get("user"), topic=None)


# pylint: disable=too-many-return-statements
def _handle_onboarding_post(topic: Optional[str]) -> Union[WerkzeugResponse, str]:
    """Handles POST requests for the onboarding route."""
    if "user" not in session:
        flash("Please log in to continue the assessment.")
        return redirect(url_for("auth.login"))

    if not topic:
        # Should ideally not happen if form includes topic or URL has it
        topic = request.form.get("topic")
        if not topic:
            flash("Topic missing. Cannot process answer.")
            return redirect(url_for("index"))  # Or some other default page
        # Redirect to GET with topic if it was missing in URL but present in form
        return redirect(
            url_for(".onboarding_route", topic=topic)
        )  # Use . for relative blueprint url_for

    answer = request.form.get("answer")
    if answer is None:
        flash("No answer provided.")
        return redirect(url_for(".onboarding_route", topic=topic))

    result = _submit_answer(answer)

    if result:
        if result.get("is_complete"):
            knowledge_level = result.get("knowledge_level")
            logger.info(
                f"Assessment complete for topic {topic}. Level: {knowledge_level}"
            )
            # Assuming syllabus route exists in the main app or another blueprint
            # Adjust 'syllabus.syllabus_route' if the blueprint/route name differs
            return redirect(url_for("syllabus.syllabus_route", topic=topic, level=knowledge_level))
        else:
            # Continue assessment
            logger.info("Assessment continuing.")
            return render_template(
                "onboarding.html",
                user=session["user"],
                topic=topic,
                question=result.get("question"),
                difficulty=result.get("difficulty"),
                feedback=result.get("feedback"),
            )
    else:
        # Error flash handled in _submit_answer
        # Redirect back to the start of the onboarding for the topic on error
        logger.warning("Redirecting to start of onboarding due to submission error.")
        return redirect(url_for(".onboarding_route", topic=topic))


# --- Main Blueprint Route ---


@onboarding_bp.route("/<topic>", methods=["GET", "POST"]) # type: ignore[misc]
@onboarding_bp.route( # type: ignore[misc]
    "/", defaults={"topic": None}, methods=["GET"]
)  # Handle base /onboarding/ route
def onboarding_route(topic: Optional[str]) -> Union[WerkzeugResponse, str]:
    """
    Handles the onboarding process for a given topic.
    Delegates to GET or POST handlers.
    """
    if request.method == "POST":
        return _handle_onboarding_post(topic)
    else:  # GET
        return _handle_onboarding_get(topic)
