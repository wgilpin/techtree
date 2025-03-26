# Tech Tree Demo

This project demonstrates a simple adaptive learning quiz using the Gemini API, Tavily API for internet search, and LangGraph. The project includes both a terminal-based version (`demo.py`) and a Streamlit web application that provides a more user-friendly interface.

## What it does

The Tech Tree application is an adaptive learning system that:

1. Asks the user to choose a topic
2. Searches the internet for information about the topic using the Tavily API
3. Generates questions of varying difficulty (easy, medium, hard) based on the retrieved information
4. Adjusts the difficulty based on the user's performance:
   - If the user answers a question correctly, the difficulty increases
   - If the user answers incorrectly, the difficulty remains the same
   - If the user answers two questions incorrectly in a row, the quiz ends
5. Provides a final assessment of the user's knowledge level based on a weighted score

The questions are generated based on the latest information available online, making them accurate and up-to-date.

## Available Interfaces

### Terminal Interface

The `demo.py` script runs an interactive quiz in the terminal, with a simple text-based interface.

### Streamlit Web Application

The Streamlit app (`streamlit_app/app.py`) provides a more user-friendly chat-based interface with:
- A clean, modern UI with chat bubbles
- Real-time feedback on answers
- Visual representation of the final assessment
- Option to restart the quiz with a new topic

## Prerequisites

- Python 3.12 or higher
- A Google API key with access to the Gemini API
- A Tavily API key for internet search functionality (get one at [tavily.com](https://tavily.com))
- Required Python packages:
  - google-generativeai
  - python-dotenv
  - langgraph
  - streamlit (for the web application)

## Setup

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/wgilpin/techtree.git
    cd techtree
    ```


2.  **Create a virtual environment:**

    It's recommended to use a virtual environment to manage dependencies. You can create one using `uv` (recommended) or `venv`.

    **Using `uv` (recommended):**

    If you don't have `uv` installed, install it with:
    ```bash
    pip install uv
    ```
    Then create and activate the virtual environment:
    ```bash
    uv venv
    uv activate
    ```

    **Using `venv`:**
    ```bash
    python3 -m venv .venv
    ```

    Activate the virtual environment:

    -   On Windows:

        ```bash
        .venv\Scripts\activate
        ```

    -   On macOS and Linux:

        ```bash
        source .venv/bin/activate
        ```

3.  **Install dependencies:**

    **Using `uv` (recommended):**
    ```bash
    uv pip install -r pyproject.toml
    ```
    Or, you can install the dependencies directly:
    ```bash
    uv pip install google-generativeai python-dotenv langgraph streamlit
    ```


4.  **Create a `.env` file:**

    Create a file named `.env` in the root directory of the project. Add the following lines to the file, replacing `YOUR_XXX_API_KEY` with your actual API keys and setting the backend API URL:

    ```
    # Required API Keys
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    TAVILY_API_KEY=YOUR_TAVILY_API_KEY

    # URL for the backend API server (used by the Flask frontend)
    API_URL="http://localhost:8000"
    ```

    Recommended but not required is free [LangSmith](https://www.langchain.com/langsmith) tracing. To use it, add the lines

    ```
    LANGSMITH_TRACING=true
    LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
    LANGSMITH_API_KEY=<YOUR LANGSMITH API KEY>
    ```

## Running the application

Once you've set up the environment and installed the dependencies, you can run either version of the application:

### Terminal Version

Run the terminal-based demo script with:

```bash
python demo.py
```

The script will prompt you to choose a topic and then start asking questions in the terminal.

### Streamlit Web Application

Run the Streamlit web application with:

```bash
streamlit run onboarding/streamlit_app/app.py
```

This will launch a local web server and open the application in your default web browser. If the browser doesn't open automatically, you can access the application at http://localhost:8501.

The Streamlit app provides a more user-friendly interface with chat bubbles, real-time feedback, and a visual representation of your final assessment.

## Syllabus Demo

The `syllabus_demo.py` script demonstrates how to use the LangGraph to generate a syllabus for a given topic. It uses the Gemini API to generate the syllabus.

### Running the Syllabus Demo

To run the syllabus demo, execute the following command:

```bash
python syllabus_demo.py
```

The script will prompt you to enter a topic, and then generate a syllabus for that topic.