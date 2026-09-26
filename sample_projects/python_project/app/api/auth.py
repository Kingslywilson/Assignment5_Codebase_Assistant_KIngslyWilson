from app.services.auth_service import authenticate_user


def login(username: str, password: str):
    """Authenticate a user and return an access token."""
    user = authenticate_user(username, password)

    if user is None:
        return {"error": "Invalid credentials"}

    return {
        "access_token": user["access_token"],
        "token_type": "bearer",
    }