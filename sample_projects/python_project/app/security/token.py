import base64


def create_access_token(user_id: int) -> str:
    """Create a simple encoded access token."""
    value = f"user:{user_id}"
    return base64.b64encode(value.encode()).decode()