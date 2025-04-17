import os
import sqlite3
import pandas as pd
import streamlit as st

def ensure_db_initialized():
    """Ensure database is initialized for Streamlit Cloud"""
    # Check if database exists, if not create it
    if not os.path.exists("muawin.db"):
        st.info("Initializing database for first use...")
        
        # Import and run db_init
        from db_init import main
        main()
        
        # Import and run any additional db migrations
        try:
            from db_migrate import migrate_database
            migrate_database()
        except Exception as e:
            st.warning(f"Database migration error: {e}")
        
        try:
            from db_add_tests import add_tests_column
            add_tests_column()
        except Exception as e:
            st.warning(f"Adding tests column error: {e}")
        
        try:
            from db_update_prescriptions import update_prescriptions_storage
            update_prescriptions_storage()
        except Exception as e:
            st.warning(f"Updating prescriptions storage error: {e}")
            
        # Ensure 'data/prescription' directory exists
        os.makedirs("data/prescription", exist_ok=True)
        
        st.success("Database initialized successfully!")
    else:
        # Database exists, verify it's properly set up
        conn = sqlite3.connect("muawin.db")
        cursor = conn.cursor()
        
        # Check that tables exist
        tables = ["doctors", "patients", "consultations"]
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                st.error(f"Table {table} is missing from the database!")
        
        # Check that admin user exists
        cursor.execute("SELECT id FROM doctors WHERE username = 'admin'")
        if not cursor.fetchone():
            st.warning("Admin user not found, creating default admin...")
            cursor.execute(
                "INSERT INTO doctors (username, password, name, email, specialization) VALUES ('admin', 'admin', 'Admin Doctor', 'admin@example.com', 'General Practice')"
            )
            conn.commit()
            st.success("Default admin user created!")
        
        conn.close()
        
        # Ensure 'data/prescription' directory exists
        os.makedirs("data/prescription", exist_ok=True)
        
        st.info("Database is ready to use.")

if __name__ == "__main__":
    ensure_db_initialized()