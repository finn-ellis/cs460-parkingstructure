"""
Pytest fixtures for the ParkingStructure server tests.

The ``reset_db`` fixture re-initialises the in-memory database singleton
before every test so each test starts from a known clean state.

The ``client`` fixture creates a fully-initialised Flask + SocketIO app
so that ``socketio.emit()`` calls inside the business logic work normally
(even though no real WebSocket clients are connected during tests).
"""

import pytest
from src.server.app import create_app
from src.server.database import db


@pytest.fixture(autouse=True)
def reset_db():
    """Re-initialise the database singleton to a clean state before each test."""
    db.__init__()


@pytest.fixture
def client():
    """Flask test client backed by a fully-initialised app (Flask + SocketIO)."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Log in as admin and return Authorization headers."""
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
