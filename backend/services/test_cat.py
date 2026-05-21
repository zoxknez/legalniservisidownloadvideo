import json
from hrti_auth import HRTIAuth

def main():
    auth = HRTIAuth()
    try:
        auth.login("anonymoushrt", "an0nPasshrt")
        print("Login success.")
        
        # Call GetCatalogue manually with ReferenceId and ItemsPerPage
        payload = {
            "ReferenceId": "domaći_filmovi",
            "ItemsPerPage": 5,
            "PageNumber": 1,
        }
        resp = auth.session.post(
            "https://hrti.hrt.hr/api/api/ott/GetCatalogue",
            json=payload,
            headers=auth._api_headers(),
            timeout=15
        )
        resp.raise_for_status()
        cat = resp.json().get("Result", {})
        print("Keys of catalogue result:", list(cat.keys()))
        items = cat.get("Items", [])
        print(f"Items count: {len(items)}")
        if items:
            print("First item keys:", list(items[0].keys()))
            print("First item sample:")
            print(json.dumps(items[0], indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
