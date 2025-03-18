# Tech Tree Demo

This project demonstrates a simple adaptive learning quiz using the Gemini API and LangGraph. The `demo.py` script implements a question-and-answer system that adjusts the difficulty of questions based on the user's performance.

## What it does

The `demo.py` script runs an interactive quiz in the terminal. It starts by asking the user to choose a topic. Then, it asks questions of increasing difficulty (easy, medium, hard).

- If the user answers a question correctly, the difficulty increases.
- If the user answers incorrectly, the difficulty remains the same.
- If the user answers two questions incorrectly in a row, the quiz ends.

At the end of the quiz, the script provides a final assessment of the user's knowledge level based on a weighted score.

The topic is *not* subject to an internet search, so will need to be know to the model (Gemini 2.0 Pro).

## Prerequisites

- Python 3.12 or higher
- A Google API key with access to the Gemini API

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
    uv pip install -r requirements.txt
    ```
    If `requirements.txt` does not exist, you can install the dependencies directly:
    ```bash
    uv pip install google-generativeai python-dotenv langgraph
    ```

    **Using `pip`:**
    ```bash
    pip install -r requirements.txt
    ```
    If `requirements.txt` does not exist, you can install the dependencies directly:
    ```bash
    pip install google-generativeai python-dotenv langgraph
    ```

4.  **Create a `.env` file:**

    Create a file named `.env` in the root directory of the project. Add the following line to the file, replacing `YOUR_API_KEY` with your actual Google API key:

    ```
    GEMINI_API_KEY=YOUR_API_KEY
    ```

    Recommended but not required is free [LangSmith](https://www.langchain.com/langsmith) tracing. To use it, add the lines

    ```
    LANGSMITH_TRACING=true
    LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
    LANGSMITH_API_KEY=<YOUR LANGSMITH API KEY>
    ```

## Running the demo

Once you've set up the environment and installed the dependencies, you can run the demo script with:

```bash
python demo.py
```

The script will prompt you to choose a topic and then start asking questions.