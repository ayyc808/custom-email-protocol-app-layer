# Authentication Module
# Handles password hashing and user authentication.

import bcrypt


def hash_password(password: str) -> str:
    # Hash a password using bcrypt with auto-generated salt.
    # Returns hashed password string (includes salt).
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    # Verify a password against its bcrypt hash.
    # Returns True if password matches, False otherwise.
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )


def validate_credentials(username: str, password: str) -> tuple:
    # Validate username and password meet requirements.
    # Returns (is_valid, error_message)

    if not username or not isinstance(username, str):
        return False, "Username cannot be empty"

    if len(username) < 3 or len(username) > 32:
        return False, "Username must be 3-32 characters"

    if not username.isalnum():
        return False, "Username must be alphanumeric only"

    if not password or len(password) < 4:
        return False, "Password must be at least 4 characters"

    return True, ""