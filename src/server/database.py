"""
In-memory database for the parking structure demo.

Stores authorized badges, parking spot occupancy, gate states,
event logs, power state, and admin credentials.
All data is ephemeral -- resets on server restart.
"""

import threading
from datetime import datetime, timezone


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
        self.gates = {
            1: {"type": "entry", "open": False, "override": False, "override_state": False},
            2: {"type": "exit", "open": False, "override": False, "override_state": False},
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
            if gate_id in self.gates:
                self.gates[gate_id]["open"] = is_open
                return True
            return False

    def set_gate_override(self, gate_id, override_enabled, override_state):
        with self._lock:
            if gate_id in self.gates:
                self.gates[gate_id]["override"] = override_enabled
                self.gates[gate_id]["override_state"] = override_state
                if override_enabled:
                    self.gates[gate_id]["open"] = override_state
                return True
            return False

    def get_all_gates(self):
        with self._lock:
            return {gid: dict(g) for gid, g in self.gates.items()}

    # ---- Occupancy helpers ----

    def increment_cars(self):
        with self._lock:
            if self.num_cars_inside < self.capacity:
                self.num_cars_inside += 1
            return self.num_cars_inside

    def decrement_cars(self):
        with self._lock:
            if self.num_cars_inside > 0:
                self.num_cars_inside -= 1
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
                    return floor_id
            return None

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

    def set_power_source(self, source):
        with self._lock:
            self.power["source"] = source

    def set_outage_mode(self, enabled):
        with self._lock:
            self.power["outage_mode"] = enabled

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
