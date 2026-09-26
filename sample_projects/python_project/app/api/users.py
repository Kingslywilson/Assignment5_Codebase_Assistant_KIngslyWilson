from app.services.user_service import create_user_record


def create_user(username: str, password: str):
    """Create a new user account."""
    return create_user_record(username, password)