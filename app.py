#pylint: disable=logging-fstring-interpolation

"""
Main application module for the TechTree frontend.

This module contains the Flask application that serves as the frontend for the
TechTree learning platform. It handles user authentication, routing, and
interaction with the backend API.
"""
import logging
import os
from functools import wraps

import requests
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)

# Configure logging to use the same file as the backend
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('techtree.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
"""
Flask application instance.
"""

app.secret_key = "your-secret-key"  # For session management
API_URL = "http://localhost:8000"  # Your FastAPI backend

# Create necessary directories
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('static/images', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('templates/components', exist_ok=True)

# Authentication decorator
def login_required(f):
    """
    Decorator for routes that require a logged-in user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles the main index route.

    If the user is logged in, redirects to the dashboard.
    Otherwise, redirects to the login page.
    Allows POST requests to initiate onboarding for a specific topic.
    """
    if request.method == "POST":
        topic = request.form.get('topic')
        if topic:
            return redirect(url_for('onboarding', topic=topic))

    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user login.

    If the login is successful, stores user data in the session and redirects
    to the dashboard.
    If the login fails, displays an error message.
    """
    error = None
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Call FastAPI auth endpoint using form data format
            response = requests.post(
                f"{API_URL}/auth/login",
                data={
                    'username': email,
                    'password': password
                },
                timeout=30
            )

            if response.ok:
                user_data = response.json()
                # Store user data in session
                session['user'] = {
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'access_token': user_data['access_token']
                }
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid credentials. Please try again."
        except requests.RequestException as e:
            logger.error(f"Login error: {str(e)}")
            error = f"Login error: {str(e)}"

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Handles user registration.

    If the registration is successful, stores user data in the session and
    redirects to the dashboard.
    If the registration fails, displays an error message.
    """
    error = None
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')

        try:
            # Call FastAPI register endpoint
            response = requests.post(
                f"{API_URL}/auth/register",
                json={
                    'email': email,
                    'password': password,
                    'name': name
                },
                timeout=30
            )

            if response.ok:
                user_data = response.json()
                # Store user data in session
                session['user'] = {
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'access_token': user_data['access_token']
                }
                return redirect(url_for('dashboard'))
            else:
                error = response.json().get('detail', 'Registration failed. Please try again.')
        except requests.RequestException as e:
            logger.error(f"Registration error: {str(e)}")
            error = f"Registration error: {str(e)}"

    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    """
    Handles user logout.

    Removes user data from the session and redirects to the login page.
    """
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    """
    Displays the user's dashboard.

    Fetches in-progress courses from the backend API and displays them.
    Requires the user to be logged in.
    """
    try:
        # Get in-progress courses
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/progress/courses",
            headers=headers,
            timeout=30
        )

        if response.ok:
            courses = response.json()
            return render_template("dashboard.html", user=session['user'], courses=courses)
        else:
            flash("Failed to load courses. Please try again later.")
            return render_template("dashboard.html", user=session['user'], courses=[])
    except requests.RequestException as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash(f"Error: {str(e)}")
        return render_template("dashboard.html", user=session['user'], courses=[])

@app.route("/onboarding/<topic>", methods=["GET", "POST"])
def onboarding(topic=None):
    """
    Handles the onboarding process for a given topic.

    If the request method is POST, processes the user's answer and either
    continues the assessment or redirects to the syllabus page.
    If the request method is GET, starts a new assessment for the given topic.
    """
    if request.method == "POST":
        if not topic:
            topic = request.form.get('topic')
            return redirect(url_for('onboarding', topic=topic))

        answer = request.form.get('answer')
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}

        try:
            response = requests.post(
                f"{API_URL}/onboarding/answer",
                json={'answer': answer},
                headers=headers,
                timeout=30
            )

            if response.ok:
                result = response.json()
                if result.get('is_complete'):
                    # Assessment complete, redirect to syllabus
                    knowledge_level = result.get('knowledge_level')
                    return redirect(url_for('syllabus', topic=topic, level=knowledge_level))

                # Continue assessment
                return render_template(
                    "onboarding.html",
                    user=session['user'],
                    topic=topic,
                    question=result.get('question'),
                    difficulty=result.get('difficulty'),
                    feedback=result.get('feedback')
                )
            else:
                flash("Failed to process your answer. Please try again.")
        except requests.RequestException as e:
            logger.error(f"Onboarding error: {str(e)}")
            flash(f"Error: {str(e)}")

    # GET request or initial load
    if topic:
        try:
            headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
            response = requests.post(
                f"{API_URL}/onboarding/assessment",
                json={'topic': topic},
                headers=headers,
                timeout=30
            )

            if response.ok:
                result = response.json()
                return render_template(
                    "onboarding.html",
                    user=session['user'],
                    topic=topic,
                    question=result.get('question'),
                    difficulty=result.get('difficulty')
                )
            else:
                flash("Failed to start assessment. Please try again.")
                return render_template("onboarding.html", user=session['user'], topic=None)
        except requests.RequestException as e:
            logger.error(f"Onboarding error: {str(e)}")
            flash(f"Error: {str(e)}")
            return render_template("onboarding.html", user=session['user'], topic=None)
    else:
        return render_template("onboarding.html", user=session['user'], topic=None)

@app.route("/syllabus/<topic>/<level>")
@login_required
def syllabus(topic, level):
    """
    Displays the syllabus for a given topic and level.

    Fetches the syllabus data from the backend API.
    Requires the user to be logged in.
    """
    try:
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/syllabus/topic/{topic}/level/{level}",
            headers=headers,
            timeout=30
        )

        if response.ok:
            syllabus_data = response.json()
            return render_template(
                "syllabus.html",
                user=session['user'],
                topic=topic,
                level=level,
                syllabus=syllabus_data
            )
        else:
            flash("Failed to load syllabus. Please try again later.")
            return render_template("syllabus.html", user=session['user'], syllabus=None)
    except requests.RequestException as e:
        logger.error(f"Syllabus error: {str(e)}")
        flash(f"Error: {str(e)}")
        return render_template("syllabus.html", user=session['user'], syllabus=None)

@app.route("/lesson/<syllabus_id>/<module>/<lesson>")
@login_required
def lesson(syllabus_id, module, lesson_arg):
    """
    Displays a specific lesson.

    Fetches the lesson data from the backend API.
    Requires the user to be logged in.
    """
    try:
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/lesson/{syllabus_id}/{module}/{lesson_arg}",
            headers=headers,
            timeout=30
        )

        if response.ok:
            lesson_data = response.json()
            return render_template(
                "lesson.html",
                user=session['user'],
                syllabus_id=syllabus_id,
                module=module,
                lesson=lesson_arg,
                lesson_data=lesson_data
            )
        else:
            flash("Failed to load lesson. Please try again later.")
            return render_template("lesson.html", user=session['user'], lesson_data=None)
    except requests.RequestException as e:
        logger.error(f"Lesson error: {str(e)}")
        flash(f"Error: {str(e)}")
        return render_template("lesson.html", user=session['user'], lesson_data=None)

@app.route("/lesson/exercise/evaluate", methods=["POST"])
@login_required
def evaluate_exercise():
    """
    Evaluates a user's answer to an exercise.

    Sends the answer to the backend API for evaluation and returns the result.
    Requires the user to be logged in.
    """
    data = request.json
    lesson_id = data.get('lesson_id')
    exercise_index = data.get('exercise_index')
    answer = data.get('answer')

    try:
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.post(
            f"{API_URL}/lesson/exercise/evaluate",
            json={
                'lesson_id': lesson_id,
                'exercise_index': exercise_index,
                'answer': answer
            },
            headers=headers,
            timeout=30
        )

        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to evaluate exercise'}), 400
    except requests.RequestException as e:
        logger.error(f"Exercise evaluation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)