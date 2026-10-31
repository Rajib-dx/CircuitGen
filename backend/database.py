# backend/database.py
import sqlite3
import os

# Store the DB in the backend folder
DB_PATH = os.path.join(os.path.dirname(__file__), 'circuits.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_prompt TEXT,
            skidl_code TEXT,
            visual_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_generation(prompt: str, skidl_code: str, visual_json: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (user_prompt, skidl_code, visual_json) VALUES (?, ?, ?)", 
        (prompt, skidl_code, visual_json)
    )
    conn.commit()
    conn.close()