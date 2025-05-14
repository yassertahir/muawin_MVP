import sqlite3
import os
import sys

def migrate_consultation_referrals():
    """
    Add referrals column to the consultations table if it doesn't exist.
    This is needed to store JSON data about referrals in the consultations table.
    """
    conn = sqlite3.connect("docassist.db")
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(consultations)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add referrals column if it doesn't exist
    if "referrals" not in columns:
        try:
            cursor.execute("ALTER TABLE consultations ADD COLUMN referrals TEXT")
            print("Added referrals column to consultations table")
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Error adding referrals column: {e}")
    else:
        print("referrals column already exists in consultations table")
    
    conn.close()
    return True

if __name__ == "__main__":
    migrate_consultation_referrals()
    print("Migration complete")