# StudyMate-AI

An intelligent study companion and personalized learning assistant powered by AI.

## Features
- **Smart Note Processing & RAG**: Semantic and TF-IDF search across study notes.
- **Adaptive Quiz Generator**: Automatically generate quizzes based on notes and student mastery.
- **Spaced Repetition (SRS)**: Flashcards powered by SM-2 spaced repetition algorithm.
- **Interactive AI Tutor**: Socratic tutoring that guides students step-by-step.
- **Hybrid AI Engine**: Works with Claude/Gemini LLM APIs or completely offline without an API key.

## Setup Instructions

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   Copy `.env.example` to `.env` and add your API keys:
   ```bash
   cp .env.example .env
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```
