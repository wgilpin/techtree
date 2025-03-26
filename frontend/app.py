# pylint: disable=logging-fstring-interpolation

"""
Main application module for the TechTree frontend.

This module contains the Flask application that serves as the frontend for the
TechTree learning platform. It handles user authentication, routing, and
interaction with the backend API.
"""
import logging
import os

import requests
from dotenv import load_dotenv
from flask import current_app
from flask import Flask, flash, redirect, render_template, request, session, url_for
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

app.secret_key = "your-secret-key"  # For session management

# Load API_URL from environment variable into app config
# Provide a default value in case the environment variable is not set
app.config["API_URL"] = os.environ.get("API_URL", "http://localhost:8000")
logger.info(f"Backend API URL set to: {app.config['API_URL']}")

# NOTE: Standard directories like 'static' and 'templates' should exist
# as part of the project structure and be checked into version control.
# Runtime creation via os.makedirs is generally not recommended here.

# Authentication decorator moved to frontend.auth.auth


# --- Core App Routes ---


@app.route("/", methods=["GET", "POST"])
def index():
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


@app.route("/dashboard")
@login_required  # This now refers to the imported decorator
def dashboard():
    """
    Displays the user's dashboard.

    Fetches in-progress courses from the backend API and displays them.
    Requires the user to be logged in.
    """
    try:
        # Get in-progress courses
        api_url = current_app.config["API_URL"]  # Get URL from app config
        headers = {"Authorization": f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{api_url}/progress/courses", headers=headers, timeout=30
        )

        if response.ok:
            courses = response.json()
            return render_template(
                "dashboard.html", user=session["user"], courses=courses
            )
        flash("Failed to load courses. Please try again later.")
        return render_template("dashboard.html", user=session["user"], courses=[])
    except requests.RequestException as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash(f"Error: {str(e)}")
        return render_template("dashboard.html", user=session["user"], courses=[])


# Onboarding routes moved to frontend.onboarding.onboarding blueprint

# Syllabus route moved to frontend.syllabus.syllabus blueprint


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
