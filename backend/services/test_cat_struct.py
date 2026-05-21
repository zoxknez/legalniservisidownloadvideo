import json
from hrti_auth import HRTIAuth

def main():
    auth = HRTIAuth()
    try:
        auth.login("anonymoushrt", "an0nPasshrt")
        print("Login success.")
        
        # GetCatalogueStructure
        resp = auth.session.post(
            f"{auth.hrtiDomain if hasattr(auth, 'hrtiDomain') else 'https://hrti.hrt.hr'}/api/api/ott/GetCatalogueStructure",
            json={},
            headers=auth._api_headers(),
            timeout=15
        )
        resp.raise_for_status()
        res = resp.json()
        print("Keys of response:", list(res.keys()))
        if res.get("ErrorCode") == 0:
            result = res.get("Result", [])
            print(f"Result count: {len(result)}")
            # Let's save the catalog structure to a temp file for inspection
            with open("cat_struct.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("Catalogue structure saved to cat_struct.json")
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
