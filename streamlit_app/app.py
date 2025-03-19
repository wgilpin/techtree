"""Streamlit UI for the techTree demo"""
#pylint: disable=wrong-import-position

import sys
sys.path.append(".")

import streamlit as st
from ai.langgraph_app import TechTreeAI

# Set page config
st.set_page_config(
    page_title="Tech Tree - Adaptive Learning",
    page_icon="🌳",
    layout="wide",
)

# App title
st.title("Tech Tree - Adaptive Learning")

# App description
st.markdown(
    """
    This app demonstrates an adaptive learning system that asks questions
    of increasing difficulty based on your performance.
    The questions are generated based on the latest information available
    online, making them accurate and up-to-date.
    """
)

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.messages = []
    st.session_state.tech_tree_ai = TechTreeAI()
    st.session_state.topic = ""
    st.session_state.search_completed = False
    st.session_state.search_status = ""
    st.session_state.quiz_started = False
    st.session_state.quiz_completed = False
    st.session_state.topic_submitted = False
    st.session_state.initialized = True


def handle_answer_submission():
    """Handle answer submission."""
    answer = st.session_state.answer_input
    if answer:
        # Add the answer to the messages
        st.session_state.messages.append({"role": "user", "content": answer})

        # Evaluate the answer
        evaluation_result = st.session_state.tech_tree_ai.evaluate_answer(answer)

        # Determine feedback message
        if evaluation_result["is_correct"]:
            feedback = "Correct!"
        elif evaluation_result["is_partially_correct"]:
            feedback = "Partially correct. " + evaluation_result.get("feedback", "")
        else:
            feedback = "Incorrect. " + evaluation_result.get("feedback", "")

        # Clean up the feedback message to remove any potential issues
        feedback = feedback.strip()
        
        # Add the feedback to the messages
        st.session_state.messages.append({"role": "assistant", "content": feedback})

        # Check if the quiz is complete
        if evaluation_result["is_complete"]:
            st.session_state.quiz_completed = True

            # Get the final assessment
            assessment = st.session_state.tech_tree_ai.get_final_assessment()

            # Create the final assessment message
            # Build the final assessment message
            # Check if the assessment dictionary has the expected keys.
            required_keys = [
                "correct_answers",
                "partially_correct_answers",
                "incorrect_answers",
                "total_score",
                "max_possible_score",
                "weighted_percentage",
                "knowledge_level",
            ]
            if not all(key in assessment for key in required_keys):
                final_message = "Error: Incomplete assessment data."
            else:
                # Simple text message for the chat
                final_message = "Thanks for playing the Tech Tree demo! Your final assessment is ready."
                
                # Store assessment data in session state for display outside the chat
                st.session_state.final_assessment = assessment

            # Add the final assessment to the messages
            st.session_state.messages.append(
                {"role": "assistant", "content": final_message}
            )
        else:
            # Generate the next question
            evaluation_result = st.session_state.tech_tree_ai.generate_question()
            question = f"[{evaluation_result['difficulty_str']}] {evaluation_result['question']}"
            st.session_state.messages.append({"role": "assistant", "content": question})
            st.session_state.answer_input = ""
            st.rerun()


# Topic selection
def handle_topic_submission():
    """Handle topic submission."""
    if st.session_state.topic_input:
        st.session_state.topic = st.session_state.topic_input
        st.session_state.messages.append(
            {
                "role": "user",
                "content": f"I want to learn about {st.session_state.topic}",
            }
        )
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Great! Let's explore {st.session_state.topic}."+
                    "I'll search for some information to create questions for you.",
            }
        )
        st.session_state.topic_input = ""  # Clear the input
        st.session_state.topic_submitted = True  # Set the flag


if not st.session_state.topic:
    st.subheader("What topic would you like to explore?")

    topic = st.text_input(
        "Enter a topic", key="topic_input", on_change=handle_topic_submission
    )

# Check if topic is submitted and rerun if needed
if st.session_state.topic_submitted:
    st.session_state.topic_submitted = False
    st.rerun()

# If topic is selected but search not completed
elif not st.session_state.search_completed and st.session_state.topic:
    st.info(f"Searching for information about '{st.session_state.topic}'...")

    # Initialize the agent with the topic
    st.session_state.tech_tree_ai.initialize(st.session_state.topic)

    # Perform search
    result = st.session_state.tech_tree_ai.perform_search()
    st.session_state.search_status = result["search_status"]
    st.session_state.search_completed = True

    # Generate first question
    result = st.session_state.tech_tree_ai.generate_question()
    question_text = f"[{result['difficulty_str']}] {result['question']}"
    st.session_state.messages.append({"role": "assistant", "content": question_text})
    st.session_state.quiz_started = True
    st.rerun()

# If search completed and quiz not completed
elif not st.session_state.quiz_completed:
    # Display the search status
    st.text(st.session_state.search_status)

    # Inject custom CSS for chat bubbles
    st.markdown(
        """
        <style>
        .message-container {
            display: flex;
            margin-bottom: 10px;
            clear: both;
        }
        .user-message {
            display: flex;
            justify-content: flex-end;
        }
        .assistant-message {
            display: flex;
            justify-content: flex-start;
        }
        .message-bubble {
            padding: 10px 15px;
            border-radius: 18px;
            max-width: 70%;
            word-wrap: break-word;
        }
        .user-bubble {
            background-color: #0084ff;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }
        .assistant-bubble {
            background-color: #f0f0f0;
            color: black;
            border-bottom-left-radius: 5px;
        }
        .avatar-icon {
            margin: 0 8px;
            align-self: flex-end;
        }
        /* Hide stray div tags */
        div:empty {
            display: none;
        }
        /* Hide stray closing div tags */
        </div> {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Display chat messages
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.container().markdown(
                f"""<div class="message-container user-message">
                        <div class="message-bubble user-bubble">
                            {message["content"]}
                        </div>
                        <span class="avatar-icon">👤</span>
                    </div>""",
                unsafe_allow_html=True,
            )
        else:
            # Use a container to isolate each message
            with st.container():
                st.markdown(
                    f"""<div class="message-container assistant-message">
                            <span class="avatar-icon">🌳</span>
                            <div class="message-bubble assistant-bubble">
                                {message["content"]}
                            </div>
                        </div>""",
                    unsafe_allow_html=True,
                )

    # Answer input
    if st.session_state.quiz_started:
        st.text_input(
            "Your answer", key="answer_input", on_change=handle_answer_submission
        )


# If quiz completed
else:
    # Inject custom CSS for chat bubbles (same as in the quiz section)
    st.markdown(
        """
        <style>
        .message-container {
            display: flex;
            margin-bottom: 10px;
            clear: both;
        }
        .user-message {
            display: flex;
            justify-content: flex-end;
        }
        .assistant-message {
            display: flex;
            justify-content: flex-start;
        }
        .message-bubble {
            padding: 10px 15px;
            border-radius: 18px;
            max-width: 70%;
            word-wrap: break-word;
        }
        .user-bubble {
            background-color: #0084ff;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }
        .assistant-bubble {
            background-color: #f0f0f0;
            color: black;
            border-bottom-left-radius: 5px;
        }
        .avatar-icon {
            margin: 0 8px;
            align-self: flex-end;
        }
        /* Hide stray div tags */
        div:empty {
            display: none;
        }
        /* Hide stray closing div tags */
        </div> {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Display chat messages
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.container().markdown(
                f"""<div class="message-container user-message">
                        <div class="message-bubble user-bubble">
                            {message["content"]}
                        </div>
                        <span class="avatar-icon">👤</span>
                    </div>""",
                unsafe_allow_html=True,
            )
        else:
            # Use a container to isolate each message
            with st.container():
                st.markdown(
                    f"""<div class="message-container assistant-message">
                            <span class="avatar-icon">🌳</span>
                            <div class="message-bubble assistant-bubble">
                                {message["content"]}
                            </div>
                        </div>""",
                    unsafe_allow_html=True,
                )
    
    # Display final assessment with proper formatting using Streamlit components
    if hasattr(st.session_state, 'final_assessment'):
        assessment = st.session_state.final_assessment
        
        # Create a visually appealing final assessment section
        st.markdown("---")
        
        # Title with custom styling
        st.markdown(
            """
            <h2 style="color: #2E7D32; text-align: center; margin-bottom: 20px;">
                Final Assessment Results
            </h2>
            """,
            unsafe_allow_html=True
        )
        
        # Create three columns for the assessment metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Correct Answers",
                value=assessment['correct_answers'],
                delta=None,
            )
            
        with col2:
            st.metric(
                label="Partially Correct",
                value=assessment['partially_correct_answers'],
                delta=None,
            )
            
        with col3:
            st.metric(
                label="Incorrect Answers",
                value=assessment['incorrect_answers'],
                delta=None,
            )
        
        # Score information
        st.markdown("---")
        score_col1, score_col2 = st.columns([2, 1])
        
        with score_col1:
            st.markdown(
                f"""
                <div style="background-color: #f0f7fa; padding: 15px; border-radius: 10px; text-align: center;">
                    <h3 style="margin: 0; color: #0277bd;">Weighted Score</h3>
                    <p style="font-size: 24px; font-weight: bold; margin: 10px 0;">
                        {assessment['total_score']:.1f}/{assessment['max_possible_score']:.1f}
                        <span style="color: #0277bd;">({assessment['weighted_percentage']:.1f}%)</span>
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        with score_col2:
            st.markdown(
                f"""
                <div style="background-color: #e8f5e9; padding: 15px; border-radius: 10px; height: 100%; text-align: center;">
                    <h3 style="margin: 0; color: #2E7D32;">Knowledge Level</h3>
                    <p style="font-size: 24px; font-weight: bold; margin: 10px 0; color: #2E7D32;">
                        {assessment['knowledge_level']}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown("---")

    # Restart button
    if st.button("Start a new quiz"):
        st.session_state.messages = []
        st.session_state.topic = ""
        st.session_state.search_completed = False
        st.session_state.search_status = ""
        st.session_state.quiz_started = False
        st.session_state.quiz_completed = False
        st.session_state.tech_tree_ai = TechTreeAI()
        # Clear the final assessment if it exists
        if hasattr(st.session_state, 'final_assessment'):
            delattr(st.session_state, 'final_assessment')
        st.rerun()

# Footer
st.markdown("---")
st.markdown("Tech Tree Demo - Powered by Gemini and Tavily")
