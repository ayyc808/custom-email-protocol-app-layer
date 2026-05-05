# Custom Email Protocol - Database Module
# Handles all database operations for message storage and user management.
# Uses SQLite with thread-safe operations.

import sqlite3
import threading
from typing import List, Optional, Dict
import bcrypt


class DatabaseManager:
    # Thread-safe database manager for email storage.
    # Handles user authentication, message storage, and retrieval.

    def __init__(self, db_path: str = 'email_server.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        # Initialize database schema with tables and indexes.
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    username  TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user  TEXT NOT NULL,
                    to_user    TEXT NOT NULL,
                    subject    TEXT,
                    body       TEXT,
                    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read       BOOLEAN DEFAULT 0,
                    FOREIGN KEY (from_user) REFERENCES users(username),
                    FOREIGN KEY (to_user)   REFERENCES users(username)
                )
            ''')

            # Index for faster inbox queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_to_user
                ON messages(to_user)
            ''')

            # Index for faster timestamp sorting
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp)
            ''')

            conn.commit()
            conn.close()

    def create_user(self, username: str, password: str) -> bool:
        # Create a new user account.
        # Returns True if created, False if username already exists.
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                    (username, password_hash)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate username
            finally:
                if conn:
                    conn.close()

    def authenticate_user(self, username: str, password: str) -> bool:
        # Verify username and password.
        # Returns True if credentials are valid.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT password_hash FROM users WHERE username = ?',
                    (username,)
                )
                result = cursor.fetchone()
            finally:
                if conn:
                    conn.close()

        if result:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                result[0].encode('utf-8')
            )
        return False

    def user_exists(self, username: str) -> bool:
        # Check if a username exists in the database.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM users WHERE username = ?', (username,)
                )
                result = cursor.fetchone()
            finally:
                if conn:
                    conn.close()
        return result is not None

    def store_message(self, from_user: str, to_user: str,
                      subject: str, body: str) -> Optional[int]:
        # Store a new message.
        # Returns message_id on success, None if either user doesn't exist.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Check sender exists
                cursor.execute(
                    'SELECT 1 FROM users WHERE username = ?', (from_user,)
                )
                if not cursor.fetchone():
                    return None

                # Check recipient exists
                cursor.execute(
                    'SELECT 1 FROM users WHERE username = ?', (to_user,)
                )
                if not cursor.fetchone():
                    return None

                # Insert the message
                cursor.execute(
                    '''INSERT INTO messages (from_user, to_user, subject, body)
                       VALUES (?, ?, ?, ?)''',
                    (from_user, to_user, subject, body)
                )
                message_id = cursor.lastrowid
                conn.commit()
                return message_id

            except Exception as e:
                print(f"Error storing message: {e}")
                return None

            finally:
                # Always close connection even if we returned early
                if conn:
                    conn.close()

    def get_messages_for_user(self, username: str) -> List[Dict]:
        # Get all inbox messages for a user, newest first.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT message_id, from_user, subject, timestamp, read
                       FROM messages WHERE to_user = ?
                       ORDER BY timestamp DESC''',
                    (username,)
                )
                messages = [dict(row) for row in cursor.fetchall()]
            finally:
                if conn:
                    conn.close()
        return messages

    def get_message(self, message_id: int, username: str) -> Optional[Dict]:
        # Get a full message by ID.
        # Only succeeds if username is the recipient. Marks message as read.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT * FROM messages
                       WHERE message_id = ? AND to_user = ?''',
                    (message_id, username)
                )
                result = cursor.fetchone()

                if result:
                    # Mark as read
                    cursor.execute(
                        'UPDATE messages SET read = 1 WHERE message_id = ?',
                        (message_id,)
                    )
                    conn.commit()
                    return dict(result)

                return None

            finally:
                if conn:
                    conn.close()

    def delete_message(self, message_id: int, username: str) -> bool:
        # Delete a message. Only succeeds if username is the recipient.
        # Returns True if deleted, False if not found or unauthorized.
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM messages WHERE message_id = ? AND to_user = ?',
                    (message_id, username)
                )
                deleted = cursor.rowcount > 0
                conn.commit()
                return deleted
            finally:
                if conn:
                    conn.close()