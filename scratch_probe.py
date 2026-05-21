import requests
import socket
import urllib.parse

domains = [
    "rtsplaneta.rs",
    "api.rtsplaneta.rs",
    "rts-api.morescreens.com",
    "rts.morescreens.com",
    "rtsplaneta.morescreens.com",
    "rtsplaneta-api.morescreens.com",
    "rts-ott.morescreens.com",
    "rtsplaneta-ott.morescreens.com",
    "rts-live.morescreens.com",
    "spectar.tv",
    "api.spectar.tv",
    "rts.spectar.tv",
    "rtsplaneta.spectar.tv"
]

paths = [
    "/api/api/ott/getIPAddress",
    "/api/ott/getIPAddress",
    "/ott/getIPAddress",
    "/api/getIPAddress",
    "/client.svc/json/RegisterDevice"
]

for domain in domains:
    print(f"--- Probing {domain} ---")
    try:
        ip = socket.gethostbyname(domain)
        print(f"Resolved to {ip}")
    except socket.gaierror:
        print("DNS resolution failed")
        continue

    for path in paths:
        url = f"https://{domain}{path}"
        try:
            # Let's send a simple GET or POST request
            # For getIPAddress it's a GET in HRTi. Let's do a GET first
            resp = requests.get(url, timeout=5)
            print(f"GET {path} -> {resp.status_code}")
            if resp.status_code == 200:
                print(f"  Response: {resp.text[:100]}")
            # If 405, let's try POST
            if resp.status_code == 405 or path == "/client.svc/json/RegisterDevice":
                resp_p = requests.post(url, json={}, timeout=5)
                print(f"POST {path} -> {resp_p.status_code}")
                if resp_p.status_code == 200:
                    print(f"  Response: {resp_p.text[:100]}")
        except Exception as e:
            print(f"Request to {url} failed: {e}")
