import sqlite3
import pandas as pd

def update_patients_csv():
    """
    Update the patients.csv file with the latest data from the database.
    This ensures the patient list displayed in the app is current.
    """
    try:
        # Connect to database
        conn = sqlite3.connect("muawin.db")
        
        # Query all patient IDs from the database
        df = pd.read_sql("SELECT id as patientId FROM patients", conn)
        
        # Save to CSV (overwriting the existing file)
        df.to_csv('patients.csv', index=False)
        
        print(f"Updated patients.csv with {len(df)} patient records")
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating patients.csv: {str(e)}")
        return False

if __name__ == "__main__":
    update_patients_csv()