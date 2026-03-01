"""
Pytest fixtures for the ParkingStructure server tests.
"""

import pytest
from src.server.app import create_app
from src.server.database import db


@pytest.fixture(autouse=True)
def reset_db():
    """Reset the in-memory database singleton to a clean state before each test."""
    db.badges = {"B001", "B002", "B003", "B004", "B005"}
    db.spots = {
        1: {f"1-{i:02d}": False for i in range(1, 26)},
        2: {f"2-{i:02d}": False for i in range(1, 26)},
        3: {f"3-{i:02d}": False for i in range(1, 26)},
    }
    db.capacity = 75
    db.num_cars_inside = 0
    db.gates = {
        1: {"type": "entry", "open": False, "override": False, "override_state": False},
        2: {"type": "exit", "open": False, "override": False, "override_state": False},
    }
    db.event_log = []
    db.power = {"source": "grid", "outage_mode": False}
    db.lockdown = False
    db.admin_tokens = set()


@pytest.fixture
def client():
    """Flask test client with testing mode enabled."""
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
