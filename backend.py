import os
from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client(api_key=API_KEY)

MODEL = "gemini-3.8-flash"


# -------------------------
# READ PDF
# -------------------------

def read_pdf(pdf_file):

    try:
        reader = PdfReader(pdf_file)

        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""

        if not text.strip():
            raise ValueError("No readable text found in PDF")

        return text

    except Exception as e:
        raise ValueError(f"PDF Reading Error: {e}")


# -------------------------
# GENERATE QUIZ
# -------------------------

def generate_quiz(notes):

    if not notes.strip():
        return "Please upload study notes first."

    prompt = f"""
    You are an expert teacher.

    Create 5 MCQ questions from these study notes.

    Rules:
    1. Each question must have 4 options.
    2. Give only one correct answer.
    3. Provide a short explanation.
    4. Use simple student-friendly language.

    Study Notes:
    {notes[:12000]}
    """

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        return response.text

    except Exception as e:
        return f"Quiz Generation Error: {e}"


# -------------------------
# AI TEACHER
# -------------------------

def ask_teacher(question, notes=""):

    if not question.strip():
        return "Please enter a question."

    prompt = f"""
    You are StudyMate AI, a helpful AI teacher.

    Explain concepts in simple language.

    Use examples wherever possible.

    Study Notes:
    {notes[:12000]}

    Student Question:
    {question}
    """

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        return response.text

    except Exception as e:
        return f"AI Teacher Error: {e}"