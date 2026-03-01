"""
Gate Controller -- handles entry/exit gate lifecycle.

Implements use cases:
  4.1 Successful Entry (RFID scan -> validate -> open -> log -> close)
  4.3 Successful Exit  (detect -> check lockdown -> open -> log -> close)
"""

import json
import queue

from flask import Blueprint, Response, jsonify, request, stream_with_context

from .database import db

gate_bp = Blueprint("gate", __name__, url_prefix="/gate")


@gate_bp.route("/status", methods=["GET"])
def gate_status():
    """Return current state of all gates."""
    return jsonify(db.get_all_gates())


@gate_bp.route("/stream", methods=["GET"])
def gate_stream():
    """
    SSE stream — pushes gate state to all connected clients whenever
    setGateState() or enableGateOverride() is called by any controller.

    Models the real-world feedback channel: after the main controller
    commands a gate actuator, the position sensor confirms the new state
    and broadcasts it to all displays in the facility.
    """
    @stream_with_context
    def event_stream():
        q = db.subscribe_gate_events()
        # Send current state of both gates immediately on connect
        for gate_id, gate_data in db.get_all_gates().items():
            yield f"data: {json.dumps({'gate_id': gate_id, **gate_data})}\n\n"
        try:
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield f"data: {json.dumps(payload)}\n\n"
                except queue.Empty:
                    # Heartbeat keeps the connection alive through proxies
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            db.unsubscribe_gate_events(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
    Approach-lane sensor input.  active=True means a vehicle is present;
    active=False means the lane cleared (vehicle backed away).

    Rising edge  → entry gate prompts RFID; exit gate opens (if no lockdown/override).
    Sensor state is persisted in the database so the SSE stream reflects it
    on all connected displays — the same way a real facility controller would
    broadcast actuator state after receiving a sensor signal.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    active = bool(data.get("active", True))   # sensor toggle: True = vehicle present

    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    # Persist sensor state — SSE notifies all connected displays
    db.set_approach_sensor(gate_id, active)

    if not active:
        # Falling edge: vehicle backed away — no gate action needed
        return jsonify({"gate_id": gate_id, "action": "sensor_cleared"})

    # Rising edge: vehicle present — evaluate gate logic
    if gate["override"]:
        return jsonify({
            "gate_id": gate_id,
            "action": "override_active",
            "gate_open": gate["open"],
        })

    if gate["type"] == "exit":
        # Use case 4.3 — exit flow
        if db.lockdown:
            return jsonify({"gate_id": gate_id, "action": "denied", "reason": "lockdown"}), 403
        db.set_gate_state(gate_id, True)
        db.log_event("Exit_VehicleDetected", gate_id=gate_id)
        return jsonify({"gate_id": gate_id, "action": "gate_opened"})

    # Entry gate — wait for RFID
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
    IR clearance-sensor input.  active=True means the vehicle is currently
    breaking the beam (in the gate path); active=False means the beam has
    restored (vehicle fully cleared — isPathBlocked() returned False).

    Falling edge (active=False) is the trigger for:
      - occupancy increment/decrement
      - approach sensor reset (vehicle has moved on)
      - gate close (unless held by admin override)

    Storing the sensor state lets the SSE stream reflect it on all displays.
    """
    data = request.get_json(force=True)
    gate_id = data.get("gate_id")
    active = bool(data.get("active", True))   # sensor toggle: True = beam broken

    gate = db.get_gate(gate_id)
    if gate is None:
        return jsonify({"error": "Gate not found"}), 404

    # Persist sensor state — SSE notifies all connected displays
    db.set_clearance_sensor(gate_id, active)

    if active:
        # Rising edge: vehicle entering the path — wait for it to clear
        return jsonify({"gate_id": gate_id, "action": "vehicle_in_path"})

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

    updated_gate = db.get_gate(gate_id)
    occupancy = db.get_occupancy()
    return jsonify({
        "gate_id": gate_id,
        "gate_open": updated_gate["open"],
        "occupancy": occupancy,
    })
