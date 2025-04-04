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
DATABASE_PATH = "muawin.db"

# OpenAI API key
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "your-api-key")

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
    diagnosis: str
    prescription: str
    date: str

# Helper function to create prescription PDF
def create_prescription_pdf(patient_data, diagnosis, prescription):
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
    # In a real application, this would fetch from the database
    # For demo, we'll simulate retrieving data
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
            "pre_conditions": result["pre_conditions"]
        }
    
    # If not found in DB, return simulated data
    # In a real app, you'd raise a 404 error
    return {
        "name": f"Patient {patient_id}",
        "age": 35,
        "gender": "Male",
        "temperature": "37.2°C",
        "blood_pressure": "120/80",
        "pre_conditions": "None"
    }

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
            template="Generate a detailed prescription with appropriate medications available in the Pakistani market for this diagnosis: {diagnosis}"
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
            INSERT INTO consultations (doctor_id, patient_id, symptoms, diagnosis, prescription, consultation_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.doctor_id,
                request.patient_id,
                json.dumps(request.symptoms),
                request.diagnosis,
                request.prescription,
                request.date
            )
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Run server with: uvicorn api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
