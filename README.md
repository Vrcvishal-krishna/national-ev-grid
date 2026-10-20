# National EV Grid Command Center (India) ⚡

A unified, high-performance telemetry command system monitoring **3,823 deduplicated metropolitan charging hubs** and **12,266 operational high-power charging sockets** across India's top 7 metropolitan areas.

## Metropolitan Coverage
1. **Pune & PCMC**: 428 Hubs | 1,534 Guns (`/pune/`)
2. **Mumbai MMR**: 918 Hubs | 2,778 Guns (`/mumbai/`)
3. **Kolkata & Howrah**: 168 Hubs | 727 Guns (`/kolkata/`)
4. **Ahmedabad & Gandhinagar**: 210 Hubs | 500 Guns (`/ahmedabad/`)
5. **Bengaluru**: 521 Hubs | 1,857 Guns (`/bengaluru/`)
6. **Greater Delhi-NCR**: 1,124 Hubs | 3,670 Guns (`/delhi-ncr/`)
7. **Greater Hyderabad**: 454 Hubs | 1,200 Guns (`/hyderabad/`)

**Total National Footprint:** 3,823 Hubs | 12,266 Guns | 626.8 MW Combined Capacity

## Architecture
- **Unified Single-Port Web Service**: Runs on Render or any cloud container using standard library Python 3.
- **Master Portal (`/`)**: Displays real-time national aggregates and quick-launch cards.
- **Subpath Routing**: Each city dashboard lives seamlessly under `/{city_id}/`.
- **Zero Standby**: Poller daemons consume zero CPU and bandwidth until telemetry is toggled.
- **Keepalive Endpoint**: `/health` and `/ping` return 2-byte `OK` for uptime monitors (cron-job.org).
