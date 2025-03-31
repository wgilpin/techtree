# pylint: disable=logging-fstring-interpolation

"""
Main application module for the TechTree frontend.

This module contains the Flask application that serves as the frontend for the
TechTree learning platform. It handles user authentication, routing, and
interaction with the backend API.
"""
import logging
from typing import cast
import os

import requests
from dotenv import load_dotenv
from flask import current_app
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.wrappers import Response as WerkzeugResponse # type: ignore[import-not-found]
from werkzeug.routing.exceptions import BuildError # type: ignore[import-not-found] # Import BuildError
import markdown
from .auth.auth import auth_bp, login_required
from .lessons.lessons import lessons_bp
from .onboarding.onboarding import onboarding_bp
from .syllabus.syllabus import syllabus_bp


# Load environment variables from .env file
load_dotenv()


# Configure logging to use the same file as the backend
# Configure logging to use the same file as the backend, with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("techtree.log", encoding="utf-8")],
)
logger = logging.getLogger(__name__)
logger.info("Logging initialized in app.py")

# Suppress Werkzeug "Detected change" INFO logs
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.WARNING)
app = Flask(__name__)
"""
Flask application instance.
"""

# Register the markdown filter for Jinja2 templates
@app.template_filter('markdown') # type: ignore[misc]
def markdown_filter(text: str) -> str:
    """Converts a Markdown string to HTML."""
    return cast(str, markdown.markdown(text))

app.secret_key = "your-secret-key"  # For session management

# Load API_URL from environment variable into app config
# Load API_URL from environment variable into app config
# Provide a default value in case the environment variable is not set
app.config["API_URL"] = os.environ.get("API_URL", "http://localhost:8000")
logger.info(f"Backend API URL set to: {app.config['API_URL']}")

# NOTE: Standard directories like 'static' and 'templates' should exist
# as part of the project structure and be checked into version control.
# Runtime creation via os.makedirs is generally not recommended here.

# Authentication decorator moved to frontend.auth.auth

# --- Core App Routes ---


@app.route("/", methods=["GET", "POST"]) # type: ignore[misc]
def index() -> WerkzeugResponse:
    """
    Handles the main index route.

    If the user is logged in, redirects to the dashboard.
    Otherwise, redirects to the login page.
    Allows POST requests to initiate onboarding for a specific topic.
    """
    if request.method == "POST":
        topic = request.form.get("topic")
        if topic:
            # Use blueprint name in url_for: 'onboarding.onboarding_route'
            return redirect(url_for("onboarding.onboarding_route", topic=topic))

    if "user" in session:
        # Assuming dashboard route is still in this file or main app context
        return redirect(url_for("dashboard"))
    # Redirect to login route within the auth blueprint
    return redirect(url_for("auth.login"))


# Login, Register, Logout routes moved to frontend.auth.auth blueprint


@app.route("/dashboard") # type: ignore[misc]
@login_required  # This now refers to the imported decorator
def dashboard() -> str:
    """
    Displays the user's dashboard.

    Fetches in-progress courses from the backend API and displays them.
    Requires the user to be logged in.
    """
    courses_list = [] # Default to empty list
    try:
        api_url = current_app.config["API_URL"]
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{api_url}/progress/courses", headers=headers, timeout=30
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        # Extract the list of courses from the 'courses' key
        courses_list = response_data.get("courses", [])

    except requests.exceptions.HTTPError as http_err:
        # Handle specific HTTP errors (like 401 Unauthorized, 500 Internal Server Error)
        error_detail = "Failed to load courses."
        try:
            # Try to get a more specific error message from the backend response
            error_json = http_err.response.json()
            error_detail = error_json.get("detail", error_detail)
        except (ValueError, AttributeError):
            # If response is not JSON or doesn't have 'detail'
            error_detail = f"{error_detail} Status: {http_err.response.status_code}"
        logger.error(f"Dashboard HTTP error fetching courses: {error_detail}")
        flash(error_detail, "error")

    except requests.exceptions.RequestException as req_err:
        # Handle other request errors (connection, timeout, etc.)
        logger.error(f"Dashboard request error fetching courses: {req_err}", exc_info=True)
        flash(f"Error communicating with the server: {req_err}", "error")

    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error on dashboard: {e}")
        flash("An unexpected error occurred while loading the dashboard.", "error")

    # Always render the template, passing the (potentially empty) courses_list
    return cast(str, render_template(
        "dashboard.html", user=session["user"], courses=courses_list
    ))


# Onboarding routes moved to frontend.onboarding.onboarding blueprint

# Syllabus route moved to frontend.syllabus.syllabus blueprint


# --- Error Handlers ---
@app.errorhandler(BuildError) # type: ignore[misc]
def handle_build_error(e: BuildError) -> WerkzeugResponse:
    """Logs BuildError exceptions and redirects the user."""
    logger.error(f"URL Build Error: {e}", exc_info=True)
    flash("An internal error occurred building a URL. "
          "Please try again later or contact support if the issue persists.", "error")
    # Redirect to a safe page
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))


# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(lessons_bp, url_prefix="/lesson")
app.register_blueprint(onboarding_bp, url_prefix="/onboarding")
app.register_blueprint(
    syllabus_bp, url_prefix="/syllabus"
)  # Register syllabus blueprint


if __name__ == "__main__":
    # This block is useful for direct execution but won't work correctly
    # with the package structure and relative imports if run as `python frontend/app.py`.
    # Running via `flask run` (as configured in start_fe.sh and launch.json)
    # is the intended method.
    logger.warning(
        "Running app directly; intended method is 'flask run' from project root."
    )
    app.run(debug=True, port=5000)
