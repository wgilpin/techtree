"""Streamlit UI for the Tech Tree Syllabus demo"""

# pylint: disable=wrong-import-position

import sys

sys.path.append(".")

import json
from io import StringIO
import streamlit as st
from syllabus.ai.langgraph_app import SyllabusAI

# Set page config
st.set_page_config(
    page_title="Tech Tree - Syllabus Creator",
    page_icon="🌳",
    layout="wide",
)


def run_app():
    """Run the Streamlit app."""
    # App title
    st.title("Tech Tree - Syllabus Creator")

    # App description
    st.markdown(
        """
        This app demonstrates the syllabus creation feature of Tech Tree.
        You can create a new syllabus for any topic, tailored to your knowledge level.
        """
    )

    # Initialize session state
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
        st.session_state.messages = []
        st.session_state.syllabus_ai = SyllabusAI()
        st.session_state.topic = ""
        st.session_state.knowledge_level = ""
        st.session_state.syllabus = None
        st.session_state.syllabus_presented = False
        st.session_state.feedback_submitted = False
        st.session_state.syllabus_accepted = False
        st.session_state.topic_submitted = False
        st.session_state.knowledge_level_submitted = False
        st.session_state.initialized = True

    # Topic selection
    def handle_topic_submission():
        """Handle topic submission."""
        if st.session_state.topic_input:
            st.session_state.topic = st.session_state.topic_input
            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": f"I want to create a syllabus for {st.session_state.topic}",
                }
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"""Great! Let me know your knowledge level for
                    {st.session_state.topic} so I can tailor the syllabus appropriately.""",
                }
            )
            st.session_state.topic_input = ""  # Clear the input
            st.session_state.topic_submitted = True  # Set the flag

    # Knowledge level selection

    # Handle feedback submission
    def handle_feedback_submission():
        """Handle feedback submission."""
        feedback = st.session_state.feedback_input
        if feedback:
            st.session_state.messages.append({"role": "user", "content": feedback})

            # Update the syllabus with feedback
            updated_syllabus = st.session_state.syllabus_ai.update_syllabus(feedback)
            st.session_state.syllabus = updated_syllabus

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": """I've updated the syllabus based on your feedback.
                                What do you think of this version?""",
                }
            )

            st.session_state.feedback_submitted = True
            st.session_state.feedback_input = ""  # Clear the input

    # Handle syllabus acceptance
    def handle_syllabus_acceptance():
        """Handle syllabus acceptance."""
        st.session_state.messages.append(
            {"role": "user", "content": "I accept this syllabus."}
        )

        # Save the syllabus
        st.session_state.syllabus_ai.save_syllabus()

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"""Great! I've saved this syllabus for {st.session_state.topic}
                               at the {st.session_state.knowledge_level} level.""",
            }
        )

        st.session_state.syllabus_accepted = True

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
    def display_chat():
        """Display chat messages."""
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

    # Display syllabus
    def display_syllabus(syllabus):
        """Display the syllabus."""
        st.subheader(f"Syllabus: {syllabus['topic']}")
        st.write(f"**Level:** {syllabus['level']}")
        st.write(f"**Duration:** {syllabus['duration']}")

        st.write("**Learning Objectives:**")
        for i, objective in enumerate(syllabus["learning_objectives"], 1):
            st.write(f"{i}. {objective}")

        st.write("**Modules:**")
        for module in syllabus["modules"]:
            with st.expander(f"Week {module['week']}: {module['title']}"):
                for i, lesson in enumerate(module["lessons"], 1):
                    st.write(f"{i}. {lesson['title']}")

    def syllabus_to_markdown(syllabus):
        """Convert syllabus to markdown format."""
        md = f"# Syllabus: {syllabus['topic']}\n"
        md += f"**Level:** {syllabus['level']}\n"
        md += f"**Duration:** {syllabus['duration']}\n\n"

        md += "## Learning Objectives:\n"
        for i, objective in enumerate(syllabus["learning_objectives"], 1):
            md += f"{i}. {objective}\n"

        md += "\n## Modules:\n"
        for module in syllabus["modules"]:
            md += f"### Week {module['week']}: {module['title']}\n"
            for i, lesson in enumerate(module["lessons"], 1):
                md += f"{i}. {lesson['title']}\n"
            md += "\n"
        return md

    def generate_download_link(syllabus, topic, level):
        """Generates a download link for the syllabus in markdown format."""
        markdown_text = syllabus_to_markdown(syllabus)
        file_name = f"{topic}_{level}_syllabus.md"

        # Use StringIO to create an in-memory text stream
        markdown_stream = StringIO(markdown_text)

        st.download_button(
            label="Download Syllabus (Markdown)",
            data=markdown_stream.getvalue(),  # Get the string value from StringIO
            file_name=file_name,
            mime="text/markdown",
        )

    def generate_json_download_link(syllabus, topic, level):
        """Generates a download link for the syllabus in JSON format."""
        json_text = json.dumps(syllabus, indent=4)
        file_name = f"{topic}_{level}_syllabus.json"

        st.download_button(
            label="Download Syllabus (JSON)",
            data=json_text,
            file_name=file_name,
            mime="application/json",
        )

    # Main UI flow
    if not st.session_state.topic:
        # Topic input
        st.subheader("What topic would you like to create a syllabus for?")
        st.text_input(
            "Enter a topic", key="topic_input", on_change=handle_topic_submission
        )

        # Display chat
        display_chat()

    # Check if topic is submitted and rerun if needed
    elif st.session_state.topic_submitted:
        st.session_state.topic_submitted = False
        st.rerun()

    elif not st.session_state.knowledge_level:
        # Add a message asking for knowledge level if not already present
        if len(st.session_state.messages) == 2:  # Only the initial topic messages
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"What is your knowledge level for {st.session_state.topic}?"
                    " Please select from the options below.",
                }
            )

        # Display chat first so the user sees the prompt
        display_chat()

        # Knowledge level selection
        with st.form(key="knowledge_level_form"):
            knowledge_level = st.selectbox(
                "Knowledge Level",
                options=["beginner", "early learner", "good knowledge", "advanced"],
                key="knowledge_level_select",
                label_visibility="collapsed",
            )

            submit_button = st.form_submit_button(label="Confirm Knowledge Level")

            if submit_button:
                st.session_state.knowledge_level = knowledge_level
                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content":
                            f"My knowledge level is {st.session_state.knowledge_level_select}",
                    }
                )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"""Thanks! Let me check if we already have a syllabus for
                                    {st.session_state.topic} at the
                                    {st.session_state.knowledge_level_select} level or create
                                    a new one for you.""",
                    }
                )
                st.session_state.knowledge_level_submitted = True
                st.rerun()

    # Check if knowledge level is submitted and display syllabus
    elif st.session_state.knowledge_level_submitted:
        st.session_state.knowledge_level_submitted = False
        st.rerun()

    elif not st.session_state.syllabus_presented:
        # Display loading message
        with st.spinner(
            f"Creating syllabus for {st.session_state.topic} at "
            f"{st.session_state.knowledge_level} level..."
        ):
            # Initialize AI with topic and knowledge level
            st.session_state.syllabus_ai.initialize(
                st.session_state.topic, st.session_state.knowledge_level
            )

            # Get or create syllabus
            syllabus = st.session_state.syllabus_ai.get_or_create_syllabus()
            st.session_state.syllabus = syllabus

            # Check if this is an existing syllabus from the database
            is_existing = (
                st.session_state.syllabus_ai.state["existing_syllabus"] is not None
            )

            if is_existing:
                st.session_state.syllabus_accepted = True

            # Add message to chat
            if is_existing:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content":
                            f"I found an existing syllabus for {st.session_state.topic}"
                            f"at the {st.session_state.knowledge_level} level."
                            "Would you like to accept it or provide feedback for improvements?",
                    }
                )
            else:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content":
                            f"Here's a new syllabus for {st.session_state.topic}"
                            f" at the {st.session_state.knowledge_level} level."
                            "Would you like to accept it or provide feedback for improvements?",
                    }
                )

            st.session_state.syllabus_presented = True
            st.rerun()

    elif not st.session_state.syllabus_accepted:
        # Display chat
        display_chat()

        # Display syllabus
        display_syllabus(st.session_state.syllabus)

        # Feedback or acceptance
        col1, col2 = st.columns(2)

        with col1:
            st.text_input(
                "Provide feedback to improve the syllabus",
                key="feedback_input",
                on_change=handle_feedback_submission,
            )

        with col2:
            if st.button("Accept Syllabus"):
                handle_syllabus_acceptance()
                st.rerun()

        # Check if feedback is submitted and rerun if needed
        if st.session_state.feedback_submitted:
            st.session_state.feedback_submitted = False
            st.rerun()

    else:
        # Display chat
        display_chat()

        # Display final syllabus
        st.subheader("Final Accepted Syllabus")
        display_syllabus(st.session_state.syllabus)

        # Generate download link
        generate_download_link(
            st.session_state.syllabus,
            st.session_state.syllabus["topic"],
            st.session_state.syllabus["level"],
        )
        generate_json_download_link(
            st.session_state.syllabus,
            st.session_state.syllabus["topic"],
            st.session_state.syllabus["level"],
        )
        # No need to display chat again
        # display_chat()

        # No need to display final syllabus again
        # st.subheader("Final Accepted Syllabus")
        # display_syllabus(st.session_state.syllabus)

        # Restart button
        if st.button("Create Another Syllabus"):
            st.session_state.messages = []
            st.session_state.topic = ""
            st.session_state.knowledge_level = ""
            st.session_state.syllabus = None
            st.session_state.syllabus_presented = False
            st.session_state.feedback_submitted = False
            st.session_state.syllabus_accepted = False
            st.session_state.syllabus_ai = SyllabusAI()
            st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("Tech Tree Syllabus Demo - Powered by Gemini and Tavily")


if __name__ == "__main__":
    run_app()
