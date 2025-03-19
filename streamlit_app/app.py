import streamlit as st
import sys
import os

# Add the parent directory to the path so we can import the ai module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    This app demonstrates an adaptive learning system that asks questions of increasing difficulty based on your performance.
    The questions are generated based on the latest information available online, making them accurate and up-to-date.
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
    st.session_state.initialized = True

# Topic selection
if not st.session_state.topic:
    st.subheader("What topic would you like to explore?")
    
    topic = st.text_input("Enter a topic")
    
    if st.button("Start Quiz") and topic:
        st.session_state.topic = topic
        st.session_state.tech_tree_ai.initialize(topic)
        st.session_state.messages.append({"role": "user", "content": f"I want to learn about {topic}"})
        st.session_state.messages.append({"role": "assistant", "content": f"Great! Let's explore {topic}. I'll search for some information to create questions for you."})
        st.rerun()

# If topic is selected but search not completed
elif not st.session_state.search_completed:
    st.info(f"Searching for information about '{st.session_state.topic}'...")
    
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
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Answer input
    answer = st.text_input("Your answer")
    
    if st.button("Submit Answer") and answer:
        # Add the answer to the messages
        st.session_state.messages.append({"role": "user", "content": answer})
        
        # Evaluate the answer
        result = st.session_state.tech_tree_ai.evaluate_answer(answer)
        
        # Determine feedback message
        if result["is_correct"]:
            feedback = "Correct! " + result.get("feedback", "")
        elif result["is_partially_correct"]:
            feedback = "Partially correct. " + result.get("feedback", "")
        else:
            feedback = "Incorrect. " + result.get("feedback", "")
        
        # Add the feedback to the messages
        st.session_state.messages.append({"role": "assistant", "content": feedback})
        
        # Check if the quiz is complete
        if result["is_complete"]:
            st.session_state.quiz_completed = True
            
            # Get the final assessment
            assessment = st.session_state.tech_tree_ai.get_final_assessment()
            
            # Create the final assessment message
            final_message = "Thanks for playing the Tech Tree demo!\n\n"
            final_message += "Final Assessment:\n"
            final_message += f"Correct answers: {assessment['correct_answers']}\n"
            final_message += f"Partially correct answers: {assessment['partially_correct_answers']}\n"
            final_message += f"Incorrect answers: {assessment['incorrect_answers']}\n\n"
            final_message += f"Weighted score: {assessment['total_score']:.1f}/{assessment['max_possible_score']:.1f} "
            final_message += f"({assessment['weighted_percentage']:.1f}%)\n"
            final_message += f"Overall knowledge level: {assessment['knowledge_level']}"
            
            # Add the final assessment to the messages
            st.session_state.messages.append({"role": "assistant", "content": final_message})
        else:
            # Generate the next question
            result = st.session_state.tech_tree_ai.generate_question()
            question_text = f"[{result['difficulty_str']}] {result['question']}"
            st.session_state.messages.append({"role": "assistant", "content": question_text})
        
        st.rerun()

# If quiz completed
else:
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Restart button
    if st.button("Start a new quiz"):
        st.session_state.messages = []
        st.session_state.topic = ""
        st.session_state.search_completed = False
        st.session_state.search_status = ""
        st.session_state.quiz_started = False
        st.session_state.quiz_completed = False
        st.session_state.tech_tree_ai = TechTreeAI()
        st.rerun()

# Footer
st.markdown("---")
st.markdown("Tech Tree Demo - Powered by Gemini and Tavily")