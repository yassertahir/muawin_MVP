import sqlite3
import pandas as pd

def update_database():
    # Connect to existing DB
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    # Check if language column exists
    cursor.execute("PRAGMA table_info(patients)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'language' not in column_names:
        # Add language column
        cursor.execute("ALTER TABLE patients ADD COLUMN language TEXT DEFAULT 'English'")
        
        # Update existing patients with default language values
        cursor.execute("""
        UPDATE patients SET language = CASE
            WHEN id = 'P001' THEN 'Urdu'
            WHEN id = 'P002' THEN 'English'
            WHEN id = 'P003' THEN 'Urdu'
            WHEN id = 'P004' THEN 'Punjabi'
            WHEN id = 'P005' THEN 'Sindhi'
            ELSE 'English'
        END
        """)
        
        # Update the patients CSV to include language
        cursor.execute("SELECT id, language FROM patients")
        patient_data = cursor.fetchall()
        
        # Read existing CSV
        df = pd.read_csv('patients.csv')
        
        # Add language column if not exists
        if 'language' not in df.columns:
            df['language'] = 'English'  # Default
            
            # Update with values from DB
            for patient_id, language in patient_data:
                df.loc[df['patientId'] == patient_id, 'language'] = language
            
            # Save updated CSV
            df.to_csv('patients.csv', index=False)
        
        print("Database updated with language column")
    else:
        print("Language column already exists")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()