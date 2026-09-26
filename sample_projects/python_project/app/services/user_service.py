from app.security.password import hash_password
from app.db.database import save_user


def create_user_record(username: str, password: str):
    """Hash the password and save a new user."""
    password_hash = hash_password(password)

    return save_user(
        username=username,
        password_hash=password_hash,
    )