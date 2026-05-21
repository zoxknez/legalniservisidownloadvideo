import json
from hrti_auth import HRTIAuth

def main():
    auth = HRTIAuth()
    try:
        auth.login("anonymoushrt", "an0nPasshrt")
        print("Login success.")
        
        # GetCatalogue for krimići
        payload = {
            "ReferenceId": "krimići",
            "ItemsPerPage": 10,
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
        items = cat.get("Items", [])
        print(f"Krimići items count: {len(items)}")
        
        series_uuid = None
        for item in items:
            series_data = item.get("SeriesData")
            # If SeriesData is present and not empty
            if series_data:
                series_uuid = item.get("ReferenceId")
                print(f"Found series: {item.get('Title')} (UUID: {series_uuid})")
                print("SeriesData keys:", list(series_data.keys()))
                break
                
        if series_uuid:
            # GetSeasons
            payload = {"SeriesReferenceId": series_uuid}
            resp = auth.session.post(
                "https://hrti.hrt.hr/api/api/ott/GetSeasons",
                json=payload,
                headers=auth._api_headers(),
                timeout=15
            )
            resp.raise_for_status()
            seasons = resp.json().get("Result", [])
            print(f"Seasons count: {len(seasons)}")
            if seasons:
                print("First season:", seasons[0])
                season_uuid = seasons[0].get("ReferenceId")
                
                # GetEpisodes
                payload = {
                    "SeriesReferenceId": series_uuid,
                    "SeasonReferenceId": season_uuid
                }
                resp = auth.session.post(
                    "https://hrti.hrt.hr/api/api/ott/GetEpisodes",
                    json=payload,
                    headers=auth._api_headers(),
                    timeout=15
                )
                resp.raise_for_status()
                episodes = resp.json().get("Result", [])
                print(f"Episodes count: {len(episodes)}")
                if episodes:
                    print("First episode keys:", list(episodes[0].keys()))
                    print("First episode Title:", episodes[0].get("Title"))
                    print("First episode ReferenceId:", episodes[0].get("ReferenceId"))
                    
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
