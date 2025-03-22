"""Streamlit UI for the Tech Tree Lesson demo"""

# pylint: disable=wrong-import-position
# pylint: disable=broad-exception-caught

import inspect
import sys
import uuid
from datetime import datetime

sys.path.append(".")

import streamlit as st
from tinydb import Query, TinyDB

from lessons.ai.langgraph_app import LessonAI
from syllabus.ai.langgraph_app import SyllabusAI

# Set page config
st.set_page_config(
    page_title="Tech Tree - Lesson Demo",
    page_icon="🌳",
    layout="wide",
)

# Initialize the database
db = TinyDB("syllabus_db.json")
syllabi_table = db.table("syllabi")
user_progress_table = db.table("user_progress")

# Import the syllabi_table from the syllabus module to ensure consistency
from syllabus.ai.langgraph_app import syllabi_table as syllabus_ai_syllabi_table


def print_method_name():
    """Prints the name of the calling method."""
    frame = inspect.currentframe().f_back  # Go back one frame to get the caller
    method_name = frame.f_code.co_name
    class_name = ""
    if "self" in frame.f_locals:
        class_name = frame.f_locals["self"].__class__.__name__ + "."
    print(f"DEBUG: called {class_name}{method_name}")


def run_app():
    """Run the Streamlit app."""
    print_method_name()
    # App title
    st.title("Tech Tree - Lesson Demo")

    # App description
    st.markdown(
        """
        This app demonstrates the lesson experience feature of Tech Tree.
        You can explore lessons from any syllabus, tailored to your knowledge level.
        """
    )

    # Initialize session state
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
        st.session_state.messages = []
        st.session_state.lesson_ai = LessonAI()
        st.session_state.user_email = ""
        st.session_state.topic = ""
        st.session_state.knowledge_level = ""
        st.session_state.syllabus = None
        st.session_state.module_title = ""
        st.session_state.lesson_title = ""
        st.session_state.lesson_content = None
        st.session_state.current_exercise_index = 0
        st.session_state.current_assessment_index = 0
        st.session_state.exercise_responses = {}
        st.session_state.assessment_responses = {}
        st.session_state.exercise_feedback = {}
        st.session_state.assessment_feedback = {}
        st.session_state.lesson_completed = False
        st.session_state.user_email_submitted = False
        st.session_state.topic_submitted = False
        st.session_state.knowledge_level_submitted = False
        st.session_state.syllabus_selected = False
        st.session_state.lesson_selected = False
        st.session_state.initialized = True

    # User authentication
    def handle_user_email_submission():
        """Handle user email submission."""
        print_method_name()
        if st.session_state.user_email_input:
            st.session_state.user_email = st.session_state.user_email_input
            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": f"My email is {st.session_state.user_email}",
                }
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "Great! Now, what topic would you like to explore?",
                }
            )
            st.session_state.user_email_input = ""  # Clear the input
            st.session_state.user_email_submitted = True  # Set the flag

    # Topic selection
    def handle_topic_submission():
        """Handle topic submission."""
        print_method_name()
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
                    "content": f"""Great! Let me know your knowledge level for
                    {st.session_state.topic} so I can tailor the lessons appropriately.""",
                }
            )
            st.session_state.topic_input = ""  # Clear the input
            st.session_state.topic_submitted = True  # Set the flag

    # Handle exercise submission
    def handle_exercise_submission(exercise_id):
        """Handle exercise submission."""
        print_method_name()
        response = st.session_state[f"exercise_{exercise_id}_input"]
        if response:
            # Evaluate the response
            feedback = st.session_state.lesson_ai.evaluate_response(
                response, exercise_id
            )

            # Store the response and feedback
            st.session_state.exercise_responses[exercise_id] = response
            st.session_state.exercise_feedback[exercise_id] = feedback

            # Clear the input
            st.session_state[f"exercise_{exercise_id}_input"] = ""

    # Handle assessment submission
    def handle_assessment_submission(assessment_id):
        """Handle assessment submission."""
        print_method_name()
        response = st.session_state[f"assessment_{assessment_id}_input"]
        if response:
            # Evaluate the response
            feedback = st.session_state.lesson_ai.evaluate_response(
                response, assessment_id
            )

            # Store the response and feedback
            st.session_state.assessment_responses[assessment_id] = response
            st.session_state.assessment_feedback[assessment_id] = feedback

            # Clear the input
            st.session_state[f"assessment_{assessment_id}_input"] = ""

    # Handle lesson completion
    def handle_lesson_completion():
        """Handle lesson completion."""
        print_method_name()
        # Save progress
        st.session_state.lesson_ai.save_progress()

        # Mark lesson as completed
        st.session_state.lesson_completed = True

        # Add message
        st.session_state.messages.append(
            {"role": "user", "content": "I've completed this lesson."}
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"""Great job completing the lesson on "{st.session_state.lesson_title}"!
                Your progress has been saved. You can now continue to the next lesson or
                explore other topics.""",
            }
        )

    # Inject custom CSS for chat bubbles and lesson content
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
        .lesson-container {
            background-color: #f9f9f9;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #e0e0e0;
        }
        .exercise-container {
            background-color: #f0f7ff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #d0e5ff;
        }
        .assessment-container {
            background-color: #fff7f0;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #ffe5d0;
        }
        .feedback-container {
            background-color: #f0fff7;
            border-radius: 10px;
            padding: 15px;
            margin-top: 10px;
            border: 1px solid #d0ffe5;
        }
        .misconception-container {
            background-color: #fff0f0;
            border-radius: 10px;
            padding: 15px;
            margin-top: 10px;
            border: 1px solid #ffd0d0;
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
        print_method_name()

        # Only show the info message if we're past the initial state
        # and there are no messages (which shouldn't happen)
        if not st.session_state.messages:
            if (
                hasattr(st.session_state, "user_email_submitted")
                and st.session_state.user_email_submitted
            ):
                st.info("No messages to display. Start by entering your topic.")
            return

        try:
            for message in st.session_state.messages:
                # Check if message has the required keys
                if "role" not in message or "content" not in message:
                    st.error(f"Message is missing required keys: {message}")
                    continue

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
        except Exception as e:
            st.error(f"Error displaying chat: {str(e)}")
            st.write("Messages structure:")
            st.write(st.session_state.messages)

    # Display syllabus
    def display_syllabus(syllabus):
        """Display the syllabus."""
        print_method_name()
        print(f"DEBUG: display_syllabus called with syllabus: {type(syllabus)}")
        print(
            f"DEBUG: Syllabus keys: {syllabus.keys() if isinstance(syllabus, dict) else 'Not a dict'}"
        )

        try:
            # Check if syllabus has the required keys
            required_keys = [
                "topic",
                "level",
                "duration",
                "learning_objectives",
                "modules",
            ]
            missing_keys = [key for key in required_keys if key not in syllabus]

            if missing_keys:
                st.error(
                    f"Syllabus is missing required keys: {', '.join(missing_keys)}"
                )
                st.write("Syllabus structure:")
                st.write(syllabus)
                print(f"DEBUG: Missing keys in syllabus: {missing_keys}")
                return

            st.subheader(f"Syllabus: {syllabus['topic']}")
            st.write(f"**Level:** {syllabus['level']}")
            st.write(f"**Duration:** {syllabus['duration']}")

            st.write("**Learning Objectives:**")
            for i, objective in enumerate(syllabus["learning_objectives"], 1):
                st.write(f"{i}. {objective}")

            st.write("**Modules:**")
            for module in syllabus["modules"]:
                # Check if module has the required keys
                if (
                    "week" not in module
                    or "title" not in module
                    or "lessons" not in module
                ):
                    st.error(f"Module is missing required keys: {module}")
                    continue

                with st.expander(f"Week {module['week']}: {module['title']}"):
                    for i, lesson in enumerate(module["lessons"], 1):
                        # Check if lesson has the required keys
                        if "title" not in lesson:
                            st.error(f"Lesson is missing required keys: {lesson}")
                            continue

                        if st.button(
                            f"{i}. {lesson['title']}",
                            key=f"lesson_{module['title']}_{lesson['title']}",
                        ):
                            st.session_state.module_title = module["title"]
                            st.session_state.lesson_title = lesson["title"]
                            st.session_state.lesson_selected = True
                            st.rerun()
        except Exception as e:
            st.error(f"Error displaying syllabus: {str(e)}")
            st.write("Syllabus structure:")
            st.write(syllabus)

    # Display lesson content
    def display_lesson_content(content):
        """Display the lesson content."""
        print_method_name()
        st.markdown("<div class='lesson-container'>", unsafe_allow_html=True)

        # Display exposition content
        st.markdown(content["exposition_content"])

        # Display thought questions
        st.subheader("Thought Questions")
        for i, question in enumerate(content["thought_questions"], 1):
            st.write(f"{i}. {question}")

        st.markdown("</div>", unsafe_allow_html=True)

        # Display active exercises
        st.subheader("Active Exercises")
        for i, exercise in enumerate(content["active_exercises"], 1):
            st.markdown("<div class='exercise-container'>", unsafe_allow_html=True)
            st.write(f"**Exercise {i}: {exercise['type'].capitalize()}**")
            st.write(exercise["question"])

            # Display hints
            if "hints" in exercise and exercise["hints"]:
                with st.expander("Hints"):
                    for j, hint in enumerate(exercise["hints"], 1):
                        st.write(f"Hint {j}: {hint}")

            # Check if this exercise has been answered
            if exercise["id"] in st.session_state.exercise_responses:
                st.write("**Your Response:**")
                st.write(st.session_state.exercise_responses[exercise["id"]])

                # Display feedback
                if exercise["id"] in st.session_state.exercise_feedback:
                    feedback = st.session_state.exercise_feedback[exercise["id"]]
                    st.markdown(
                        "<div class='feedback-container'>", unsafe_allow_html=True
                    )
                    st.write("**Feedback:**")
                    st.write(feedback["feedback"])
                    st.markdown("</div>", unsafe_allow_html=True)

                    # Display misconceptions
                    if feedback["misconceptions"]:
                        st.markdown(
                            "<div class='misconception-container'>",
                            unsafe_allow_html=True,
                        )
                        st.write("**Misconceptions to Address:**")
                        for misconception in feedback["misconceptions"]:
                            st.write(f"- {misconception}")
                        st.markdown("</div>", unsafe_allow_html=True)
            else:
                # Display input for response
                st.text_area(
                    "Your response",
                    key=f"exercise_{exercise['id']}_input",
                    height=100,
                )

                if st.button("Submit", key=f"submit_exercise_{exercise['id']}"):
                    handle_exercise_submission(exercise["id"])
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # Display knowledge assessment
        st.subheader("Knowledge Assessment")
        for i, assessment in enumerate(content["knowledge_assessment"], 1):
            st.markdown("<div class='assessment-container'>", unsafe_allow_html=True)
            st.write(f"**Question {i}:**")
            st.write(assessment["question"])

            # For multiple choice questions
            if assessment["type"] == "multiple_choice":
                # Check if this assessment has been answered
                if assessment["id"] in st.session_state.assessment_responses:
                    st.write("**Your Answer:**")
                    st.write(st.session_state.assessment_responses[assessment["id"]])

                    # Display feedback
                    if assessment["id"] in st.session_state.assessment_feedback:
                        feedback = st.session_state.assessment_feedback[
                            assessment["id"]
                        ]
                        st.markdown(
                            "<div class='feedback-container'>", unsafe_allow_html=True
                        )
                        st.write("**Feedback:**")
                        st.write(feedback["feedback"])
                        st.markdown("</div>", unsafe_allow_html=True)

                        # Display misconceptions
                        if feedback["misconceptions"]:
                            st.markdown(
                                "<div class='misconception-container'>",
                                unsafe_allow_html=True,
                            )
                            st.write("**Misconceptions to Address:**")
                            for misconception in feedback["misconceptions"]:
                                st.write(f"- {misconception}")
                            st.markdown("</div>", unsafe_allow_html=True)
                else:
                    # Display options
                    st.radio(
                        "Select your answer",
                        assessment["options"],
                        key=f"assessment_{assessment['id']}_input",
                    )

                    if st.button("Submit", key=f"submit_assessment_{assessment['id']}"):
                        handle_assessment_submission(assessment["id"])
                        st.rerun()
            else:
                # For other types of questions
                # Check if this assessment has been answered
                if assessment["id"] in st.session_state.assessment_responses:
                    st.write("**Your Response:**")
                    st.write(st.session_state.assessment_responses[assessment["id"]])

                    # Display feedback
                    if assessment["id"] in st.session_state.assessment_feedback:
                        feedback = st.session_state.assessment_feedback[
                            assessment["id"]
                        ]
                        st.markdown(
                            "<div class='feedback-container'>", unsafe_allow_html=True
                        )
                        st.write("**Feedback:**")
                        st.write(feedback["feedback"])
                        st.markdown("</div>", unsafe_allow_html=True)

                        # Display misconceptions
                        if feedback["misconceptions"]:
                            st.markdown(
                                "<div class='misconception-container'>",
                                unsafe_allow_html=True,
                            )
                            st.write("**Misconceptions to Address:**")
                            for misconception in feedback["misconceptions"]:
                                st.write(f"- {misconception}")
                            st.markdown("</div>", unsafe_allow_html=True)
                else:
                    # Display input for response
                    st.text_area(
                        "Your response",
                        key=f"assessment_{assessment['id']}_input",
                        height=100,
                    )

                    if st.button("Submit", key=f"submit_assessment_{assessment['id']}"):
                        handle_assessment_submission(assessment["id"])
                        st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # Check if all exercises and assessments have been completed
        all_exercises_completed = all(
            exercise["id"] in st.session_state.exercise_responses
            for exercise in content["active_exercises"]
        )

        all_assessments_completed = all(
            assessment["id"] in st.session_state.assessment_responses
            for assessment in content["knowledge_assessment"]
        )

        if (
            all_exercises_completed
            and all_assessments_completed
            and not st.session_state.lesson_completed
        ):
            if st.button("Complete Lesson"):
                handle_lesson_completion()
                st.rerun()

    # Display user progress
    def display_user_progress(user_email, topic):
        """Display the user's progress for a topic."""
        print_method_name()
        user_query = Query()
        progress = user_progress_table.search(user_query.user_email == user_email)

        if not progress or topic not in progress[0]:
            st.write("No progress data available.")
            return

        topic_progress = progress[0][topic]

        st.subheader("Your Progress")

        # Display overall progress
        st.progress(topic_progress["overall_progress"])
        st.write(f"Overall Progress: {topic_progress['overall_progress'] * 100:.1f}%")

        # Display overall performance
        st.write(
            f"Overall Performance: {topic_progress['overall_performance'] * 100:.1f}%"
        )

        # Display completed lessons
        st.write("**Completed Lessons:**")
        for lesson in topic_progress["completed_lessons"]:
            st.write(f"- {lesson}")

        # Display current lesson
        st.write(f"**Current Lesson:** {topic_progress['current_lesson']}")

    # Main UI flow
    if not st.session_state.user_email:
        print("Need user email")
        # User email input
        st.subheader("Please enter your email to get started")
        st.text_input(
            "Email", key="user_email_input", on_change=handle_user_email_submission
        )

        # Display chat
        display_chat()

    # Check if user email is submitted and rerun if needed
    elif st.session_state.user_email_submitted:
        st.session_state.user_email_submitted = False
        st.rerun()

    elif not st.session_state.topic:
        print("Need topic")
        # Display chat first so the user sees the prompt
        display_chat()

        # Topic input
        st.subheader("What topic would you like to learn about?")
        st.text_input(
            "Enter a topic", key="topic_input", on_change=handle_topic_submission
        )

    # Check if topic is submitted and rerun if needed
    elif st.session_state.topic_submitted:
        st.session_state.topic_submitted = False
        st.rerun()

    elif not st.session_state.knowledge_level:
        print("Need knowledge level")
        # Add a message asking for knowledge level if not already present
        if len(st.session_state.messages) == 4:  # Only the initial messages
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
                        "content": f"My knowledge level is {st.session_state.knowledge_level_select}",
                    }
                )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"""Thanks! Let me check if we have a syllabus for
                                    {st.session_state.topic} at the
                                    {st.session_state.knowledge_level_select} level.""",
                    }
                )
                st.session_state.knowledge_level_submitted = True
                st.rerun()

    # Check if knowledge level is submitted and retrieve syllabus
    elif st.session_state.knowledge_level_submitted:
        print("DEBUG: Knowledge level submitted, retrieving syllabus")
        print(f"DEBUG: Topic: {st.session_state.topic}")
        print(f"DEBUG: Knowledge level: {st.session_state.knowledge_level}")

        st.session_state.knowledge_level_submitted = False

        # Initialize AI with topic and knowledge level
        with st.spinner(
            f"Retrieving syllabus for {st.session_state.topic} at "
            f"{st.session_state.knowledge_level} level..."
        ):
            try:
                st.session_state.lesson_ai.initialize(
                    st.session_state.topic,
                    st.session_state.knowledge_level,
                    st.session_state.user_email,
                )

                # Get the syllabus
                st.session_state.syllabus = st.session_state.lesson_ai.state["syllabus"]
                # Also store it in syllabus_data as a backup
                st.session_state.syllabus_data = st.session_state.syllabus
                print(f"DEBUG: Retrieved syllabus: {type(st.session_state.syllabus)}")
                print(
                    f"DEBUG: Syllabus keys: {st.session_state.syllabus.keys() if isinstance(st.session_state.syllabus, dict) else 'Not a dict'}"
                )
                print("DEBUG: Stored syllabus in syllabus_data")
                # Add message to chat
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"I found a syllabus for {st.session_state.topic}"
                        f" at the {st.session_state.knowledge_level} level."
                        " Please select a lesson to begin.",
                    }
                )

                # Store the syllabus in a separate variable to ensure it's not lost
                st.session_state.syllabus_data = st.session_state.syllabus

                # Set the flag to indicate that the syllabus is selected
                st.session_state.syllabus_selected = True

                print("DEBUG: Setting syllabus_selected to True")
                print("DEBUG: About to rerun after setting syllabus_selected")
                print(f"DEBUG: Session state before rerun: {st.session_state}")

                # Force a rerun to update the UI
                st.rerun()
            except ValueError:
                # No syllabus found, generate one
                with st.spinner(
                    f"Generating a new syllabus for {st.session_state.topic} at "
                    f"{st.session_state.knowledge_level} level..."
                ):
                    try:
                        # Create a SyllabusAI instance
                        syllabus_ai = SyllabusAI()

                        # Initialize with topic and knowledge level
                        syllabus_ai.initialize(
                            st.session_state.topic,
                            st.session_state.knowledge_level,
                            st.session_state.user_email,
                        )

                        # Generate a syllabus
                        syllabus_ai.get_or_create_syllabus()

                        # Get the generated syllabus
                        syllabus = syllabus_ai.state["generated_syllabus"]
                        if syllabus is None:
                            syllabus = syllabus_ai.state["existing_syllabus"]

                        # Prepare the syllabus for saving

                        now = datetime.now().isoformat()

                        # Create a complete syllabus object
                        complete_syllabus = {
                            "topic": syllabus["topic"],
                            "level": syllabus["level"],
                            "duration": syllabus["duration"],
                            "learning_objectives": syllabus["learning_objectives"],
                            "modules": syllabus["modules"],
                            "uid": str(uuid.uuid4()),
                            "created_at": now,
                            "updated_at": now,
                            "is_master": True,
                            "user_entered_topic": st.session_state.topic,
                        }

                        # Save the syllabus to the database directly
                        if not syllabus_ai.state["existing_syllabus"]:
                            syllabus_ai_syllabi_table.insert(complete_syllabus)

                        # Use the complete syllabus
                        st.session_state.syllabus = complete_syllabus
                        # Also store it in syllabus_data as a backup
                        st.session_state.syllabus_data = complete_syllabus
                        print("DEBUG: Stored syllabus in syllabus_data")
                    except Exception as e:
                        st.error(f"Error generating syllabus: {str(e)}")
                        # Don't reset the topic, just show the error and let the user try again
                        # with the same topic or they can manually change it
                        st.session_state.knowledge_level_submitted = False
                        # Add a message to the chat about the error
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": f"""I encountered an error while generating a syllabus for
                                            '{st.session_state.topic}'.
                                            Please try again or choose a different topic.""",
                            }
                        )
                        st.rerun()

                    # If we got here, syllabus generation was successful
                    # Add message to chat
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"I've generated a new syllabus for {st.session_state.topic}"
                            f" at the {st.session_state.knowledge_level} level."
                            " Please select a lesson to begin.",
                        }
                    )

                    st.session_state.syllabus_selected = True
                    st.rerun()

    elif st.session_state.syllabus_selected and not st.session_state.lesson_selected:
        print("DEBUG: Displaying syllabus page")
        print(f"DEBUG: Syllabus selected: {st.session_state.syllabus_selected}")
        print(f"DEBUG: Lesson selected: {st.session_state.lesson_selected}")
        print(f"DEBUG: Syllabus: {str(st.session_state.syllabus)[0:30]}")
        print(f"DEBUG: Syllabus data: {st.session_state.get('syllabus_data')}")

        try:
            # Check if syllabus is available in either syllabus or syllabus_data
            if not st.session_state.syllabus and not st.session_state.get(
                "syllabus_data"
            ):
                st.error(
                    "No syllabus available. Please try again with a different topic."
                )
                print("DEBUG: No syllabus available")
                # Reset to topic selection
                st.session_state.topic = ""
                st.session_state.knowledge_level = ""
                st.session_state.syllabus_selected = False
                st.rerun()

            # If syllabus is not available but syllabus_data is, use syllabus_data
            if not st.session_state.syllabus and st.session_state.get("syllabus_data"):
                st.session_state.syllabus = st.session_state.syllabus_data
                print("DEBUG: Restored syllabus from syllabus_data")

            # Add a header to make sure something is visible
            st.header("Syllabus Selection")
            st.write(
                "Please select a lesson from the syllabus below to begin learning."
            )

            # Display chat
            display_chat()

            # Display syllabus and allow lesson selection
            display_syllabus(st.session_state.syllabus)

            # Display user progress if available
            if (
                st.session_state.user_email
                and st.session_state.syllabus
                and "topic" in st.session_state.syllabus
            ):
                display_user_progress(
                    st.session_state.user_email, st.session_state.syllabus["topic"]
                )
        except Exception as e:
            st.error(f"Error displaying syllabus page: {str(e)}")
            st.write("Current session state:")
            st.write(
                {
                    "topic": st.session_state.topic,
                    "knowledge_level": st.session_state.knowledge_level,
                    "syllabus_selected": st.session_state.syllabus_selected,
                    "has_syllabus": st.session_state.syllabus is not None,
                }
            )
            # Add a button to reset the app
            if st.button("Reset App"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    elif st.session_state.lesson_selected and not st.session_state.lesson_content:
        try:
            # Get lesson content
            with st.spinner(
                f"Generating content for lesson '{st.session_state.lesson_title}'..."
            ):
                try:
                    # Check if we have all the necessary data
                    if not st.session_state.topic or not st.session_state.knowledge_level:
                        st.error("Missing required data (topic or knowledge level). Please start over.")
                        # Reset session state to start over
                        for key in list(st.session_state.keys()):
                            if key != "initialized":  # Keep the initialized flag
                                del st.session_state[key]
                        st.rerun()

                    # Re-initialize LessonAI if needed
                    if not hasattr(st.session_state.lesson_ai, 'state') or st.session_state.lesson_ai.state is None:
                        print(f"Re-initializing LessonAI with topic: {st.session_state.topic}, knowledge level: {st.session_state.knowledge_level}")
                        st.session_state.lesson_ai.initialize(
                            st.session_state.topic,
                            st.session_state.knowledge_level,
                            st.session_state.user_email,
                        )
                        # Retrieve the syllabus after initialization
                        st.session_state.lesson_ai.state = st.session_state.lesson_ai.graph.invoke({}, {"current": "retrieve_syllabus"})

                    # Now get the lesson content
                    st.session_state.lesson_content = (
                        st.session_state.lesson_ai.get_lesson_content(
                            st.session_state.module_title, st.session_state.lesson_title
                        )
                    )

                    # Add message to chat
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"Here's the lesson content for '{st.session_state.lesson_title}'."
                            " Read through the material, complete the exercises, and take the assessment.",
                        }
                    )

                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating lesson content: {str(e)}")
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"I encountered an error while generating content for '{st.session_state.lesson_title}'. Please try again or select a different lesson.",
                        }
                    )
                    # Reset lesson selection
                    st.session_state.lesson_selected = False
                    st.rerun()
        except Exception as e:
            st.error(f"Error in lesson content generation: {str(e)}")
            # Add a button to go back to syllabus
            if st.button("Return to Syllabus"):
                st.session_state.lesson_selected = False
                st.rerun()

    elif st.session_state.lesson_content:
        # Display chat
        display_chat()

        # Display lesson content
        st.header(st.session_state.lesson_title)
        st.subheader(f"Module: {st.session_state.module_title}")

        display_lesson_content(st.session_state.lesson_content)

        # If lesson is completed, show next lesson options
        if st.session_state.lesson_completed:
            st.subheader("What would you like to do next?")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Return to Syllabus"):
                    # Reset lesson state but keep syllabus
                    st.session_state.module_title = ""
                    st.session_state.lesson_title = ""
                    st.session_state.lesson_content = None
                    st.session_state.current_exercise_index = 0
                    st.session_state.current_assessment_index = 0
                    st.session_state.exercise_responses = {}
                    st.session_state.assessment_responses = {}
                    st.session_state.exercise_feedback = {}
                    st.session_state.assessment_feedback = {}
                    st.session_state.lesson_completed = False
                    st.session_state.lesson_selected = False
                    st.rerun()

            with col2:
                if st.button("Explore a Different Topic"):
                    # Reset everything except user email
                    st.session_state.messages = []
                    st.session_state.lesson_ai = LessonAI()
                    st.session_state.topic = ""
                    st.session_state.knowledge_level = ""
                    st.session_state.syllabus = None
                    st.session_state.module_title = ""
                    st.session_state.lesson_title = ""
                    st.session_state.lesson_content = None
                    st.session_state.current_exercise_index = 0
                    st.session_state.current_assessment_index = 0
                    st.session_state.exercise_responses = {}
                    st.session_state.assessment_responses = {}
                    st.session_state.exercise_feedback = {}
                    st.session_state.assessment_feedback = {}
                    st.session_state.lesson_completed = False
                    st.session_state.topic_submitted = False
                    st.session_state.knowledge_level_submitted = False
                    st.session_state.syllabus_selected = False
                    st.session_state.lesson_selected = False
                    st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("Tech Tree Lesson Demo - Powered by Gemini")


if __name__ == "__main__":
    run_app()
