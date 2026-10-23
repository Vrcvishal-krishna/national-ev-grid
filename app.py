import gzip
import hashlib
#!/usr/bin/env python3
"""
National EV Grid Command Center - Unified Multi-City Service
Single Web Service running all 7 Metropolitan Grids:
  - Pune & PCMC
  - Mumbai MMR
  - Kolkata & Howrah
  - Ahmedabad & Gandhinagar
  - Bengaluru
  - Greater Delhi-NCR
  - Greater Hyderabad
Exposes Master Gateway at '/' and individual city grids at '/{city_id}/'.
"""

import os
import sys
import time
import json
import threading
import mimetypes
import importlib.util
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

os.environ['TZ'] = 'Asia/Kolkata'
if hasattr(time, 'tzset'):
    time.tzset()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CITIES = [
    {
        "id": "pune",
        "name": "Pune & PCMC",
        "dir": "pune",
        "daemon_file": "hinjewadi_daemon.py",
        "color": "#10b981",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "mumbai",
        "name": "Mumbai MMR",
        "dir": "mumbai",
        "daemon_file": "mumbai_daemon.py",
        "color": "#06b6d4",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "kolkata",
        "name": "Kolkata & Howrah",
        "dir": "kolkata",
        "daemon_file": "kolkata_daemon.py",
        "color": "#f59e0b",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "ahmedabad",
        "name": "Ahmedabad & Gandhinagar",
        "dir": "ahmedabad",
        "daemon_file": "ahmedabad_daemon.py",
        "color": "#8b5cf6",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "bengaluru",
        "name": "Bengaluru",
        "dir": "bengaluru",
        "daemon_file": "bengaluru_daemon.py",
        "color": "#ec4899",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "delhi-ncr",
        "name": "Greater Delhi-NCR",
        "dir": "delhi-ncr",
        "daemon_file": "delhi_ncr_daemon.py",
        "color": "#3b82f6",
        "state_file": "telemetry_state.json"
    },
    {
        "id": "hyderabad",
        "name": "Greater Hyderabad",
        "dir": "hyderabad",
        "daemon_file": "hyderabad_daemon.py",
        "color": "#14b8a6",
        "state_file": "telemetry_state.json"
    }
]

CITY_MAP = {c["id"]: c for c in CITIES}

def get_city_state(city_id: str) -> bool:
    c = CITY_MAP.get(city_id)
    if not c:
        return False
    sf = os.path.join(BASE_DIR, c["dir"], c["state_file"])
    if os.path.exists(sf):
        try:
            with open(sf) as f:
                return json.load(f).get("running", False)
        except Exception:
            pass
    return False

def set_city_state(city_id: str, running: bool):
    c = CITY_MAP.get(city_id)
    if not c:
        return
    sf = os.path.join(BASE_DIR, c["dir"], c["state_file"])
    with open(sf, "w") as f:
        json.dump({"running": running, "updated_at": time.time()}, f)

CITY_BASE_STATS = {
    "pune": {"hubs": 428, "capacity_mw": 78.2},
    "mumbai": {"hubs": 918, "capacity_mw": 141.6},
    "kolkata": {"hubs": 168, "capacity_mw": 37.1},
    "ahmedabad": {"hubs": 210, "capacity_mw": 25.5},
    "bengaluru": {"hubs": 521, "capacity_mw": 94.7},
    "delhi-ncr": {"hubs": 1124, "capacity_mw": 188.5},
    "hyderabad": {"hubs": 454, "capacity_mw": 61.2}
}

LATEST_METRICS_CACHE = {}

def get_city_metrics(city_id: str):
    if city_id in LATEST_METRICS_CACHE:
        cached = LATEST_METRICS_CACHE[city_id]
        m = cached.get("metrics", {})
        hubs = cached.get("hubs", 0)
        guns = m.get("total_guns", 0)
        base = CITY_BASE_STATS.get(city_id, {"hubs": hubs, "capacity_mw": 0.0})
        capacity_mw = base.get("capacity_mw", (guns * 55.0) / 1000.0)
        return m, hubs, capacity_mw

    c = CITY_MAP.get(city_id)
    if not c:
        return {}, 0, 0.0
    jf = os.path.join(BASE_DIR, c["dir"], "live_telemetry.json")
    metrics = {}
    hubs = 0
    if os.path.exists(jf):
        try:
            with open(jf) as f:
                d = json.load(f)
                metrics = d.get("metrics", {})
                hubs = len(d.get("stations", []))
                LATEST_METRICS_CACHE[city_id] = {"metrics": metrics, "hubs": hubs}
        except Exception:
            pass
    guns = metrics.get("total_guns", 0)
    base = CITY_BASE_STATS.get(city_id, {"hubs": hubs, "capacity_mw": 0.0})
    capacity_mw = base.get("capacity_mw", (guns * 55.0) / 1000.0)
    return metrics, hubs, capacity_mw

def get_national_metrics():
    tot_hubs = 0
    tot_guns = 0
    tot_mw = 0.0
    tot_active = 0
    tot_energy_24h = 0.0
    city_statuses = {}

    for c in CITIES:
        cid = c["id"]
        m, hubs, cap = get_city_metrics(cid)
        guns = m.get("total_guns", 0)
        active = m.get("active_charging", 0)
        e24 = m.get("total_energy_kwh_24h", 0.0)
        running = get_city_state(cid)

        tot_hubs += hubs
        tot_guns += guns
        tot_mw += cap
        tot_active += active
        tot_energy_24h += e24

        city_statuses[cid] = {
            "name": c["name"],
            "hubs": hubs,
            "guns": guns,
            "capacity_mw": round(cap, 1),
            "active_charging": active,
            "energy_delivered_today_kwh": round(e24, 1),
            "running": running
        }

    return {
        "total_hubs": tot_hubs,
        "total_guns": tot_guns,
        "total_capacity_mw": round(tot_mw, 1),
        "total_active_charging": tot_active,
        "total_energy_delivered_today_kwh": round(tot_energy_24h, 1),
        "cities": city_statuses
    }

def run_city_daemon(city_config, delay=0):
    """Background worker for a city. Strictly zero standby when running=False."""
    if delay > 0:
        time.sleep(delay)

    cid = city_config["id"]
    cdir = os.path.join(BASE_DIR, city_config["dir"])
    daemon_path = os.path.join(cdir, city_config["daemon_file"])
    
    if cdir not in sys.path:
        sys.path.insert(0, cdir)
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    if not os.path.exists(daemon_path):
        print(f"[{cid.upper()}] Daemon file not found: {daemon_path}", file=sys.stderr)
        return

    try:
        spec = importlib.util.spec_from_file_location(f"{cid}_daemon_mod", daemon_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_db()
        
        with open(mod.STATIONS_INDEX) as f:
            raw_stations = json.load(f)
            excluded_ids = getattr(mod, "EXCLUDED_STATION_IDS", set())
            excluded_names = getattr(mod, "EXCLUDED_NAMES", set())
            stations_list = [
                s for s in raw_stations
                if s.get("station_id") not in excluded_ids
                and not any(ex in (s.get("name") or s.get("station_name") or "") for ex in excluded_names)
            ]
        print(f"[{cid.upper()}] Ready. Tracking {len(stations_list)} hubs.")
    except Exception as e:
        print(f"[{cid.upper()}] Init error: {e}", file=sys.stderr)
        return

    import gc
    while True:
        if not get_city_state(cid):
            time.sleep(2)
            continue
        try:
            p = mod.poll_network_live(stations_list)
            m = p["metrics"]
            LATEST_METRICS_CACHE[cid] = {"metrics": m, "hubs": len(p["stations"])}
            print(f"[{cid.upper()}] {p.get('display_time')} | {len(p['stations'])} hubs | {m['active_charging']} ACTIVE")
        except Exception as e:
            print(f"[{cid.upper()}] Poller error: {e}", file=sys.stderr)
        finally:
            gc.collect()
        time.sleep(30)

GATEWAY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>National EV Grid Command Center - India</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #060b18;
      --card-bg: #0c1427;
      --border: #1e293b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --emerald: #10b981;
      --cyan: #06b6d4;
      --blue: #3b82f6;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      padding: 28px 36px;
      min-height: 100vh;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .title-area h1 {
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .pulse-dot {
      width: 12px;
      height: 12px;
      background: var(--emerald);
      border-radius: 50%;
      box-shadow: 0 0 12px var(--emerald);
      animation: pulse 1.6s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.35; transform: scale(0.85); }
    }
    .sub-title {
      color: var(--text-muted);
      font-size: 13px;
      margin-top: 5px;
    }
    .top-controls {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .ctrl-btn {
      padding: 9px 16px;
      font-weight: 700;
      font-size: 13px;
      border: 1px solid var(--border);
      cursor: pointer;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .btn-start-all {
      background: #065f46;
      color: #34d399;
      border-color: #059669;
    }
    .btn-start-all:hover {
      background: #047857;
      color: #fff;
    }
    .btn-stop-all {
      background: #7f1d1d;
      color: #f87171;
      border-color: #dc2626;
    }
    .btn-stop-all:hover {
      background: #991b1b;
      color: #fff;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .stat-box {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px 20px;
    }
    .stat-box .label {
      font-size: 11px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-box .num {
      font-size: 30px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      margin-top: 6px;
    }
    .stat-box .desc {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .city-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
      gap: 20px;
    }
    .city-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.2s, border-color 0.2s;
    }
    .city-card:hover {
      transform: translateY(-2px);
      border-color: #3b82f6;
    }
    .city-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 14px;
    }
    .city-name {
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.3px;
    }
    .badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
    }
    .badge-active {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-standby {
      background: rgba(148, 163, 184, 0.1);
      color: #94a3b8;
      border: 1px solid rgba(148, 163, 184, 0.2);
    }
    .city-metrics {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin: 14px 0;
      background: rgba(0,0,0,0.25);
      padding: 12px;
      border-radius: 8px;
    }
    .cm-item .cml {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
    }
    .cm-item .cmv {
      font-size: 17px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      color: #fff;
      margin-top: 2px;
    }
    .card-actions {
      display: flex;
      gap: 10px;
      margin-top: 10px;
    }
    .btn-open {
      flex: 1;
      text-align: center;
      background: #1e293b;
      color: #fff;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
      padding: 11px;
      border-radius: 6px;
      transition: background 0.2s;
    }
    .btn-open:hover {
      background: #2563eb;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title-area">
      <h1><div class="pulse-dot"></div> NATIONAL EV GRID COMMAND CENTER</h1>
      <div class="sub-title">24/7 Metropolitan Telemetry &bull; Unified Single-Service Cloud Architecture &bull; 7 Metros</div>
    </div>
    <div class="top-controls">
      <button class="ctrl-btn btn-start-all" onclick="toggleAll(true)">▶ START ALL TELEMETRY</button>
      <button class="ctrl-btn btn-stop-all" onclick="toggleAll(false)">⏹ STOP ALL</button>
    </div>
  </div>

  <div class="summary-grid">
    <div class="stat-box">
      <div class="label">METROPOLITAN HUBS</div>
      <div class="num" id="stat-hubs" style="color: #38bdf8;">--</div>
      <div class="desc">Deduplicated across 7 Metros</div>
    </div>
    <div class="stat-box">
      <div class="label">OPERATIONAL GUNS</div>
      <div class="num" id="stat-guns" style="color: #4ade80;">--</div>
      <div class="desc">Physical High-Power Sockets</div>
    </div>
    <div class="stat-box">
      <div class="label">INSTALLED CAPACITY</div>
      <div class="num" id="stat-mw" style="color: #facc15;">-- MW</div>
      <div class="desc">Combined Grid Connected Power</div>
    </div>
    <div class="stat-box">
      <div class="label">ACTIVE CHARGING SESSIONS</div>
      <div class="num" id="stat-active" style="color: #c084fc;">--</div>
      <div class="desc">Live Fleet Charging In Progress</div>
    </div>
  </div>

  <div class="city-grid" id="city-cards-container">
    <!-- Rendered dynamically -->
  </div>

  <script>
    async function loadMetrics() {
      try {
        const res = await fetch('/api/national_metrics');
        const data = await res.json();
        
        document.getElementById('stat-hubs').innerText = Number(data.total_hubs).toLocaleString();
        document.getElementById('stat-guns').innerText = Number(data.total_guns).toLocaleString();
        document.getElementById('stat-mw').innerText = Number(data.total_capacity_mw).toLocaleString() + ' MW';
        document.getElementById('stat-active').innerText = Number(data.total_active_charging).toLocaleString();

        const container = document.getElementById('city-cards-container');
        let html = '';
        const cityConfigs = [
          {id: 'pune', name: 'Pune & PCMC', color: '#10b981'},
          {id: 'mumbai', name: 'Mumbai MMR', color: '#06b6d4'},
          {id: 'kolkata', name: 'Kolkata & Howrah', color: '#f59e0b'},
          {id: 'ahmedabad', name: 'Ahmedabad & Gandhinagar', color: '#8b5cf6'},
          {id: 'bengaluru', name: 'Bengaluru', color: '#ec4899'},
          {id: 'delhi-ncr', name: 'Greater Delhi-NCR', color: '#3b82f6'},
          {id: 'hyderabad', name: 'Greater Hyderabad', color: '#14b8a6'}
        ];

        for (const cfg of cityConfigs) {
          const c = data.cities[cfg.id] || {hubs:0, guns:0, capacity_mw:0, active_charging:0, running:false};
          const badgeClass = c.running ? 'badge-active' : 'badge-standby';
          const badgeText = c.running ? '● TELEMETRY ACTIVE' : '○ STANDBY';
          
          html += `
            <div class="city-card">
              <div class="city-card-header">
                <div>
                  <div class="city-name" style="color: ${cfg.color}">${cfg.name}</div>
                  <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Subpath /${cfg.id}/</div>
                </div>
                <div class="badge ${badgeClass}">${badgeText}</div>
              </div>
              <div class="city-metrics">
                <div class="cm-item">
                  <div class="cml">Hubs</div>
                  <div class="cmv">${c.hubs}</div>
                </div>
                <div class="cm-item">
                  <div class="cml">Guns</div>
                  <div class="cmv">${c.guns}</div>
                </div>
                <div class="cm-item">
                  <div class="cml">Capacity</div>
                  <div class="cmv">${c.capacity_mw} MW</div>
                </div>
                <div class="cm-item">
                  <div class="cml">Active Now</div>
                  <div class="cmv" style="color: #4ade80;">${c.active_charging}</div>
                </div>
              </div>
              <div class="card-actions">
                <a href="/${cfg.id}/" target="_blank" class="btn-open">
                  Open ${cfg.name} Grid &rarr;
                </a>
              </div>
            </div>
          `;
        }
        container.innerHTML = html;
      } catch (err) {
        console.error("Failed to load metrics:", err);
      }
    }

    async function toggleAll(start) {
      const endpoint = start ? '/api/start_all' : '/api/stop_all';
      await fetch(endpoint);
      setTimeout(loadMetrics, 500);
    }

    loadMetrics();
    setInterval(loadMetrics, 10000);
  </script>
</body>
</html>
"""

class UnifiedRouterHandler(SimpleHTTPRequestHandler):
    def do_HEAD(self):
        """Zero-overhead HEAD keepalive for monitors."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', '2')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        ua = self.headers.get('User-Agent', '').lower()

        # Zero-overhead keepalive for cron-job.org and monitors
        if path in ['/health', '/ping', '/healthz', '/status'] or 'cron-job' in ua:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'OK')
            return

        # Central Gateway Root
        if path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(GATEWAY_HTML.encode('utf-8'))
            return

        # National API endpoints
        if path == '/api/debug_mumbai_fetch':
            res = {}
            import traceback, urllib.request, ssl
            # Test Tata direct
            try:
                url = "https://ezcharge.tatapower.com/HobsIntegration/syncRequestHandler?transid=test&service=GET_CHARGING_STATIONS_ALL"
                req = urllib.request.Request(url, data=b'{"userid":"","profileid":"PUBLIC","filter":{"radius":"","connector_type":"ALL"}}', headers={"Content-Type":"application/json","Authorization":"Basic NDUzNDY5VFBMOnNhZG1wd2Q=","User-Agent":"Mozilla/5.0"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
                    body = r.read()
                    res["tata_raw"] = {"status": r.status, "len": len(body), "preview": body[:100].decode('utf-8', errors='ignore')}
            except Exception as e:
                res["tata_raw"] = {"error": str(e), "type": type(e).__name__}

            # Test Jio direct
            try:
                import jiobp_fetcher
                tkn = jiobp_fetcher.get_auth_token()
                res["jio_token"] = bool(tkn)
                # Check refresh
                new_tkn = jiobp_fetcher.refresh_jiobp_token()
                res["jio_refresh"] = bool(new_tkn)
            except Exception as e:
                res["jio_error"] = str(e)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
            return

        if path == '/api/national_metrics':
            data = get_national_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        if path == '/api/start_all':
            for c in CITIES:
                set_city_state(c["id"], True)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "all_started", "running": true}')
            return

        if path == '/api/stop_all':
            for c in CITIES:
                set_city_state(c["id"], False)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "all_stopped", "running": false}')
            return

        # Route city requests: /{city_id} or /{city_id}/...
        parts = [p for p in path.split('/') if p]
        if parts:
            city_id = parts[0]
            if city_id in CITY_MAP:
                # If accessed without trailing slash, redirect to ensure relative paths work
                if len(parts) == 1 and not path.endswith('/'):
                    self.send_response(302)
                    self.send_header('Location', f'/{city_id}/')
                    self.end_headers()
                    return

                city_cfg = CITY_MAP[city_id]
                subpath = '/'.join(parts[1:])

                # Check city API endpoints
                if subpath == 'api/start_telemetry':
                    set_city_state(city_id, True)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "started", "running": true}')
                    return

                if subpath == 'api/stop_telemetry':
                    set_city_state(city_id, False)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "stopped", "running": false}')
                    return

                if subpath == 'api/telemetry_status':
                    st = get_city_state(city_id)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"running": st}).encode('utf-8'))
                    return

                # Map to file in city directory
                rel_file = subpath if subpath else 'index.html'
                target_file = os.path.join(BASE_DIR, city_cfg["dir"], rel_file)

                if os.path.exists(target_file) and os.path.isfile(target_file):
                    mime, _ = mimetypes.guess_type(target_file)
                    if not mime:
                        mime = 'application/octet-stream'
                    if target_file.endswith('.json'):
                        mime = 'application/json'

                    with open(target_file, 'rb') as f:
                        body = f.read()

                    etag = f'"{hashlib.md5(body).hexdigest()[:16]}"'
                    client_etag = self.headers.get('If-None-Match')

                    if client_etag and client_etag.strip() == etag:
                        self.send_response(304)
                        self.end_headers()
                        return

                    use_gzip = 'gzip' in self.headers.get('Accept-Encoding', '') and len(body) > 1024
                    if use_gzip:
                        body = gzip.compress(body, compresslevel=6)

                    self.send_response(200)
                    self.send_header('Content-Type', mime)
                    if use_gzip:
                        self.send_header('Content-Encoding', 'gzip')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('ETag', etag)
                    self.send_header('Cache-Control', 'no-cache, public')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'404 Not Found')
                    return

        # 404 for unknown routes
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'404 Not Found')

def main():
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"

    print("=" * 65)
    print(f"NATIONAL EV GRID - UNIFIED CLOUD ENGINE (PORT {port})")
    print("=" * 65)

    # Launch background daemons for each city with staggered start
    for i, c in enumerate(CITIES):
        t = threading.Thread(target=run_city_daemon, args=(c, i * 4), daemon=True)
        t.start()

    server = ThreadingHTTPServer((host, port), UnifiedRouterHandler)
    print(f"🚀 Unified National Service active at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down unified service cleanly...")
        server.server_close()

if __name__ == "__main__":
    main()
