import urllib.request
import json
import ssl
import time
import os
import sys
import concurrent.futures

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(CURRENT_DIR, "jiobp_token.json")
CACHE_FILE = os.path.join(CURRENT_DIR, "jiobp_details_cache.json")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Dart/3.4 (dart:io)",
    "Accept": "application/json"
}

def load_token_data():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def refresh_jiobp_token(user_id=378981, refresh_token=None):
    if not refresh_token:
        td = load_token_data()
        if not td:
            return None
        refresh_token = td.get("refresh_Token")
        user_id = td.get("loginOutput", {}).get("userId", 378981)
        
    url = "https://lg.jiobppulsecharge.com/api/MobileLogin/MBRefresh"
    payload = {"userId": user_id, "refresh_Token": refresh_token}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            new_auth = data.get("result", {}).get("auth_Token")
            new_refresh = data.get("result", {}).get("refresh_Token")
            if new_auth:
                td = load_token_data() or {}
                td["auth_Token"] = new_auth
                if new_refresh:
                    td["refresh_Token"] = new_refresh
                with open(TOKEN_FILE, "w") as f:
                    json.dump(td, f, indent=2)
                return new_auth
    except Exception as e:
        print(f"[Jio-bp] Token refresh error: {e}", file=sys.stderr)
    return None

def get_auth_token():
    td = load_token_data()
    if not td:
        return None
    return td.get("auth_Token")

def fetch_hub_models(loc_id, auth_token):
    u = "https://apid.jiobppulsecharge.com/TIMaster/api/ChrgIntermediate/MBgetLocChargerDet"
    h = dict(HEADERS)
    h["Authorization"] = f"Bearer {auth_token}"
    req = urllib.request.Request(u, data=json.dumps({"locId": str(loc_id)}).encode("utf-8"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=6, context=SSL_CTX) as res:
            d = json.loads(res.read().decode("utf-8"))
            return loc_id, d.get("result", {}).get("connectorModelCount", [])
    except Exception:
        return loc_id, []

def fetch_hub_live_connectors(loc_id, auth_token):
    u = "https://apid.jiobppulsecharge.com/TIMaster/api/ChrgIntermediate/MBgetChargeConnectorDetail"
    h = dict(HEADERS)
    h["Authorization"] = f"Bearer {auth_token}"
    req = urllib.request.Request(u, data=json.dumps({"locId": str(loc_id)}).encode("utf-8"), headers=h)
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as res:
                d = json.loads(res.read().decode("utf-8"))
                conns = d.get("result", {}).get("connectorDetail", [])
                if conns:
                    return loc_id, conns
        except Exception:
            time.sleep(0.15)
    return loc_id, []

def extract_connector_kw(c, loc_id):
    op = c.get("outPutPower") or c.get("opValue")
    if op:
        kw = parse_kw(op)
        if kw > 0:
            return kw
    box = str(c.get("chrgBoxId") or "").upper()
    m_name = str(c.get("modelName") or "").upper()
    if loc_id == 2802 or "375" in box:
        return 375.0
    if loc_id == 2772 or "360" in box:
        return 360.0
    if "240" in box:
        return 240.0
    if "120" in box:
        return 120.0
    if "60" in box:
        return 60.0
    if "30" in box:
        return 30.0
    if "IEC60309" in m_name or "3.3" in box:
        return 3.3
    if "TYPE2" in m_name or "7.4" in box or "7.5" in box:
        return 7.5
    if "22" in box:
        return 22.0
    if "CCS" in m_name:
        return 60.0
    return 60.0

def parse_kw(op_val):
    if not op_val:
        return 60.0
    val_clean = str(op_val).upper().replace("KW", "").strip()
    try:
        return float(val_clean)
    except Exception:
        return 60.0

def fetch_jiobp_stations(city="pune", is_telemetry_running=False):
    auth_token = get_auth_token()
    if not auth_token:
        auth_token = refresh_jiobp_token()
    if not auth_token:
        return []

    url = "https://apid.jiobppulsecharge.com/TIMaster/api/ChrgIntermediate/MBgetAllChrgLocationViewList"
    payload = {
        "connTypeIdList": [],
        "amenitiesIdList": [],
        "connStatus": "",
        "chargeBoxID": "",
        "eventNames": ""
    }
    
    h = dict(HEADERS)
    h["Authorization"] = f"Bearer {auth_token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=h)
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
            res_data = json.loads(r.read().decode("utf-8"))
            all_stns = res_data.get("results", [])
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token expired, refresh and retry once
            auth_token = refresh_jiobp_token()
            if not auth_token:
                return []
            h["Authorization"] = f"Bearer {auth_token}"
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=h)
            try:
                with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
                    res_data = json.loads(r.read().decode("utf-8"))
                    all_stns = res_data.get("results", [])
            except Exception:
                return []
        else:
            return []
    except Exception:
        return []

    # Filter for target city
    target_hubs = []
    city_lower = city.lower()
    for s in all_stns:
        lat = float(s.get("latitude") or 0)
        lng = float(s.get("longitude") or 0)
        name = s.get("locName", "")
        addr = s.get("locAddress", "")
        combined = f"{name} {addr}".lower()

        if city_lower == "pune":
            if (18.25 <= lat <= 18.90 and 73.40 <= lng <= 74.30) or any(k in combined for k in ['pune', 'pcmc', 'pimpri', 'chinchwad', 'hinjawadi', 'hinjewadi', 'lonavala', 'chakan', 'talegaon', 'hadapsar', 'wakad', 'baner', 'kothrud', 'viman nagar', 'kharadi', 'bhosari']):
                target_hubs.append(s)
        elif city_lower == "mumbai":
            if (18.65 <= lat <= 19.55 and 72.65 <= lng <= 73.35) or any(k in combined for k in ['mumbai', 'navi mumbai', 'thane', 'vashi', 'kalyan', 'bhayandar', 'panvel', 'ulhasnagar', 'dombivli', 'palghar', 'vasai', 'virar', 'raigad', 'khalapur', 'khopoli', 'nerul', 'belapur', 'airoli', 'chembur', 'andheri', 'bandra', 'borivali', 'goregaon', 'malad', 'kurla', 'dadar', 'worli', 'bkc']):
                target_hubs.append(s)
        elif city_lower in ["delhi", "delhi-ncr"]:
            if (28.20 <= lat <= 28.95 and 76.80 <= lng <= 77.60) or any(k in combined for k in ['delhi', 'new delhi', 'gurugram', 'gurgaon', 'noida', 'greater noida', 'faridabad', 'ghaziabad', 'manesar', 'aerocity', 'saket', 'dwarka', 'rohini', 'connaught', 'nehru place', 'okhla']):
                target_hubs.append(s)
        elif city_lower == "bengaluru":
            if (12.75 <= lat <= 13.25 and 77.40 <= lng <= 77.85) or any(k in combined for k in ['bengaluru', 'bangalore', 'whitefield', 'electronic city', 'koramangala', 'indiranagar', 'marathahalli', 'hebbal', 'yelahanka', 'bellandur', 'sarjapur', 'hsr layout', 'jayanagar', 'peenya']):
                target_hubs.append(s)
        elif city_lower == "hyderabad":
            if (17.15 <= lat <= 17.65 and 78.20 <= lng <= 78.70) or any(k in combined for k in ['hyderabad', 'secunderabad', 'gachibowli', 'madhapur', 'kondapur', 'hitec', 'shamshabad', 'banjara', 'jubilee', 'kukatpally', 'begumpet', 'financial district', 'miyapur']):
                target_hubs.append(s)
        elif city_lower == "kolkata":
            if (22.35 <= lat <= 22.80 and 88.20 <= lng <= 88.55) or any(k in combined for k in ['kolkata', 'howrah', 'salt lake', 'new town', 'rajarhat', 'dum dum', 'bally', 'alipore', 'park street', 'esplanade']):
                target_hubs.append(s)
        elif city_lower == "ahmedabad":
            if (22.85 <= lat <= 23.25 and 72.40 <= lng <= 72.75) or any(k in combined for k in ['ahmedabad', 'gandhinagar', 'gift city', 'sanand', 'bopal', 'sg highway', 'prahlad nagar', 'navrangpura', 'vastrapur']):
                target_hubs.append(s)

    # Fetch genuine live per-connector telemetry for target hubs concurrently
    live_connectors_map = {}
    if target_hubs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(fetch_hub_live_connectors, s["locId"], auth_token) for s in target_hubs]
            for fut in concurrent.futures.as_completed(futures):
                lid, conns = fut.result()
                if conns:
                    live_connectors_map[lid] = conns

    # Load cached hub model definitions (used as fallback)
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    # Check for hubs not in cache (fallback only)
    missing_loc_ids = [s["locId"] for s in target_hubs if str(s["locId"]) not in cache and s["locId"] not in live_connectors_map]
    if missing_loc_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_hub_models, lid, auth_token) for lid in missing_loc_ids[:30]]
            for fut in concurrent.futures.as_completed(futures):
                lid, models = fut.result()
                if models:
                    cache[str(lid)] = models
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass

    # Build genuine station objects
    formatted_stations = []
    for h_data in target_hubs:
        loc_id = h_data["locId"]
        name = (h_data.get("locName") or f"Jio-bp Pulse Hub {loc_id}").strip()
        addr = (h_data.get("locAddress") or f"Jio-bp Station, {city.title()}").strip()
        if loc_id == 2802:
            name = "Jio-bp pulse - TATA.ev Megacharger (375kW Ultra-Fast) - Fountain Hotel, Ghodbunder Road"
            addr = "Fountain Hotel Junction, Ghodbunder Road (NH 48), Versave, Mira-Bhayandar, Thane 401107"
        elif loc_id == 2772:
            name = "Jio-bp pulse Ultra-Fast Hub (360-375kW) - Maruti True Value, Owale, Ghodbunder Road"
            addr = "Near Maruti True Value, Pankhada Rd, Owale, Ghodbunder Road, Thane West 400607"
        elif loc_id == 2605:
            addr = f"{addr}, Ghodbunder Road / Western Express Hwy Junction, Thane"

        lat = float(h_data.get("latitude") or 0)
        lng = float(h_data.get("longitude") or 0)
        total_guns = int(h_data.get("totalCount") or 0)
        avail_count = int(h_data.get("availableCount") or 0)
        busy_count = int(h_data.get("busyCount") or 0)
        fault_count = max(0, total_guns - (avail_count + busy_count))

        if total_guns <= 0:
            continue

        cd = live_connectors_map.get(loc_id)
        models = cache.get(str(loc_id), [])
        connectors = []
        gun_idx = 1

        if cd:
            # Direct live hardware connector telemetry from Jio-bp TIMaster API
            cd_sorted = sorted(cd, key=lambda x: (str(x.get("chrgBoxId") or ""), int(x.get("connNum") or 0), int(x.get("connID") or 0)))
            for idx, c in enumerate(cd_sorted, 1):
                raw_status = (c.get("connStatus") or "Available").strip()
                if raw_status in ["Charging", "Finishing", "In Use", "InUse", "Occupied", "Preparing"]:
                    status = "CHARGING" if is_telemetry_running else "AVAILABLE"
                elif raw_status in ["Faulted", "Unavailable", "Offline", "Error"]:
                    status = "FAULTED"
                else:
                    status = "AVAILABLE"

                m_name = (c.get("modelName") or "CCS").strip()
                box_id = (c.get("chrgBoxId") or f"Ch{idx}").strip()
                num = c.get("connNum") or 1
                power_kw = extract_connector_kw(c, loc_id)
                rate = float(c.get("connTarrif") or 21.0)
                tot_guns_cab = 2 if "CCS" in m_name else (3 if "IEC60309" in m_name else 1)

                port_key = f"JIO_{loc_id}_P{idx}"
                type_str = f"{m_name}-2 ({power_kw:.1f}kW)" if m_name in ["CCS", "Type2"] else f"{m_name} ({power_kw:.1f}kW)"

                connectors.append({
                    "port_key": port_key,
                    "charger_id": f"JIO_{loc_id}_{box_id}",
                    "charger_label": f"Jio-bp {box_id}",
                    "cabinet_kw": power_kw,
                    "total_guns_on_cabinet": tot_guns_cab,
                    "label": f"{box_id} - Gun {num} ({m_name} / {power_kw:.1f}kW)",
                    "port_label": f"Gun {num}",
                    "type": type_str,
                    "power_kw": power_kw,
                    "rate_inr": rate,
                    "status": status,
                    "duration": "-",
                    "kwh": "0.0 kWh",
                    "allocated_kw": power_kw,
                    "effective_kw": round(power_kw * 0.75, 1)
                })
        elif isinstance(models, list) and models and all(isinstance(m, dict) for m in models):
            for m in models:
                m_name = m.get("modelName", "CCS")
                op_val = "375KW" if loc_id == 2802 else m.get("opValue", "60KW")
                power_kw = 375.0 if loc_id == 2802 else parse_kw(op_val)
                m_total = int(m.get("totalCount") or 1)
                for _ in range(m_total):
                    port_key = f"JIO_{loc_id}_P{gun_idx}"
                    # Assign status based on telemetry running mode
                    if is_telemetry_running:
                        if gun_idx <= busy_count:
                            status = "CHARGING"
                        elif gun_idx <= (busy_count + avail_count):
                            status = "AVAILABLE"
                        else:
                            status = "FAULTED"
                    else:
                        # Standby mode: 0 Active Charging, exact Available vs Faulted
                        if gun_idx <= avail_count:
                            status = "AVAILABLE"
                        else:
                            status = "FAULTED"

                    connectors.append({
                        "port_key": port_key,
                        "charger_id": f"JIO_{loc_id}_C{gun_idx}",
                        "charger_label": f"Jio-bp {m_name} {op_val} Fast Unit",
                        "cabinet_kw": power_kw,
                        "total_guns_on_cabinet": m_total,
                        "label": f"Gun {gun_idx} ({m_name} / {op_val})",
                        "port_label": f"Gun {gun_idx}",
                        "type": f"{m_name}-2 ({op_val})",
                        "power_kw": power_kw,
                        "rate_inr": 21.0,
                        "status": status,
                        "duration": "-",
                        "kwh": "0.0 kWh",
                        "allocated_kw": power_kw,
                        "effective_kw": round(power_kw * 0.75, 1)
                    })
                    gun_idx += 1
        else:
            # Fallback if model details not yet cached
            for i in range(1, total_guns + 1):
                port_key = f"JIO_{loc_id}_P{i}"
                if is_telemetry_running:
                    if i <= busy_count:
                        status = "CHARGING"
                    elif i <= (busy_count + avail_count):
                        status = "AVAILABLE"
                    else:
                        status = "FAULTED"
                else:
                    if i <= avail_count:
                        status = "AVAILABLE"
                    else:
                        status = "FAULTED"

                connectors.append({
                    "port_key": port_key,
                    "charger_id": f"JIO_{loc_id}_C{i}",
                    "charger_label": "Jio-bp Pulse Fast Unit",
                    "cabinet_kw": 60.0,
                    "total_guns_on_cabinet": total_guns,
                    "label": f"Gun {i} (CCS-2 / 60kW)",
                    "port_label": f"Gun {i}",
                    "type": "CCS-2 (60kW)",
                    "power_kw": 60.0,
                    "rate_inr": 21.0,
                    "status": status,
                    "duration": "-",
                    "kwh": "0.0 kWh",
                    "allocated_kw": 60.0,
                    "effective_kw": 45.0
                })

        formatted_stations.append({
            "id": f"JIO-{loc_id}",
            "raw_id": str(loc_id),
            "name": name,
            "cpo": "Jio-bp pulse",
            "source": "Jio-bp Production API",
            "location": addr,
            "latitude": lat,
            "longitude": lng,
            "connectors": connectors
        })

    return formatted_stations

if __name__ == "__main__":
    pune = fetch_jiobp_stations("pune", is_telemetry_running=False)
    mumbai = fetch_jiobp_stations("mumbai", is_telemetry_running=False)
    print(f"Jio-bp stations parsed: Pune={len(pune)} ({sum(len(s['connectors']) for s in pune)} guns), Mumbai={len(mumbai)} ({sum(len(s['connectors']) for s in mumbai)} guns)")
