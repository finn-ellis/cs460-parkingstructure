"""
Black-box API tests for the ParkingStructure server.

Every test interacts with the server exclusively through HTTP API calls.
No direct imports from the backend are used in this file.

Covers:
  - App root and global status endpoints
  - Gate Controller (use cases 4.1 Successful Entry, 4.3 Successful Exit)
  - Parking Controller (use case 4.2 Parking Spot Update)
  - Admin Controller (use case 4.5 Admin Gate Override, badge CRUD, CCTV, events)
  - Power Controller (use case 4.4 Emergency Power Failure)
"""


# ---------------------------------------------------------------------------
# Helpers — multi-step sensor flows executed entirely through the API
# ---------------------------------------------------------------------------

def _enter_vehicle(client, badge_uid="B001"):
    """Drive one car through the complete entry sequence (gate 1).

    1. Approach sensor fires  (vehicle-detected)
    2. Driver presents badge  (rfid-scan)
    3. IR beam breaks          (vehicle-entered active=True)
    4. IR beam restores        (vehicle-entered active=False → occupancy++)
    """
    client.post("/gate/vehicle-detected", json={"gate_id": 1})
    client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": badge_uid})
    client.post("/gate/vehicle-entered", json={"gate_id": 1, "active": True})
    client.post("/gate/vehicle-entered", json={"gate_id": 1, "active": False})


def _exit_vehicle(client):
    """Drive one car through the complete exit sequence (gate 2).

    1. Approach sensor fires  (vehicle-detected → gate opens)
    2. IR beam breaks          (vehicle-entered active=True)
    3. IR beam restores        (vehicle-entered active=False → occupancy--)
    """
    client.post("/gate/vehicle-detected", json={"gate_id": 2})
    client.post("/gate/vehicle-entered", json={"gate_id": 2, "active": True})
    client.post("/gate/vehicle-entered", json={"gate_id": 2, "active": False})


def _login(client):
    """Log in as admin and return an Authorization header dict."""
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


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
        for key in ("occupancy", "gates", "power", "lockdown"):
            assert key in data

    def test_status_initial_values(self, client):
        data = client.get("/status").get_json()
        assert data["occupancy"]["num_cars_inside"] == 0
        assert data["occupancy"]["capacity"] == 75
        assert data["lockdown"] is False
        assert data["power"]["source"] == "grid"
        assert data["power"]["outage_mode"] is False


# ---------------------------------------------------------------------------
# Gate Controller — status queries
# ---------------------------------------------------------------------------

class TestGateStatus:
    def test_all_gates_returned(self, client):
        data = client.get("/gate/status").get_json()
        assert "1" in data
        assert "2" in data

    def test_single_gate_entry(self, client):
        data = client.get("/gate/status/1").get_json()
        assert data["gate_id"] == 1
        assert data["type"] == "entry"
        assert data["open"] is False

    def test_single_gate_exit(self, client):
        data = client.get("/gate/status/2").get_json()
        assert data["gate_id"] == 2
        assert data["type"] == "exit"

    def test_invalid_gate_returns_404(self, client):
        assert client.get("/gate/status/99").status_code == 404


# ---------------------------------------------------------------------------
# Gate Controller — Use Case 4.1: Successful Entry
# ---------------------------------------------------------------------------

class TestEntryFlow:
    """Full entry-gate lifecycle tested through the HTTP API."""

    def test_vehicle_detected_returns_success(self, client):
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 1})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_vehicle_detected_sets_approach_sensor(self, client):
        client.post("/gate/vehicle-detected", json={"gate_id": 1})
        gate = client.get("/gate/status/1").get_json()
        assert gate["approach_sensor"] is True

    def test_entry_gate_stays_closed_after_detect(self, client):
        """Entry gate awaits RFID — should NOT open on detect alone."""
        client.post("/gate/vehicle-detected", json={"gate_id": 1})
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is False

    def test_rfid_valid_opens_gate(self, client):
        client.post("/gate/vehicle-detected", json={"gate_id": 1})
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["gate_open"] is True
        # Verify via status endpoint
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is True

    def test_rfid_invalid_badge_denied(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "INVALID"})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["valid"] is False
        assert data["gate_open"] is False

    def test_rfid_missing_badge_uid(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1})
        assert resp.status_code == 400

    def test_rfid_on_exit_gate_rejected(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 2, "badge_uid": "B001"})
        assert resp.status_code == 400

    def test_rfid_invalid_gate(self, client):
        resp = client.post("/gate/rfid-scan", json={"gate_id": 99, "badge_uid": "B001"})
        assert resp.status_code == 404

    def test_full_entry_increments_occupancy(self, client):
        _enter_vehicle(client)
        occ = client.get("/status").get_json()["occupancy"]
        assert occ["num_cars_inside"] == 1

    def test_gate_closes_after_entry(self, client):
        _enter_vehicle(client)
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is False
        assert gate["approach_sensor"] is False

    def test_multiple_entries(self, client):
        for _ in range(5):
            _enter_vehicle(client)
        assert client.get("/status").get_json()["occupancy"]["num_cars_inside"] == 5

    def test_invalid_gate_vehicle_detected(self, client):
        assert client.post("/gate/vehicle-detected", json={"gate_id": 99}).status_code == 404

    def test_vehicle_detected_falling_edge(self, client):
        """active=False means vehicle left approach lane — sensor clears."""
        client.post("/gate/vehicle-detected", json={"gate_id": 1, "active": True})
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 1, "active": False})
        assert resp.status_code == 200
        gate = client.get("/gate/status/1").get_json()
        assert gate["approach_sensor"] is False

    def test_valid_scan_logs_entry_event(self, client, auth_headers):
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B002"})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "Entry" in [e["type"] for e in events]

    def test_denied_scan_logs_entry_denied_event(self, client, auth_headers):
        client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "BOGUS"})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "Entry_Denied" in [e["type"] for e in events]


# ---------------------------------------------------------------------------
# Gate Controller — Use Case 4.3: Successful Exit
# ---------------------------------------------------------------------------

class TestExitFlow:
    """Full exit-gate lifecycle tested through the HTTP API."""

    def test_exit_detect_opens_gate(self, client):
        """Exit gate opens immediately on vehicle detection (no RFID needed)."""
        client.post("/gate/vehicle-detected", json={"gate_id": 2})
        gate = client.get("/gate/status/2").get_json()
        assert gate["open"] is True

    def test_full_exit_decrements_occupancy(self, client):
        _enter_vehicle(client)
        assert client.get("/status").get_json()["occupancy"]["num_cars_inside"] == 1
        _exit_vehicle(client)
        assert client.get("/status").get_json()["occupancy"]["num_cars_inside"] == 0

    def test_exit_gate_closes_after_clearance(self, client):
        _enter_vehicle(client)
        _exit_vehicle(client)
        gate = client.get("/gate/status/2").get_json()
        assert gate["open"] is False
        assert gate["approach_sensor"] is False

    def test_occupancy_does_not_go_negative(self, client):
        """Exiting with 0 cars should leave occupancy at 0."""
        _exit_vehicle(client)
        assert client.get("/status").get_json()["occupancy"]["num_cars_inside"] == 0

    def test_exit_denied_during_lockdown(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 2})
        assert resp.status_code == 403

    def test_invalid_gate_vehicle_entered(self, client):
        assert client.post("/gate/vehicle-entered", json={"gate_id": 99}).status_code == 404

    def test_closed_gate_rejects_vehicle_entered(self, client):
        """IR sensor firing on a closed gate is an invalid sequence."""
        resp = client.post("/gate/vehicle-entered", json={"gate_id": 1, "active": False})
        assert resp.status_code == 400

    def test_exit_logs_event(self, client, auth_headers):
        _enter_vehicle(client)
        _exit_vehicle(client)
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "Exit" in [e["type"] for e in events]


# ---------------------------------------------------------------------------
# Gate Controller — capacity limit
# ---------------------------------------------------------------------------

class TestCapacity:
    def test_rfid_denied_at_capacity(self, client):
        """When the facility is full, RFID scan returns 403."""
        for _ in range(75):
            _enter_vehicle(client)
        occ = client.get("/status").get_json()["occupancy"]
        assert occ["num_cars_inside"] == 75
        assert occ["capacity"] == 75
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert "capacity" in resp.get_json()["error"].lower()

    def test_occupancy_percentage(self, client):
        _enter_vehicle(client)
        pct = client.get("/parking/occupancy").get_json()["global"]["percentage"]
        assert pct > 0


# ---------------------------------------------------------------------------
# Gate Controller — override interaction
# ---------------------------------------------------------------------------

class TestGateOverrideInteraction:
    """Verify that admin override affects gate sensor logic."""

    def test_override_blocks_rfid(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert "override" in resp.get_json()["error"].lower()

    def test_override_holds_gate_open_after_vehicle_clears(self, client, auth_headers):
        """Gate held open by override should not close when vehicle clears."""
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        client.post("/gate/vehicle-entered", json={"gate_id": 1, "active": True})
        client.post("/gate/vehicle-entered", json={"gate_id": 1, "active": False})
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is True

    def test_override_vehicle_detected_returns_success(self, client, auth_headers):
        """Vehicle detected while override is active still succeeds."""
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 1})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Parking Controller — Use Case 4.2: Spot Update
# ---------------------------------------------------------------------------

class TestSpotUpdate:
    def test_spot_update_returns_success(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_spot_update_reflected_in_floor(self, client):
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        floor = client.get("/parking/floor/1").get_json()
        assert floor["spots"]["1-01"] is True
        assert floor["occupied"] == 1
        assert floor["available"] == 24

    def test_spot_vacate(self, client):
        client.post("/parking/spot-update", json={"spot_id": "2-05", "occupied": True})
        client.post("/parking/spot-update", json={"spot_id": "2-05", "occupied": False})
        floor = client.get("/parking/floor/2").get_json()
        assert floor["spots"]["2-05"] is False
        assert floor["occupied"] == 0

    def test_string_bool_payload_is_parsed(self, client):
        client.post("/parking/spot-update", json={"spot_id": "1-02", "occupied": "true"})
        floor = client.get("/parking/floor/1").get_json()
        assert floor["spots"]["1-02"] is True

    def test_spot_update_does_not_change_occupancy(self, client):
        """Spot sensor != gate occupancy counter (per use case 4.2 spec)."""
        before = client.get("/status").get_json()["occupancy"]["num_cars_inside"]
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        after = client.get("/status").get_json()["occupancy"]["num_cars_inside"]
        assert before == after

    def test_all_spots_occupied_on_floor(self, client):
        for i in range(1, 26):
            client.post("/parking/spot-update", json={"spot_id": f"3-{i:02d}", "occupied": True})
        floor = client.get("/parking/floor/3").get_json()
        assert floor["available"] == 0
        assert floor["occupied"] == 25

    def test_unknown_spot_returns_404(self, client):
        resp = client.post("/parking/spot-update", json={"spot_id": "X-99", "occupied": True})
        assert resp.status_code == 404

    def test_missing_fields_returns_400(self, client):
        assert client.post("/parking/spot-update", json={"spot_id": "1-01"}).status_code == 400
        assert client.post("/parking/spot-update", json={"occupied": True}).status_code == 400

    def test_spot_update_logs_event(self, client, auth_headers):
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "SpotUpdate" in [e["type"] for e in events]


# ---------------------------------------------------------------------------
# Parking Controller — occupancy & floor queries
# ---------------------------------------------------------------------------

class TestParkingOccupancy:
    def test_occupancy_shape(self, client):
        data = client.get("/parking/occupancy").get_json()
        assert "global" in data
        assert "floors" in data
        assert len(data["floors"]) == 3

    def test_initial_occupancy_all_available(self, client):
        data = client.get("/parking/occupancy").get_json()
        assert data["global"]["num_cars_inside"] == 0
        for floor in data["floors"]:
            assert floor["occupied"] == 0
            assert floor["available"] == 25

    def test_floor_detail(self, client):
        data = client.get("/parking/floor/1").get_json()
        assert data["floor_id"] == 1
        assert data["total"] == 25
        assert data["occupied"] == 0
        assert data["available"] == 25

    def test_invalid_floor_returns_404(self, client):
        assert client.get("/parking/floor/99").status_code == 404

    def test_floor_reflects_spot_update(self, client):
        client.post("/parking/spot-update", json={"spot_id": "2-03", "occupied": True})
        data = client.get("/parking/floor/2").get_json()
        assert data["occupied"] == 1
        assert data["spots"]["2-03"] is True


# ---------------------------------------------------------------------------
# Admin Controller — authentication
# ---------------------------------------------------------------------------

class TestAdminAuth:
    def test_login_success(self, client):
        resp = client.post("/admin/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_failure(self, client):
        resp = client.post("/admin/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_logout(self, client, auth_headers):
        resp = client.post("/admin/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_token_invalidated_after_logout(self, client, auth_headers):
        client.post("/admin/logout", headers=auth_headers)
        resp = client.get("/admin/badges", headers=auth_headers)
        assert resp.status_code == 401

    def test_protected_endpoint_without_auth(self, client):
        assert client.get("/admin/badges").status_code == 401

    def test_protected_endpoint_with_bad_token(self, client):
        resp = client.get("/admin/badges", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin Controller — Use Case 4.5: Gate Override
# ---------------------------------------------------------------------------

class TestGateOverride:
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
        # Verify via status
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is True
        assert gate["override"] is True

    def test_override_closes_gate(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": False},
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["gate_open"] is False
        gate = client.get("/gate/status/1").get_json()
        assert gate["open"] is False

    def test_disable_override(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": False},
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["override"] is False
        gate = client.get("/gate/status/1").get_json()
        assert gate["override"] is False
        assert gate["open"] is False  # defaults to closed when override is removed

    def test_override_requires_auth(self, client):
        resp = client.post("/admin/gate-override", json={"gate_id": 1})
        assert resp.status_code == 401

    def test_override_invalid_gate(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"gate_id": 99, "override": True, "state": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_override_missing_gate_id(self, client, auth_headers):
        resp = client.post(
            "/admin/gate-override",
            json={"override": True, "state": True},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_override_is_logged(self, client, auth_headers):
        client.post(
            "/admin/gate-override",
            json={"gate_id": 1, "override": True, "state": True},
            headers=auth_headers,
        )
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "AdminGateOverride" in [e["type"] for e in events]


# ---------------------------------------------------------------------------
# Admin Controller — lockdown
# ---------------------------------------------------------------------------

class TestLockdown:
    def test_enable_lockdown(self, client, auth_headers):
        resp = client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["lockdown"] is True

    def test_disable_lockdown(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.post("/admin/lockdown", json={"enabled": False}, headers=auth_headers)
        assert resp.get_json()["lockdown"] is False

    def test_lockdown_status_endpoint(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        data = client.get("/admin/lockdown").get_json()
        assert data["lockdown"] is True

    def test_lockdown_reflected_in_system_status(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        data = client.get("/status").get_json()
        assert data["lockdown"] is True

    def test_lockdown_requires_auth(self, client):
        resp = client.post("/admin/lockdown", json={"enabled": True})
        assert resp.status_code == 401

    def test_lockdown_blocks_exit(self, client, auth_headers):
        client.post("/admin/lockdown", json={"enabled": True}, headers=auth_headers)
        resp = client.post("/gate/vehicle-detected", json={"gate_id": 2})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin Controller — badge management
# ---------------------------------------------------------------------------

class TestBadgeManagement:
    def test_list_badges(self, client, auth_headers):
        resp = client.get("/admin/badges", headers=auth_headers)
        assert resp.status_code == 200
        assert "B001" in resp.get_json()["badges"]

    def test_add_badge(self, client, auth_headers):
        resp = client.post("/admin/badges", json={"badge_uid": "NEW01"}, headers=auth_headers)
        assert resp.status_code == 201
        assert "NEW01" in resp.get_json()["badges"]

    def test_add_badge_then_use_for_entry(self, client, auth_headers):
        client.post("/admin/badges", json={"badge_uid": "TEMP1"}, headers=auth_headers)
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "TEMP1"})
        assert resp.status_code == 200
        assert resp.get_json()["valid"] is True

    def test_remove_badge(self, client, auth_headers):
        resp = client.delete("/admin/badges/B005", headers=auth_headers)
        assert resp.status_code == 200
        assert "B005" not in resp.get_json()["badges"]

    def test_removed_badge_denied_at_gate(self, client, auth_headers):
        client.delete("/admin/badges/B001", headers=auth_headers)
        resp = client.post("/gate/rfid-scan", json={"gate_id": 1, "badge_uid": "B001"})
        assert resp.status_code == 403
        assert resp.get_json()["valid"] is False

    def test_add_badge_missing_uid(self, client, auth_headers):
        resp = client.post("/admin/badges", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_badge_endpoints_require_auth(self, client):
        assert client.get("/admin/badges").status_code == 401
        assert client.post("/admin/badges", json={"badge_uid": "X"}).status_code == 401
        assert client.delete("/admin/badges/B001").status_code == 401


# ---------------------------------------------------------------------------
# Admin Controller — CCTV
# ---------------------------------------------------------------------------

class TestCctv:
    def test_list_cameras(self, client, auth_headers):
        resp = client.get("/admin/cctv", headers=auth_headers)
        assert resp.status_code == 200
        cameras = resp.get_json()["cameras"]
        assert len(cameras) == 5
        assert cameras[0]["id"] == 1

    def test_single_camera(self, client, auth_headers):
        resp = client.get("/admin/cctv/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["status"] == "online"
        assert "feed_url" in data

    def test_camera_not_found(self, client, auth_headers):
        assert client.get("/admin/cctv/99", headers=auth_headers).status_code == 404

    def test_cctv_requires_auth(self, client):
        assert client.get("/admin/cctv").status_code == 401
        assert client.get("/admin/cctv/1").status_code == 401


# ---------------------------------------------------------------------------
# Admin Controller — event log
# ---------------------------------------------------------------------------

class TestEventLog:
    def test_events_require_auth(self, client):
        assert client.get("/admin/events").status_code == 401

    def test_login_creates_event(self, client, auth_headers):
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "AdminLogin" in [e["type"] for e in events]

    def test_entry_creates_event(self, client, auth_headers):
        _enter_vehicle(client)
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "Entry" in [e["type"] for e in events]

    def test_exit_creates_event(self, client, auth_headers):
        _enter_vehicle(client)
        _exit_vehicle(client)
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "Exit" in [e["type"] for e in events]

    def test_spot_update_creates_event(self, client, auth_headers):
        client.post("/parking/spot-update", json={"spot_id": "1-01", "occupied": True})
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "SpotUpdate" in [e["type"] for e in events]

    def test_events_have_required_fields(self, client, auth_headers):
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        for event in events:
            assert "type" in event
            assert "timestamp" in event

    def test_events_limit_parameter(self, client, auth_headers):
        for _ in range(5):
            _enter_vehicle(client)
        events = client.get("/admin/events?limit=2", headers=auth_headers).get_json()["events"]
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Power Controller — Use Case 4.4: Emergency Power Failure
# ---------------------------------------------------------------------------

class TestPowerController:
    def test_initial_power_state(self, client):
        data = client.get("/power/status").get_json()
        assert data["source"] == "grid"
        assert data["outage_mode"] is False

    def test_power_failure(self, client):
        resp = client.post("/power/failure")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        # Verify via GET
        data = client.get("/power/status").get_json()
        assert data["source"] == "ups"
        assert data["outage_mode"] is True

    def test_power_restore(self, client):
        client.post("/power/failure")
        resp = client.post("/power/restore")
        assert resp.status_code == 200
        data = client.get("/power/status").get_json()
        assert data["source"] == "grid"
        assert data["outage_mode"] is False

    def test_power_reflected_in_system_status(self, client):
        client.post("/power/failure")
        data = client.get("/status").get_json()
        assert data["power"]["source"] == "ups"
        assert data["power"]["outage_mode"] is True

    def test_power_failure_creates_event(self, client, auth_headers):
        client.post("/power/failure")
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "PowerFailure" in [e["type"] for e in events]

    def test_power_restore_creates_event(self, client, auth_headers):
        client.post("/power/failure")
        client.post("/power/restore")
        events = client.get("/admin/events", headers=auth_headers).get_json()["events"]
        assert "PowerRestored" in [e["type"] for e in events]
