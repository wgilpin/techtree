from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
import os
import json
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
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
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        topic = request.form.get('topic')
        if topic:
            return redirect(url_for('onboarding', topic=topic))

    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
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
                timeout=5
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
                timeout=5
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
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        # Get in-progress courses
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/progress/courses",
            headers=headers,
            timeout=5
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
@login_required
def onboarding(topic=None):
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
                timeout=5
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
                timeout=5
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
    try:
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/syllabus/topic/{topic}/level/{level}",
            headers=headers,
            timeout=5
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
def lesson(syllabus_id, module, lesson):
    try:
        headers = {'Authorization': f"Bearer {session['user']['access_token']}"}
        response = requests.get(
            f"{API_URL}/lesson/{syllabus_id}/{module}/{lesson}",
            headers=headers,
            timeout=5
        )

        if response.ok:
            lesson_data = response.json()
            return render_template(
                "lesson.html",
                user=session['user'],
                syllabus_id=syllabus_id,
                module=module,
                lesson=lesson,
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
            timeout=5
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