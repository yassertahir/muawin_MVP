import streamlit as st
import pandas as pd
import requests
import json
import sqlite3
from datetime import datetime
import os
import tempfile
from fpdf import FPDF
import base64
import re
from streamlit_modal import Modal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
# Import our new function for updating patients.csv
from db_update_patients import update_patients_csv
import shutil  # For file operations
import subprocess  # For running wkhtmltopdf

# Only configure the page if not already configured
# if not hasattr(st, '_is_page_config_set'):
#     st.set_page_config(page_title="DocAssist - AI Assistant for Doctors", layout="wide")
#     st._is_page_config_set = True
if 'BASE_URL' in st.session_state:
    BASE_URL = st.session_state['BASE_URL']
else:
    BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8000")
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
if "tests" not in st.session_state:
    st.session_state.tests = []
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
if "consultation_saved" not in st.session_state:
    st.session_state.consultation_saved = False
if "referrals" not in st.session_state:
    st.session_state.referrals = []

# Base URL for API
# Update to use Streamlit secrets or environment variable
import os
BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8000")

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
    st.session_state.consultation_saved = False
    # Clear the PDF paths when starting a new conversation
    st.session_state.view_pdf_path = None
    st.session_state.view_html_path = None
    # Reset the tests list for new consultations
    st.session_state.tests = []
    # Reset selected_tests to prevent tests from persisting between consultations
    if "selected_tests" in st.session_state:
        st.session_state.selected_tests = []
    # Clear the medications list to prevent data leakage between consultations
    if "medications" in st.session_state:
        del st.session_state.medications

def get_patient_list():
    try:
        # Query patients directly from the database
        conn = sqlite3.connect("docassist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM patients")
        patients = [row[0] for row in cursor.fetchall()]
        conn.close()
        return patients
    except Exception as e:
        st.error(f"Error loading patient list: {e}")
        return []

def get_patient_data(patient_id):
    response = requests.get(f"{BASE_URL}/patient/{patient_id}")
    if response.status_code == 200:
        patient_data = response.json()
        
        # Debug logging to see what's in the pre_conditions field
        if 'pre_conditions' in patient_data:
            print(f"DEBUG - Loaded pre_conditions: {patient_data['pre_conditions']}, type: {type(patient_data['pre_conditions'])}")
            
            # Handle different formats of pre_conditions
            if isinstance(patient_data['pre_conditions'], list):
                patient_data['pre_conditions'] = ", ".join(patient_data['pre_conditions'])
            elif patient_data['pre_conditions'] and patient_data['pre_conditions'].startswith("[") and patient_data['pre_conditions'].endswith("]"):
                # This might be a string representation of a list
                try:
                    # Try to parse it as JSON
                    import json
                    conditions_list = json.loads(patient_data['pre_conditions'].replace("'", "\""))
                    if isinstance(conditions_list, list):
                        patient_data['pre_conditions'] = ", ".join(conditions_list)
                except:
                    # If parsing fails, clean up the string
                    patient_data['pre_conditions'] = (patient_data['pre_conditions']
                                                    .strip("[]")
                                                    .replace("'", "")
                                                    .replace("\"", ""))
                                                    
            # Print the final format
            print(f"DEBUG - Normalized pre_conditions: {patient_data['pre_conditions']}")
        
        return patient_data
    else:
        st.error("Failed to fetch patient data")
        return None

def get_patient_details(patient_id):
    try:
        response = requests.get(f"{BASE_URL}/patients/{patient_id}")
        if response.status_code == 200:
            patient_data = response.json()
            # Add the ID to the patient data
            patient_data['id'] = patient_id
            return patient_data
        else:
            st.error(f"Failed to get patient details: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error retrieving patient details: {str(e)}")
        return None

def get_patient_history(patient_id, limit=3):
    """Get a patient's previous consultation records"""
    try:
        response = requests.get(f"{BASE_URL}/patient-history/{patient_id}?limit={limit}")
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"Could not fetch patient history: {response.status_code}")
            return []
    except Exception as e:
        st.warning(f"Error fetching patient history: {str(e)}")
        return []

def get_common_symptoms():
    return [
        "Fever", "Headache", "Cough", "Sore Throat", "Fatigue", "Nausea",
        "Vomiting", "Diarrhea", "Abdominal Pain", "Chest Pain", "Shortness of Breath",
        "Dizziness", "Rash", "Joint Pain", "Back Pain", "Sweating", "Chills"
    ]

def get_common_tests():
    """Return a list of common medical tests for selection"""
    return [
        "Complete Blood Count (CBC)", 
        "Blood Glucose Test", 
        "Lipid Profile", 
        "Liver Function Test (LFT)",
        "Kidney Function Test (KFT)", 
        "Thyroid Function Test",
        "Urine Analysis", 
        "Electrocardiogram (ECG/EKG)", 
        "Chest X-ray",
        "Ultrasound", 
        "CT Scan", 
        "MRI",
        "COVID-19 Test", 
        "Hemoglobin A1c (HbA1c)", 
        "C-Reactive Protein (CRP)",
        "Vitamin D Test", 
        "Vitamin B12 Test",
        "Hepatitis Panel"
    ]

def generate_diagnosis(patient_data, symptoms):
    """Generate a diagnosis based on patient data and symptoms without patient history in the main prompt"""
    # Fetch patient history
    patient_id = st.session_state.patient_id
    patient_history = get_patient_history(patient_id)
    
    # Start with the basic patient data prompt
    prompt = f"""You are a primary healthcare physician in Pakistan. A patient with following details:
Name: {patient_data['name']}
Age: {patient_data['age']}
Gender: {patient_data['gender']}
Temperature: {patient_data['temperature']}
Blood Pressure: {patient_data['blood_pressure']}
Pre-existing Conditions: {patient_data['pre_conditions']}

Showing the following symptoms:
{', '.join(symptoms)}
"""

    # Complete the prompt with the expected response format
    prompt += """
You must evaluate this case and provide a structured response in the EXACT format below.
Follow this format precisely, with no deviations:

PATIENT HISTORY SUMMARY:
[Leave this section blank for now. It will be filled in separately.]

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

    # Call the API to generate diagnosis
    response = requests.post(
        f"{BASE_URL}/generate-diagnosis",
        json={"prompt": prompt}
    )
    
    if response.status_code == 200:
        diagnosis = response.json()["diagnosis"]
        
        # Now, if we have patient history, generate a separate history summary
        if patient_history:
            history_prompt = f"""You are a primary healthcare physician reviewing a patient's history. 
The patient has the following previous consultations:

"""
            for i, record in enumerate(patient_history):
                history_prompt += f"\nVisit Date: {record['date']}\n"
                
                # Include vital signs if available
                if record.get('vital_signs'):
                    vs = record['vital_signs']
                    history_prompt += f"Vital Signs: Temperature {vs.get('temperature', 'N/A')}, "
                    history_prompt += f"BP {vs.get('blood_pressure', 'N/A')}\n"
                    
                # Include pre-existing conditions if available
                if record.get('pre_conditions'):
                    history_prompt += f"Pre-existing Conditions: {record['pre_conditions']}\n"
                    
                # Include symptoms
                if record.get('symptoms'):
                    history_prompt += f"Symptoms: {', '.join(record['symptoms'])}\n"
                    
                history_prompt += f"Diagnosis: {record['diagnosis']}\n"
                history_prompt += f"Prescription: {record['prescription']}\n"
                
                if i < len(patient_history) - 1:
                    history_prompt += "-" * 40 + "\n"  # Separator between records
            
            history_prompt += """
Based on the patient's history above, create a concise summary of their medical history.
Highlight any patterns, recurring issues, or relevant information that could be important for
the current diagnosis. Keep it brief and focused on medically relevant details only.
"""
            
            # Get history summary
            response = requests.post(
                f"{BASE_URL}/generate-diagnosis",
                json={"prompt": history_prompt}
            )
            
            if response.status_code == 200:
                history_summary = response.json()["diagnosis"]
                
                # Replace the placeholder in the diagnosis with the actual history summary
                if "PATIENT HISTORY SUMMARY:" in diagnosis:
                    parts = diagnosis.split("PATIENT HISTORY SUMMARY:")
                    if len(parts) > 1:
                        # Find the end of the history section
                        history_end = parts[1].find("DIAGNOSIS:")
                        if history_end > 0:
                            # Replace the placeholder with the generated summary
                            diagnosis = parts[0] + "PATIENT HISTORY SUMMARY:\n" + history_summary.strip() + "\n\n" + parts[1][history_end:]
        
        return diagnosis
    else:
        st.error("Failed to generate diagnosis")
        return None

def regenerate_diagnosis(original_prompt, doctor_comments):
    # Fetch patient history (it's included in the original_prompt)
    
    prompt = f"""Another doctor has provide following comments about the diagnosis:
{doctor_comments}

Patient information is:
{original_prompt}

Analyse and provide diagnosis with the same format as before, including the PATIENT HISTORY SUMMARY section."""

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
Include dosage, frequency, and duration for each medication. For each medication, also include:
1. Potential interactions with other common medications
2. Pregnancy safety information (category and recommendations)
3. Common side effects

Format your response as a structured table with the following columns:
- Medication Name
- Dosage
- Frequency
- Duration
- Side Effects
- Medication Interactions
- Pregnancy Safety

Ensure all columns are properly filled with relevant information."""

    response = requests.post(
        f"{BASE_URL}/generate-prescription",
        json={"prompt": prompt}
    )
    
    if response.status_code == 200:
        raw_prescription = response.json()["prescription"]
        
        return raw_prescription
    else:
        st.error("Failed to generate prescription")
        return None

def save_consultation(doctor_id, patient_id, symptoms, diagnosis, prescription, tests=None):
    try:
        # Make sure patient_data is available
        if not hasattr(st.session_state, 'patient_data') or not st.session_state.patient_data:
            st.error("Cannot save consultation: patient data not available")
            return False
            
        # Get vital signs from patient data
        vital_signs = {
            "temperature": st.session_state.patient_data.get('temperature', ''),
            "blood_pressure": st.session_state.patient_data.get('blood_pressure', '')
        }
        
        # Initial data structure without prescription_pdf
        data = {
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "symptoms": symptoms,
            "vital_signs": vital_signs,
            "diagnosis": diagnosis,
            "prescription": prescription,
            "tests": tests if tests else st.session_state.tests,  # Use provided tests or from session state
            "referrals": st.session_state.referrals if hasattr(st.session_state, 'referrals') else [],  # Add referrals from session state
            "date": datetime.now().isoformat()
        }
        
        # Save consultation to get the consultation_id first
        response = requests.post(
            f"{BASE_URL}/save-consultation",
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            consultation_id = result.get("consultation_id")
            
            # Now save the PDF if we have a PDF path and consultation_id
            if consultation_id and hasattr(st.session_state, 'view_pdf_path') and st.session_state.view_pdf_path:
                # Save the PDF to data/prescription directory
                pdf_dest_path = save_prescription_pdf(
                    st.session_state.view_pdf_path, 
                    patient_id, 
                    consultation_id
                )
                
                # If PDF was saved successfully, update the consultation record
                if pdf_dest_path:
                    # Create updated data with prescription_pdf path
                    updated_data = data.copy()
                    updated_data["prescription_pdf"] = pdf_dest_path
                    
                    # Update via a separate API endpoint or directly in the database
                    conn = sqlite3.connect("docassist.db")
                    cursor = conn.cursor()
                    
                    try:
                        cursor.execute(
                            "UPDATE consultations SET prescription_pdf = ? WHERE id = ?",
                            (pdf_dest_path, consultation_id)
                        )
                        conn.commit()
                        st.success(f"Prescription PDF path saved to database: {pdf_dest_path}")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Failed to update prescription PDF path: {str(e)}")
                    finally:
                        conn.close()
            
            # Also save individual referrals to the referrals table
            if hasattr(st.session_state, 'referrals') and st.session_state.referrals:
                for referral in st.session_state.referrals:
                    save_referral(
                        doctor_id,
                        patient_id,
                        referral.get("specialist_id", 0),
                        referral.get("reason", "")
                    )
                st.success(f"Saved {len(st.session_state.referrals)} referrals to database")
            
            return True
        else:
            st.error(f"Failed to save consultation: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error saving consultation: {str(e)}")
        return False

def create_prescription_pdf(patient_data, diagnosis, prescription, tests=None):
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
    
    # Add referrals section if there are any referrals in session state
    if hasattr(st.session_state, 'referrals') and st.session_state.referrals:
        story.append(Paragraph("<b>Referrals:</b>", styles['Heading3']))
        if needs_translation:
            referrals_label = translate_text("Referrals", patient_language)
            if referrals_label:
                story.append(Paragraph(f"({referrals_label})", styles['Translation']))
        
        # Add each referral
        for referral in st.session_state.referrals:
            specialist = referral.get('specialist', {})
            specialist_name = specialist.get('name', 'Unknown Specialist')
            specialist_category = specialist.get('category', 'Unknown Category')
            reason = referral.get('reason', 'No reason specified')
            
            referral_text = f"{specialist_name} ({specialist_category}) - {reason}"
            story.append(Paragraph(f"• {referral_text}", styles['Normal']))
            
            if needs_translation:
                referral_translation = translate_text(referral_text, patient_language)
                if referral_translation:
                    story.append(Paragraph(f"({referral_translation})", styles['Translation']))
        
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
                medications.append(parse_medication_details(line))
                
            if reading_instructions and line.strip():
                additional_instructions += line + "\n"
        
        # Create HTML table for medications
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Medications:</b>", styles['Heading3']))
        table_data = [["Medication", "Dosage", "Frequency", "Duration", "Side Effects", "Interactions", "Pregnancy Safety"]]
        for med in medications:
            table_data.append([
                med.get('medication', ''),
                med.get('dosage', ''),
                med.get('frequency', ''),
                med.get('duration', ''),
                med.get('side_effects', ''),
                med.get('interactions', ''),
                med.get('pregnancy_safety', '')
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
    
    # Add tests if present
    if tests and len(tests) > 0:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Recommended Medical Tests:</b>", styles['Heading3']))
        if needs_translation:
            tests_label = translate_text("Recommended Medical Tests", patient_language)
            if tests_label:
                story.append(Paragraph(f"({tests_label})", styles['Translation']))
                
        # Add tests as bullet points
        for test in tests:
            story.append(Paragraph(f"• {test}", styles['Normal']))
            if needs_translation:
                test_translation = translate_text(test, patient_language)
                if test_translation:
                    story.append(Paragraph(f"({test_translation})", styles['Translation']))
    
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
            
            # Add referrals if present
            if hasattr(st.session_state, 'referrals') and st.session_state.referrals:
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 10, "Referrals:", 0, 1)
                pdf.set_font('Arial', '', 12)
                for referral in st.session_state.referrals:
                    specialist = referral.get('specialist', {})
                    pdf.multi_cell(0, 8, f"- {specialist.get('name', 'Unknown')} ({specialist.get('category', 'Unknown')}) - {referral.get('reason', 'No reason specified')}")
            
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Prescription:", 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 8, prescription.encode('ascii', 'replace').decode('ascii'))
            
            # Add tests if present
            if tests and len(tests) > 0:
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 10, "Recommended Tests:", 0, 1)
                pdf.set_font('Arial', '', 12)
                for test in tests:
                    pdf.cell(0, 8, f"- {test}", 0, 1)
            
            pdf.output(temp_filename)
            st.warning("Generated PDF with limited character support (no translations).")
        except Exception as e2:
            st.error(f"PDF generation failed completely: {str(e2)}")
            return None
    
    return temp_filename

def create_prescription_pdf_legacy(patient_data, diagnosis, prescription, tests=None):
    """Legacy PDF generation function used as fallback when HTML-to-PDF fails"""
    st.write("Using legacy PDF generation method...")
    return create_prescription_pdf(patient_data, diagnosis, prescription, tests)

def create_prescription_html(patient_data, diagnosis, prescription, tests=None):
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
    
    # Add referrals section if there are any referrals in session state
    if hasattr(st.session_state, 'referrals') and st.session_state.referrals:
        html.append("    <div class='section'>")
        html.append("        <div class='header'>Referrals:</div>")
        if needs_translation:
            referrals_label = translate_text("Referrals", patient_language)
            if referrals_label:
                direction_class = "rtl" if is_rtl else "ltr"
                html.append(f"        <div class='translation {direction_class}'>{referrals_label}</div>")
        
        html.append("        <div class='content'>")
        html.append("            <ul>")
        
        # Add each referral
        for referral in st.session_state.referrals:
            specialist = referral.get('specialist', {})
            specialist_name = specialist.get('name', 'Unknown Specialist')
            specialist_category = specialist.get('category', 'Unknown Category')
            reason = referral.get('reason', 'No reason specified')
            
            referral_text = f"{specialist_name} ({specialist_category}) - {reason}"
            html.append(f"                <li>{referral_text}</li>")
            
            if needs_translation:
                referral_translation = translate_text(referral_text, patient_language)
                if referral_translation:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"                <div class='translation {direction_class}'>({referral_translation})</div>")
        
        html.append("            </ul>")
        html.append("        </div>")
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
                medications.append(parse_medication_details(line))
                
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
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Interactions</th>")
        html.append("                        <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Pregnancy Safety</th>")
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
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('interactions', '')}</td>")
            html.append(f"                        <td style='border: 1px solid #ddd; padding: 8px;'>{med.get('pregnancy_safety', '')}</td>")
            html.append("                    </tr>")
            
            # If translation needed, add a row for translation
            if needs_translation:
                med_str = f"{med.get('medication', '')}"
                if med.get('dosage'): med_str += f" - {med.get('dosage')}"
                if med.get('frequency'): med_str += f" - {med.get('frequency')}"
                if med.get('duration'): med_str += f" - {med.get('duration')}"
                if med.get('side_effects'): med_str += f" (Side effects: {med.get('side_effects')})"
                if med.get('interactions'): med_str += f" (Interactions: {med.get('interactions')})"
                if med.get('pregnancy_safety'): med_str += f" (Pregnancy safety: {med.get('pregnancy_safety')})"
                
                med_translation = translate_text(med_str, patient_language)
                if med_translation:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"                    <tr class='{direction_class}' style='background-color: #f9f9f9;'>")
                    html.append(f"                        <td colspan='7' style='border: 1px solid #ddd; padding: 8px; font-style: italic; color: #555;'>{med_translation}</td>")
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
    
    # Add tests section if tests are present
    if tests and len(tests) > 0:
        html.append("    <div class='section'>")
        html.append("        <div class='header'>Recommended Medical Tests:</div>")
        if needs_translation:
            tests_label = translate_text("Recommended Medical Tests", patient_language)
            if tests_label:
                direction_class = "rtl" if is_rtl else "ltr"
                html.append(f"        <div class='translation {direction_class}'>{tests_label}</div>")
        
        html.append("        <div class='content'>")
        html.append("            <ul>")
        for test in tests:
            html.append(f"                <li>{test}</li>")
            if needs_translation:
                test_translation = translate_text(test, patient_language)
                if test_translation:
                    direction_class = "rtl" if is_rtl else "ltr"
                    html.append(f"                <div class='translation {direction_class}'>({test_translation})</div>")
        html.append("            </ul>")
        html.append("        </div>")
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
    
    # Get tests from session state
    tests = st.session_state.tests if hasattr(st.session_state, 'tests') and st.session_state.tests else None
    
    # First create the HTML version which handles translations properly
    html_path = create_prescription_html(patient_data, diagnosis, prescription, tests)
    
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
            return create_prescription_pdf_legacy(patient_data, diagnosis, prescription, tests), html_path
        
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
            return create_prescription_pdf_legacy(patient_data, diagnosis, prescription, tests), html_path
            
    except Exception as e:
        st.error(f"Error converting HTML to PDF: {str(e)}")
        # Fall back to ReportLab method
        return create_prescription_pdf_legacy(patient_data, diagnosis, prescription, tests), html_path

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
                label="💾 Download Prescription PDF",
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
    
    # Display HTML version directly as it has better browser compatibility
    if html_path:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        st.markdown("### Prescription Preview (HTML Version)")
        st.components.v1.html(html_content, height=600, scrolling=True)
    
    # Display PDF with warning about browser compatibility
    st.markdown("### PDF Preview (May be blocked by some browsers)")
    st.info("⚠️ PDF preview may be blocked by Chrome's security in Streamlit Cloud. If you can't see the PDF below, please use the download buttons above to view the prescription.")
    
    if pdf_path:
        try:
            with open(pdf_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
            pdf_display = f"""
                <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error displaying PDF: {e}")
    
    # Add print instructions
    st.markdown("""
    ### Printing Instructions
    1. Download the PDF or HTML version using the buttons above
    2. Open the downloaded file in your browser or PDF viewer
    3. Use the print function in your browser/viewer
    """)

def parse_medication_details(med_line):
    """Parse medication details from either bullet point format or markdown table row"""
    # Initialize medication parts
    med = {
        "medication": "",
        "dosage": "",
        "frequency": "",
        "duration": "",
        "side_effects": "",
        "interactions": "",
        "pregnancy_safety": ""
    }
    
    # Check if this is a markdown table row (starts with |)
    if med_line.startswith("|"):
        # This is a markdown table row, parse it accordingly
        columns = [col.strip() for col in med_line.split("|")]
        # Remove empty entries (from the beginning and end of the split)
        columns = [col for col in columns if col]
        
        # Map columns to medication fields based on position
        # Standard column order: Name, Dosage, Frequency, Duration, Side Effects, Interactions, Pregnancy
        if len(columns) >= 1:
            med["medication"] = columns[0]
        if len(columns) >= 2:
            med["dosage"] = columns[1]
        if len(columns) >= 3:
            med["frequency"] = columns[2]
        if len(columns) >= 4:
            med["duration"] = columns[3]
        if len(columns) >= 5:
            med["side_effects"] = columns[4]
        if len(columns) >= 6:
            med["interactions"] = columns[5]
        if len(columns) >= 7:
            med["pregnancy_safety"] = columns[6]
        
        print(f"Parsed table row: {med}")
        return med
    
    # If not a table row, proceed with the original parsing logic
    # Remove bullet point if present
    if med_line.startswith("• "):
        med_line = med_line[2:].strip()
    
    # First, try to find labeled sections for specialized fields (more reliable)
    labeled_fields = {
        "Side Effects:": "side_effects",
        "Side effects:": "side_effects",
        "Medication Interactions:": "interactions", 
        "Drug Interactions:": "interactions",
        "Interactions:": "interactions",
        "Pregnancy Safety:": "pregnancy_safety",
        "Pregnancy safety:": "pregnancy_safety",
        "Pregnancy Category:": "pregnancy_safety",
        "Pregnancy:": "pregnancy_safety"
    }
    
    # Handle each specialized field separately
    remaining_line = med_line
    for label, field in labeled_fields.items():
        if label in remaining_line:
            parts = remaining_line.split(label, 1)
            before_text = parts[0].strip()
            after_text = parts[1].strip()
            
            # Find the next label if any
            next_label_pos = len(after_text)
            next_label = None
            for next_label_candidate in labeled_fields.keys():
                if next_label_candidate in after_text:
                    pos = after_text.find(next_label_candidate)
                    if 0 <= pos < next_label_pos:
                        next_label_pos = pos
                        next_label = next_label_candidate
            
            if next_label:
                # Extract content up to the next label
                med[field] = after_text[:next_label_pos].strip()
                # Keep the rest (including the next label) for further processing
                remaining_line = before_text + " " + after_text[next_label_pos:]
            else:
                # This is the last labeled section
                med[field] = after_text.strip()
                remaining_line = before_text
    
    # Now parse the remaining line for the basic medication information
    # Simple case: "Medication - Dosage - Frequency - Duration" format
    parts = [p.strip() for p in remaining_line.split(" - ")]
    
    if len(parts) >= 1:
        med["medication"] = parts[0].strip()
    if len(parts) >= 2:
        med["dosage"] = parts[1].strip()
    if len(parts) >= 3:
        med["frequency"] = parts[2].strip()
    if len(parts) >= 4:
        med["duration"] = parts[3].strip()
    
    # Check for side effects in parentheses if not already found
    if not med["side_effects"]:
        sidx = remaining_line.find("(")
        if sidx > 0:
            eidx = remaining_line.find(")", sidx)
            if eidx > sidx:
                possible_side_effects = remaining_line[sidx+1:eidx].strip()
                # Only use if it looks like side effects
                if len(possible_side_effects) > 5 and "side" in possible_side_effects.lower():
                    med["side_effects"] = possible_side_effects
    
    # Final clean up - remove parentheses and extra formatting
    for field in med:
        if med[field]:
            # Remove unnecessary parentheses and extra spaces
            med[field] = med[field].replace("(", "").replace(")", "").strip()
            # If the field accidentally starts with a field label, remove it
            for label in labeled_fields:
                if med[field].startswith(label):
                    med[field] = med[field][len(label):].strip()
    
    print(f"Parsed text line: {med_line} -> {med}")
    return med

def update_patient_conditions(patient_id, pre_conditions):
    """Update patient's pre-existing conditions in the database"""
    try:
        # Handle different formats of pre_conditions
        if isinstance(pre_conditions, list):
            # Convert list to comma-separated string
            pre_conditions_str = ", ".join(pre_conditions)
        else:
            # If it's already a string, just use it
            pre_conditions_str = pre_conditions
            
        # Remove any square brackets if they accidentally got included in the string
        pre_conditions_str = pre_conditions_str.replace("[", "").replace("]", "").replace("'", "").replace("\"", "")
            
        response = requests.post(
            f"{BASE_URL}/update-patient",
            params={"patient_id": patient_id, "pre_conditions": pre_conditions_str}
        )
        if response.status_code == 200:
            return True
        else:
            st.error(f"Failed to update patient conditions: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error updating patient data: {str(e)}")
        return False

def save_prescription_pdf(pdf_path, patient_id, consultation_id):
    """
    Save a prescription PDF to the data/prescription directory with format
    PATIENTID_CONSULTATIONID.pdf
    
    Args:
        pdf_path: Path to the temporary PDF file
        patient_id: ID of the patient
        consultation_id: ID of the consultation
        
    Returns:
        Path to the saved PDF file or None if failed
    """
    import os
    import shutil
    
    # Create data/prescription directory if it doesn't exist
    prescription_dir = "data/prescription"
    if not os.path.exists(prescription_dir):
        try:
            os.makedirs(prescription_dir)
        except Exception as e:
            st.error(f"Failed to create prescription directory: {str(e)}")
            return None
    
    # Create the filename: PATIENTID_CONSULTATIONID.pdf
    filename = f"{patient_id}_{consultation_id}.pdf"
    dest_path = os.path.join(prescription_dir, filename)
    
    # Get absolute path for external applications
    abs_dest_path = os.path.abspath(dest_path)
    
    try:
        # Copy the file from temporary location to destination
        shutil.copyfile(pdf_path, dest_path)
        st.success(f"Prescription PDF saved to {dest_path}")
        return abs_dest_path
    except Exception as e:
        st.error(f"Failed to save prescription PDF: {str(e)}")
        return None

def clear_consultation_data():
    """Clear all consultation records from database for demo purposes"""
    if st.session_state.authenticated:
        try:
            response = requests.post(f"{BASE_URL}/clear-consultations")
            if response.status_code == 200:
                result = response.json()
                st.success(f"{result['message']}")
                return True
            else:
                st.error(f"Failed to clear database: {response.text}")
                return False
        except Exception as e:
            st.error(f"Error clearing database: {str(e)}")
            return False
    else:
        st.error("You must be logged in to clear the database")
        return False

def get_specialist_categories():
    """Get a list of all specialist categories from the API"""
    try:
        response = requests.get(f"{BASE_URL}/specialist-categories")
        if response.status_code == 200:
            return response.json()["categories"]
        else:
            st.warning(f"Could not fetch specialist categories: {response.status_code}")
            return []
    except Exception as e:
        st.warning(f"Error fetching specialist categories: {str(e)}")
        return []

def get_specialists_by_category(category):
    """Get a list of specialists filtered by category"""
    try:
        response = requests.get(f"{BASE_URL}/specialists?category={category}")
        if response.status_code == 200:
            return response.json()["specialists"]
        else:
            st.warning(f"Could not fetch specialists: {response.status_code}")
            return []
    except Exception as e:
        st.warning(f"Error fetching specialists: {str(e)}")
        return []

def get_all_specialists():
    """Get a list of all specialists"""
    try:
        response = requests.get(f"{BASE_URL}/specialists")
        if response.status_code == 200:
            return response.json()["specialists"]
        else:
            st.warning(f"Could not fetch specialists: {response.status_code}")
            return []
    except Exception as e:
        st.warning(f"Error fetching specialists: {str(e)}")
        return []

def save_referral(doctor_id, patient_id, specialist_id, reason):
    """Save a referral to the database"""
    try:
        data = {
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "specialist_id": specialist_id,
            "reason": reason,
            "date": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{BASE_URL}/save-referral",
            json=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to save referral: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error saving referral: {str(e)}")
        return None

def display_login():
    # Add logo at the top of the login page
    col1, col2 = st.columns([1, 3])
    with col1:
        try:
            # Removed Muawin logo reference
            st.write("DocAssist")
        except:
            st.write("DocAssist")
    with col2:
        st.title("DocAssist - AI Assistant for Doctors")
    
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
    # Add logo at the top of the page
    col1, col2 = st.columns([1, 3])
    with col1:
        try:
            # Removed Muawin logo reference
            st.write("DocAssist")
        except:
            st.write("DocAssist")
    with col2:
        st.title("DocAssist - AI Assistant for Doctors")
    
    # Sidebar for session controls
    with st.sidebar:
        st.button("Logout", on_click=logout)
        st.button("Start New Consultation", on_click=start_new_conversation)
        st.button("Clear Database", on_click=clear_consultation_data)
    
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
        
        # Update the pre_conditions in patient data and the database
        if selected_conditions != existing_conditions:
            patient_data['pre_conditions'] = ", ".join(selected_conditions)
            if update_patient_conditions(st.session_state.patient_id, patient_data['pre_conditions']):
                st.success("Pre-existing conditions updated")
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
        diagnosis_text = st.session_state.diagnosis

        # Check if there's a patient history summary section
        if "PATIENT HISTORY SUMMARY:" in diagnosis_text:
            history_start = diagnosis_text.find("PATIENT HISTORY SUMMARY:") + len("PATIENT HISTORY SUMMARY:")
            history_end = diagnosis_text.find("DIAGNOSIS:")
            
            if history_end > history_start:
                history_summary = diagnosis_text[history_start:history_end].strip()
                st.subheader("Patient History Summary")
                st.write(history_summary)
                
                # Remove history summary from the diagnosis display to avoid duplication
                diagnosis_display = diagnosis_text[history_end:]
                st.subheader("Current Diagnosis")
                st.write(diagnosis_display)
            else:
                # Fall back to displaying the full text if parsing fails
                st.write(diagnosis_text)
        else:
            # If no history section, display the diagnosis as before
            st.write(diagnosis_text)
        
        # Check if there's a raw prescription in the session state that we need to confirm
        if "temp_raw_prescription" in st.session_state:
            if st.button("Continue with this Prescription"):
                st.session_state.prescription = st.session_state.temp_raw_prescription
                # Clear the temporary prescription
                del st.session_state.temp_raw_prescription
                st.experimental_rerun()
            return
        
        # Extract possible diagnoses from the text
        import re
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
                    
                # Update the diagnosis
                st.session_state.diagnosis = final_diagnosis
                
                # Generate prescription and set it directly in the session state
                raw_prescription = generate_prescription(final_diagnosis, patient_data)
                if raw_prescription:
                    # Skip the confirmation step and go straight to prescription editing
                    st.session_state.prescription = raw_prescription
                    st.session_state.final_prescription = False
                    st.experimental_rerun()
        else:
            # If no diagnoses could be extracted, just provide buttons for the next steps
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Accept Diagnosis"):
                    # Generate prescription and set it directly in the session state
                    raw_prescription = generate_prescription(st.session_state.diagnosis, patient_data)
                    if raw_prescription:
                        # Skip the confirmation step and go straight to prescription editing
                        st.session_state.prescription = raw_prescription
                        st.session_state.final_prescription = False
                        st.experimental_rerun()
    
    elif st.session_state.prescription and not st.session_state.final_prescription:
        # Force scroll to top with an empty container and key
        st.empty()
        
        # Important: Use st.markdown with anchor HTML at the very top to force browser to start at the top
        st.markdown('<div id="top-anchor"></div>', unsafe_allow_html=True)
        
        # Main content starts here
        patient_data = st.session_state.patient_data
        diagnosis = st.session_state.diagnosis
        prescription = st.session_state.prescription
        
        # Patient information at the top
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
            # This is a markdown table format - parse it directly
            lines = prescription.strip().split('\n')
            table_start = False
            header_line = -1
            
            # Find the header line
            for i, line in enumerate(lines):
                if line.strip().startswith("|") and "-|-" in lines[i+1] if i+1 < len(lines) else False:
                    header_line = i
                    break
            
            if header_line >= 0:
                # Get the header column names
                header = [col.strip() for col in lines[header_line].strip().split("|")]
                header = [col for col in header if col]  # Remove empty strings
                
                # Map header columns to medication fields
                field_positions = {
                    "medication": -1,
                    "dosage": -1, 
                    "frequency": -1,
                    "duration": -1,
                    "side_effects": -1,
                    "interactions": -1,
                    "pregnancy_safety": -1
                }
                
                # Map positions based on header names
                for i, col in enumerate(header):
                    col_lower = col.lower()
                    if ("medication" in col_lower and "name" in col_lower) or "medication name" in col_lower:
                        field_positions["medication"] = i
                    elif "medication" in col_lower and "interaction" in col_lower:
                        field_positions["interactions"] = i
                    elif "dosage" in col_lower or "dose" in col_lower:
                        field_positions["dosage"] = i
                    elif "frequency" in col_lower:
                        field_positions["frequency"] = i
                    elif "duration" in col_lower:
                        field_positions["duration"] = i
                    elif "side" in col_lower and "effect" in col_lower:
                        field_positions["side_effects"] = i
                    elif "interaction" in col_lower:
                        field_positions["interactions"] = i
                    elif "pregnancy" in col_lower:
                        field_positions["pregnancy_safety"] = i
                
                # Process data rows
                for i in range(header_line + 2, len(lines)):  # Skip header and separator
                    line = lines[i].strip()
                    if not line or not line.startswith("|"):
                        continue
                        
                    columns = [col.strip() for col in line.split("|")]
                    columns = [col for col in columns if col]  # Remove empty strings
                    
                    if len(columns) < len(header):
                        continue  # Skip incomplete rows
                        
                    med = {
                        "medication": "",
                        "dosage": "",
                        "frequency": "",
                        "duration": "",
                        "side_effects": "",
                        "interactions": "",
                        "pregnancy_safety": ""
                    }
                    
                    # Fill in the medication fields based on mapped positions
                    for field, pos in field_positions.items():
                        if pos >= 0 and pos < len(columns):
                            med[field] = columns[pos]
                    
                    if med["medication"].strip():  # Only add non-empty medications
                        medications.append(med)
        else:
            # Try parsing it as bullet points or other format
            lines = re.split(r'\n+', prescription)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this is a medication line (usually starts with bullet, number, etc.)
                if line.startswith("• ") or re.match(r'^\d+\.', line) or ":" not in line[:15]:
                    medications.append(parse_medication_details(line))
        
        # If no medications were extracted, add an empty row
        if not medications:
            medications.append({
                "medication": "",
                "dosage": "",
                "frequency": "",
                "duration": "",
                "side_effects": "",
                "interactions": "",
                "pregnancy_safety": ""
            })
        
        # Create session state for medications if it doesn't exist
        if "medications" not in st.session_state:
            st.session_state.medications = medications
        
        # Display the editable prescription table
        st.write("### Edit Prescription")
        
        # Create column headers for the table
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([3, 2, 2, 2, 2, 2, 2, 1])
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
            st.write("**Interactions**")
        with col7:
            st.write("**Pregnancy Safety**")
        with col8:
            st.write("**Action**")
        
        # Display each medication as a row in the table
        for i, med in enumerate(st.session_state.medications):
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([3, 2, 2, 2, 2, 2, 2, 1])
            
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
                st.session_state.medications[i]["interactions"] = st.text_input(
                    "Interactions", 
                    value=med.get("interactions", ""), 
                    key=f"inter_{i}", 
                    label_visibility="collapsed"
                )
            
            with col7:
                st.session_state.medications[i]["pregnancy_safety"] = st.text_input(
                    "Pregnancy Safety", 
                    value=med.get("pregnancy_safety", ""), 
                    key=f"preg_{i}", 
                    label_visibility="collapsed"
                )
            
            with col8:
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
                "side_effects": "",
                "interactions": "",
                "pregnancy_safety": ""
            })
            st.experimental_rerun()
        
        # Additional instructions text area
        additional_instructions = st.text_area(
            "Additional Instructions", 
            value="", 
            height=100, 
            help="Add any additional instructions, lifestyle recommendations, etc."
        )
        
        # Tests section after the medications
        st.subheader("Recommended Medical Tests")
        common_tests = get_common_tests()
        
        # Initialize selected tests if not in session state
        if "selected_tests" not in st.session_state:
            st.session_state.selected_tests = []
            
        # Display previously selected tests
        if st.session_state.selected_tests:
            st.write("**Selected Tests:**")
            for i, test in enumerate(st.session_state.selected_tests):
                col1, col2 = st.columns([10, 1])
                with col1:
                    st.write(f"• {test}")
                with col2:
                    if st.button("✕", key=f"remove_test_{i}"):
                        st.session_state.selected_tests.pop(i)
                        st.experimental_rerun()
        
        # Create columns for test selection checkboxes
        test_cols = st.columns(3)
        
        # Track newly selected tests
        new_selected_tests = []
        
        for i, test in enumerate(common_tests):
            col_idx = i % 3
            with test_cols[col_idx]:
                # Skip tests already selected
                if test in st.session_state.selected_tests:
                    continue
                    
                # Create checkbox for each test
                if st.checkbox(test, key=f"test_{i}"):
                    new_selected_tests.append(test)
        
        # Custom test input
        custom_test = st.text_input("Add custom test", key="custom_test_input")
        if st.button("Add Custom Test") and custom_test:
            new_selected_tests.append(custom_test)
            st.experimental_rerun()
        
        # Add new selected tests to session state
        if new_selected_tests:
            st.session_state.selected_tests.extend(new_selected_tests)
            
        # Update tests in the main session state
        st.session_state.tests = st.session_state.selected_tests
        
        # Specialist Referrals section
        st.subheader("Specialist Referrals")
        
        # Initialize referrals in session state if it doesn't exist
        if "referrals" not in st.session_state:
            st.session_state.referrals = []
            
        # Display previously added referrals
        if st.session_state.referrals:
            st.write("**Selected Referrals:**")
            for i, referral in enumerate(st.session_state.referrals):
                col1, col2 = st.columns([10, 1])
                with col1:
                    specialist = referral.get("specialist", {})
                    st.write(f"• {specialist.get('name', 'Unknown')} ({specialist.get('category', 'Unknown')}) - {referral.get('reason', 'No reason specified')}")
                with col2:
                    if st.button("✕", key=f"remove_referral_{i}"):
                        st.session_state.referrals.pop(i)
                        st.experimental_rerun()
        
        # Get specialist categories and create a dropdown
        specialist_categories = get_specialist_categories()
        
        if specialist_categories:
            selected_category = st.selectbox(
                "Select Specialist Category", 
                [""] + specialist_categories,
                key="specialist_category"
            )
            
            if selected_category:
                # Get specialists in the selected category
                specialists = get_specialists_by_category(selected_category)
                
                if specialists:
                    # Create a dropdown for selecting a specialist
                    selected_specialist_id = st.selectbox(
                        "Select Specialist",
                        [""] + [(f"{s['id']}: {s['name']} - {s['hospital']}") for s in specialists],
                        key="specialist_select"
                    )
                    
                    if selected_specialist_id and ":" in selected_specialist_id:
                        # Extract the specialist ID from the selection
                        specialist_id = int(selected_specialist_id.split(":")[0])
                        
                        # Find the specialist in the list
                        selected_specialist = next((s for s in specialists if s['id'] == specialist_id), None)
                        
                        if selected_specialist:
                            # Show specialist details
                            st.write(f"**Hospital:** {selected_specialist['hospital']}")
                            st.write(f"**Contact:** {selected_specialist['contact']}")
                            st.write(f"**Availability:** {selected_specialist['availability']}")
                            
                            # Add reason for referral
                            referral_reason = st.text_area(
                                "Reason for Referral", 
                                height=100,
                                key="referral_reason"
                            )
                            
                            # Button to add the referral
                            if st.button("Add Referral"):
                                if referral_reason:
                                    # Add the referral to session state
                                    st.session_state.referrals.append({
                                        "specialist_id": specialist_id,
                                        "specialist": selected_specialist,
                                        "reason": referral_reason
                                    })
                                    st.experimental_rerun()
                                else:
                                    st.warning("Please provide a reason for the referral")
                else:
                    st.info(f"No specialists found in category: {selected_category}")
        else:
            st.warning("No specialist categories found. Please check the database setup.")
            
            # Allow for manual referral entry as fallback
            manual_referral = st.text_area(
                "Manual Referral Note", 
                height=100,
                key="manual_referral",
                help="Enter manual referral details if specialist selection is not working"
            )
            
            if st.button("Add Manual Referral"):
                if manual_referral:
                    st.session_state.referrals.append({
                        "specialist_id": 0,  # Placeholder ID
                        "specialist": {"name": "Manual Referral", "category": "Other"},
                        "reason": manual_referral
                    })
                    st.experimental_rerun()
                else:
                    st.warning("Please provide referral details")
        
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
                    
                    # Add the side effects, interactions and pregnancy safety in a clear format
                    if med.get("side_effects", "").strip():
                        final_prescription += f" Side effects: {med['side_effects']}"
                    
                    if med.get("interactions", "").strip():
                        final_prescription += f" Interactions: {med['interactions']}"
                    
                    if med.get("pregnancy_safety", "").strip():
                        final_prescription += f" Pregnancy Safety: {med['pregnancy_safety']}"
                    
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
                    medications.append(parse_medication_details(line))
                    
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
                "side_effects": "Side Effects",
                "interactions": "Interactions",
                "pregnancy_safety": "Pregnancy Safety"
            }
            
            # Only include columns that exist in the dataframe
            display_columns = [col for col in ["medication", "dosage", "frequency", "duration", "side_effects", "interactions", "pregnancy_safety"] 
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
        
        # Modify the "Generate Prescription" button handler
        with col1:
            if st.button("Generate Prescription"):
                # Generate PDF and HTML
                pdf_path, html_path = create_prescription(patient_data, diagnosis, prescription)
                
                if pdf_path and html_path:
                    # Store the paths in session state
                    st.session_state.view_pdf_path = pdf_path
                    st.session_state.view_html_path = html_path
                    
                    # Show view/download buttons
                    create_modal_buttons(pdf_path, html_path, patient_data['name'])
                    
                    # Only save if not already saved
                    if not st.session_state.consultation_saved:
                        if save_consultation(
                            st.session_state.doctor_id,
                            st.session_state.patient_id,
                            st.session_state.symptoms if isinstance(st.session_state.symptoms, list) else
                                [s.strip() for s in st.session_state.symptoms.split(',')],
                            diagnosis,
                            prescription
                        ):
                            st.success("Consultation saved to database")
                            st.session_state.consultation_saved = True
                        else:
                            st.error("Failed to save consultation")

        # Modify the "End Consultation" button handler
        with col2:
            if st.button("End Consultation"):
                # Generate PDF first if it hasn't been generated yet
                if not hasattr(st.session_state, 'view_pdf_path') or not st.session_state.view_pdf_path:
                    st.info("Generating prescription PDF before saving consultation...")
                    # Generate PDF and HTML
                    pdf_path, html_path = create_prescription(patient_data, diagnosis, prescription)
                    
                    if pdf_path and html_path:
                        # Store the paths in session state
                        st.session_state.view_pdf_path = pdf_path
                        st.session_state.view_html_path = html_path
                
                # Only save if not already saved
                if not st.session_state.consultation_saved:
                    save_result = save_consultation(
                        st.session_state.doctor_id,
                        st.session_state.patient_id,
                        st.session_state.symptoms if isinstance(st.session_state.symptoms, list) else
                            [s.strip() for s in st.session_state.symptoms.split(',')],
                        diagnosis,
                        prescription
                    )
                    
                    if save_result:
                        st.success("Consultation and prescription PDF saved successfully")
                        st.session_state.consultation_saved = True
                    else:
                        st.error("Failed to save consultation")
                        # Option to continue or force end
                        if st.button("Force End Without Saving"):
                            start_new_conversation()
                            st.experimental_rerun()
                else:
                    # Already saved, just end the consultation
                    st.success("Consultation already saved, ending session")
                    
                # Reset for new consultation
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
