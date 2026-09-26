import hashlib


def hash_password(password: str) -> str:
    """Create a SHA-256 hash for the supplied password."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""
    return hash_password(password) == password_hash