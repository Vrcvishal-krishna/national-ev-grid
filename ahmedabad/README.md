# Greater Ahmedabad & Gandhinagar EV Charging Telemetry Command Center

Live operational command center and high-precision telemetry engine for the Greater Ahmedabad & Gandhinagar metropolitan area across the Sabarmati, SG Highway, and GIFT City corridors.

### Network Coverage
- **Metropolitan Grid:** 210 deduplicated public & fleet charging hubs
- **Hardware Capacity:** 500 physical guns | 34,933.6 kW installed grid load
- **CPO Integration:**
  - ChargeZone (Gujarat HQ & Fleet): 205 sockets
  - Statiq Network: 129 sockets
  - Tata Power EZ Charge: 57 sockets
  - Jio-bp pulse (Public + Fleet): 40 sockets
  - goEgo Network: 26 sockets
  - GLIDA (MG Motor): 12 sockets
  - BPCL: 11 sockets
  - Shell Recharge: 10 sockets
  - Torrent Power: 7 sockets
  - Sunfuel: 2 sockets
  - HPCL: 1 socket

### Architecture & Standby Policy
- **Zero Synthetic Data:** 100% genuine hardware telemetry directly queried from CPO cloud APIs and OCPP gateways.
- **Standby Baseline:** Default state is locked at `{"running": false}` (0 active charging, real Available/Faulted baseline). Polling daemon activates strictly when triggered via `[▶ START LIVE TELEMETRY]`.
- **Zero Cross-City Contamination:** Isolated registry bounded strictly between latitudes 22.85–23.30 N and longitudes 72.40–72.78 E.

### Deployment
Configured for automated zero-dependency deployment on Render using standard Python HTTP server and SQLite:
```bash
python app.py
```
