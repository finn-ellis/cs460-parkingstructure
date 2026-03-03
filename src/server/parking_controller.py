"""
Parking Availability Controller -- handles per-spot sensor updates and occupancy queries.

Structure: 3 floors, 25 spots per floor (75 total capacity).

Implements use case:
  4.2 Parking Spot Update (spot sensor -> update DB -> update floor sign)
"""

from flask import Blueprint, jsonify, request
from .database import db

parking_bp = Blueprint("parking", __name__, url_prefix="/parking")


@parking_bp.route("/spot-update", methods=["POST"])
def spot_update():
    """
    isSpotOccupied(spotID) + toggleSpotLED(spotID, state) + updateFloorSign(floorID, count, status)

    Sensor input: called when a parking spot sensor detects a state change.
    Updates the spot in the database; the DB layer emits floor_update via WebSocket.
    Note: this does NOT change num_cars_inside (per use case 4.2).
    Returns only {"success": true} — callers must not rely on this response for state.
    """
    data = request.get_json(force=True)
    spot_id = data.get("spot_id")
    occupied_raw = data.get("occupied")

    if spot_id is None or occupied_raw is None:
        return jsonify({"error": "spot_id and occupied are required"}), 400

    if isinstance(occupied_raw, str):
        occupied = occupied_raw.lower() in {"true", "1", "t", "y", "yes"}
    else:
        occupied = bool(occupied_raw)

    floor_id = db.set_spot(spot_id, occupied)
    if floor_id is None:
        return jsonify({"error": "Spot not found"}), 404

    db.log_event(
        "SpotUpdate",
        details={"spot_id": spot_id, "occupied": occupied, "floor_id": floor_id},
    )

    return jsonify({"success": True})


@parking_bp.route("/occupancy", methods=["GET"])
def occupancy():
    """Return global occupancy (cars inside) and per-floor breakdown."""
    return jsonify({
        "global": db.get_occupancy(),
        "floors": db.get_all_floors(),
    })


@parking_bp.route("/floor/<int:floor_id>", methods=["GET"])
def floor_detail(floor_id):
    """Return detailed spot map for a single floor."""
    floor_info = db.get_floor(floor_id)
    if floor_info is None:
        return jsonify({"error": "Floor not found"}), 404
    return jsonify(floor_info)
