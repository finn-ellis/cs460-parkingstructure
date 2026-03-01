# CS460 Parking Project
Finn Ellis (manager)
Samuel Landis
Ike Osode
Liepa Lavickyte
Younes Slaoui

# Run details
Python flask backend & node/react/vite frontend.
I recommend initializing a Python virtual environment first & installing dependencies there. Commands:
```sh
python3 -m venv .venv
source .venv/bin/activate #windows: .\.venv\bin\Activate.ps1 or something
pip install -r requirements.txt
```

Frontend:
```sh
cd src/demo/frontend
npm run dev #or npm run preview, etc
```

To run, first run the backend with `python3 -m flask --app src/server/ run`
Then, run the frontend with `npm --prefix src/demo/frontend run dev`

# Implementation Details
# Demo
Frontend software for simulating I/O with the server software
## Demo Inputs (controls)
- Gate exit sensor (binary)
- Gate entered sensor (binary)
- RFID entry (just input an ID)
- Choose spot to park in GUI
- Admin page with:
 - Simple login enter credentials page
 - Entry & exit gate override switches
 - List of authorized badge codes (with ability to add/remove)
 - Fake CCTV "choose camera" display

## Demo Outputs (visualizers)
- Exit gate
- Entry gate
- RFID success/fail (temp. green/red indicator)
- Parking occupancy counter (and percentage of maximum)
- Per-floor parking occupancy visualization

# Main Controller Server
Local web server handling lifecycle & communication between components

# Components:
## Gate Controller
- Connects simulated exit gate sensor to exit game actuator
- Makes open signal accessible to RFID controller. Closes entry gate after gate entered sensor is triggered.
- Makes admin override controls accessible
- Makes an RFID scan API accessible. Receives a badge ID from a scanned badge & validates against database
- Calls open on successful RFID scan

## Database Controller
- HAndles database
- Contains authorized badge IDs
- Contains parking occupancy stats (cars in the facility, per-spot occupancy booleans/floor bitmaps)
- 3 floors, 25 spots per floor (75 total capacity)
- Contains entry log (badges IDs scanned for entry)
- Allows validation of Badge ID

## Parking Sensor Controller
- Listens to per-spot sensor inputs and modifies database accordingly
- Sets parking lights to reflect database state

## Admin Controller/API
- Allows simple login functionality
- Allows entry & exit gate overrides via gate controller
- Adding, removing, querying list of badge IDs
- Simulated/fake CCTV feed

# Use cases:
Architecture must follow the design defined by the following use cases:

## 4.1 Successful Entry

Actor: Authorized Driver

Primary goal: Gain access to the facility and update global capacity

Pre-condition: Gate is in idle state (closed, but monitoring entry)

Trigger: Entry gate sensor detects a vehicle.

Flow:

The Gate Controller detects a vehicle and alerts the Main Controller.



isVehicleDetected(int gateID)

The driver taps their badge; the Gate Controller captures the UID.



readBadgeUID()

The Main Controller validates the UID against the Database.



validateEmployee(string UID)

Upon successful validation, the Main Controller commands the gate to open.



setGateState(int gateID, true)

The Main Controller logs the successful entry event.



logEvent("Entry", gateID, timestamp)

The Gate Controller monitors the path for safety during transit.



isPathBlocked()

Post-condition: the Main Controller increments the global occupancy count in the Database; gate closes behind the vehicle.



## 4.2 Parking Spot Update

Actor: Vehicle / Spot Sensor

Primary goal: Update the availability count and displays

Pre-condition: Parking spot is available

Trigger: Vehicle enters a vacant parking spot.

Flow:

The Parking Availability Controller detects a state change via the ultrasonic sensor.



isSpotOccupied(int spotID)

The Main Controller receives the "Occupied" signal and commands the stall light to turn off.



toggleSpotLED(int spotID, false)

The Main Controller calculates the new per-floor total and updates the level displays.



updateFloorSign(int floorID, int count, "AVAILABLE")

Note: This action does not change the (num_cars_inside) variable.

Post-condition: The Main Controller updates the local occupancy map within the Database.



## 4.3 Successful Exit

Actor: Authorized Driver

Goal: Exit the facility and update global capacity records.

Pre-conditions: The vehicle is currently parked within the structure; Admin override is disabled.

Trigger: The vehicle approaches the exit gate lane.

Flow:

The Gate Controller detects vehicle mass via the exit lane sensor and alerts the Main Controller.



isVehicleDetected(int gateID)

The Main Controller verifies that the system is not in an emergency "Lockdown" state.

The Main Controller instructs the Gate Controller to raise the exit barrier.

setGateState(int gateID, true)

The vehicle passes through the gate; the Gate Controller monitors the path via the infrared sensor to ensure the lane is clear.



isPathBlocked()

Once the vehicle has cleared the lane, the Main Controller decrements the global variable num_cars_inside within the Database.

The Main Controller logs the timestamped exit transaction for security auditing.

logEvent("Exit", gateID, timestamp)

The Main Controller commands the Gate Controller to lower the barrier arm.



setGateState(int gateID, false)

Post-condition: The global capacity is updated, and the gate returns to an idle, closed state.



## 4.4 Emergency Power Failure

Actor: CPMS / UPS System

Primary goal: Ensure safety and facility resilience

Pre-condition: The system is operating on the primary grid power

Trigger: Power failure detected

Flow:

The Power Supply Controller detects the failure and switches to the UPS.



getPowerSourceState()

switchSource(int sourceID)

The Main Controller initiates "Power Outage Mode" logic.

The Main Controller commands a power cut to non-essential guidance hardware.

setPowerCut(true)

The Main Controller ensures the Database remains active for continuous security logging.

Post-condition: Essential functionality continues.



## 4.5 Admin Gate Override

Actor: Facility Administrator

Goal: Manually control a gate for maintenance or security reasons

Pre-conditions: Admin is logged into a secure session

Trigger: Admin selects a gate override command on the dashboard

Flow:

The Admin authenticates through the Admin API.



login(string username, string password)

The Admin issues a manual "Open" command for a specific gate.



enableGateOverride(gate, true, true)

The Main Controller bypasses standard RFID logic and instructs the Gate Controller.



setGateState(int gateID, true)

Post-condition: The action is logged in the Database for audit purposes