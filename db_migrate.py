import sqlite3
import os

def migrate_database():
    """Add new columns to consultations table if they don't exist"""
    if not os.path.exists("muawin.db"):
        print("Database does not exist. Run db_init.py first.")
        return
        
    # Connect to database
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(consultations)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add vital_signs column if it doesn't exist
    if "vital_signs" not in columns:
        try:
            cursor.execute("ALTER TABLE consultations ADD COLUMN vital_signs TEXT")
            print("Added vital_signs column to consultations table")
        except sqlite3.OperationalError as e:
            print(f"Error adding vital_signs column: {e}")
    
    # Add pre_conditions column if it doesn't exist
    if "pre_conditions" not in columns:
        try:
            cursor.execute("ALTER TABLE consultations ADD COLUMN pre_conditions TEXT")
            print("Added pre_conditions column to consultations table")
        except sqlite3.OperationalError as e:
            print(f"Error adding pre_conditions column: {e}")
    
    conn.commit()
    conn.close()
    print("Database migration complete.")

if __name__ == "__main__":
    migrate_database()