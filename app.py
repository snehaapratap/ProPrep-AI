import streamlit as st
import google.generativeai as genai
import os
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv
from google.api_core import retry
import time

st.set_page_config(layout="centered")
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Please set your Google API key in the .env file")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Initialize session states
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_question" not in st.session_state:
    st.session_state.current_question = 0
if "resume_analyzed" not in st.session_state:
    st.session_state.resume_analyzed = False
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False

# Function to process PDF
def process_pdf(uploaded_file):
    try:
        pdf_bytes = BytesIO(uploaded_file.read())
        pdf_reader = PyPDF2.PdfReader(pdf_bytes)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return ""

# Function to generate questions based on resume
def generate_questions(resume_text):
    max_retries = 3
    retry_delay = 2  
    
    for attempt in range(max_retries):
        try:
            prompt = f"""Based on this resume: {resume_text}
            Generate 5 relevant interview questions. Return ONLY an array of questions."""
            
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            
            questions = response.text.strip().split('\n')
            return [q.strip().strip('0123456789.') for q in questions if q.strip()]
            
        except Exception as e:
            if attempt < max_retries - 1:
                st.warning(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            else:
                st.error(f"Failed to generate questions after {max_retries} attempts. Error: {str(e)}")
                return ["What are your key strengths?",
                        "Tell me about your most challenging project.",
                        "Where do you see yourself in 5 years?",
                        "What made you choose your field of study/work?",
                        "How do you handle difficult situations at work?"]

# Main UI
st.title("Resume Analysis & Interview Bot 🤖")

# PDF Upload Section
if not st.session_state.resume_analyzed:
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type=['pdf'])
    if uploaded_file:
        with st.spinner('Analyzing resume...'):
            resume_text = process_pdf(uploaded_file)
            if resume_text:  # Only proceed if PDF processing was successful
                st.session_state.questions = generate_questions(resume_text)
                st.session_state.resume_analyzed = True
                st.rerun()
            else:
                st.error("Failed to process the PDF. Please try again with a different file.")

# Interview Section
if st.session_state.resume_analyzed and not st.session_state.interview_complete:
    if st.session_state.current_question < len(st.session_state.questions):
        st.write(f"### Question {st.session_state.current_question + 1}:")
        st.write(st.session_state.questions[st.session_state.current_question])
        
        user_answer = st.text_area("Your answer:", key=f"answer_{st.session_state.current_question}")
        
        if st.button("Next Question"):
            if user_answer:
                st.session_state.messages.append(("Question", st.session_state.questions[st.session_state.current_question]))
                st.session_state.messages.append(("Answer", user_answer))
                st.session_state.current_question += 1
                if st.session_state.current_question >= len(st.session_state.questions):
                    st.session_state.interview_complete = True
                st.rerun()
            else:
                st.error("Please provide an answer before continuing.")

# Feedback Section
if st.session_state.interview_complete:
    if "feedback_given" not in st.session_state:
        with st.spinner('Generating feedback...'):
            feedback_prompt = "Based on these interview responses:\n"
            for i in range(0, len(st.session_state.messages), 2):
                feedback_prompt += f"\nQ: {st.session_state.messages[i][1]}\nA: {st.session_state.messages[i+1][1]}\n"
            feedback_prompt += "\nProvide a comprehensive feedback on the interview responses, including strengths and areas for improvement."
            
            feedback = model.generate_content(feedback_prompt)
            st.session_state.feedback = feedback.text
            st.session_state.feedback_given = True

    st.write("### Interview Feedback")
    st.write(st.session_state.feedback)

    if st.button("Start New Interview"):
        for key in ['messages', 'current_question', 'resume_analyzed', 'interview_complete', 
                   'questions', 'feedback_given', 'feedback']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()