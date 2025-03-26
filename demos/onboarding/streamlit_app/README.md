# Tech Tree Streamlit App

This is a Streamlit-based chat interface for the Tech Tree adaptive learning system. It provides a user-friendly way to interact with the Tech Tree AI, which asks questions of increasing difficulty based on your performance.

## Features

- Chat-based interface for a more natural interaction
- Topic selection at the beginning of the conversation
- Real-time internet search for up-to-date information
- Adaptive difficulty based on your answers
- Final assessment of your knowledge level

## How to Run

1. Make sure you have all the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure you have the required API keys in your `.env` file:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

3. Run the Streamlit app:
   ```bash
   streamlit run streamlit_app/app.py
   ```

## How to Use

1. Enter a topic you want to learn about
2. The app will search the internet for information about the topic
3. Answer the questions that are presented to you
4. The difficulty will adapt based on your performance
5. After the quiz ends, you'll receive a final assessment of your knowledge level

## Architecture

The app consists of two main components:

1. **AI Module**: Encapsulates the langgraph app from the original demo.py
2. **Streamlit App**: Provides a chat-based interface for interacting with the AI module

The AI module handles the core functionality:
- Internet search using the Tavily API
- Question generation using the Gemini API
- Answer evaluation
- Adaptive difficulty
- Final assessment

The Streamlit app handles the user interface:
- Chat bubbles for user input and system responses
- Topic selection
- Display of questions and feedback
- Final assessment display