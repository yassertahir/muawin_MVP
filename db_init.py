import sqlite3
import os
import pandas as pd

# Check if database exists, if not create it
if not os.path.exists("muawin.db"):
    # Connect to database (this creates the file if it doesn't exist)
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        email TEXT,
        specialization TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE patients (
        id TEXT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT,
        temperature TEXT,
        blood_pressure TEXT,
        pre_conditions TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE consultations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER,
        patient_id TEXT,
        symptoms TEXT,  -- JSON string array
        diagnosis TEXT,
        prescription TEXT,
        consultation_date TEXT,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id),
        FOREIGN KEY (patient_id) REFERENCES patients (id)
    )
    ''')
    
    # Insert default admin user
    cursor.execute('''
    INSERT INTO doctors (username, password, name, email, specialization)
    VALUES (?, ?, ?, ?, ?)
    ''', ('admin', 'admin', 'Admin Doctor', 'admin@example.com', 'General Practice'))
    
    # Generate sample patients
    sample_patients = [
        ('P001', 'Ahmed Khan', 45, 'Male', '37.2°C', '130/85', 'Hypertension'),
        ('P002', 'Fatima Ali', 32, 'Female', '36.8°C', '120/80', 'None'),
        ('P003', 'Imran Shah', 28, 'Male', '37.5°C', '118/76', 'Asthma'),
        ('P004', 'Ayesha Ahmed', 56, 'Female', '37.0°C', '140/90', 'Diabetes, Hypertension'),
        ('P005', 'Zainab Malik', 22, 'Female', '36.7°C', '110/70', 'None')
    ]
    
    cursor.executemany('''
    INSERT INTO patients (id, name, age, gender, temperature, blood_pressure, pre_conditions)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', sample_patients)
    
    # Create patients.csv file for dropdown selection
    patients_df = pd.DataFrame([{'patientId': p[0]} for p in sample_patients])
    patients_df.to_csv('patients.csv', index=False)
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Database initialized with tables and sample data.")
else:
    print("Database already exists. Skipping initialization.")

if __name__ == "__main__":
    # This will run when script is executed directly
    print("Database initialization complete.")
