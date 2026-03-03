"""
Admin Controller -- admin authentication, gate overrides, badge management, CCTV.

Implements use case:
  4.5 Admin Gate Override (login -> override gate -> log)
Also covers:
  - Badge CRUD
  - Simulated CCTV camera listing
  - Event log access
"""

import secrets
from flask import Blueprint, jsonify, request
from .database import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Simulated CCTV cameras
CAMERAS = {
    1: {"name": "Entry Gate", "location": "Level 0 - Entry"},
    2: {"name": "Exit Gate", "location": "Level 0 - Exit"},
    3: {"name": "Floor 1 East", "location": "Level 1"},
    4: {"name": "Floor 2 East", "location": "Level 2"},
    5: {"name": "Floor 3 East", "location": "Level 3"},
}


def _require_auth():
    """Check for a valid admin token in the Authorization header."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not db.verify_token(token):
        return False
    return True


# ---- Authentication ----

@admin_bp.route("/login", methods=["POST"])
def login():
    """
    login(username, password)
    Returns a bearer token on success.
    """
    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")

    if db.verify_admin(username, password):
        token = secrets.token_hex(16)
        db.add_token(token)
        db.log_event("AdminLogin", details={"username": username})
        return jsonify({"token": token})
    return jsonify({"error": "Invalid credentials"}), 401


@admin_bp.route("/logout", methods=["POST"])
def logout():
    """Invalidate the current admin token."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not db.verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401
    db.remove_token(token)
    return jsonify({"ok": True})


# ---- Gate Override (Use Case 4.5) ----

@admin_bp.route("/gate-override", methods=["POST"])
def gate_override():
    """
    enableGateOverride(gate, override_enabled, override_state)
    Bypasses standard RFID logic for a specific gate.
    """
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    override_enabled = data.get("override", True)
    override_state = data.get("state", True)

    if gate_id is None:
        return jsonify({"error": "gate_id required"}), 400

    ok = db.set_gate_override(gate_id, override_enabled, override_state)
    if not ok:
        return jsonify({"error": "Gate not found"}), 404

    db.log_event(
        "AdminGateOverride",
        gate_id=gate_id,
        details={"override": override_enabled, "state": override_state},
    )
    return jsonify({
        "gate_id": gate_id,
        "override": override_enabled,
        "gate_open": override_state if override_enabled else db.get_gate(gate_id)["open"],
    })


# ---- Lockdown toggle ----

@admin_bp.route("/lockdown", methods=["POST"])
def lockdown():
    """Toggle facility lockdown."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    enabled = data.get("enabled", True)
    db.set_lockdown(enabled)
    db.log_event("Lockdown", details={"enabled": db.get_lockdown()})
    return jsonify({"lockdown": db.get_lockdown()})


@admin_bp.route("/lockdown", methods=["GET"])
def lockdown_status():
    """Get current lockdown state."""
    return jsonify({"lockdown": db.get_lockdown()})


# ---- Badge management ----

@admin_bp.route("/badges", methods=["GET"])
def list_badges():
    """Return all authorized badge UIDs."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"badges": db.list_badges()})


@admin_bp.route("/badges", methods=["POST"])
def add_badge():
    """Add a new authorized badge UID."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    uid = data.get("badge_uid")
    if not uid:
        return jsonify({"error": "badge_uid required"}), 400
    db.add_badge(uid)
    db.log_event("BadgeAdded", details={"badge_uid": uid})
    return jsonify({"ok": True, "badges": db.list_badges()}), 201


@admin_bp.route("/badges/<uid>", methods=["DELETE"])
def remove_badge(uid):
    """Remove an authorized badge UID."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    db.remove_badge(uid)
    db.log_event("BadgeRemoved", details={"badge_uid": uid})
    return jsonify({"ok": True, "badges": db.list_badges()})


# ---- CCTV ----

@admin_bp.route("/cctv", methods=["GET"])
def cctv_list():
    """List available simulated CCTV cameras."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"cameras": [
        {"id": cid, **info} for cid, info in CAMERAS.items()
    ]})


@admin_bp.route("/cctv/<int:camera_id>", methods=["GET"])
def cctv_feed(camera_id):
    """Return simulated feed info for a camera."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    cam = CAMERAS.get(camera_id)
    if cam is None:
        return jsonify({"error": "Camera not found"}), 404
    return jsonify({
        "id": camera_id,
        **cam,
        "status": "online",
        "feed_url": f"/static/cctv_placeholder_{camera_id}.jpg",
    })


# ---- Event log ----

@admin_bp.route("/events", methods=["GET"])
def events():
    """Return recent event log entries."""
    if not _require_auth():
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", 50, type=int)
    return jsonify({"events": db.get_events(limit)})
