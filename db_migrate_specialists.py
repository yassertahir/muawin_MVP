import sqlite3
import os

def migrate_specialists_table():
    """
    Add specialists table to the database and populate it with sample data.
    """
    conn = sqlite3.connect("muawin.db")
    cursor = conn.cursor()
    
    # Check if specialists table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='specialists'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        print("Creating specialists table...")
        
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
        
        # Add sample specialists
        sample_specialists = [
            # Cardiologists
            ("Dr. Ahmed Khan", "Cardiology", "Aga Khan University Hospital", "+92-21-111-911-911", "Mon, Wed, Fri: 9AM-1PM"),
            ("Dr. Saima Zubair", "Cardiology", "National Institute of Cardiovascular Diseases", "+92-21-9920-1271", "Tue, Thu: 10AM-2PM"),
            
            # Neurologists
            ("Dr. Farhan Ali", "Neurology", "Liaquat National Hospital", "+92-21-3412-7600", "Mon, Wed: 5PM-8PM"),
            ("Dr. Nadia Memon", "Neurology", "Shifa International Hospital", "+92-51-8464-646", "Mon-Fri: 9AM-12PM"),
            
            # Orthopedics
            ("Dr. Adeel Iqbal", "Orthopedics", "South City Hospital", "+92-21-3520-0935", "Tue, Thu, Sat: 6PM-9PM"),
            ("Dr. Zainab Raza", "Orthopedics", "Indus Hospital", "+92-21-3511-2709", "Mon, Wed, Fri: 2PM-5PM"),
            
            # Dermatologists
            ("Dr. Sadia Aslam", "Dermatology", "Patel Hospital", "+92-21-3453-0941", "Tue, Thu: 3PM-6PM"),
            ("Dr. Kamal Hassan", "Dermatology", "Dr. Ziauddin Hospital", "+92-21-3538-3892", "Mon, Wed, Fri: 4PM-7PM"),
            
            # Psychiatrists
            ("Dr. Faisal Mahmood", "Psychiatry", "Institute of Behavioral Sciences", "+92-42-3578-5643", "Mon-Fri: 10AM-1PM"),
            ("Dr. Ayesha Malik", "Psychiatry", "Karachi Psychiatric Hospital", "+92-21-3661-1290", "Tue, Thu, Sat: 11AM-3PM"),
            
            # Ophthalmologists
            ("Dr. Sohail Ahmed", "Ophthalmology", "Al-Shifa Trust Eye Hospital", "+92-51-5487-820", "Mon, Wed, Fri: 9AM-12PM"),
            ("Dr. Rabia Zuberi", "Ophthalmology", "LRBT Free Eye Hospital", "+92-21-3666-1056", "Tue, Thu: 2PM-5PM"),
            
            # ENT Specialists
            ("Dr. Taimur Shah", "ENT", "National ENT Center", "+92-51-2876-534", "Mon-Fri: 5PM-8PM"),
            ("Dr. Hina Qureshi", "ENT", "Liaquat National Hospital", "+92-21-3412-7600", "Sat-Sun: 10AM-2PM"),
            
            # Pulmonologists
            ("Dr. Bilal Javed", "Pulmonology", "Ojha Institute of Chest Diseases", "+92-21-9920-4776", "Mon, Wed, Fri: 10AM-1PM"),
            ("Dr. Sana Khan", "Pulmonology", "National Institute of Diseases of Chest", "+92-42-9921-3471", "Tue, Thu: 3PM-6PM"),
            
            # Gynecologists
            ("Dr. Sameera Abid", "Gynecology", "Lady Dufferin Hospital", "+92-21-3276-1355", "Mon-Fri: 9AM-1PM"),
            ("Dr. Humera Syed", "Gynecology", "Civil Hospital", "+92-21-9921-5960", "Mon, Wed, Fri: 2PM-5PM"),
            
            # Pediatricians
            ("Dr. Amjad Ali", "Pediatrics", "National Institute of Child Health", "+92-21-9920-4932", "Mon-Fri: 8AM-12PM"),
            ("Dr. Fatima Jaffar", "Pediatrics", "Children's Hospital", "+92-42-9923-0402", "Tue, Thu, Sat: 10AM-2PM")
        ]
        
        cursor.executemany(
            "INSERT INTO specialists (name, category, hospital, contact, availability) VALUES (?, ?, ?, ?, ?)",
            sample_specialists
        )
        
        # Commit changes
        conn.commit()
        print("Specialists table created and populated with sample data")
    else:
        print("Specialists table already exists, skipping migration")
    
    conn.close()
    return True

if __name__ == "__main__":
    migrate_specialists_table()
    print("Migration complete")