from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
from datetime import datetime
import json
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.agents import load_tools, initialize_agent, AgentType
from langchain.prompts import PromptTemplate
from fastapi.middleware.cors import CORSMiddleware
import os
import streamlit as st
from googletrans import Translator

# Use Streamlit secrets if available, otherwise try to load from .env
try:
    # When running in Streamlit Cloud
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    # If you have a SerpAPI key, uncomment this:
    # os.environ["SERPAPI_API_KEY"] = st.secrets.get("SERPAPI_API_KEY", "")
except:
    # When running locally with .env file
    from dotenv import load_dotenv
    load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DATABASE_PATH = "docassist.db"

# Initialize LangChain components
def get_llm():
    # Create a new LLM instance for each request to avoid context leakage
    return OpenAI(temperature=0.7, model_name="gpt-3.5-turbo")

search_tools = load_tools(["serpapi"], llm=get_llm())

# Initialize the agent
agent = initialize_agent(
    search_tools,
    get_llm(),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class DiagnosisRequest(BaseModel):
    prompt: str

class PrescriptionRequest(BaseModel):
    prompt: str

class ConsultationRequest(BaseModel):
    doctor_id: int
    patient_id: str
    symptoms: List[str]
    vital_signs: dict  # Keep this field for temperature, BP, etc
    diagnosis: str
    prescription: str
    tests: Optional[List[str]] = None  # List of tests to be performed
    prescription_pdf: Optional[str] = None  # Path to PDF file
    referrals: Optional[List[dict]] = None  # List of specialist referrals
    date: str

class TranslationRequest(BaseModel):
    text: str
    target_language: str

class ReferralRequest(BaseModel):
    doctor_id: int
    patient_id: str
    specialist_id: int
    reason: str
    date: str

# Helper function to create prescription PDF
def create_prescription_pdf(patient_data, diagnosis, prescription, tests=None):
    from fpdf import FPDF
    import tempfile
    import os
    
    # Create a temporary file
    temp_filename = os.path.join(tempfile.gettempdir(), "prescription.pdf")
    
    # Create PDF
    pdf = FPDF()
    # Set font to support Unicode characters
    pdf.add_page()
    pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)
    
    # Add header
    pdf.set_font('DejaVu', '', 16)
    pdf.cell(0, 10, "Medical Prescription", 0, 1, 'C')
    pdf.ln(5)
    
    # Add patient information
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 8, f"Patient: {patient_data.get('name', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Age: {patient_data.get('age', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Gender: {patient_data.get('gender', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Date: {patient_data.get('date', 'N/A')}", 0, 1)
    pdf.ln(5)
    
    # Add diagnosis
    pdf.set_font('DejaVu', '', 14)
    pdf.cell(0, 10, "Diagnosis:", 0, 1)
    pdf.set_font('DejaVu', '', 12)
    
    # Replace bullet points with a hyphen to avoid Unicode issues
    diagnosis_text = diagnosis.replace('\u2022', '-')
    
    # Add diagnosis with multiline support
    pdf.multi_cell(0, 8, diagnosis_text)
    pdf.ln(5)
    
    # Add prescription
    pdf.set_font('DejaVu', '', 14)
    pdf.cell(0, 10, "Prescription:", 0, 1)
    pdf.set_font('DejaVu', '', 12)
    
    # Replace bullet points with a hyphen to avoid Unicode issues
    prescription_text = prescription.replace('\u2022', '-')
    
    # Add prescription with multiline support
    pdf.multi_cell(0, 8, prescription_text)
    
    # Add tests if present
    if tests and len(tests) > 0:
        pdf.ln(5)
        pdf.set_font('DejaVu', '', 14)
        pdf.cell(0, 10, "Recommended Tests:", 0, 1)
        pdf.set_font('DejaVu', '', 12)
        
        for test in tests:
            pdf.cell(0, 8, f"- {test}", 0, 1)
    
    # Output the PDF
    pdf.output(temp_filename)
    
    return temp_filename

# Routes
@app.post("/login")
def login(request: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM doctors WHERE username = ? AND password = ?",
        (request.username, request.password)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {"doctor_id": result["id"]}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/patient/{patient_id}")
def get_patient(patient_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM patients WHERE id = ?",
        (patient_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "name": result["name"],
            "age": result["age"],
            "gender": result["gender"],
            "temperature": result["temperature"],
            "blood_pressure": result["blood_pressure"],
            "pre_conditions": result["pre_conditions"],
            "language": result["language"]  # Added language field
        }
    
    # If not found in DB, return simulated data
    return {
        "name": f"Patient {patient_id}",
        "age": 35,
        "gender": "Male",
        "temperature": "37.2°C",
        "blood_pressure": "120/80",
        "pre_conditions": "None",
        "language": "English"  # Default language
    }

@app.get("/patient-history/{patient_id}")
def get_patient_history(patient_id: str, limit: int = 3):
    """Get patient's consultation history, limited to the most recent records"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First get the patient's pre-existing conditions (from patient table)
    cursor.execute("SELECT pre_conditions FROM patients WHERE id = ?", (patient_id,))
    patient_result = cursor.fetchone()
    pre_conditions = patient_result["pre_conditions"] if patient_result else ""
    
    cursor.execute(
        """
        SELECT diagnosis, prescription, consultation_date, 
               vital_signs, symptoms, tests
        FROM consultations 
        WHERE patient_id = ? 
        ORDER BY consultation_date DESC 
        LIMIT ?
        """,
        (patient_id, limit)
    )
    
    results = cursor.fetchall()
    conn.close()
    
    history = []
    for row in results:
        vital_signs = {}
        try:
            if row["vital_signs"]:
                vital_signs = json.loads(row["vital_signs"])
        except:
            vital_signs = {}
            
        symptoms = []
        try:
            if row["symptoms"]:
                symptoms = json.loads(row["symptoms"])
        except:
            symptoms = []
            
        tests = []
        try:
            if row["tests"]:
                tests = json.loads(row["tests"])
        except:
            tests = []
            
        history.append({
            "diagnosis": row["diagnosis"],
            "prescription": row["prescription"],
            "date": row["consultation_date"],
            "vital_signs": vital_signs,
            "symptoms": symptoms,
            "tests": tests,
            # Add pre-existing conditions from patient table, not consultation
            "pre_conditions": pre_conditions
        })
    
    return history

@app.post("/generate-diagnosis")
def generate_diagnosis(request: DiagnosisRequest):
    try:
        # Create a fresh LLM instance for this request
        llm = get_llm()
        
        # Use LangChain with OpenAI
        diagnosis_prompt = PromptTemplate(
            input_variables=["patient_info"],
            template="{patient_info}"
        )
        
        diagnosis_chain = LLMChain(llm=llm, prompt=diagnosis_prompt)
        diagnosis = diagnosis_chain.run(request.prompt)
        
        return {"diagnosis": diagnosis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-prescription")
def generate_prescription(request: PrescriptionRequest):
    try:
        # Create a fresh LLM instance for this request
        llm = get_llm()
        
        # Use LangChain with OpenAI and search tools
        medication_prompt = PromptTemplate(
            input_variables=["diagnosis"],
            template="""Generate a detailed prescription with appropriate medications available in the Pakistani market for this diagnosis: {diagnosis}
            
Include for each medication:
1. Medication name
2. Dosage information
3. Frequency of administration
4. Duration of treatment
5. Common side effects
6. Potential interactions with other medications
7. Pregnancy safety information (FDA category and recommendations)

Format your response as a structured and clear table with all the above information."""
        )
        
        # First try with direct LLM for faster response
        medication_chain = LLMChain(llm=llm, prompt=medication_prompt)
        prescription = medication_chain.run(request.prompt)
        
        # If we need to search for specific medications, we could use the agent
        # result = agent.run(f"Find specific medications available in Pakistan for {prescription}")
        
        return {"prescription": prescription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-consultation")
def save_consultation(request: ConsultationRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            INSERT INTO consultations (
                doctor_id, patient_id, symptoms, vital_signs,
                diagnosis, prescription, prescription_pdf, consultation_date, 
                tests, referrals
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.doctor_id,
                request.patient_id,
                json.dumps(request.symptoms),
                json.dumps(request.vital_signs),
                request.diagnosis,
                request.prescription,
                request.prescription_pdf,
                request.date,
                json.dumps(request.tests) if request.tests else None,
                json.dumps(request.referrals) if request.referrals else None
            )
        )
        # Get the ID of the inserted record
        consultation_id = cursor.lastrowid
        conn.commit()
        return {"status": "success", "consultation_id": consultation_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/translate")
def translate_text(request: TranslationRequest):
    try:
        translator = Translator()
        translated = translator.translate(request.text, dest=request.target_language.lower())
        return {"translated_text": translated.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")

@app.post("/update-patient")
def update_patient(patient_id: str, pre_conditions: str):
    """Update patient information, particularly pre-existing conditions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE patients SET pre_conditions = ? WHERE id = ?",
            (pre_conditions, patient_id)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/clear-consultations")
def clear_consultations():
    """Clear all records from the consultations table for demo purposes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Keep a count of how many records were deleted
        cursor.execute("SELECT COUNT(*) FROM consultations")
        count = cursor.fetchone()[0]
        
        # Delete all records from consultations table
        cursor.execute("DELETE FROM consultations")
        
        # Also remove any prescription PDFs
        import os
        import glob
        pdf_dir = "data/prescription"
        if os.path.exists(pdf_dir):
            files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
            for f in files:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Error removing file {f}: {e}")
        
        conn.commit()
        return {"status": "success", "message": f"Cleared {count} consultation records and associated PDFs"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/specialist-categories")
def get_specialist_categories():
    """Get all unique specialist categories"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT category FROM specialists ORDER BY category")
        categories = [row["category"] for row in cursor.fetchall()]
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/specialists")
def get_specialists(category: Optional[str] = None):
    """Get all specialists, optionally filtered by category"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if category:
            cursor.execute(
                "SELECT * FROM specialists WHERE category = ? ORDER BY name",
                (category,)
            )
        else:
            cursor.execute("SELECT * FROM specialists ORDER BY category, name")
            
        specialists = []
        for row in cursor.fetchall():
            specialists.append({
                "id": row["id"],
                "name": row["name"],
                "category": row["category"],
                "hospital": row["hospital"],
                "contact": row["contact"],
                "availability": row["availability"]
            })
        return {"specialists": specialists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/specialist/{specialist_id}")
def get_specialist(specialist_id: int):
    """Get a specific specialist by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT * FROM specialists WHERE id = ?",
            (specialist_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Specialist not found")
            
        specialist = {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "hospital": row["hospital"],
            "contact": row["contact"],
            "availability": row["availability"]
        }
        return specialist
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/save-referral")
def save_referral(request: ReferralRequest):
    """Save a specialist referral"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            INSERT INTO referrals (
                doctor_id, patient_id, specialist_id, reason, referral_date
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.doctor_id,
                request.patient_id,
                request.specialist_id,
                request.reason,
                request.date
            )
        )
        # Get the ID of the inserted record
        referral_id = cursor.lastrowid
        conn.commit()
        return {"status": "success", "referral_id": referral_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Run server with: uvicorn api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
