import sqlite3
import os
import pandas as pd

def main():
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
            vital_signs TEXT, -- New field: storing temperature, BP as JSON
            pre_conditions TEXT, -- New field: pre-existing conditions
            diagnosis TEXT,
            prescription TEXT,
            consultation_date TEXT,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
        ''')
        
        # Create specialists table
        cursor.execute('''
        CREATE TABLE specialists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            hospital TEXT,
            contact TEXT,
            availability TEXT
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
        
        # Generate sample specialists
        sample_specialists = [
            ('Dr. Asim Riaz', 'Cardiologist', 'Punjab Institute of Cardiology, Lahore', '+92-42-99200031', 'Mon-Fri, 9am-5pm'),
            ('Dr. Farah Khan', 'Cardiologist', 'Aga Khan University Hospital, Karachi', '+92-21-34930051', 'Tue-Sat, 10am-6pm'),
            ('Dr. Imran Yousuf', 'Neurologist', 'Shifa International Hospital, Islamabad', '+92-51-8464646', 'Mon-Thu, 9am-4pm'),
            ('Dr. Saima Chaudhry', 'Neurologist', 'Doctors Hospital, Lahore', '+92-42-35862493', 'Wed-Sun, 11am-7pm'),
            ('Dr. Tariq Mahmood', 'Orthopedic Surgeon', 'Liaquat National Hospital, Karachi', '+92-21-34412754', 'Mon-Fri, 8am-2pm'),
            ('Dr. Hina Shahid', 'Orthopedic Surgeon', 'Mayo Hospital, Lahore', '+92-42-99211129', 'Tue-Sat, 9am-3pm'),
            ('Dr. Adeel Ahmed', 'Dermatologist', 'Pakistan Institute of Medical Sciences, Islamabad', '+92-51-9261170', 'Mon-Wed, 10am-4pm'),
            ('Dr. Naila Jabeen', 'Dermatologist', 'Jinnah Hospital, Lahore', '+92-42-99231400', 'Thu-Sun, 11am-5pm'),
            ('Dr. Zubair Ali', 'Gastroenterologist', 'Aga Khan University Hospital, Karachi', '+92-21-34930051', 'Mon-Fri, 9am-5pm'),
            ('Dr. Saba Karim', 'Gastroenterologist', 'Shaukat Khanum Memorial Hospital, Lahore', '+92-42-35945100', 'Tue-Sat, 10am-6pm'),
            ('Dr. Naveed Khan', 'Endocrinologist', 'Shifa International Hospital, Islamabad', '+92-51-8464646', 'Mon-Thu, 9am-4pm'),
            ('Dr. Amina Iqbal', 'Endocrinologist', 'Services Hospital, Lahore', '+92-42-99203402', 'Wed-Sun, 11am-7pm'),
            ('Dr. Salman Malik', 'Ophthalmologist', 'Al-Shifa Trust Eye Hospital, Rawalpindi', '+92-51-5487820', 'Mon-Fri, 8am-2pm'),
            ('Dr. Rabia Aziz', 'Ophthalmologist', 'Mayo Hospital, Lahore', '+92-42-99211129', 'Tue-Sat, 9am-3pm'),
            ('Dr. Kamran Sheikh', 'ENT Specialist', 'Pakistan Institute of Medical Sciences, Islamabad', '+92-51-9261170', 'Mon-Wed, 10am-4pm'),
            ('Dr. Fariha Tahir', 'ENT Specialist', 'Jinnah Hospital, Lahore', '+92-42-99231400', 'Thu-Sun, 11am-5pm'),
            ('Dr. Bilal Raza', 'Psychiatrist', 'Aga Khan University Hospital, Karachi', '+92-21-34930051', 'Mon-Fri, 9am-5pm'),
            ('Dr. Sadia Anwar', 'Psychiatrist', 'Punjab Institute of Mental Health, Lahore', '+92-42-99210896', 'Tue-Sat, 10am-6pm'),
            ('Dr. Omar Farooq', 'Nephrologist', 'Shifa International Hospital, Islamabad', '+92-51-8464646', 'Mon-Thu, 9am-4pm'),
            ('Dr. Nadia Hamid', 'Nephrologist', 'Doctors Hospital, Lahore', '+92-42-35862493', 'Wed-Sun, 11am-7pm')
        ]
        
        cursor.executemany('''
        INSERT INTO specialists (name, category, hospital, contact, availability)
        VALUES (?, ?, ?, ?, ?)
        ''', sample_specialists)
        
        # Create patients.csv file for dropdown selection
        patients_df = pd.DataFrame([{'patientId': p[0]} for p in sample_patients])
        patients_df.to_csv('patients.csv', index=False)
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print("Database initialized with tables and sample data.")
    else:
        print("Database already exists. Skipping initialization.")
    
    return True

if __name__ == "__main__":
    # This will run when script is executed directly
    main()
    print("Database initialization complete.")
