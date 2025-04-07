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
if "modal_pdf_view" not in st.session_state:
    st.session_state.modal_pdf_view = False
if "modal_html_view" not in st.session_state:
    st.session_state.modal_html_view = False
if "view_pdf_path" not in st.session_state:
    st.session_state.view_pdf_path = None
if "view_html_path" not in st.session_state:
    st.session_state.view_html_path = None

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
    
    # Parse prescription
    if "PRESCRIPTION:" in prescription and "• " in prescription:
        medications = []
        additional_instructions = ""
        
        lines = prescription.split("\n")
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
                # Parse medication info from line
                med_line = line.strip()[2:].strip()  # Remove bullet point
                parts = med_line.split(" - ")
                
                med = {
                    "medication": parts[0].strip() if len(parts) > 0 else "",
                    "dosage": parts[1].strip() if len(parts) > 1 else "",
                    "frequency": parts[2].strip() if len(parts) > 2 else "",
                    "duration": parts[3].strip() if len(parts) > 3 else ""
                }
                
                # Extract side effects if present
                if "Side effects:" in med_line:
                    side_effects_start = med_line.find("Side effects:")
                    if side_effects_start > 0:
                        med["side_effects"] = med_line[side_effects_start + 13:].strip("() ")
                
                medications.append(med)
                
            if reading_instructions and line.strip():
                additional_instructions += line + "\n"
        
        # Create HTML table for medications
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Medications:</b>", styles['Heading3']))
        table_data = [["Medication", "Dosage", "Frequency", "Duration", "Side Effects"]]
        for med in medications:
            table_data.append([
                med.get('medication', ''),
                med.get('dosage', ''),
                med.get('frequency', ''),
                med.get('duration', ''),
                med.get('side_effects', '')
            ])
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        
        if additional_instructions.strip():
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>Additional Instructions:</b>", styles['Heading3']))
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

def create_prescription_pdf_legacy(patient_data, diagnosis, prescription):
    """Legacy PDF generation function used as fallback when HTML-to-PDF fails"""
    st.write("Using legacy PDF generation method...")
    return create_prescription_pdf(patient_data, diagnosis, prescription)

def create_prescription_html(patient_data, diagnosis, prescription):
    """Generate an HTML version of the prescription with proper RTL support"""
    import os
    import tempfile
    import base64
    
    # Create a temporary file
    temp_filename = os.path.join(tempfile.gettempdir(), "prescription.html")
    
    # Patient language and translation check
    patient_language = patient_data.get('language', 'English')
    needs_translation = patient_language.lower() != 'english'
    
    # Check if language is RTL
    rtl_languages = ['urdu', 'arabic', 'persian', 'sindhi']
    is_rtl = patient_language.lower() in rtl_languages
    
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
                return response.json().get("translated_text")
            return None
        except Exception as e:
            st.error(f"Translation error: {str(e)}")
            return None
    
    # Function to convert newlines to <br> tags
    def nl2br(text):
        if text:
            return text.replace("\n", "<br>")
        return ""
    
    # Load QR code image and convert to base64 for embedding in HTML
    try:
        with open("Muawin_WA.png", "rb") as qr_file:
            qr_base64 = base64.b64encode(qr_file.read()).decode('utf-8')
        qr_img_html = f'<img src="data:image/png;base64,{qr_base64}" style="float:right; width:100px; height:100px; margin-left:15px;">'
    except Exception as e:
        st.warning(f"QR code image not found: {e}")
        qr_img_html = ""
    
    # Build HTML content
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html>")
    html.append("<head>")
    html.append("    <meta charset='UTF-8'>")
    html.append("    <title>Medical Prescription</title>")
    html.append("    <style>")
    html.append("        body { font-family: Arial, sans-serif; margin: 20px; }")
    html.append("        .rtl { direction: rtl; text-align: right; }")
    html.append("        .ltr { direction: ltr; text-align: left; }")
    html.append("        .translation { color: #555; font-style: italic; margin: 5px 0 15px 0; }")
    html.append("        h1 { text-align: center; }")
    html.append("        .section { margin-top: 20px; }")
    html.append("        .header { font-weight: bold; margin-top: 15px; }")
    html.append("        .content { margin-left: 20px; }")
    html.append("        @media print {")
    html.append("            .no-print { display: none; }")
    html.append("            body { margin: 1cm; }")
    html.append("        }")
    html.append("        .header-container { display: flex; justify-content: space-between; align-items: center; }")
    html.append("        .qr-code { width: 100px; height: 100px; }")
    html.append("    </style>")
    html.append("</head>")
    html.append("<body>")
    
    # Header with QR code
    html.append("    <div class='header-container'>")
    html.append(f"        <h1 style='margin-right: auto;'>Medical Prescription</h1>{qr_img_html}")
    html.append("    </div>")
    
    # Header translation
    if needs_translation:
        header_translation = translate_text("Medical Prescription", patient_language)
        if header_translation:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"    <div class='translation {direction_class}'>{header_translation}</div>")
    
    # Patient information
    html.append("    <div class='section'>")
    html.append(f"        <div><strong>Patient:</strong> {patient_data.get('name', 'N/A')}</div>")
    
    # Patient translation
    if needs_translation:
        patient_label = translate_text("Patient", patient_language)
        if patient_label:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{patient_label}: {patient_data.get('name', 'N/A')}</div>")
    
    # Age information
    html.append(f"        <div><strong>Age:</strong> {patient_data.get('age', 'N/A')}</div>")
    if needs_translation:
        age_label = translate_text("Age", patient_language)
        if age_label:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{age_label}: {patient_data.get('age', 'N/A')}</div>")
    
    # Gender information
    html.append(f"        <div><strong>Gender:</strong> {patient_data.get('gender', 'N/A')}</div>")
    if needs_translation:
        gender_label = translate_text("Gender", patient_language)
        gender_value = translate_text(patient_data.get('gender', 'N/A'), patient_language)
        if gender_label and gender_value:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{gender_label}: {gender_value}</div>")
    
    # Date information
    current_date = datetime.now().strftime('%Y-%m-%d')
    html.append(f"        <div><strong>Date:</strong> {current_date}</div>")
    if needs_translation:
        date_label = translate_text("Date", patient_language)
        if date_label:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{date_label}: {current_date}</div>")
    
    html.append("    </div>")
    
    # Diagnosis section
    html.append("    <div class='section'>")
    html.append("        <div class='header'>Diagnosis:</div>")
    if needs_translation:
        diagnosis_label = translate_text("Diagnosis", patient_language)
        if diagnosis_label:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{diagnosis_label}</div>")
    
    # Format diagnosis with line breaks
    html.append(f"        <div class='content'>{nl2br(diagnosis)}</div>")
    if needs_translation:
        diagnosis_translation = translate_text(diagnosis, patient_language)
        if diagnosis_translation:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation content {direction_class}'>{nl2br(diagnosis_translation)}</div>")
    
    html.append("    </div>")
    
    # Prescription section
    html.append("    <div class='section'>")
    html.append("        <div class='header'>Prescription:</div>")
    if needs_translation:
        prescription_label = translate_text("Prescription", patient_language)
        if prescription_label:
            direction_class = "rtl" if is_rtl else "ltr"
            html.append(f"        <div class='translation {direction_class}'>{prescription_label}</div>")
    
    # Parse prescription
    if "PRESCRIPTION:" in prescription and "• " in prescription:
        medications = []
        additional_instructions = ""
        
        lines = prescription.split("\n")
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
                # Parse medication info from line
                med_line = line.strip()[2:].strip()  # Remove bullet point
                parts = med_line.split(" - ")
                
                med = {
                    "medication": parts[0].strip() if len(parts) > 0 else "",
                    "dosage": parts[1].strip() if len(parts) > 1 else "",
                    "frequency": parts[2].strip() if len(parts) > 2 else "",
                    "duration": parts[3].strip() if len(parts) > 3 else ""
                }
                
                # Extract side effects if present
                if "Side effects:" in med_line:
                    side_effects_start = med_line.find("Side effects:")
                    if side_effects_start > 0:
                        med["side_effects"] = med_line[side_effects_start + 13:].strip("() ")
                
                medications.append(med)
                
            if reading_instructions and line.strip():
                additional_instructions += line + "\n"
        
        # Create HTML table for medications
        html.append("        <div class='content'>")
        html.append("            <table style='width: 100%; border-collapse: collapse; margin: 15px 0;'>")
        html.append("                <thead>")
        html.append("                    <tr style='background-color: #f2f2f2;'>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Medication</th>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Dosage</th>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Frequency</th>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Duration</th>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Side Effects</th>")
        html.append("                    </tr>")
        html.append("                </thead>")
        html.append("                <tbody>")
        
        # Add each medication as a row
        for med in medications:
            html.append("                    <tr>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('medication', '')}</td>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('dosage', '')}</td>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('frequency', '')}</td>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('duration', '')}</td>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('side_effects', '')}</td>")
            html.append("                    </tr>")
            
            # If translation needed, add a row for translation
            if needs_translation:
                med_str = f"{med.get('medication', '')}"
                if med.get('dosage'): med_str += f" - {med.get('dosage')}"
                if med.get('frequency'): med_str += f" - {med.get('frequency')}"
                if med.get('duration'): med_str += f" - {med.get('duration')}"
                if med.get('side_effects'): med_str += f" (Side effects: {med.get('side_effects')})"
                
                med_translation = translate_text(med_str, patient_language)
                if med_translation:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"                    <tr class='{direction_class}' style='background-color: #f9f9f9;'>")
                    html.append(f"                        <td colspan='5' style='border: 1px solid #ddd; padding: 8px; font-style: italic; color: #555;'>{med_translation}</td>")
                    html.append("                    </tr>")
        
        html.append("                </tbody>")
        html.append("            </table>")
        html.append("        </div>")
        
        # Add additional instructions
        if additional_instructions.strip():
            html.append("        <div class='header'>Additional Instructions:</div>")
            if needs_translation:
                instr_label = translate_text("Additional Instructions", patient_language)
                if instr_label:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"        <div class='translation {direction_class}'>{instr_label}</div>")
            
            html.append(f"        <div class='content'>{nl2br(additional_instructions)}</div>")
            if needs_translation:
                instr_translation = translate_text(additional_instructions, patient_language)
                if instr_translation:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"        <div class='translation content {direction_class}'>{nl2br(instr_translation)}</div>")
    else:
        # Raw prescription text
        html.append(f"        <div class='content'>{nl2br(prescription)}</div>")
        if needs_translation:
            prescription_translation = translate_text(prescription, patient_language)
            if prescription_translation:
                direction_class = "rtl" if is_rtl else "ltr"
                html.append(f"        <div class='translation content {direction_class}'>{nl2br(prescription_translation)}</div>")
    
    html.append("    </div>")
    
    # Print button
    html.append("    <div class='no-print' style='margin-top: 30px; text-align: center;'>")
    html.append("        <button onclick='window.print()'>Print Prescription</button>")
    html.append("    </div>")
    
    # Close HTML
    html.append("</body>")
    html.append("</html>")
    
    # Write to file
    try:
        with open(temp_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(html))
        
        return temp_filename
    except Exception as e:
        st.error(f"Error generating HTML: {str(e)}")
        return None

def create_prescription(patient_data, diagnosis, prescription):
    """Generate both HTML and PDF prescriptions using the HTML-first approach"""
    import os
    import tempfile
    import subprocess
    
    st.write("Generating prescription documents...")
    
    # First create the HTML version which handles translations properly
    html_path = create_prescription_html(patient_data, diagnosis, prescription)
    
    if not html_path:
        st.error("Failed to generate HTML prescription")
        return None, None
    
    # Now convert HTML to PDF using wkhtmltopdf (much better RTL support than ReportLab)
    pdf_path = os.path.join(tempfile.gettempdir(), "prescription.pdf")
    
    try:
        # Check if wkhtmltopdf is installed
        result = subprocess.run(['which', 'wkhtmltopdf'], capture_output=True, text=True)
        wkhtmltopdf_path = result.stdout.strip()
        
        if not wkhtmltopdf_path:
            st.warning("wkhtmltopdf not found. Installing it would improve PDF generation with RTL languages.")
            # Fall back to ReportLab method
            return create_prescription_pdf_legacy(patient_data, diagnosis, prescription), html_path
        
        # Convert HTML to PDF using wkhtmltopdf
        cmd = [
            wkhtmltopdf_path,
            '--encoding', 'UTF-8',
            '--margin-top', '20',
            '--margin-right', '20',
            '--margin-bottom', '20',
            '--margin-left', '20',
            html_path,
            pdf_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            st.success("PDF generated successfully from HTML")
            return pdf_path, html_path
        else:
            st.warning(f"HTML to PDF conversion failed: {result.stderr}")
            # Fall back to ReportLab method
            return create_prescription_pdf_legacy(patient_data, diagnosis, prescription), html_path
            
    except Exception as e:
        st.error(f"Error converting HTML to PDF: {str(e)}")
        # Fall back to ReportLab method
        return create_prescription_pdf_legacy(patient_data, diagnosis, prescription), html_path

def get_pdf_display_link(pdf_path):
    """Generate HTML to display a PDF in an iframe"""
    with open(pdf_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    
    pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>
    """
    return pdf_display

def get_html_display_content(html_path):
    """Read HTML file and return its content for embedding in iframe"""
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Wrap the HTML content in an iframe with appropriate styling
    iframe_content = f"""
        <iframe srcdoc="{html_content.replace('"', '&quot;')}" 
                style="width: 100%; height: 600px; border: 1px solid #ddd; border-radius: 5px;">
        </iframe>
    """
    return iframe_content

def create_modal_buttons(pdf_path, html_path, patient_name):
    """Create download button and in-page viewer instead of modal popup"""
    col1, col2 = st.columns(2)
    
    # Store the path in session state
    st.session_state.view_pdf_path = pdf_path
    st.session_state.view_html_path = html_path
    
    with col1:
        # Provide direct download option
        if pdf_path:
            with open(pdf_path, "rb") as pdf_file:
                PDFbyte = pdf_file.read()
                
            st.download_button(
                label="💾 Download Prescription",
                data=PDFbyte,
                file_name=f"prescription_{patient_name.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
    
    with col2:
        if html_path:
            with open(html_path, "rb") as html_file:
                html_bytes = html_file.read()
                
            st.download_button(
                label="💾 Download HTML Version",
                data=html_bytes,
                file_name=f"prescription_{patient_name.replace(' ', '_')}.html",
                mime="text/html"
            )
    
    # Display PDF directly in the page (no modal needed)
    st.markdown("### Prescription Preview")
    pdf_display = get_pdf_display_link(pdf_path)
    st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Add a print button
    st.markdown("""
    <script>
    function printPage() {
        window.print();
    }
    </script>
    <div style="text-align: center; margin: 20px 0;">
        <button onclick="printPage()" style="padding: 8px 16px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
            🖨️ Print
        </button>
    </div>
    """, unsafe_allow_html=True)

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
            # Make temperature editable
            temp_default = patient_data.get('temperature', '')
            patient_data['temperature'] = st.text_input("Temperature (°C)", 
                                                    value=temp_default,
                                                    help="Enter patient temperature")
            
            # Make blood pressure editable
            bp_default = patient_data.get('blood_pressure', '')
            patient_data['blood_pressure'] = st.text_input("Blood Pressure", 
                                                        value=bp_default,
                                                        help="Format: systolic/diastolic (e.g., 120/80)")
            
            # Update session state with the edited values
            st.session_state.patient_data = patient_data
        
        # Pre-existing conditions as interactive selection
        st.subheader("Pre-existing Conditions")
        
        # List of common pre-existing conditions
        common_conditions = [
            "Diabetes", "Hypertension", "Asthma", "COPD", "Heart Disease", 
            "Stroke", "Cancer", "Arthritis", "Depression", "Anxiety", 
            "Thyroid Disorder", "Kidney Disease", "Liver Disease", "Obesity",
            "Allergies", "Epilepsy"
        ]
        
        # Get existing conditions as a list
        existing_conditions = []
        if patient_data.get('pre_conditions'):
            existing_conditions = [c.strip() for c in patient_data['pre_conditions'].split(',')]
        
        # Store selected conditions
        selected_conditions = []
        
        # Create checkbox columns for conditions
        cond_cols = st.columns(3)
        for i, condition in enumerate(common_conditions):
            col_idx = i % 3
            with cond_cols[col_idx]:
                # Check if this condition is in the existing list
                is_checked = condition in existing_conditions
                if st.checkbox(condition, value=is_checked, key=f"condition_{condition}"):
                    selected_conditions.append(condition)
        
        # Custom condition input
        custom_condition = st.text_input("Add other pre-existing condition")
        if custom_condition and st.button("Add Condition"):
            if "temp_custom_conditions" not in st.session_state:
                st.session_state.temp_custom_conditions = []
            st.session_state.temp_custom_conditions.append(custom_condition)
            st.experimental_rerun()
        
        # Display custom conditions that have been added but not yet confirmed
        if "temp_custom_conditions" in st.session_state and st.session_state.temp_custom_conditions:
            st.write("**Custom conditions to be added:**")
            for condition in st.session_state.temp_custom_conditions:
                selected_conditions.append(condition)
                st.write(f"- {condition}")
        
        # Update the pre_conditions in patient data
        patient_data['pre_conditions'] = ", ".join(selected_conditions)
        st.session_state.patient_data = patient_data
        
        # Symptom selection (keep existing code)
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
        prescription = st.session_state.prescription
        
        st.subheader("Patient Information")
        st.write(f"**Name:** {patient_data['name']}, **Age:** {patient_data['age']}, **Gender:** {patient_data['gender']}")
        
        st.subheader("Diagnosis")
        st.write(diagnosis)
        
        st.subheader("Prescription")
        
        # Parse prescription into table format
        medications = []
        additional_instructions = ""
        
        if "PRESCRIPTION:" in prescription and "• " in prescription:
            lines = prescription.split("\n")
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
                    med_line = line.strip()[2:].strip()  # Remove bullet point
                    parts = med_line.split(" - ")
                    
                    med = {
                        "medication": parts[0].strip() if len(parts) > 0 else "",
                        "dosage": parts[1].strip() if len(parts) > 1 else "",
                        "frequency": parts[2].strip() if len(parts) > 2 else "",
                        "duration": parts[3].strip() if len(parts) > 3 else ""
                    }
                    
                    # Extract side effects if present
                    if "Side effects:" in med_line:
                        side_effects_start = med_line.find("Side effects:")
                        if side_effects_start > 0:
                            med["side_effects"] = med_line[side_effects_start + 13:].strip("() ")
                    
                    medications.append(med)
                    
                if reading_instructions and line.strip():
                    additional_instructions += line + "\n"
        
        # Display medications in a table
        if medications:
            st.write("### Medications")
            
            # Create DataFrame for easy table display
            import pandas as pd
            meds_df = pd.DataFrame(medications)
            
            # Rename columns for better display
            column_names = {
                "medication": "Medication",
                "dosage": "Dosage",
                "frequency": "Frequency", 
                "duration": "Duration",
                "side_effects": "Side Effects"
            }
            
            # Only include columns that exist in the dataframe
            display_columns = [col for col in ["medication", "dosage", "frequency", "duration", "side_effects"] 
                            if col in meds_df.columns]
            
            # Rename columns and display
            meds_df = meds_df[display_columns].rename(columns={k: v for k, v in column_names.items() if k in display_columns})
            st.table(meds_df)
        
        # Display additional instructions
        if additional_instructions.strip():
            st.write("### Additional Instructions")
            st.write(additional_instructions)
        
        # Allow editing in text area if needed
        with st.expander("Edit Raw Prescription Text"):
            edited_prescription = st.text_area("Edit if needed", value=prescription, height=300)
            if edited_prescription != prescription:
                prescription = edited_prescription
                st.session_state.prescription = prescription
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Generate Prescription"):
                # Use the new unified function that generates both formats
                pdf_path, html_path = create_prescription(patient_data, diagnosis, prescription)
                
                if pdf_path and html_path:
                    # Store the paths in session state
                    st.session_state.view_pdf_path = pdf_path
                    st.session_state.view_html_path = html_path
                    
                    # Show view/download buttons
                    create_modal_buttons(pdf_path, html_path, patient_data['name'])
                    
                    # Save consultation                
                    if save_consultation(
                        st.session_state.doctor_id,
                        st.session_state.patient_id,
                        st.session_state.symptoms if isinstance(st.session_state.symptoms, list) else
                            [s.strip() for s in st.session_state.symptoms.split(',')],
                        diagnosis,
                        prescription
                    ):
                        st.success("Consultation saved to database")
        
        with col2:
            if st.button("End Consultation"):
                # Similar code as before...
                # First save the consultation data
                # PROBLEM: The symptoms are being passed as a string, but API expects a list
                symptoms_list = st.session_state.symptoms
                if isinstance(symptoms_list, str):
                    # Convert comma-separated string to list if needed
                    symptoms_list = [s.strip() for s in symptoms_list.split(',')]
                    
                if save_consultation(
                    st.session_state.doctor_id,
                    st.session_state.patient_id,
                    symptoms_list,  # Pass as a list
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
    # if st.session_state.modal_pdf_view and hasattr(st.session_state, 'view_pdf_path'):
    #     show_pdf_modal()

# Show modal if triggered from a previous run
if st.session_state.modal_pdf_view and hasattr(st.session_state, 'view_pdf_path'):
    show_pdf_modal()

# Main app logic
if st.session_state.authenticated:
    display_main_interface()
else:
    display_login()
