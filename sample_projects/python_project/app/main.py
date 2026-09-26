from app.api.auth import login
from app.api.users import create_user


def create_application():
    """Create and configure the application routes."""
    routes = {
        "/login": login,
        "/users": create_user,
    }
    return routes


app = create_application()