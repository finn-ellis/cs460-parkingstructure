"""
Main Controller Server -- Flask application factory.

Registers all component blueprints and starts the local web server
for the parking structure demo.
"""

from flask import Flask, jsonify
from flask_cors import CORS

from .database import db
from .events import socketio
from .gate_controller import gate_bp
from .parking_controller import parking_bp
from .admin_controller import admin_bp
from .power_controller import power_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Attach SocketIO to the Flask app
    socketio.init_app(app)

    # Register component blueprints
    app.register_blueprint(gate_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(power_bp)

    # Health / root endpoint
    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "ParkingStructure Main Controller",
            "status": "running",
            "endpoints": [
                "/gate",
                "/parking",
                "/admin",
                "/power",
            ],
        })

    # Global system status
    @app.route("/status", methods=["GET"])
    def system_status():
        return jsonify({
            "occupancy": db.get_occupancy(),
            "gates": db.get_all_gates(),
            "power": db.get_power_state(),
            "lockdown": db.get_lockdown(),
        })

    return app


def main():
    app = create_app()
    # Use socketio.run so WebSocket upgrades are handled correctly.
    # allow_unsafe_werkzeug is required for the dev reloader to coexist
    # with simple-websocket WS upgrades.
    socketio.run(app, host="127.0.0.1", port=5000, debug=True,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
