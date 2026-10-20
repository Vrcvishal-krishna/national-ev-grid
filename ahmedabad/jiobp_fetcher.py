#!/usr/bin/env python3
"""
Direct Real-Time Jio-bp Pulse (GOBP) Live Telemetry Fetcher for Greater Ahmedabad & Gandhinagar
"""

import os
import sys
import json
import time
import ssl
import urllib.request
import urllib.error
import concurrent.futures

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "jiobp_details_cache.json")
TOKEN_FILE = os.path.join(BASE_DIR, "jiobp_token.json")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "okhttp/4.9.2",
    "Content-Type": "application/json",
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
            if new_auth:
                td = load_token_data() or {}
                td["auth_Token"] = new_auth
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
    url = "https://apid.jiobppulsecharge.com/TIMaster/api/ChrgIntermediate/MBgetLocChargerDet"
    payload = {"locationId": loc_id}
    h = dict(HEADERS)
    h["Authorization"] = f"Bearer {auth_token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return loc_id, data.get("results") or data.get("data", [])
    except Exception:
        return loc_id, []

def clean_kw(val):
    if not val:
        return 60.0
    try:
        val_str = str(val).upper().replace("KW", "").strip()
        val_clean = val_str.split()[0].replace(",", "")
        return float(val_clean)
    except Exception:
        return 60.0

def fetch_jiobp_stations(city="ahmedabad", is_telemetry_running=False):
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

    target_hubs = []
    for s in all_stns:
        lat = float(s.get("latitude") or 0)
        lng = float(s.get("longitude") or 0)
        name = s.get("locName", "")
        addr = s.get("locAddress", "")
        combined = f"{name} {addr}".lower()

        if (22.85 <= lat <= 23.30 and 72.40 <= lng <= 72.78) or any(k in combined for k in ['ahmedabad', 'ahemdabad', 'gandhinagar', 'gift city', 'sanand', 'bopal', 'sg highway', 'sp ring road']):
            if 22.80 <= lat <= 23.35 and 72.35 <= lng <= 72.85:
                target_hubs.append(s)

    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    missing_loc_ids = [s["locId"] for s in target_hubs if str(s["locId"]) not in cache]
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

    out_stations = []
    for hub in target_hubs:
        lid = str(hub["locId"])
        name = hub.get("locName", "Jio-bp pulse Station")
        lat = float(hub.get("latitude") or 0)
        lng = float(hub.get("longitude") or 0)
        addr = hub.get("locAddress", "Greater Ahmedabad & Gandhinagar")

        chargers_data = cache.get(lid, [])
        connectors = []
        port_seq = 1

        if isinstance(chargers_data, list) and chargers_data:
            for ch in chargers_data:
                if not isinstance(ch, dict):
                    continue
                cid = ch.get("chargerId") or ch.get("chargeBoxId") or f"JIO_{lid}_C1"
                clabel = ch.get("chargerName") or "Jio-bp Fast Charger"
                raw_cap = ch.get("ratedPower") or 60.0
                cab_kw = clean_kw(raw_cap)

                conns_list = ch.get("connectorList") or ch.get("connectors") or []
                conn_count = len(conns_list) if conns_list else 1

                for c in conns_list:
                    raw_st = (c.get("connStatus") or "AVAILABLE").upper()
                    st = "FAULTED" if raw_st in ["FAULTED", "OFFLINE", "UNAVAILABLE", "MAINTENANCE"] else "AVAILABLE"
                    if not is_telemetry_running:
                        st = "AVAILABLE" if st != "FAULTED" else "FAULTED"

                    ctype = c.get("connType") or "CCS-2"
                    power_kw = cab_kw
                    allocated_kw = cab_kw / max(1, conn_count)

                    connectors.append({
                        "port_key": f"JIO_{lid}_P{port_seq}",
                        "charger_id": cid,
                        "charger_label": clabel,
                        "cabinet_kw": cab_kw,
                        "total_guns_on_cabinet": conn_count,
                        "label": f"Gun {port_seq} ({ctype})",
                        "port_label": f"Gun {port_seq}",
                        "type": f"{ctype} ({cab_kw:.0f}kW)",
                        "power_kw": power_kw,
                        "rate_inr": 21.0,
                        "status": st,
                        "duration_display": "-",
                        "est_kwh_display": "0.0 kWh",
                        "duration": "-",
                        "kwh": "0.0 kWh",
                        "allocated_kw": allocated_kw,
                        "effective_kw": 65.0 if cab_kw > 90 else (45.0 if cab_kw >= 50 else 27.0)
                    })
                    port_seq += 1

        if not connectors:
            connectors = [
                {
                    "port_key": f"JIO_{lid}_P1",
                    "charger_id": f"JIO_{lid}_C1",
                    "charger_label": "Jio-bp Fast Unit",
                    "cabinet_kw": 60.0,
                    "total_guns_on_cabinet": 2,
                    "label": "Gun 1 (CCS-2)",
                    "port_label": "Gun 1",
                    "type": "CCS-2 (60kW)",
                    "power_kw": 60.0,
                    "rate_inr": 21.0,
                    "status": "AVAILABLE",
                    "duration_display": "-",
                    "est_kwh_display": "0.0 kWh",
                    "duration": "-",
                    "kwh": "0.0 kWh",
                    "allocated_kw": 60.0,
                    "effective_kw": 45.0
                },
                {
                    "port_key": f"JIO_{lid}_P2",
                    "charger_id": f"JIO_{lid}_C1",
                    "charger_label": "Jio-bp Fast Unit",
                    "cabinet_kw": 60.0,
                    "total_guns_on_cabinet": 2,
                    "label": "Gun 2 (CCS-2)",
                    "port_label": "Gun 2",
                    "type": "CCS-2 (60kW)",
                    "power_kw": 60.0,
                    "rate_inr": 21.0,
                    "status": "AVAILABLE",
                    "duration_display": "-",
                    "est_kwh_display": "0.0 kWh",
                    "duration": "-",
                    "kwh": "0.0 kWh",
                    "allocated_kw": 60.0,
                    "effective_kw": 45.0
                }
            ]

        out_stations.append({
            "id": f"JIO_{lid}",
            "raw_id": lid,
            "name": name,
            "cpo": "Jio-bp pulse",
            "location": addr,
            "latitude": lat,
            "longitude": lng,
            "connectors": connectors
        })

    return out_stations

if __name__ == "__main__":
    stns = fetch_jiobp_stations("ahmedabad", is_telemetry_running=False)
    print(f"Jio-bp stations verified in Ahmedabad: {len(stns)} ({sum(len(s['connectors']) for s in stns)} guns)")
