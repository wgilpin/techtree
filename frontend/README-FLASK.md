# TechTree Flask Frontend

This is a Flask implementation of the TechTree frontend, replacing the original Svelte frontend while maintaining the same functionality and API interactions.

## Features

- User authentication (login, register, logout)
- Dashboard with in-progress courses
- Topic assessment and onboarding
- Syllabus viewing
- Interactive lessons with exercises

## Prerequisites

- Python 3.8 or higher
- FastAPI backend running on http://localhost:8000

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure the FastAPI backend is running on http://localhost:8000

## Running the Application

1. Start the Flask application:

```bash
python app.py
```

2. Open your browser and navigate to http://localhost:5000

## Project Structure

- `app.py` - Main Flask application
- `templates/` - Jinja2 templates
  - `base.html` - Base template with common layout
  - `login.html` - Login page
  - `register.html` - Registration page
  - `dashboard.html` - User dashboard
  - `onboarding.html` - Topic assessment
  - `syllabus.html` - Syllabus view
  - `lesson.html` - Lesson view with exercises
- `static/` - Static assets
  - `css/main.css` - Main stylesheet
  - `images/` - Images (add a logo.jpeg file here)
  - `js/` - JavaScript files (if needed)

## Notes

- This application uses Flask sessions for user authentication
- API requests are made directly to the FastAPI backend
- The application is designed to be a drop-in replacement for the Svelte frontend

## Customization

- Update the `API_URL` in `app.py` if your backend is running on a different address
- Replace the placeholder logo in `static/images/logo.jpeg` with your own logo
- Modify the secret key in `app.py` for production use