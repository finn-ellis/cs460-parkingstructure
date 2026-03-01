"""
Gate Controller -- handles entry/exit gate lifecycle.

Implements use cases:
  4.1 Successful Entry (RFID scan -> validate -> open -> log -> close)
  4.3 Successful Exit  (detect -> check lockdown -> open -> log -> close)
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
    isVehicleDetected(gateID)
    Called when the entry/exit gate sensor detects a vehicle.
    For exit gates (and no lockdown), automatically opens the gate.
    For entry gates, returns waiting-for-rfid so the frontend can prompt a scan.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    # If gate has admin override active, follow override state
    if gate["override"]:
        return jsonify({
            "gate_id": gate_id,
            "action": "override_active",
            "gate_open": gate["open"],
        })

    if gate["type"] == "exit":
        # Use case 4.3 -- exit flow
        if db.lockdown:
            return jsonify({"gate_id": gate_id, "action": "denied", "reason": "lockdown"}), 403
        db.set_gate_state(gate_id, True)
        db.log_event("Exit_VehicleDetected", gate_id=gate_id)
        return jsonify({"gate_id": gate_id, "action": "gate_opened"})

    # Entry gate -- wait for RFID
    return jsonify({"gate_id": gate_id, "action": "awaiting_rfid"})


@gate_bp.route("/rfid-scan", methods=["POST"])
def rfid_scan():
    """
    readBadgeUID() + validateEmployee(UID)
    Receives a badge UID, validates it, and opens the entry gate on success.
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
    Called after the vehicle has passed through the entry gate.
    Increments global occupancy and closes the gate.
    (isPathBlocked() is simulated by the frontend triggering this endpoint.)
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    if not gate["open"] and not gate["override"]:
        return jsonify({"error": "Gate is closed; invalid sensor sequence"}), 400

    if gate["type"] == "entry":
        count = db.increment_cars()
    else:
        # For exit: decrement
        count = db.decrement_cars()
        db.log_event("Exit", gate_id=gate_id)

    # Close gate behind the vehicle unless held by admin override
    if not gate["override"]:
        db.set_gate_state(gate_id, False)

    updated_gate = db.get_gate(gate_id)

    occupancy = db.get_occupancy()
    return jsonify({
        "gate_id": gate_id,
        "gate_open": updated_gate["open"],
        "occupancy": occupancy,
    })
