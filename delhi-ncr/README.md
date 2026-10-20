# Greater Delhi-NCR EV Charging Telemetry Command Center

Live operational command center and high-precision telemetry engine for the Greater Delhi-NCR metropolitan area across the National Capital Territory (NCT) of Delhi, Gurugram, Noida, Greater Noida, Faridabad, and Ghaziabad.

### Network Coverage
- **Metropolitan Grid:** 1,124 deduplicated public & fleet charging hubs
- **Hardware Capacity:** 3,670 physical guns | 192,682.1 kW (192.7 MW) installed grid load
- **CPO Integration:**
  - Statiq Network (National HQ & Roamed): 2,073 sockets
  - Tata Power EZ Charge (DMRC Metro & Public): 708 sockets
  - ChargeZone (Public + Commercial + Fleet): 284 sockets
  - goEgo Network: 264 sockets
  - Jio-bp pulse (Public + Dedicated Fleet): 186 sockets
  - GLIDA (MG Motor & Fleet): 95 sockets
  - BPCL: 50 sockets
  - HPCL: 7 sockets
  - Sunfuel: 3 sockets

### Architecture & Standby Policy
- **Zero Synthetic Data:** 100% genuine hardware telemetry queried directly from CPO cloud APIs and OCPP gateways.
- **Standby Baseline:** Default state is locked at `{"running": false}` (0 active charging, real Available/Faulted baseline). Polling daemon activates strictly when triggered via `[▶ START LIVE TELEMETRY]`.
- **Zero Cross-City Contamination:** Isolated registry bounded strictly between latitudes 28.20–28.92 N and longitudes 76.80–77.60 E.

### Deployment
Configured for automated zero-dependency deployment on Render using standard Python HTTP server and SQLite:
```bash
python app.py
```
