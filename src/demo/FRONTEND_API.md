# Frontend → Backend API Guide

Base URL: `http://127.0.0.1:5000`

All request/response bodies are JSON. Admin-protected endpoints require the header:
```
Authorization: Bearer <token>
```
where `<token>` is obtained from `POST /admin/login`.

---

## 1. Demo Inputs (Controls)

### 1.1 Gate Exit Sensor — vehicle approaches the exit lane

Fires when the exit-lane sensor detects a vehicle. The server checks for lockdown and opens the exit gate automatically.

```
POST /gate/vehicle-detected
Body: { "gate_id": 2 }
```

**Success (gate opened)**
```json
{ "gate_id": 2, "action": "gate_opened" }
```
**Denied (lockdown active)**
```json
HTTP 403
{ "gate_id": 2, "action": "denied", "reason": "lockdown" }
```

---

### 1.2 Gate Entered Sensor — vehicle has cleared the gate

Fires after the ultrasonic clearance sensor confirms the vehicle has fully passed through. Closes the gate and updates occupancy.

**Entry gate (after a successful RFID scan):**
```
POST /gate/vehicle-entered
Body: { "gate_id": 1 }
```
**Exit gate (after the exit gate was opened):**
```
POST /gate/vehicle-entered
Body: { "gate_id": 2 }
```

**Response**
```json
{
  "gate_id": 1,
  "gate_open": false,
  "occupancy": {
    "num_cars_inside": 3,
    "capacity": 75,
    "percentage": 4.0
  }
}
```

> Use the returned `occupancy` to refresh the occupancy counter and percentage visualizer immediately.

---

### 1.3 RFID Entry — driver taps badge at entry gate

Step 1 — Signal that a vehicle is waiting (optional; no log entry is created at this stage):
```
POST /gate/vehicle-detected
Body: { "gate_id": 1 }
Response: { "gate_id": 1, "action": "awaiting_rfid" }
```

Step 2 — Submit the badge UID:
```
POST /gate/rfid-scan
Body: { "gate_id": 1, "badge_uid": "<scanned-id>" }
```

**Valid badge — gate opens**
```json
HTTP 200
{ "gate_id": 1, "badge_uid": "B001", "valid": true, "gate_open": true }
```
Show **green** RFID indicator. Then wait for the gate-entered sensor (1.2) to close the gate.

**Invalid badge**
```json
HTTP 403
{ "gate_id": 1, "badge_uid": "BOGUS", "valid": false, "gate_open": false }
```
Show **red** RFID indicator.

**Facility at capacity**
```json
HTTP 403
{ "error": "Facility at capacity" }
```

---

### 1.4 Choose Spot to Park (GUI spot sensor)

Call this when the user selects a spot as occupied or free in the GUI. This models the physical ultrasonic spot sensor.

```
POST /parking/spot-update
Body: { "spot_id": "2-07", "occupied": true }
```
`spot_id` format: `"<floor>-<spot>"` e.g. `"1-01"` through `"3-25"`.

**Response**
```json
{
  "spot_id": "2-07",
  "occupied": true,
  "led_on": false,
  "floor": {
    "floor_id": 2,
    "occupied": 1,
    "available": 24,
    "total": 25,
    "status": "AVAILABLE",
    "spots": { "2-01": false, "2-02": false, ..., "2-07": true, ... }
  }
}
```

- `led_on: false` → stall guide light is off (spot taken)
- `led_on: true` → stall guide light is on (spot free)
- Use `floor.spots` to redraw the per-floor occupancy map.
- Use `floor.status` (`"AVAILABLE"` / `"FULL"`) to update the floor sign.

---

### 1.5 Admin Page

#### 1.5.1 Login

```
POST /admin/login
Body: { "username": "admin", "password": "admin" }
```
```json
HTTP 200
{ "token": "a3f9..." }
```
Store the token; include it as `Authorization: Bearer <token>` on all subsequent admin calls.

```json
HTTP 401
{ "error": "Invalid credentials" }
```

#### 1.5.2 Logout

```
POST /admin/logout
Headers: Authorization: Bearer <token>
```
```json
{ "ok": true }
```

---

#### 1.5.3 Entry & Exit Gate Override Switches

**Enable override (force open or force closed):**
```
POST /admin/gate-override
Headers: Authorization: Bearer <token>
Body: { "gate_id": 1, "override": true, "state": true }
```
- `gate_id` — `1` = entry, `2` = exit
- `state: true` → gate held open; `state: false` → gate held closed

**Disable override (return gate to normal RFID/sensor control):**
```
POST /admin/gate-override
Headers: Authorization: Bearer <token>
Body: { "gate_id": 1, "override": false, "state": false }
```

**Response**
```json
{ "gate_id": 1, "override": true, "gate_open": true }
```

---

#### 1.5.4 Authorized Badge List

**List all badges:**
```
GET /admin/badges
Headers: Authorization: Bearer <token>
```
```json
{ "badges": ["B001", "B002", "B003", "B004", "B005"] }
```

**Add a badge:**
```
POST /admin/badges
Headers: Authorization: Bearer <token>
Body: { "badge_uid": "BNEW" }
```
```json
HTTP 201
{ "ok": true, "badges": ["B001", "B002", "B003", "B004", "B005", "BNEW"] }
```

**Remove a badge:**
```
DELETE /admin/badges/<uid>
Headers: Authorization: Bearer <token>
```
```json
{ "ok": true, "badges": ["B002", "B003", "B004", "B005"] }
```

---

#### 1.5.5 Fake CCTV — Choose Camera Display

**List cameras:**
```
GET /admin/cctv
Headers: Authorization: Bearer <token>
```
```json
{
  "cameras": [
    { "id": 1, "name": "Entry Gate",   "location": "Level 0 - Entry" },
    { "id": 2, "name": "Exit Gate",    "location": "Level 0 - Exit"  },
    { "id": 3, "name": "Floor 1 East", "location": "Level 1"         },
    { "id": 4, "name": "Floor 2 East", "location": "Level 2"         },
    { "id": 5, "name": "Floor 3 East", "location": "Level 3"         }
  ]
}
```

**Select a camera:**
```
GET /admin/cctv/<camera_id>
Headers: Authorization: Bearer <token>
```
```json
{
  "id": 3,
  "name": "Floor 1 East",
  "location": "Level 1",
  "status": "online",
  "feed_url": "/static/cctv_placeholder_3.jpg"
}
```
Display the image at `feed_url` as the fake CCTV frame. Swap it whenever the user picks a different camera.

---

## 2. Demo Outputs (Visualizers)

All visualizer state can be polled or derived from the responses above. Use these endpoints to initialize or refresh the UI.

### 2.1 Gate State (Entry & Exit)

```
GET /gate/status/1    → entry gate
GET /gate/status/2    → exit gate
```
```json
{ "gate_id": 1, "type": "entry", "open": false, "override": false, "override_state": false }
```
Animate the gate arm up/down based on `open`.

To poll all gates at once:
```
GET /gate/status
```

---

### 2.2 RFID Success / Fail Indicator

Driven entirely by the response to `POST /gate/rfid-scan` (see 1.3).
- `"valid": true` → flash **green** for ~2 s
- `"valid": false` or HTTP 403 → flash **red** for ~2 s

---

### 2.3 Parking Occupancy Counter & Percentage

```
GET /parking/occupancy
```
```json
{
  "global": {
    "num_cars_inside": 12,
    "capacity": 75,
    "percentage": 16.0
  },
  "floors": [ ... ]
}
```
Display `num_cars_inside / capacity` and `percentage`.

Also returned inline by `POST /gate/vehicle-entered` — use that response to update instantly without a separate poll.

---

### 2.4 Per-Floor Parking Occupancy Visualization

```
GET /parking/occupancy       → all three floors in one call
GET /parking/floor/<floor_id>  → single floor detail
```

Single floor response:
```json
{
  "floor_id": 1,
  "occupied": 3,
  "available": 22,
  "total": 25,
  "spots": {
    "1-01": true,
    "1-02": false,
    ...
  }
}
```
Iterate `spots` to colour each cell in the floor grid (occupied = filled, available = empty). Also returned inline by `POST /parking/spot-update`.

---

## 3. Global System Status (one-shot poll on load)

```
GET /status
```
```json
{
  "occupancy": { "num_cars_inside": 0, "capacity": 75, "percentage": 0.0 },
  "gates": {
    "1": { "type": "entry", "open": false, "override": false, "override_state": false },
    "2": { "type": "exit",  "open": false, "override": false, "override_state": false }
  },
  "power": { "source": "grid", "outage_mode": false },
  "lockdown": false
}
```
Use this on page load to hydrate all visualizers at once.

---

## 4. Event Log (Admin)

```
GET /admin/events?limit=50
Headers: Authorization: Bearer <token>
```
```json
{
  "events": [
    { "type": "Entry", "gate_id": 1, "details": { "badge_uid": "B001" }, "timestamp": "2026-03-01T14:00:00+00:00" },
    { "type": "Exit",  "gate_id": 2, "details": null, "timestamp": "2026-03-01T14:05:00+00:00" }
  ]
}
```
Render as a scrollable table on the admin page. Refresh after any gate or badge action.

---

## 5. Error Reference

| HTTP | Meaning |
|------|---------|
| 400 | Missing or invalid request field |
| 401 | No token / invalid token / bad credentials |
| 403 | Access denied (lockdown, override active, at capacity, invalid badge) |
| 404 | Gate / spot / floor / camera not found |
