"""
In-memory database for the parking structure demo.

Stores authorized badges, parking spot occupancy, gate states,
event logs, power state, and admin credentials.
All data is ephemeral -- resets on server restart.
"""

import threading
from datetime import datetime, timezone

from .events import socketio


class Database:
    def __init__(self):
        self._lock = threading.Lock()

        # --- Authorized badge UIDs ---
        self.badges = {"B001", "B002", "B003", "B004", "B005"}

        # --- Parking spots: floor_id -> {spot_id: occupied} ---
        # 3 floors, 25 spots each (75 total capacity)
        self.spots = {
            1: {f"1-{i:02d}": False for i in range(1, 26)},
            2: {f"2-{i:02d}": False for i in range(1, 26)},
            3: {f"3-{i:02d}": False for i in range(1, 26)},
        }
        self.capacity = sum(len(s) for s in self.spots.values())

        # --- Global occupancy (vehicles that entered through the gate) ---
        self.num_cars_inside = 0

        # --- Gates ---
        # gate 1 = entry, gate 2 = exit
        # approach_sensor : True while a vehicle is waiting at the approach lane
        # clearance_sensor: True while a vehicle is breaking the IR beam in the gate path
        self.gates = {
            1: {"type": "entry", "open": False, "override": False, "override_state": False,
                "approach_sensor": False, "clearance_sensor": False},
            2: {"type": "exit",  "open": False, "override": False, "override_state": False,
                "approach_sensor": False, "clearance_sensor": False},
        }

        # --- Event log ---
        self.event_log = []

        # --- Power state ---
        self.power = {
            "source": "grid",
            "outage_mode": False,
        }

        # --- System flags ---
        self.lockdown = False

        # --- Admin credentials (demo only) ---
        self.admin_username = "admin"
        self.admin_password = "admin"

        # --- Active admin session tokens ---
        self.admin_tokens = set()

    # ---- Badge helpers ----

    def validate_badge(self, uid):
        with self._lock:
            return uid in self.badges

    def add_badge(self, uid):
        with self._lock:
            self.badges.add(uid)

    def remove_badge(self, uid):
        with self._lock:
            self.badges.discard(uid)

    def list_badges(self):
        with self._lock:
            return sorted(self.badges)

    # ---- Gate helpers ----

    def get_gate(self, gate_id):
        with self._lock:
            gate = self.gates.get(gate_id)
            return dict(gate) if gate else None

    def set_gate_state(self, gate_id, is_open):
        with self._lock:
            if gate_id not in self.gates:
                return False
            self.gates[gate_id]["open"] = is_open
        # Notify outside the lock — models actuator position feedback signal
        self._notify_gate_listeners(gate_id)
        return True

    def set_gate_override(self, gate_id, override_enabled, override_state):
        with self._lock:
            if gate_id not in self.gates:
                return False
            self.gates[gate_id]["override"] = override_enabled
            self.gates[gate_id]["override_state"] = override_state
            if override_enabled:
                self.gates[gate_id]["open"] = override_state
            else:
                # Returning to normal sensor-driven control — safe default is closed
                self.gates[gate_id]["open"] = False
        # Notify outside the lock — models actuator position feedback signal
        self._notify_gate_listeners(gate_id)
        return True

    def get_all_gates(self):
        with self._lock:
            return {gid: dict(g) for gid, g in self.gates.items()}

    # ---- Sensor state helpers ----
    # These model the physical sensor inputs that feed into the gate controller.

    def set_approach_sensor(self, gate_id, active):
        """Approach-lane sensor: True = vehicle waiting at the gate."""
        with self._lock:
            if gate_id not in self.gates:
                return False
            self.gates[gate_id]["approach_sensor"] = active
        self._notify_gate_listeners(gate_id)
        return True

    def set_clearance_sensor(self, gate_id, active):
        """IR clearance sensor: True = vehicle is in the gate path (beam broken)."""
        with self._lock:
            if gate_id not in self.gates:
                return False
            self.gates[gate_id]["clearance_sensor"] = active
        self._notify_gate_listeners(gate_id)
        return True

    # ---- Gate WebSocket helpers ----

    def _notify_gate_listeners(self, gate_id: int) -> None:
        """
        Broadcast the current gate state to all connected WebSocket clients.
        Called after any gate state mutation, outside the main lock.
        Models the physical feedback signal a real gate actuator sends
        back to the main controller after executing a command.
        """
        gate_data = self.get_gate(gate_id)
        if gate_data is None:
            return
        payload = {"gate_id": gate_id, **gate_data}
        socketio.emit("gate_update", payload)

    # ---- Occupancy helpers ----

    def increment_cars(self):
        with self._lock:
            if self.num_cars_inside < self.capacity:
                self.num_cars_inside += 1
        socketio.emit("occupancy_update", self.get_occupancy())
        return self.num_cars_inside

    def decrement_cars(self):
        with self._lock:
            if self.num_cars_inside > 0:
                self.num_cars_inside -= 1
        socketio.emit("occupancy_update", self.get_occupancy())
        return self.num_cars_inside

    def get_occupancy(self):
        with self._lock:
            return {
                "num_cars_inside": self.num_cars_inside,
                "capacity": self.capacity,
                "percentage": round(self.num_cars_inside / self.capacity * 100, 1)
                if self.capacity
                else 0,
            }

    # ---- Spot helpers ----

    def set_spot(self, spot_id, occupied):
        with self._lock:
            for floor_id, floor_spots in self.spots.items():
                if spot_id in floor_spots:
                    floor_spots[spot_id] = occupied
                    break
            else:
                return None
        # Emit updated floor state to all connected clients
        floor_info = self.get_floor(floor_id)
        if floor_info:
            status = "FULL" if floor_info["available"] == 0 else "AVAILABLE"
            socketio.emit("floor_update", {**floor_info, "status": status})
        return floor_id

    def get_floor(self, floor_id):
        with self._lock:
            floor = self.spots.get(floor_id)
            if floor is None:
                return None
            occupied = sum(1 for v in floor.values() if v)
            total = len(floor)
            return {
                "floor_id": floor_id,
                "spots": dict(floor),
                "occupied": occupied,
                "available": total - occupied,
                "total": total,
            }

    def get_all_floors(self):
        floors = []
        for fid in sorted(self.spots):
            floors.append(self.get_floor(fid))
        return floors

    # ---- Event log helpers ----

    def log_event(self, event_type, gate_id=None, details=None):
        entry = {
            "type": event_type,
            "gate_id": gate_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.event_log.append(entry)
        return entry

    def get_events(self, limit=50):
        with self._lock:
            return list(reversed(self.event_log[-limit:]))

    # ---- Power helpers ----

    def get_power_state(self):
        with self._lock:
            return dict(self.power)

    def set_power_state(self, source, outage_mode):
        """Update power source and outage mode, then emit to all clients."""
        with self._lock:
            self.power["source"] = source
            self.power["outage_mode"] = outage_mode
        socketio.emit("power_update", self.get_power_state())

    # ---- Lockdown helpers ----

    def get_lockdown(self):
        with self._lock:
            return self.lockdown

    def set_lockdown(self, enabled):
        """Update lockdown flag and emit to all clients."""
        with self._lock:
            self.lockdown = bool(enabled)
        socketio.emit("lockdown_update", {"active": self.lockdown})

    # ---- Admin auth helpers ----

    def verify_admin(self, username, password):
        return username == self.admin_username and password == self.admin_password

    def add_token(self, token):
        with self._lock:
            self.admin_tokens.add(token)

    def verify_token(self, token):
        with self._lock:
            return token in self.admin_tokens

    def remove_token(self, token):
        with self._lock:
            self.admin_tokens.discard(token)


# Singleton instance
db = Database()
