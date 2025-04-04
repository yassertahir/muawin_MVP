# Muawin AI - Doctor's Assistant MVP

This is an MVP for Muawin, an AI assistant for doctors in developing countries. The application allows doctors to input patient data and symptoms, receive AI-generated diagnoses, and create digital prescriptions.

## Features

- Doctor authentication system
- Patient data management
- Symptom selection interface
- AI-powered diagnosis generation
- Digital prescription creation
- PDF prescription export
- Consultation history tracking

## Setup Instructions

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/muawin-mvp.git
   cd muawin-mvp
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your API keys:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your actual API keys.

5. Initialize the database:
   ```
   python db_init.py
   ```

6. Start the FastAPI backend:
   ```
   uvicorn api:app --reload
   ```

7. In a new terminal, start the Streamlit frontend:
   ```
   streamlit run app.py
   ```

8. Access the application in your browser at `http://localhost:8501`

## Default Login

- Username: admin
- Password: admin

## Project Structure

- `app.py` - Streamlit frontend application
- `api.py` - FastAPI backend server
- `db_init.py` - Database initialization script
- `muawin.db` - SQLite database (created after initialization)
- `patients.csv` - Sample patient IDs for dropdown
- `requirements.txt` - Project dependencies
- `.env` - Environment variables (API keys)

## Tech Stack

- Frontend: Streamlit
- Backend: FastAPI
- Database: SQLite
- AI: OpenAI GPT via LangChain
- PDF Generation: FPDF
- Web Search: SerpAPI via LangChain
