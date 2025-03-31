# frontend/syllabus/syllabus.py
""" Blueprint for the syllabus frontend """
import logging

import requests
from flask import (
    Blueprint,
    flash,
    render_template,
    session,
    current_app, # Import current_app
)

# Import the login_required decorator from the auth blueprint
# Assuming the auth blueprint is in the parent directory's auth package
from ..auth.auth import login_required

# Configure logging for the blueprint
logger = logging.getLogger(__name__)

# Define Blueprint
syllabus_bp = Blueprint(
    'syllabus',
    __name__,
    template_folder='../templates' # Point to the main templates folder
)

# API_URL is now accessed via current_app.config['API_URL']


# --- Syllabus Route ---

@syllabus_bp.route("/<topic>/<level>") # type: ignore[misc]
@login_required # Use the imported decorator
def syllabus_route(topic: str, level: str) -> str: # Renamed function slightly
    """
    Displays the syllabus for a given topic and level.

    Fetches the syllabus data from the backend API.
    Requires the user to be logged in.
    """
    logger.info(f"Fetching syllabus for topic: {topic}, level: {level}")
    try:
        api_url = current_app.config['API_URL']
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{api_url}/syllabus/topic/{topic}/level/{level}", # Use config value
            headers=headers,
            timeout=30,
        )

        if response.ok:
            syllabus_data = response.json()
            logger.info("Successfully fetched syllabus data.")
            return render_template( # type: ignore[no-any-return]
                "syllabus.html",
                user=session["user"],
                topic=topic,
                level=level,
                syllabus=syllabus_data,
            )
        else:
            logger.error(
                f"Failed to load syllabus. Status: {response.status_code}, Text: {response.text}")
            flash("Failed to load syllabus. Please try again later.")
            return render_template("syllabus.html", user=session["user"], syllabus=None) # type: ignore[no-any-return]
    except requests.RequestException as e:
        logger.error(f"Syllabus API request failed: {str(e)}")
        flash(f"Error loading syllabus: {str(e)}")
        return render_template("syllabus.html", user=session["user"], syllabus=None) # type: ignore[no-any-return]
    except Exception as e: #pylint: disable=broad-exception-caught
        logger.exception(f"Unexpected error loading syllabus: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}")
        return render_template("syllabus.html", user=session["user"], syllabus=None) # type: ignore[no-any-return]
