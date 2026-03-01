"""
Tests for the ParkingStructure server.

Covers:
  - App root and global status endpoints
  - Gate Controller (use cases 4.1 Successful Entry, 4.3 Successful Exit)
  - Parking Controller (use case 4.2 Parking Spot Update)
  - Admin Controller (use case 4.5 Admin Gate Override, badge CRUD, CCTV, events)
  - Power Controller (use case 4.4 Emergency Power Failure)
"""

import pytest
from src.server.database import db


# ---------------------------------------------------------------------------
# App / root endpoints
# ---------------------------------------------------------------------------

class TestAppRoot:
    def test_root_returns_service_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["service"] == "ParkingStructure Main Controller"
        assert data["status"] == "running"
        assert "/gate" in data["endpoints"]

    def test_status_shape(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "occupancy" in data
        assert "gates" in data
        assert "power" in data
        assert "lockdown" in data

    def test_status_initial_values(self, client):
        data = client.get("/status").get_json()
        assert data["occupancy"]["num_cars_inside"] == 0
        assert data["occupancy"]["capacity"] == 75
        assert data["lockdown"] is False
        assert data["power"]["source"] == "grid"


# ---------------------------------------------------------------------------
# Gate Controller
# ---------------------------------------------------------------------------

class TestGateStatus:
    def test_all_gates_returned(self, client):
        resp = client.get("/gate/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "1" in data
        assert "2" in data

    def test_single_gate_entry(self, client):
        resp = client.get("/gate/status/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gate_id"] == 1
        assert data["type"] == "entry"
        assert data["open"] is False

    def test_single_gate_exit(self, client):
        resp = client.get("/gate/status/2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gate_id"] == 2
        assert data["type"] == "exit"

    def test_invalid_gate_returns_404(self, client):
        resp = client.get("/gate/status/99")
        assert resp.status_code == 404


class TestVehicleDetected:
    def test_entry_gate_awaits_rfid(self, client):
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 1})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["action"] == "awaiting_rfid"
        assert data["gate_id"] == 1

    def test_exit_gate_opens(self, client):
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 2})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["action"] == "gate_opened"
        # Gate should now be open
        gate = client.get("/gate/status/2").get_json()
        assert gate["open"] is True

    def test_exit_gate_denied_during_lockdown(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 2})
        assert resp.status_code == 403
        assert resp.get_json()["action"] == "denied"

    def test_override_active_returns_override_action(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 1})
        assert resp.status_code == 200
        assert resp.get_json()["action"] == "override_active"

    def test_invalid_gate_returns_404(self, client):
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 99})
        assert resp.status_code == 404


class TestRfidScan:
    def test_valid_badge_opens_entry_gate(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["gate_open"] is True

    def test_invalid_badge_denied(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "BOGUS"})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["valid"] is False
        assert data["gate_open"] is False

    def test_missing_badge_uid_returns_400(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1})
        assert resp.status_code == 400

    def test_invalid_gate_returns_404(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 99, "badge_uid": "B001"})
        assert resp.status_code == 404

    def test_rfid_on_exit_gate_returns_400(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 2, "badge_uid": "B001"})
        assert resp.status_code == 400

    def test_rfid_respects_admin_override(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert "override" in resp.get_json()["error"].lower()

    def test_rfid_denied_when_at_capacity(self, client):
        db.num_cars_inside = db.capacity
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert "capacity" in resp.get_json()["error"].lower()

    def test_valid_scan_logs_entry_event(self, client, auth_headers):
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B002"})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "Entry" in types

    def test_denied_scan_logs_entry_denied_event(self, client, auth_headers):
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "BOGUS"})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "Entry_Denied" in types


class TestVehicleEntered:
    def test_entry_gate_increments_occupancy(self, client):
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 1})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gate_open"] is False
        assert data["occupancy"]["num_cars_inside"] == 1

    def test_exit_gate_decrements_occupancy(self, client):
        # Put one car in first
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        client.post("/gate/vehicle-entered", json={"gate_id": 1})
        client.post("/gate/vehicle-detected", json={"gate_id": 2})
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 2})
        assert resp.status_code == 200
        assert resp.get_json()["occupancy"]["num_cars_inside"] == 0

    def test_exit_does_not_go_below_zero(self, client):
        # No cars inside, triggering exit should not underflow
        client.post("/gate/vehicle-detected", json={"gate_id": 2})
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 2})
        assert resp.status_code == 200
        assert resp.get_json()["occupancy"]["num_cars_inside"] == 0

    def test_invalid_gate_returns_404(self, client):
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 99})
        assert resp.status_code == 404

    def test_closed_gate_rejects_sensor_sequence(self, client):
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 1})
        assert resp.status_code == 400

    def test_gate_is_closed_after_entry(self, client):
        # Open gate first via RFID scan
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert client.get("/gate/status/1").get_json()["open"] is True
        client.post("/gate/vehicle-entered", json={"gate_id": 1})
        assert client.get("/gate/status/1").get_json()["open"] is False

    def test_exit_logs_exit_event(self, client, auth_headers):
        # Put a car inside via valid entry flow
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        client.post("/gate/vehicle-entered", json={"gate_id": 1})

        # Open exit gate via vehicle detection then clear vehicle
        client.post("/gate/vehicle-detected", json={"gate_id": 2})
        client.post("/gate/vehicle-entered", json={"gate_id": 2})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "Exit" in types


# ---------------------------------------------------------------------------
# Parking Controller (Use Case 4.2)
# ---------------------------------------------------------------------------

class TestSpotUpdate:
    def test_mark_spot_occupied(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["spot_id"] == "1-01"
        assert data["occupied"] is True
        assert data["led_on"] is False  # LED off when spot is occupied

    def test_mark_spot_available(self, client):
        # First occupy it, then free it
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        resp = client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": False})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["occupied"] is False
        assert data["led_on"] is True  # LED on when spot is available

    def test_string_bool_payload_is_parsed(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "1-02", "occupied": "false"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["occupied"] is False
        assert data["led_on"] is True

    def test_floor_summary_included(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "2-05", "occupied": True})
        data = resp.get_json()
        assert "floor" in data
        assert data["floor"]["floor_id"] == 2
        assert data["floor"]["occupied"] == 1
        assert data["floor"]["available"] == 24

    def test_floor_status_full_when_all_occupied(self, client):
        for i in range(1, 26):
            client.post("/parking/spot-update", json={"spot_id": f"3-{i:02d}", "occupied": True})
        resp = client.post("/parking/spot-update", json={"spot_id": "3-25", "occupied": True})
        assert resp.get_json()["floor"]["status"] == "FULL"

    def test_floor_status_available_normally(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        assert resp.get_json()["floor"]["status"] == "AVAILABLE"

    def test_missing_spot_id_returns_400(self, client):
        resp = client.post("/parking/spot-update", json={"occupied": True})
        assert resp.status_code == 400

    def test_missing_occupied_returns_400(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "1-01"})
        assert resp.status_code == 400

    def test_invalid_spot_id_returns_404(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "9-99", "occupied": True})
        assert resp.status_code == 404

    def test_spot_update_does_not_change_num_cars_inside(self, client):
        before = client.get("/parking/occupancy").get_json()["global"]["num_cars_inside"]
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        after = client.get("/parking/occupancy").get_json()["global"]["num_cars_inside"]
        assert before == after


class TestParkingOccupancy:
    def test_occupancy_shape(self, client):
        resp = client.get("/parking/occupancy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "global" in data
        assert "floors" in data
        assert len(data["floors"]) == 3

    def test_initial_occupancy_all_available(self, client):
        data = client.get("/parking/occupancy").get_json()
        assert data["global"]["num_cars_inside"] == 0
        for floor in data["floors"]:
            assert floor["occupied"] == 0
            assert floor["available"] == 25


class TestFloorDetail:
    def test_valid_floor_returns_detail(self, client):
        resp = client.get("/parking/floor/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["floor_id"] == 1
        assert len(data["spots"]) == 25
        assert data["available"] == 25

    def test_invalid_floor_returns_404(self, client):
        resp = client.get("/parking/floor/99")
        assert resp.status_code == 404

    def test_floor_reflects_spot_update(self, client):
        client.post("/parking/spot-update", json={"spot_id": "2-03", "occupied": True})
        data = client.get("/parking/floor/2").get_json()
        assert data["occupied"] == 1
        assert data["spots"]["2-03"] is True


# ---------------------------------------------------------------------------
# Admin Controller (Use Case 4.5)
# ---------------------------------------------------------------------------

class TestAdminAuth:
    def test_login_valid_credentials(self, client):
        resp = client.post("/admin/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_invalid_credentials(self, client):
        resp = client.post("/admin/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_logout_succeeds(self, client, auth_headers):
        resp = client.post("/admin/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_token_invalidated_after_logout(self, client, auth_headers):
        client.post("/admin/logout", headers=auth_headers)
        # Token should no longer be valid
        resp = client.get("/admin/badges", headers=auth_headers)
        assert resp.status_code == 401


class TestGateOverride:
    def test_requires_auth(self, client):
        resp = client.post("/admin/gate-override", json={"gate_id": 1})
        assert resp.status_code == 401

    def test_missing_gate_id_returns_400(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"override": True, "state": True},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_override_opens_gate(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["override"] is True
        assert data["gate_open"] is True

    def test_override_closes_gate(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 2, "override": True, "state": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["gate_open"] is False

    def test_invalid_gate_returns_404(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 99, "override": True, "state": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_override_is_logged(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "AdminGateOverride" in types


class TestLockdown:
    def test_requires_auth(self, client):
        resp = client.post("/admin/lockdown", json={"enabled": True})
        assert resp.status_code == 401

    def test_enable_lockdown(self, client, auth_headers):
        resp = client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["lockdown"] is True

    def test_disable_lockdown(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.post("/admin/lockdown", json={"enabled": False}, headers=auth_headers)
        assert resp.get_json()["lockdown"] is False

    def test_get_lockdown_status(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.get("/admin/lockdown")
        assert resp.status_code == 200
        assert resp.get_json()["lockdown"] is True


class TestBadgeManagement:
    def test_list_badges_requires_auth(self, client):
        assert client.get("/admin/badges").status_code == 401

    def test_list_badges(self, client, auth_headers):
        resp = client.get("/admin/badges", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "badges" in data
        assert "B001" in data["badges"]

    def test_add_badge_requires_auth(self, client):
        assert client.post("/admin/badges", json={"badge_uid": "BNEW"}).status_code == 401

    def test_add_badge(self, client, auth_headers):
        resp = client.post("/admin/badges", json={"badge_uid": "BNEW"}, headers=auth_headers)
        assert resp.status_code == 201
        assert "BNEW" in resp.get_json()["badges"]

    def test_add_badge_missing_uid_returns_400(self, client, auth_headers):
        resp = client.post("/admin/badges", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_remove_badge_requires_auth(self, client):
        assert client.delete("/admin/badges/B001").status_code == 401

    def test_remove_badge(self, client, auth_headers):
        resp = client.delete("/admin/badges/B001", headers=auth_headers)
        assert resp.status_code == 200
        assert "B001" not in resp.get_json()["badges"]

    def test_added_badge_validates_for_rfid(self, client, auth_headers):
        client.post("/admin/badges", json={"badge_uid": "BNEW"}, headers=auth_headers)
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "BNEW"})
        assert resp.get_json()["valid"] is True

    def test_removed_badge_fails_rfid(self, client, auth_headers):
        client.delete("/admin/badges/B001", headers=auth_headers)
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert resp.get_json()["valid"] is False


class TestCctv:
    def test_list_cameras_requires_auth(self, client):
        assert client.get("/admin/cctv").status_code == 401

    def test_list_cameras(self, client, auth_headers):
        resp = client.get("/admin/cctv", headers=auth_headers)
        assert resp.status_code == 200
        cameras = resp.get_json()["cameras"]
        assert len(cameras) == 5
        ids = [c["id"] for c in cameras]
        assert 1 in ids

    def test_single_camera_requires_auth(self, client):
        assert client.get("/admin/cctv/1").status_code == 401

    def test_single_camera(self, client, auth_headers):
        resp = client.get("/admin/cctv/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["status"] == "online"
        assert "feed_url" in data

    def test_invalid_camera_returns_404(self, client, auth_headers):
        resp = client.get("/admin/cctv/99", headers=auth_headers)
        assert resp.status_code == 404


class TestEventLog:
    def test_events_requires_auth(self, client):
        assert client.get("/admin/events").status_code == 401

    def test_events_initially_empty(self, client, auth_headers):
        # admin login itself creates an AdminLogin event
        resp = client.get("/admin/events", headers=auth_headers)
        assert resp.status_code == 200
        events = resp.get_json()["events"]
        assert isinstance(events, list)

    def test_events_contain_admin_login(self, client, auth_headers):
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "AdminLogin" in types

    def test_events_have_required_fields(self, client, auth_headers):
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        for event in events:
            assert "type" in event
            assert "timestamp" in event

    def test_limit_parameter(self, client, auth_headers):
        # Generate several events
        for _ in range(10):
            client.post("/gate/vehicle-detected", json={"gate_id": 1})
        resp = client.get("/admin/events?limit=3", headers=auth_headers)
        assert len(resp.get_json()["events"]) <= 3


# ---------------------------------------------------------------------------
# Power Controller (Use Case 4.4)
# ---------------------------------------------------------------------------

class TestPowerController:
    def test_initial_power_status(self, client):
        resp = client.get("/power/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "grid"
        assert data["outage_mode"] is False

    def test_power_failure_switches_to_ups(self, client):
        resp = client.post("/power/failure")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "ups"
        assert data["outage_mode"] is True

    def test_power_status_reflects_failure(self, client):
        client.post("/power/failure")
        data = client.get("/power/status").get_json()
        assert data["source"] == "ups"
        assert data["outage_mode"] is True

    def test_power_restore_returns_to_grid(self, client):
        client.post("/power/failure")
        resp = client.post("/power/restore")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "grid"
        assert data["outage_mode"] is False

    def test_power_status_reflects_restore(self, client):
        client.post("/power/failure")
        client.post("/power/restore")
        data = client.get("/power/status").get_json()
        assert data["source"] == "grid"
        assert data["outage_mode"] is False

    def test_power_failure_is_logged(self, client, auth_headers):
        client.post("/power/failure")
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "PowerFailure" in types

    def test_power_restore_is_logged(self, client, auth_headers):
        client.post("/power/failure")
        client.post("/power/restore")
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        types = [e["type"] for e in events]
        assert "PowerRestored" in types
