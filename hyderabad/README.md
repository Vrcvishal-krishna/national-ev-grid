# Greater Hyderabad EV Charging Telemetry Command Center

Live operational command center and high-precision telemetry engine for the Greater Hyderabad metropolitan area across Cyberabad, HITEC City, Gachibowli, Madhapur, Kondapur, Secunderabad, Shamshabad (RGIA), and the Outer Ring Road (ORR).

### Network Coverage
- **Metropolitan Grid:** 454 deduplicated public & fleet charging hubs
- **Hardware Capacity:** 1,200 physical guns | 91,830.3 kW (91.8 MW) installed grid load
- **CPO Integration:**
  - Statiq Network (and Roamed Feeds): 625 sockets
  - GLIDA (MG Motor & Fleet Network): 200 sockets
  - Tata Power EZ Charge: 128 sockets
  - ChargeZone (Public + Commercial + Fleet): 123 sockets
  - Jio-bp pulse (Public + Dedicated Fleet): 62 sockets
  - Shell Recharge: 39 sockets
  - BPCL: 22 sockets
  - Sunfuel: 1 socket

### Architecture & Standby Policy
- **Zero Synthetic Data:** 100% genuine hardware telemetry queried directly from CPO cloud APIs and OCPP gateways.
- **Standby Baseline:** Default state is locked at `{"running": false}` (0 active charging, real Available/Faulted baseline). Polling daemon activates strictly when triggered via `[▶ START LIVE TELEMETRY]`.
- **Zero Cross-City Contamination:** Isolated registry bounded strictly between latitudes 17.15–17.65 N and longitudes 78.20–78.70 E.

### Deployment
Configured for automated zero-dependency deployment on Render using standard Python HTTP server and SQLite:
```bash
python app.py
```
