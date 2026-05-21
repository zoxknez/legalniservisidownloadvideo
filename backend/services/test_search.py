import json
from hrti_auth import HRTIAuth

def main():
    auth = HRTIAuth()
    try:
        auth.login("anonymoushrt", "an0nPasshrt")
        print("Login success.")
        
        # Search
        payload = {
            "Query": "Simona",
            "PageNumber": 1,
            "ItemsPerPage": 24
        }
        resp = auth.session.post(
            "https://hrti.hrt.hr/api/api/ott/Search",
            json=payload,
            headers=auth._api_headers(),
            timeout=15
        )
        resp.raise_for_status()
        result = resp.json().get("Result", [])
        print("Result is a list of length:", len(result))
        if result:
            print("First item keys:", list(result[0].keys()))
            print("First item sample:")
            print(json.dumps(result[0], indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
