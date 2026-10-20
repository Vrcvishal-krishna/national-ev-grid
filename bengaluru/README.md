# Greater Bengaluru EV Charging Telemetry Command Center

Live operational command center and high-precision telemetry engine for the Greater Bengaluru metropolitan area across Outer Ring Road, Whitefield, Electronic City, Koramangala, Indiranagar, and Devanahalli corridors.

### Comprehensive Network Coverage (Public + Fleet + Commercial)
- **Metropolitan Grid:** 521 deduplicated public, commercial, and fleet hubs
- **Hardware Capacity:** 1,857 physical guns | 103,035.9 kW installed grid load
- **CPO Integration:**
  - Statiq Network: 668 sockets
  - ChargeZone (Public + Fleet + Depots): 432 sockets
  - GLIDA (MG Motor): 238 sockets
  - Tata Power EZ Charge: 211 sockets
  - Jio-bp pulse (Pulse + Fleet-Charging-Station): 108 sockets (54 verified hubs)
  - Shell Recharge: 107 sockets
  - goEgo Network: 54 sockets
  - BPCL: 33 sockets
  - HPCL: 3 sockets
  - Bolt.Earth: 2 sockets
  - Sunfuel: 1 socket

### Architecture & Standby Policy
- **Zero Synthetic Data:** 100% genuine hardware telemetry directly queried from CPO cloud APIs and OCPP gateways.
- **Standby Baseline:** Default state is locked at `{"running": false}` (0 active charging, real Available/Faulted baseline). Polling daemon activates strictly when triggered via `[▶ START LIVE TELEMETRY]`.
- **Zero Cross-City Contamination:** Isolated registry bounded strictly between latitudes 12.70–13.35 N and longitudes 77.35–77.90 E.

### Deployment
Configured for automated zero-dependency deployment on Render using standard Python HTTP server and SQLite:
```bash
python app.py
```
