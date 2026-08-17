import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

class StateManager:
    """Manages local state using SQLite for fault tolerance across reboots/power loss."""
    
    def __init__(self, db_path='state.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recording_state (
                    id INTEGER PRIMARY KEY,
                    is_recording BOOLEAN NOT NULL,
                    class_name TEXT,
                    part_number INTEGER
                )
            ''')
            # Initialize with default if empty
            cursor.execute('SELECT COUNT(*) FROM recording_state')
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO recording_state (id, is_recording, class_name, part_number)
                    VALUES (1, 0, NULL, 1)
                ''')
            conn.commit()

    def set_recording(self, class_name, part_number):
        """Called when a recording successfully starts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE recording_state
                SET is_recording = 1, class_name = ?, part_number = ?
                WHERE id = 1
            ''', (class_name, part_number))
            conn.commit()

    def clear_recording(self):
        """Called when a recording successfully finishes and stops."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE recording_state
                SET is_recording = 0, class_name = NULL, part_number = 1
                WHERE id = 1
            ''')
            conn.commit()

    def get_state(self):
        """Fetch the current state upon boot to check for interrupted recordings."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_recording, class_name, part_number FROM recording_state WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return {
                    'is_recording': bool(row[0]),
                    'class_name': row[1],
                    'part_number': row[2]
                }
            return None
