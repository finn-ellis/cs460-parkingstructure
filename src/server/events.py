"""
SocketIO singleton -- shared across the application.

Imported by app.py (to init with the Flask app) and by any module
that needs to emit real-time state updates to connected clients.

Events emitted:
  gate_update      – { gate_id, open, approach_sensor, clearance_sensor,
                       override, override_state, type }
  occupancy_update – { num_cars_inside, capacity, percentage }
  floor_update     – { floor_id, spots, occupied, available, total }
  power_update     – { source, outage_mode }
  lockdown_update  – { active }
"""

from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
