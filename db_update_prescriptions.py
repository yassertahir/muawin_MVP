import sqlite3
import os
import shutil

def update_prescriptions_storage():
    """
    Modify consultation table to add prescription PDF storage:
    1. Clear the consultation table
    2. Add a prescription_pdf column
    3. Create the data/prescription directory if it doesn't exist
    """
    print("Starting prescription storage update...")
    
    # Check if database exists
    if not os.path.exists("muawin.db"):
        print("Database does not exist. Run db_init.py first.")
        return
    
    # Create data/prescription directory if it doesn't exist
    prescription_dir = "data/prescription"
    if not os.path.exists(prescription_dir):
        os.makedirs(prescription_dir)
        print(f"Created directory: {prescription_dir}")
    else:
        # Clear existing files in prescription directory
        for file in os.listdir(prescription_dir):
            file_path = os.path.join(prescription_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print(f"Cleared existing files in {prescription_dir}")
    
    # Connect to database
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    try:
        # Check if prescription_pdf column exists
        cursor.execute("PRAGMA table_info(consultations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Clear consultation table
        cursor.execute("DELETE FROM consultations")
        print("Cleared all consultation records")
        
        # Add prescription_pdf column if it doesn't exist
        if "prescription_pdf" not in columns:
            cursor.execute("ALTER TABLE consultations ADD COLUMN prescription_pdf TEXT")
            print("Added prescription_pdf column to consultations table")
        else:
            print("prescription_pdf column already exists")
        
        conn.commit()
        print("Database update successful!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error updating database: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_prescriptions_storage()