"""
Gate Controller -- handles entry/exit gate lifecycle.

Implements use cases:
  4.1 Successful Entry (RFID scan -> validate -> open -> log -> close)
  4.3 Successful Exit  (detect -> check lockdown -> open -> log -> close)

Sensor-input endpoints (/vehicle-detected, /vehicle-entered) model real hardware
sensors: they execute the required business logic and return only {"success": true}
or an error code.  All resulting state changes are pushed to connected clients via
WebSocket events emitted by the database layer.

The /rfid-scan endpoint is a user action (badge presentation), so it
returns a meaningful result (valid/invalid) that the caller acts on directly.
"""

from flask import Blueprint, jsonify, request

from .database import db

gate_bp = Blueprint("gate", __name__, url_prefix="/gate")


@gate_bp.route("/status", methods=["GET"])
def gate_status():
    """Return current state of all gates."""
    return jsonify(db.get_all_gates())


@gate_bp.route("/status/<int:gate_id>", methods=["GET"])
def single_gate_status(gate_id):
    """Return state of a specific gate."""
    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404
    return jsonify({"gate_id": gate_id, **gate})


# ----- Use Case 4.1: Successful Entry -----

@gate_bp.route("/vehicle-detected", methods=["POST"])
def vehicle_detected():
    """
    isVehicleDetected(gateID)  — approach-lane sensor input.
    active=True  : vehicle is present at the lane.
    active=False : lane has cleared (vehicle backed away).

    Rising edge  → entry gate arms for RFID; exit gate opens (unless locked down/overridden).
    All resulting state changes are broadcast to clients via the WebSocket
    gate_update event — no state is returned in this response.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    active = bool(data.get("active", True))

    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    # Persist sensor state — WebSocket gate_update fires automatically
    db.set_approach_sensor(gate_id, active)

    if not active:
        # Falling edge: lane cleared — nothing else to do
        return jsonify({"success": True})

    # Rising edge: vehicle present — evaluate gate logic
    if gate["override"]:
        return jsonify({"success": True})

    if gate["type"] == "exit":
        # Use case 4.3 — exit flow
        if db.get_lockdown():
            return jsonify({"error": "Facility in lockdown; exit denied"}), 403
        db.set_gate_state(gate_id, True)
        db.log_event("Exit_VehicleDetected", gate_id=gate_id)
        return jsonify({"success": True})

    # Entry gate — controller now waits for RFID
    return jsonify({"success": True})


@gate_bp.route("/rfid-scan", methods=["POST"])
def rfid_scan():
    """
    readBadgeUID() + validateEmployee(UID)
    User action: badge presentation at the reader.
    Returns valid/invalid result — the UI acts on this directly.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    badge_uid = data.get("badge_uid")

    if not badge_uid:
        return jsonify({"error": "badge_uid required"}), 400

    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404
    if gate["type"] != "entry":
        return jsonify({"error": "RFID scan only applies to entry gates"}), 400

    if gate["override"]:
        return jsonify({"error": "Admin override is active; RFID entry suspended."}), 403

    occupancy = db.get_occupancy()
    if occupancy["num_cars_inside"] >= occupancy["capacity"]:
        return jsonify({"error": "Facility at capacity"}), 403

    valid = db.validate_badge(badge_uid)
    if valid:
        # setGateState(gateID, true)
        db.set_gate_state(gate_id, True)
        # logEvent("Entry", gateID, timestamp)
        db.log_event("Entry", gate_id=gate_id, details={"badge_uid": badge_uid})
        return jsonify({
            "gate_id": gate_id,
            "badge_uid": badge_uid,
            "valid": True,
            "gate_open": True,
        })
    else:
        db.log_event("Entry_Denied", gate_id=gate_id, details={"badge_uid": badge_uid})
        return jsonify({
            "gate_id": gate_id,
            "badge_uid": badge_uid,
            "valid": False,
            "gate_open": False,
        }), 403


@gate_bp.route("/vehicle-entered", methods=["POST"])
def vehicle_entered():
    """
    IR clearance-sensor input.
    active=True  : beam broken — vehicle is in the gate path.
    active=False : beam restored — vehicle has fully cleared.

    Falling edge triggers:
      - occupancy increment/decrement (→ occupancy_update WebSocket event)
      - approach sensor reset
      - gate close (unless held by admin override)

    No state is returned; all updates reach clients via WebSocket events.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    active = bool(data.get("active", True))

    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    # Persist sensor state — WebSocket gate_update fires automatically
    db.set_clearance_sensor(gate_id, active)

    if active:
        # Rising edge: vehicle entering the path — wait for it to clear
        return jsonify({"success": True})

    # Falling edge: vehicle has fully cleared the IR beam
    if not gate["open"] and not gate["override"]:
        return jsonify({"error": "Gate is closed; invalid sensor sequence"}), 400

    if gate["type"] == "entry":
        db.increment_cars()
    else:
        db.decrement_cars()
        db.log_event("Exit", gate_id=gate_id)

    # Approach sensor clears once the vehicle has moved on
    db.set_approach_sensor(gate_id, False)

    # Close gate behind the vehicle unless held by admin override
    if not gate["override"]:
        db.set_gate_state(gate_id, False)

    return jsonify({"success": True})