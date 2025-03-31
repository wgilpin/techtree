# frontend/auth/auth.py
""" Blueprint for authentication and authorization """

import logging
from typing import Callable, Any, Union, Tuple
from functools import wraps

import requests
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app, # Import current_app
    Response as FlaskResponse,
)
from werkzeug.wrappers import Response as WerkzeugResponse # type: ignore[import-not-found]

# Configure logging for the blueprint
logger = logging.getLogger(__name__)

# Define Blueprint
auth_bp = Blueprint(
    'auth',
    __name__,
    template_folder='../templates' # Point to the main templates folder
)

# API_URL is now accessed via current_app.config['API_URL']

# --- Authentication Decorator ---
# Now lives here, can be imported by other blueprints
def login_required(
    f: Callable[..., Any]
) -> Callable[..., Union[WerkzeugResponse, str, FlaskResponse, Tuple[FlaskResponse, int]]]:
    """
    Decorator for routes that require a logged-in user.
    Redirects to the login page if the user is not in the session.
    """
    @wraps(f)
    def decorated_function(
        *args: Any, **kwargs: Any
    ) -> Union[WerkzeugResponse, str, FlaskResponse, Tuple[FlaskResponse, int]]:
        if "user" not in session:
            # Redirect to the login route within this blueprint
            return redirect(url_for("auth.login"))
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Use logger associated with this blueprint
            logger.error(f"Error in login_required decorator: {str(e)}")
            raise e
    return decorated_function

# --- Authentication Routes ---

@auth_bp.route("/login", methods=["GET", "POST"]) # type: ignore[misc]
def login() -> Union[WerkzeugResponse, str]:
    """Handles user login."""
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            api_url = current_app.config['API_URL']
            response = requests.post(
                f"{api_url}/auth/token", # CORRECTED: Changed /login to /token
                data={"username": email, "password": password},
                timeout=30,
            )

            if response.ok:
                user_data = response.json()
                session["user"] = {
                    "user_id": user_data["user_id"],
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "access_token": user_data["access_token"],
                }
                # Redirect to dashboard (assuming it's in the main app or another blueprint)
                # If dashboard is in main app, 'dashboard' works.
                # If in another blueprint, use 'blueprint_name.dashboard'.
                return redirect(url_for("dashboard"))
            else:
                # Try to get more specific error from backend if available
                try:
                    detail = response.json().get("detail", "Invalid credentials.")
                    error = f"Login failed: {detail}"
                except requests.exceptions.JSONDecodeError:
                    error = f"Login failed: Status {response.status_code}"

        except requests.RequestException as e:
            logger.error(f"Login error: {str(e)}")
            error = f"Login error: {str(e)}"

    # Render the login template (assuming it's in the shared templates folder)
    return render_template("login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"]) # type: ignore[misc]
def register() -> Union[WerkzeugResponse, str]:
    """Handles user registration."""
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        name = request.form.get("name")

        try:
            api_url = current_app.config['API_URL']
            response = requests.post(
                f"{api_url}/auth/register", # Use config value
                json={"email": email, "password": password, "name": name},
                timeout=30,
            )

            if response.ok:
                user_data = response.json()
                session["user"] = {
                    "user_id": user_data["user_id"],
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "access_token": user_data["access_token"],
                }
                return redirect(url_for("dashboard")) # Redirect to dashboard
            else:
                error = response.json().get(
                    "detail", "Registration failed. Please try again."
                )
        except requests.RequestException as e:
            logger.error(f"Registration error: {str(e)}")
            error = f"Registration error: {str(e)}"

    return render_template("register.html", error=error)


@auth_bp.route("/logout") # type: ignore[misc]
def logout() -> WerkzeugResponse:
    """Handles user logout."""
    session.pop("user", None)
    # Redirect to the login page within this blueprint
    return redirect(url_for("auth.login"))
