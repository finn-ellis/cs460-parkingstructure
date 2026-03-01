"""
Power Controller -- UPS / power failure simulation.

Implements use case:
  4.4 Emergency Power Failure
    (detect failure -> switch to UPS -> outage mode -> cut non-essential)
"""

from flask import Blueprint, jsonify, request
from .database import db

power_bp = Blueprint("power", __name__, url_prefix="/power")


@power_bp.route("/status", methods=["GET"])
def power_status():
    """getPowerSourceState() -- return current power state."""
    return jsonify(db.get_power_state())


@power_bp.route("/failure", methods=["POST"])
def power_failure():
    """
    Simulate a power failure.
    switchSource(sourceID) -- switches to UPS.
    setPowerCut(true)      -- cuts non-essential hardware.
    """
    db.set_power_source("ups")
    db.set_outage_mode(True)
    db.log_event("PowerFailure", details={"source": "ups", "outage_mode": True})
    return jsonify({
        "source": "ups",
        "outage_mode": True,
    })


@power_bp.route("/restore", methods=["POST"])
def power_restore():
    """Simulate power restoration back to grid."""
    db.set_power_source("grid")
    db.set_outage_mode(False)
    db.log_event("PowerRestored", details={"source": "grid", "outage_mode": False})
    return jsonify({
        "source": "grid",
        "outage_mode": False,
    })
