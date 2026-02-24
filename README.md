# CS460 Parking Project
Finn Ellis (manager)
Samuel Landis
Ike Osode
Liepa Lavickyte
Younes Slaoui

# Implementation Details
# Demo
Frontend software for simulating I/O with the server software
## Demo Inputs (controls)
- Gate exit sensor (binary)
- Gate entered sensor (binary)
- RFID entry (just input an ID)
- Choose spot to park in GUI
- Admin page with:
 - Entry & exit gate override switches
 - List of authorized badge codes (with ability to add/remove)

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

## RFID Controller
- Simulates communication with an RFID driver. Receives a badge ID from a scanned badge & validates against database
- Sends open signal to gate controller on successful RFID scan

## Database
- Contains authorized badge IDs
- Contains parking occupancy stats (cars in the facility, per-spot occupancy boolean)
- Contains entry log (badges IDs scanned for entry)
- Allows validation of Badge ID

## Admin API
- Allows entry & exit gate overrides via gate controller
- Adding, removing, querying list of badge IDs