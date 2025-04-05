import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import os
import tempfile
from fpdf import FPDF
import base64

# Configure the page
st.set_page_config(page_title="Muawin - AI Assistant for Doctors", layout="wide")

# Initialize session state variables if they don't exist
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "patient_id" not in st.session_state:
    st.session_state.patient_id = None
if "patient_data" not in st.session_state:
    st.session_state.patient_data = None
if "symptoms" not in st.session_state:
    st.session_state.symptoms = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "diagnosis" not in st.session_state:
    st.session_state.diagnosis = None
if "prescription" not in st.session_state:
    st.session_state.prescription = None
if "final_prescription" not in st.session_state:
    st.session_state.final_prescription = False
    
# Base URL for API
BASE_URL = "http://localhost:8000"

def login(username, password):
    response = requests.post(
        f"{BASE_URL}/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        st.session_state.authenticated = True
        st.session_state.doctor_id = data["doctor_id"]
        return True
    return False

def logout():
    st.session_state.authenticated = False
    st.session_state.doctor_id = None
    st.session_state.patient_id = None
    st.session_state.patient_data = None
    st.session_state.symptoms = []
    st.session_state.chat_history = []
    st.session_state.diagnosis = None
    st.session_state.prescription = None
    st.session_state.final_prescription = False
    # Clear the medications list when logging out
    if "medications" in st.session_state:
        del st.session_state.medications

def start_new_conversation():
    st.session_state.patient_id = None
    st.session_state.patient_data = None
    st.session_state.symptoms = []
    st.session_state.chat_history = []
    st.session_state.diagnosis = None
    st.session_state.prescription = None
    st.session_state.final_prescription = False
    # Clear the medications list to prevent data leakage between consultations
    if "medications" in st.session_state:
        del st.session_state.medications

def get_patient_list():
    try:
        df = pd.read_csv("patients.csv")
        return df["patientId"].tolist()
    except Exception as e:
        st.error(f"Error loading patient list: {e}")
        return []

def get_patient_data(patient_id):
    response = requests.get(f"{BASE_URL}/patient/{patient_id}")
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch patient data")
        return None

def get_common_symptoms():
    return [
        "Fever", "Headache", "Cough", "Sore Throat", "Fatigue", "Nausea",
        "Vomiting", "Diarrhea", "Abdominal Pain", "Chest Pain", "Shortness of Breath",
        "Dizziness", "Rash", "Joint Pain", "Back Pain", "Sweating", "Chills"
    ]

def generate_diagnosis(patient_data, symptoms):
    prompt = f"""You are a primary healthcare physician in Pakistan. A patient with following details:
Name: {patient_data['name']}
Age: {patient_data['age']}
Gender: {patient_data['gender']}
Temperature: {patient_data['temperature']}
Blood Pressure: {patient_data['blood_pressure']}
Pre-existing Conditions: {patient_data['pre_conditions']}

Showing the following symptoms:
{', '.join(symptoms)}

Evaluate this and provide a list of possible diagnosis. The output format should be as follows:
DIAGNOSIS:
Reasons:
Treatment plan:"""

    response = requests.post(
        f"{BASE_URL}/generate-diagnosis",
        json={"prompt": prompt}
    )
    
    if response.status_code == 200:
        return response.json()["diagnosis"]
    else:
        st.error("Failed to generate diagnosis")
        return None

def regenerate_diagnosis(original_prompt, doctor_comments):
    prompt = f"""Another doctor has provide following comments about the diagnosis:
{doctor_comments}

Patient information is:
{original_prompt}

Analyse and provide diagnosis"""

    response = requests.post(
        f"{BASE_URL}/generate-diagnosis",
        json={"prompt": prompt}
    )
    
    if response.status_code == 200:
        return response.json()["diagnosis"]
    else:
        st.error("Failed to regenerate diagnosis")
        return None

def generate_prescription(diagnosis, patient_data):
    prompt = f"""Based on the following diagnosis for a patient in Pakistan:
{diagnosis}

Patient details:
Name: {patient_data['name']}
Age: {patient_data['age']}
Gender: {patient_data['gender']}

Generate a detailed prescription with appropriate medications available in the Pakistani market.
Include dosage, frequency, and duration for each medication. Format your response as a table of medications,
 with Name, dosage, Duration and side-effects."""

    response = requests.post(
        f"{BASE_URL}/generate-prescription",
        json={"prompt": prompt}
    )
    
    if response.status_code == 200:
        return response.json()["prescription"]
    else:
        st.error("Failed to generate prescription")
        return None

def save_consultation(doctor_id, patient_id, symptoms, diagnosis, prescription):
    data = {
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "symptoms": symptoms,
        "diagnosis": diagnosis,
        "prescription": prescription,
        "date": datetime.now().isoformat()
    }
    
    response = requests.post(
        f"{BASE_URL}/save-consultation",
        json=data
    )
    
    if response.status_code == 200:
        return True
    else:
        st.error("Failed to save consultation")
        return False

def create_prescription_pdf(patient_data, diagnosis, prescription):
    from fpdf import FPDF
    import tempfile
    import os
    import re
    
    # Create a temporary file
    temp_filename = os.path.join(tempfile.gettempdir(), "prescription.pdf")
    
    # Create PDF
    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            self.add_page()
            self.set_auto_page_break(auto=True, margin=15)
    
    pdf = PDF()
    pdf.set_font('Arial', '', 12)
    
    # Add header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, "Medical Prescription", 0, 1, 'C')
    pdf.ln(5)
    
    # Add patient information
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Patient: {patient_data.get('name', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Age: {patient_data.get('age', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Gender: {patient_data.get('gender', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Date: {patient_data.get('date', 'N/A')}", 0, 1)
    pdf.ln(5)
    
    # Add diagnosis
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Diagnosis:", 0, 1)
    pdf.set_font('Arial', '', 12)
    
    # Clean text by replacing Unicode characters
    def clean_text(text):
        # Replace Unicode bullet points, em dashes, etc. with ASCII equivalents
        text = text.replace('\u2022', '-')  # Bullet point to hyphen
        text = text.replace('\u2013', '-')  # En dash to hyphen
        text = text.replace('\u2014', '-')  # Em dash to hyphen
        text = text.replace('\u2018', "'")  # Left single quote
        text = text.replace('\u2019', "'")  # Right single quote
        text = text.replace('\u201c', '"')  # Left double quote
        text = text.replace('\u201d', '"')  # Right double quote
        text = text.replace('\u2026', '...')  # Ellipsis
        # Try to handle any other non-Latin1 characters
        return re.sub(r'[^\x00-\xff]', '?', text)
    
    # Clean and add diagnosis with multiline support
    clean_diagnosis = clean_text(diagnosis)
    pdf.multi_cell(0, 8, clean_diagnosis)
    pdf.ln(5)
    
    # Add prescription
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Prescription:", 0, 1)
    pdf.set_font('Arial', '', 12)
    
    # Parse the prescription to determine if it's in table format
    if "PRESCRIPTION:" in prescription and "• " in prescription:
        # It's likely the formatted prescription from our table
        # Extract medication details
        medications = []
        lines = prescription.split('\n')
        reading_meds = False
        reading_instructions = False
        additional_instructions = ""
        
        for line in lines:
            if "PRESCRIPTION:" in line:
                reading_meds = True
                continue
                
            if "ADDITIONAL INSTRUCTIONS:" in line:
                reading_meds = False
                reading_instructions = True
                continue
                
            if reading_meds and line.strip() and line.strip().startswith("• "):
                medications.append(line.strip())
                
            if reading_instructions and line.strip():
                additional_instructions += line + "\n"
        
        # Add medications as a formatted list
        for med in medications:
            cleaned_med = clean_text(med)
            pdf.cell(0, 8, cleaned_med, 0, 1)
        
        # Add additional instructions if any
        if additional_instructions.strip():
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Additional Instructions:", 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 8, clean_text(additional_instructions))
    else:
        # Just use the raw prescription text
        clean_prescription = clean_text(prescription)
        pdf.multi_cell(0, 8, clean_prescription)
    
    # Output the PDF
    pdf.output(temp_filename)
    
    return temp_filename

def display_login():
    st.title("Muawin - AI Assistant for Doctors")
    
    with st.form("login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="admin")
        submit = st.form_submit_button("Login")
        
        if submit:
            if login(username, password):
                st.success("Login successful!")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")

def display_main_interface():
    st.title("Muawin - AI Assistant for Doctors")
    
    # Sidebar for session controls
    with st.sidebar:
        st.button("Logout", on_click=logout)
        st.button("Start New Consultation", on_click=start_new_conversation)
    
    if st.session_state.patient_id is None:
        # Patient selection
        patient_ids = get_patient_list()
        selected_patient = st.selectbox("Select Patient ID", [""] + patient_ids)
        
        if selected_patient:
            if st.button("Get Patient Data"):
                patient_data = get_patient_data(selected_patient)
                if patient_data:
                    st.session_state.patient_id = selected_patient
                    st.session_state.patient_data = patient_data
                    st.experimental_rerun()
    
    elif st.session_state.patient_data and not st.session_state.symptoms:
        # Display patient information
        patient_data = st.session_state.patient_data
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Patient Information")
            st.write(f"**Name:** {patient_data['name']}")
            st.write(f"**Age:** {patient_data['age']}")
            st.write(f"**Gender:** {patient_data['gender']}")
        
        with col2:
            st.subheader("Vital Signs")
            st.write(f"**Temperature:** {patient_data['temperature']} °C")
            st.write(f"**Blood Pressure:** {patient_data['blood_pressure']}")
            st.write(f"**Pre-existing Conditions:** {patient_data['pre_conditions']}")
        
        # Symptom selection
        st.subheader("Symptoms")
        common_symptoms = get_common_symptoms()
        
        selected_symptoms = []
        cols = st.columns(3)
        for i, symptom in enumerate(common_symptoms):
            col_idx = i % 3
            with cols[col_idx]:
                if st.checkbox(symptom):
                    selected_symptoms.append(symptom)
        
        # Initialize a session state for temporary custom symptoms if it doesn't exist
        if "temp_custom_symptoms" not in st.session_state:
            st.session_state.temp_custom_symptoms = []
            
        # Display custom symptoms that have been added but not yet confirmed
        if st.session_state.temp_custom_symptoms:
            st.write("**Custom symptoms to be added:**")
            for i, symptom in enumerate(st.session_state.temp_custom_symptoms):
                st.write(f"- {symptom}")
                
        # Custom symptom input
        custom_symptom = st.text_input("Add custom symptom")
        if custom_symptom and st.button("Add Custom Symptom"):
            st.session_state.temp_custom_symptoms.append(custom_symptom)
            st.experimental_rerun()
        
        # Include both selected checkboxes and custom symptoms when confirming
        if st.button("Confirm Symptoms"):
            all_symptoms = selected_symptoms + st.session_state.temp_custom_symptoms
            if all_symptoms:  # Only update if there are symptoms
                st.session_state.symptoms = all_symptoms
                # Clear temporary custom symptoms
                st.session_state.temp_custom_symptoms = []
                st.experimental_rerun()
    
    elif st.session_state.symptoms and not st.session_state.diagnosis:
        # Display patient info and symptoms
        patient_data = st.session_state.patient_data
        symptoms = st.session_state.symptoms
        
        st.subheader("Patient Information")
        st.write(f"**Name:** {patient_data['name']}, **Age:** {patient_data['age']}, **Gender:** {patient_data['gender']}")
        
        st.subheader("Symptoms")
        st.write(", ".join(symptoms))
        
        if st.button("Generate Diagnosis"):
            diagnosis = generate_diagnosis(patient_data, symptoms)
            if diagnosis:
                st.session_state.diagnosis = diagnosis
                st.experimental_rerun()
    
    elif st.session_state.diagnosis and not st.session_state.prescription:
        # Display diagnosis and allow doctor feedback
        patient_data = st.session_state.patient_data
        symptoms = st.session_state.symptoms
        
        st.subheader("Patient Information")
        st.write(f"**Name:** {patient_data['name']}, **Age:** {patient_data['age']}, **Gender:** {patient_data['gender']}")
        
        st.subheader("Symptoms")
        st.write(", ".join(symptoms))
        
        st.subheader("AI-Generated Diagnosis")
        
        # Display the full diagnosis text
        st.write(st.session_state.diagnosis)
        
        # Extract possible diagnoses from the text
        import re
        diagnosis_text = st.session_state.diagnosis
        possible_diagnoses = []
        
        # Try to find diagnoses in the text - common formats like lists with bullets, numbers, or after "DIAGNOSIS:"
        if "DIAGNOSIS:" in diagnosis_text:
            diagnosis_section = diagnosis_text.split("DIAGNOSIS:")[1].split("Reasons:")[0].strip()
            possible_diagnoses = [d.strip() for d in re.split(r'[\n•\-\*]+', diagnosis_section) if d.strip()]
        else:
            # Look for bullet points or numbered lists
            possible_diagnoses = [d.strip() for d in re.split(r'[\n•\-\*\d+\.]+', diagnosis_text) 
                                 if d.strip() and len(d.strip()) < 100]  # Avoid long paragraphs
        
        # Filter out very short entries that might not be diagnoses
        possible_diagnoses = [d for d in possible_diagnoses if len(d) > 5]
        
        # If no diagnoses found, try to split by newlines
        if not possible_diagnoses:
            lines = diagnosis_text.split('\n')
            possible_diagnoses = [line.strip() for line in lines if line.strip() and len(line.strip()) < 100]
        
        # Add option for "Other" if any diagnoses were found
        if possible_diagnoses:
            possible_diagnoses.append("Other (write below)")
        
        if possible_diagnoses:
            st.subheader("Select Diagnoses")
            selected_diagnoses = []
            
            # Create checkboxes for each possible diagnosis
            for diagnosis in possible_diagnoses:
                if st.checkbox(diagnosis, key=f"diag_{diagnosis}"):
                    selected_diagnoses.append(diagnosis)
            
            # Text area for custom diagnosis or additional notes
            additional_notes = st.text_area("Additional Diagnosis Notes", height=100, 
                                           help="Add any diagnoses not listed above or additional notes")
            
            # Combine selected diagnoses and additional notes
            if st.button("Confirm Diagnosis"):
                final_diagnosis = ""
                if selected_diagnoses:
                    final_diagnosis += "Selected Diagnoses:\n" + "\n".join([f"• {d}" for d in selected_diagnoses if d != "Other (write below)"]) + "\n\n"
                if additional_notes:
                    final_diagnosis += "Additional Notes:\n" + additional_notes
                
                # If nothing was selected or written, use the original diagnosis
                if not final_diagnosis.strip():
                    final_diagnosis = diagnosis_text
                    
                # Update the diagnosis and move to prescription
                st.session_state.diagnosis = final_diagnosis
                prescription = generate_prescription(final_diagnosis, patient_data)
                if prescription:
                    st.session_state.prescription = prescription
                    st.experimental_rerun()
        else:
            # If no diagnoses could be extracted, just provide buttons for the next steps
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Accept Diagnosis"):
                    prescription = generate_prescription(st.session_state.diagnosis, patient_data)
                    if prescription:
                        st.session_state.prescription = prescription
                        st.experimental_rerun()
            
            with col2:
                if st.button("Regenerate Diagnosis"):
                    doctor_comments = st.text_area("Your comments for regeneration")
                    original_prompt = f"""You are a primary healthcare physician in Pakistan. A patient with following details:
Name: {patient_data['name']}
Age: {patient_data['age']}
Gender: {patient_data['gender']}
Temperature: {patient_data['temperature']}
Blood Pressure: {patient_data['blood_pressure']}
Pre-existing Conditions: {patient_data['pre_conditions']}

Showing the following symptoms:
{', '.join(symptoms)}"""

                    if doctor_comments and st.button("Submit Comments"):
                        new_diagnosis = regenerate_diagnosis(original_prompt, doctor_comments)
                        if new_diagnosis:
                            st.session_state.diagnosis = new_diagnosis
                            st.experimental_rerun()
            
            with col3:
                if st.button("Manual Diagnosis"):
                    manual_diagnosis = st.text_area("Enter your diagnosis")
                    if manual_diagnosis and st.button("Confirm Manual Diagnosis"):
                        st.session_state.diagnosis = manual_diagnosis
                        st.experimental_rerun()
    
    elif st.session_state.prescription and not st.session_state.final_prescription:
        patient_data = st.session_state.patient_data
        diagnosis = st.session_state.diagnosis
        prescription = st.session_state.prescription
        
        st.subheader("Patient Information")
        st.write(f"**Name:** {patient_data['name']}, **Age:** {patient_data['age']}, **Gender:** {patient_data['gender']}")
        
        st.subheader("Diagnosis")
        st.write(diagnosis)
        
        st.subheader("Generated Prescription")
        
        # Extract medication info from prescription text
        import re
        import pandas as pd
        
        # Initialize an empty list to store medications
        medications = []
        
        # Check if prescription contains a markdown/ascii table
        if "|" in prescription and "-|-" in prescription:
            # Try to parse markdown table
            lines = prescription.strip().split('\n')
            header = None
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith("|") and i < len(lines)-1 and "-|-" in line:
                    # This is the header row
                    header = [col.strip() for col in line.strip("|").split("|")]
                    break
            
            # If we found a header, extract data rows
            if header:
                for i, line in enumerate(lines):
                    if i > 0 and line.startswith("|") and not "-|-" in line:
                        columns = [col.strip() for col in line.strip("|").split("|")]
                        if len(columns) >= 4:  # At least medication, dosage, duration, side-effects
                            medications.append({
                                "medication": columns[0],
                                "dosage": columns[1],
                                "duration": columns[2],
                                "side_effects": columns[3] if len(columns) > 3 else ""
                            })
        
        # If table parsing failed, try normal text parsing
        if not medications:
            lines = re.split(r'\n+', prescription)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Remove bullet points, numbers, etc.
                cleaned_line = re.sub(r'^[\s•\-\*\d\.]+', '', line).strip()
                
                # Skip very short lines or headers
                if len(cleaned_line) < 5 or ":" in cleaned_line[:15]:
                    continue
                    
                # Try to extract medication components
                parts = re.split(r'[-,:]', cleaned_line, 4)
                
                if len(parts) >= 1:
                    med_name = parts[0].strip()
                    dosage = parts[1].strip() if len(parts) > 1 else ""
                    frequency = parts[2].strip() if len(parts) > 2 else ""
                    duration = parts[3].strip() if len(parts) > 3 else ""
                    side_effects = parts[4].strip() if len(parts) > 4 else ""
                    
                    medications.append({
                        "medication": med_name,
                        "dosage": dosage,
                        "frequency": frequency,
                        "duration": duration,
                        "side_effects": side_effects
                    })
        
        # If no medications were extracted, add an empty row
        if not medications:
            medications.append({
                "medication": "",
                "dosage": "",
                "frequency": "",
                "duration": "",
                "side_effects": ""
            })
        
        # Create session state for medications if it doesn't exist
        if "medications" not in st.session_state:
            st.session_state.medications = medications
        
        # Display the editable prescription table
        st.write("### Edit Prescription")
        
        # Create column headers for the table
        col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 3, 1])
        with col1:
            st.write("**Medication**")
        with col2:
            st.write("**Dosage**")
        with col3:
            st.write("**Frequency**")
        with col4:
            st.write("**Duration**")
        with col5:
            st.write("**Side Effects**")
        with col6:
            st.write("**Action**")
        
        # Display each medication as a row in the table
        for i, med in enumerate(st.session_state.medications):
            col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 3, 1])
            
            with col1:
                st.session_state.medications[i]["medication"] = st.text_input(
                    "Medication", 
                    value=med["medication"], 
                    key=f"med_{i}", 
                    label_visibility="collapsed"
                )
            
            with col2:
                st.session_state.medications[i]["dosage"] = st.text_input(
                    "Dosage", 
                    value=med["dosage"], 
                    key=f"dose_{i}", 
                    label_visibility="collapsed"
                )
            
            with col3:
                st.session_state.medications[i]["frequency"] = st.text_input(
                    "Frequency", 
                    value=med.get("frequency", ""), 
                    key=f"freq_{i}", 
                    label_visibility="collapsed"
                )
            
            with col4:
                st.session_state.medications[i]["duration"] = st.text_input(
                    "Duration", 
                    value=med["duration"], 
                    key=f"dur_{i}", 
                    label_visibility="collapsed"
                )
            
            with col5:
                st.session_state.medications[i]["side_effects"] = st.text_input(
                    "Side Effects", 
                    value=med.get("side_effects", ""), 
                    key=f"side_{i}", 
                    label_visibility="collapsed"
                )
            
            with col6:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.medications.pop(i)
                    st.experimental_rerun()
        
        # Button to add a new medication row
        if st.button("+ Add Medication"):
            st.session_state.medications.append({
                "medication": "",
                "dosage": "",
                "frequency": "",
                "duration": "",
                "side_effects": ""
            })
            st.experimental_rerun()
        
        # Additional instructions text area
        additional_instructions = st.text_area(
            "Additional Instructions", 
            value="", 
            height=100, 
            help="Add any additional instructions, lifestyle recommendations, etc."
        )
        
        # Finalize prescription button
        if st.button("Generate Final Prescription"):
            # Format the prescription table as text
            final_prescription = "PRESCRIPTION:\n\n"
            
            for med in st.session_state.medications:
                if med["medication"].strip():  # Only include non-empty medications
                    final_prescription += f"• {med['medication']}"
                    if med["dosage"].strip():
                        final_prescription += f" - {med['dosage']}"
                    if med.get("frequency", "").strip():
                        final_prescription += f" - {med['frequency']}"
                    if med["duration"].strip():
                        final_prescription += f" - {med['duration']}"
                    if med.get("side_effects", "").strip():
                        final_prescription += f" (Side effects: {med['side_effects']})"
                    final_prescription += "\n"
            
            if additional_instructions:
                final_prescription += f"\nADDITIONAL INSTRUCTIONS:\n{additional_instructions}\n"
            
            # Update the prescription
            st.session_state.prescription = final_prescription
            st.session_state.final_prescription = True
            st.experimental_rerun()
    
    elif st.session_state.final_prescription:
        # Display and edit prescription
        patient_data = st.session_state.patient_data
        diagnosis = st.session_state.diagnosis
        
        st.subheader("Patient Information")
        st.write(f"**Name:** {patient_data['name']}, **Age:** {patient_data['age']}, **Gender:** {patient_data['gender']}")
        
        st.subheader("Diagnosis")
        st.write(diagnosis)
        
        st.subheader("Prescription")
        prescription = st.text_area("Edit Prescription if needed", value=st.session_state.prescription, height=300)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Generate PDF"):
                pdf_path = create_prescription_pdf(patient_data, diagnosis, prescription)
                
                # Create download button for PDF
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
                    
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="prescription.pdf">Download Prescription PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
                
                # Save consultation to database
                save_consultation(
                    st.session_state.doctor_id,
                    st.session_state.patient_id,
                    st.session_state.symptoms,
                    diagnosis,
                    prescription
                )
        
        with col2:
            if st.button("End Consultation"):
                # First save the consultation data
                if save_consultation(
                    st.session_state.doctor_id,
                    st.session_state.patient_id,
                    st.session_state.symptoms,
                    diagnosis,
                    prescription
                ):
                    st.success("Consultation saved successfully")
                else:
                    st.error("Failed to save consultation")
                    # Option to continue or force end
                    if st.button("Force End Without Saving"):
                        start_new_conversation()
                        st.experimental_rerun()
                # Only clear the session if save was successful
                start_new_conversation()
                st.experimental_rerun()

# Main app logic
if st.session_state.authenticated:
    display_main_interface()
else:
    display_login()
