import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import os
import tempfile
from fpdf import FPDF
import base64
from streamlit_modal import Modal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
if "modal_pdf_preview" not in st.session_state:
    st.session_state.modal_pdf_preview = False

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

You must evaluate this case and provide a structured response in the EXACT format below.
Follow this format precisely, with no deviations:

DIAGNOSIS:
1. [First most likely diagnosis]
2. [Second most likely diagnosis] 
3. [Third most likely diagnosis]
... (more if needed)

REASONS:
- [Specific reason for diagnoses]
- [Another reason]
... (more as needed)

TREATMENT PLAN:
- [Treatment recommendation]
- [Another recommendation]
... (more as needed)

Be concise and clinical. Do not include any text outside this structure. Do not include any additional formatting."""

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
    try:
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
            st.success("Consultation saved to database")
            return True
        else:
            st.error(f"Failed to save consultation: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error saving consultation: {str(e)}")
        return False

def create_prescription_pdf(patient_data, diagnosis, prescription):
    import tempfile
    import os
    import requests
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    
    # Create a temporary file
    temp_filename = os.path.join(tempfile.gettempdir(), "prescription.pdf")
    
    # Patient language and translation check
    patient_language = patient_data.get('language', 'English')
    needs_translation = patient_language.lower() != 'english'
    
    # Register fonts with Unicode support - need to have these font files available
    try:
        # Try to register fonts for non-Latin scripts
        font_paths = {
            'urdu': '/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf',
            'arabic': '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
            'punjabi': '/usr/share/fonts/truetype/noto/NotoSansGurmukhi-Regular.ttf',
            'sindhi': '/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf',  # Uses Urdu script
            'default': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        }
        
        # Try alternative paths if the above don't work
        alt_font_paths = {
            'urdu': '/usr/share/fonts/truetype/noto/NotoSansUrdu-Regular.ttf',
            'arabic': '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            'punjabi': '/usr/share/fonts/truetype/noto/NotoSansPunjabi-Regular.ttf',
            'sindhi': '/usr/share/fonts/truetype/noto/NotoSansUrdu-Regular.ttf',
            'default': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        }
        
        # Get the appropriate font path based on language
        font_key = patient_language.lower()
        font_path = font_paths.get(font_key, font_paths['default'])
        
        # Try alternative path if first one fails
        if not os.path.exists(font_path):
            font_path = alt_font_paths.get(font_key, alt_font_paths['default'])
            
        # If that still fails, use DejaVu as fallback
        if not os.path.exists(font_path):
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            
        # Register the font if it exists
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('TranslationFont', font_path))
            st.success(f"Registered font for {patient_language}")
            
            # Create a style for translations with the appropriate font
            translation_style = ParagraphStyle(
                name='Translation',
                parent=getSampleStyleSheet()['Normal'],
                fontName='TranslationFont',
                textColor=(0.4, 0.4, 0.4),
                fontSize=10
            )
        else:
            st.warning(f"Could not find appropriate font for {patient_language}")
            translation_style = ParagraphStyle(
                name='Translation',
                parent=getSampleStyleSheet()['Normal'],
                textColor=(0.4, 0.4, 0.4),
                fontName='Helvetica-Oblique'
            )
    except Exception as e:
        st.warning(f"Error registering font: {str(e)}")
        translation_style = ParagraphStyle(
            name='Translation',
            parent=getSampleStyleSheet()['Normal'],
            textColor=(0.4, 0.4, 0.4),
            fontName='Helvetica-Oblique'
        )
    
    # Function to translate text
    def translate_text(text, target_language):
        if not needs_translation:
            return None
            
        try:
            language_code = target_language.lower()
            response = requests.post(
                f"{BASE_URL}/translate",
                json={"text": text, "target_language": language_code}
            )
            
            if response.status_code == 200:
                translated = response.json().get("translated_text")
                return translated
            return None
        except Exception as e:
            st.error(f"Translation error: {str(e)}")
            return None
    
    # Set up the document
    doc = SimpleDocTemplate(
        temp_filename,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Center',
        parent=styles['Heading2'],
        alignment=TA_CENTER
    ))
    
    # Add our translation style to styles
    styles.add(translation_style)
    
    # Story (contents)
    story = []
    
    # Add header
    story.append(Paragraph("Medical Prescription", styles['Center']))
    
    # Add translation for header
    if needs_translation:
        header_translation = translate_text("Medical Prescription", patient_language)
        if header_translation:
            story.append(Paragraph(f"({header_translation})", styles['Translation']))
    
    story.append(Spacer(1, 12))
    
    # Patient information
    story.append(Paragraph(f"<b>Patient:</b> {patient_data.get('name', 'N/A')}", styles['Normal']))
    if needs_translation:
        patient_label = translate_text("Patient", patient_language)
        if patient_label:
            story.append(Paragraph(f"({patient_label}: {patient_data.get('name', 'N/A')})", styles['Translation']))
    
    story.append(Paragraph(f"<b>Age:</b> {patient_data.get('age', 'N/A')}", styles['Normal']))
    if needs_translation:
        age_translation = translate_text("Age", patient_language)
        if age_translation:
            story.append(Paragraph(f"({age_translation}: {patient_data.get('age', 'N/A')})", styles['Translation']))
    
    story.append(Paragraph(f"<b>Gender:</b> {patient_data.get('gender', 'N/A')}", styles['Normal']))
    if needs_translation:
        gender_label = translate_text("Gender", patient_language)
        gender_value = translate_text(patient_data.get('gender', 'N/A'), patient_language)
        if gender_label and gender_value:
            story.append(Paragraph(f"({gender_label}: {gender_value})", styles['Translation']))
    
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
    if needs_translation:
        date_label = translate_text("Date", patient_language)
        if date_label:
            story.append(Paragraph(f"({date_label}: {datetime.now().strftime('%Y-%m-%d')})", styles['Translation']))
    
    story.append(Spacer(1, 12))
    
    # Diagnosis
    story.append(Paragraph("<b>Diagnosis:</b>", styles['Heading3']))
    if needs_translation:
        diagnosis_label = translate_text("Diagnosis", patient_language)
        if diagnosis_label:
            story.append(Paragraph(f"({diagnosis_label})", styles['Translation']))
    
    story.append(Paragraph(diagnosis.replace('\n', '<br/>'), styles['Normal']))
    if needs_translation:
        diagnosis_translation = translate_text(diagnosis, patient_language)
        if diagnosis_translation:
            story.append(Paragraph(diagnosis_translation.replace('\n', '<br/>'), styles['Translation']))
    
    story.append(Spacer(1, 12))
    
    # Prescription
    story.append(Paragraph("<b>Prescription:</b>", styles['Heading3']))
    if needs_translation:
        prescription_label = translate_text("Prescription", patient_language)
        if prescription_label:
            story.append(Paragraph(f"({prescription_label})", styles['Translation']))
    
    if "PRESCRIPTION:" in prescription and "• " in prescription:
        # Parse structured prescription
        medications = []
        additional_instructions = ""
        
        lines = prescription.split('\n')
        reading_meds = False
        reading_instructions = False
        
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
        
        # Add medications
        for med in medications:
            story.append(Paragraph(med.replace("• ", "&#8226; "), styles['Normal']))
            if needs_translation:
                med_translation = translate_text(med, patient_language)
                if med_translation:
                    story.append(Paragraph(med_translation.replace("• ", "&#8226; "), styles['Translation']))
        
        # Add additional instructions
        if additional_instructions.strip():
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>Additional Instructions:</b>", styles['Heading3']))
            if needs_translation:
                instr_label = translate_text("Additional Instructions", patient_language)
                if instr_label:
                    story.append(Paragraph(f"({instr_label})", styles['Translation']))
            
            story.append(Paragraph(additional_instructions.replace('\n', '<br/>'), styles['Normal']))
            if needs_translation:
                instr_translation = translate_text(additional_instructions, patient_language)
                if instr_translation:
                    story.append(Paragraph(instr_translation.replace('\n', '<br/>'), styles['Translation']))
    else:
        # Raw prescription text
        story.append(Paragraph(prescription.replace('\n', '<br/>'), styles['Normal']))
        if needs_translation:
            prescription_translation = translate_text(prescription, patient_language)
            if prescription_translation:
                story.append(Paragraph(prescription_translation.replace('\n', '<br/>'), styles['Translation']))
    
    story.append(Spacer(1, 24))
    
    # Language notice
    if needs_translation:
        notice = f"This prescription includes English and {patient_language} text."
    else:
        notice = "This prescription is in English only."
        
    story.append(Paragraph(notice, styles['Italic']))
    
    # Build the PDF document
    try:
        doc.build(story)
        st.success("PDF generated successfully")
    except Exception as e:
        st.error(f"PDF generation error: {str(e)}")
        # Fallback to simple PDF without translations
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', '', 12)
            
            pdf.cell(0, 10, "Medical Prescription", 0, 1, 'C')
            pdf.cell(0, 8, f"Patient: {patient_data.get('name', 'N/A')}", 0, 1)
            pdf.cell(0, 8, f"Age: {patient_data.get('age', 'N/A')}", 0, 1)
            pdf.cell(0, 8, f"Gender: {patient_data.get('gender', 'N/A')}", 0, 1)
            pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
            
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Diagnosis:", 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 8, diagnosis.encode('ascii', 'replace').decode('ascii'))
            
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Prescription:", 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 8, prescription.encode('ascii', 'replace').decode('ascii'))
            
            pdf.output(temp_filename)
            st.warning("Generated PDF with limited character support (no translations).")
        except Exception as e2:
            st.error(f"PDF generation failed completely: {str(e2)}")
            return None
    
    return temp_filename

def get_pdf_display_link(pdf_path):
    """Generate HTML to display a PDF in an iframe"""
    with open(pdf_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    
    pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>
    """
    return pdf_display

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
            st.write(f"**Language:** {patient_data.get('language', 'English')}")
        
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
        
        # Extract diagnoses from the structured format
        if "DIAGNOSIS:" in diagnosis_text:
            # Get the text between "DIAGNOSIS:" and "REASONS:"
            start_idx = diagnosis_text.find("DIAGNOSIS:") + len("DIAGNOSIS:")
            end_idx = diagnosis_text.find("REASONS:")
            if end_idx == -1:  # If REASONS is not found
                end_idx = len(diagnosis_text)
            
            # Extract the diagnosis section
            diagnosis_section = diagnosis_text[start_idx:end_idx].strip()
            
            # Parse numbered list (1. Diagnosis)
            numbered_pattern = r'(\d+)\.?\s+(.+?)(?=\n\d+\.|\Z)'
            matches = re.finditer(numbered_pattern, diagnosis_section, re.MULTILINE|re.DOTALL)
            
            for match in matches:
                diagnosis_text = match.group(2).strip()
                if diagnosis_text:
                    possible_diagnoses.append(diagnosis_text)
                    
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
                if len(cleaned_line < 5 or ":" in cleaned_line[:15]):
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
                if pdf_path:
                    # Save the PDF path in session state
                    st.session_state.pdf_path = pdf_path
                    
                    # Set modal state to open
                    st.session_state.modal_pdf_preview = True
                    
                    # Create download button
                    with open(pdf_path, "rb") as pdf_file:
                        PDFbyte = pdf_file.read()
                        
                    st.download_button(
                        label="Download PDF",
                        data=PDFbyte,
                        file_name=f"prescription_{patient_data['name'].replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                    
                    if save_consultation(
                        st.session_state.doctor_id,
                        st.session_state.patient_id,
                        ", ".join(st.session_state.symptoms) if isinstance(st.session_state.symptoms, list) else st.session_state.symptoms,
                        diagnosis,
                        prescription
                    ):
                        st.success("Consultation saved to database")
        
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
    
    # Show modal if triggered
    if st.session_state.modal_pdf_preview and hasattr(st.session_state, 'pdf_path'):
        modal = Modal("PDF Preview", key="pdf_preview_modal")
        with modal.container():
            st.markdown("### Prescription Preview")
            pdf_display = get_pdf_display_link(st.session_state.pdf_path)
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            if st.button("Close Preview"):
                st.session_state.modal_pdf_preview = False
                st.experimental_rerun()

# Main app logic
if st.session_state.authenticated:
    display_main_interface()
else:
    display_login()
