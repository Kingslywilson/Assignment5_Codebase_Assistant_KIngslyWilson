class User:
    """Represent a user account."""

    def __init__(self, username: str, password_hash: str):
        self.username = username
        self.password_hash = password_hash