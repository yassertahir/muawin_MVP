import sqlite3
import os

def migrate_referrals_table():
    """
    Add referrals table to the existing database if it doesn't exist.
    """
    conn = sqlite3.connect("docassist.db")
    cursor = conn.cursor()
    
    # Check if referrals table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        print("Creating referrals table...")
        
        # Create referrals table
        cursor.execute('''
        CREATE TABLE referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            patient_id TEXT,
            specialist_id INTEGER,
            reason TEXT,
            referral_date TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (specialist_id) REFERENCES specialists (id)
        )
        ''')
        
        # Commit changes
        conn.commit()
        print("Referrals table created successfully")
    else:
        print("Referrals table already exists, skipping migration")
    
    conn.close()
    return True

if __name__ == "__main__":
    migrate_referrals_table()
    print("Migration complete")