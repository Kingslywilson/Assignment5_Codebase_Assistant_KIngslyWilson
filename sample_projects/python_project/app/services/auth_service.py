from app.security.password import verify_password
from app.security.token import create_access_token
from app.db.database import find_user


def authenticate_user(username: str, password: str):
    """Find a user, verify the password, and create an access token."""
    user = find_user(username)

    if user is None:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    token = create_access_token(user["id"])

    return {
        "user_id": user["id"],
        "access_token": token,
    }