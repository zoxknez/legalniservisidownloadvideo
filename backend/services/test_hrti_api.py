import json
import urllib.request
import urllib.error
import uuid

class HRTiProber:
    def __init__(self):
        self.hrtiDomain = "https://hrti.hrt.hr"
        self.webapiurl = "api/api/ott"
        self.DEVICE_ID = str(uuid.uuid4())
        self.TOKEN = ""
        self.IP = "127.0.0.1"

    def api_post(self, url, payload):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'connection': 'keep-alive',
                'deviceid': self.DEVICE_ID,
                'operatorreferenceid': 'hrt',
                'authorization': 'Client ' + self.TOKEN,
                'ipaddress': str(self.IP),
                'content-type': 'application/json',
                'accept': 'application/json, text/plain, */*',
                'user-agent': 'kodi plugin for hrti.hrt.hr (python)',
                'devicetypeid': '6',
                'origin': self.hrtiDomain,
            },
            method='POST'
        )
        try:
            with urllib.request.urlopen(req) as res:
                resp = json.loads(res.read().decode('utf-8'))
                return resp
        except urllib.error.HTTPError as e:
            return {"http_error": e.code, "message": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def grant_access(self):
        url = f"{self.hrtiDomain}/{self.webapiurl}/GrantAccess"
        payload = {
            "Username": "anonymoushrt",
            "Password": "an0nPasshrt",
            "OperatorReferenceId": "hrt"
        }
        res = self.api_post(url, payload)
        if res and res.get("ErrorCode") == 0:
            self.TOKEN = res.get("Result", {}).get("Token")
            print("Access granted.")
            return True
        return False

def run_probe():
    prober = HRTiProber()
    if not prober.grant_access():
        print("Failed to grant access")
        return

    # Probe 2: Try Search endpoint with different payloads
    url_search = f"{prober.hrtiDomain}/{prober.webapiurl}/Search"
    payloads = [
        {"SearchTerm": "film", "ItemsPerPage": 5, "PageNumber": 1},
        {"Query": "film", "ItemsPerPage": 5, "PageNumber": 1},
        {"Value": "film", "ItemsPerPage": 5, "PageNumber": 1},
        {"SearchQuery": "film"},
        {"SearchString": "film"},
    ]
    for i, payload in enumerate(payloads):
        print(f"\nProbing Search payload option {i+1}: {payload}...")
        res = prober.api_post(url_search, payload)
        result = res.get("Result")
        print(f"Result type: {type(result)}")
        if isinstance(result, list):
            print(f"Result list length: {len(result)}")
            if len(result) > 0:
                print("First element type:", type(result[0]))
                print("First element keys:", list(result[0].keys()) if isinstance(result[0], dict) else "not dict")
                if isinstance(result[0], dict):
                    print("First element Title:", result[0].get("Title"))
                    print("First element RefId:", result[0].get("ReferenceId"))
        else:
            print("Result:", result)

if __name__ == '__main__':
    run_probe()
