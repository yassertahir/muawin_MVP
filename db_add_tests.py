import sqlite3
import os

def add_tests_column():
    """Add tests column to consultations table if it doesn't exist"""
    if not os.path.exists("muawin.db"):
        print("Database does not exist. Run db_init.py first.")
        return
        
    # Connect to database
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(consultations)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add tests column if it doesn't exist
    if "tests" not in columns:
        try:
            cursor.execute("ALTER TABLE consultations ADD COLUMN tests TEXT")
            print("Added tests column to consultations table")
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Error adding tests column: {e}")
    else:
        print("tests column already exists")
    
    conn.close()
    print("Database migration complete.")

if __name__ == "__main__":
    add_tests_column()