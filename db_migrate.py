import sqlite3
import os
import sys

def migrate_database():
    """Add new columns to consultations table if they don't exist"""
    if not os.path.exists("docassist.db"):
        print("Database file not found. Please run db_init.py first.")
        sys.exit(1)
        
    # Connect to database
    conn = sqlite3.connect("docassist.db")
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

def migrate_pre_conditions():
    """Move pre-existing conditions from consultations to patients table"""
    if not os.path.exists("docassist.db"):
        print("Database file not found. Please run db_init.py first.")
        sys.exit(1)
        
    # Connect to database
    conn = sqlite3.connect("docassist.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all patients
    cursor.execute("SELECT id FROM patients")
    patients = cursor.fetchall()
    
    for patient in patients:
        patient_id = patient["id"]
        
        # Get latest consultation with pre-existing conditions
        cursor.execute("""
            SELECT pre_conditions 
            FROM consultations 
            WHERE patient_id = ? AND pre_conditions IS NOT NULL
            ORDER BY consultation_date DESC
            LIMIT 1
        """, (patient_id,))
        
        latest = cursor.fetchone()
        
        if latest and latest["pre_conditions"]:
            # Update patient record with the conditions from their latest consultation
            cursor.execute(
                "UPDATE patients SET pre_conditions = ? WHERE id = ?",
                (latest["pre_conditions"], patient_id)
            )
            print(f"Updated patient {patient_id} with conditions: {latest['pre_conditions']}")
    
    conn.commit()
    conn.close()
    print("Pre-existing conditions migration complete.")

def remove_pre_conditions_from_consultations():
    """
    After migrating pre-existing conditions to patient table,
    remove the column from consultations table
    """
    if not os.path.exists("docassist.db"):
        print("Database file not found. Please run db_init.py first.")
        sys.exit(1)
        
    # Connect to database
    conn = sqlite3.connect("docassist.db")
    cursor = conn.cursor()
    
    try:
        print("Starting removal of pre_conditions from consultations table...")
        
        # SQLite doesn't support DROP COLUMN directly until version 3.35.0
        # So we need to use a workaround:
        
        # 1. Create a new table without the pre_conditions column
        cursor.execute("""
        CREATE TABLE consultations_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            patient_id TEXT,
            symptoms TEXT,
            vital_signs TEXT,
            diagnosis TEXT,
            prescription TEXT,
            consultation_date TEXT,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
        """)
        
        # 2. Copy data from old table to new table
        cursor.execute("""
        INSERT INTO consultations_new (
            id, doctor_id, patient_id, symptoms, vital_signs, 
            diagnosis, prescription, consultation_date
        )
        SELECT 
            id, doctor_id, patient_id, symptoms, vital_signs,
            diagnosis, prescription, consultation_date
        FROM consultations
        """)
        
        # 3. Drop old table
        cursor.execute("DROP TABLE consultations")
        
        # 4. Rename new table to original name
        cursor.execute("ALTER TABLE consultations_new RENAME TO consultations")
        
        conn.commit()
        print("Successfully removed pre_conditions column from consultations table")
        
    except Exception as e:
        conn.rollback()
        print(f"Error removing pre_conditions from consultations: {str(e)}")
    finally:
        conn.close()

# Function to add vital_signs column to consultations table
def add_vital_signs_column():
    """Add vital_signs column to consultations table if it doesn't exist"""
    if not os.path.exists("docassist.db"):
        print("Database file not found. Please run db_init.py first.")
        sys.exit(1)
        
    # Connect to database
    conn = sqlite3.connect("docassist.db")

# Function to add language column to patients table
def add_language_column():
    """Add language column to patients table if it doesn't exist"""
    if not os.path.exists("docassist.db"):
        print("Database file not found. Please run db_init.py first.")
        sys.exit(1)
        
    # Connect to database
    conn = sqlite3.connect("docassist.db")

if __name__ == "__main__":
    migrate_database()
    migrate_pre_conditions()  # First migrate data to patient table
    remove_pre_conditions_from_consultations()  # Then remove column from consultations