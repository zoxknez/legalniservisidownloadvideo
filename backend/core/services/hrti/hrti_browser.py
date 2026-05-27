#!/usr/bin/env python3
"""
HRTI (hrti.hrt.hr) Content Browser
Lists categories, category items, search results, and series episodes.
"""

import argparse
import logging
import sys
from typing import Dict, List, Optional, Any

from hrti_auth import HRTIAuth

logger = logging.getLogger(__name__)

def get_item_type(item: Dict) -> str:
    # Check if the item has SeriesData or is Type 0/3 (3 is series)
    if item.get("SeriesData"):
        return "series"
    if item.get("EpisodeData"):
        return "episode"
    return "movie"

def main():
    parser = argparse.ArgumentParser(description="HRTI (hrti.hrt.hr) Content Browser")
    parser.add_argument("--list", action="store_true", help="List all categories")
    parser.add_argument("--cat", help="List items in a category (ReferenceId)")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--search", help="Search by query")
    parser.add_argument("--series", help="List episodes in a series (Series UUID)")
    parser.add_argument("-u", "--username")
    parser.add_argument("-p", "--password")
    
    args = parser.parse_args()
    
    # Configure UTF-8 stdout if needed (prevent cp1252 crash on Windows)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        
    auth = HRTIAuth()
    
    # Try to login:
    u, p = args.username, args.password
    if not u or not p:
        u, p = auth.get_stored_credentials()
    if not u or not p:
        u, p = "anonymoushrt", "an0nPasshrt"
        
    try:
        auth.login(u, p)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)
        
    if args.list:
        try:
            resp = auth.session.post(
                "https://hrti.hrt.hr/api/api/ott/GetCatalogueStructure",
                json={},
                headers=auth._api_headers(),
                timeout=15
            )
            resp.raise_for_status()
            res = resp.json()
            if res.get("ErrorCode", -1) != 0:
                raise Exception(res.get("ErrorDescription", "Unknown error"))
                
            categories = res.get("Result", [])
            
            # Print categories in tree structure
            def print_tree(items, indent=0):
                for item in items:
                    name = item.get("Name", "")
                    ref_id = item.get("ReferenceId", "")
                    children = item.get("Children", [])
                    if children:
                        print(" " * indent + f"{name}:")
                        print_tree(children, indent + 2)
                    else:
                        print(" " * indent + f"- {ref_id}")
            print_tree(categories)
            
        except Exception as e:
            print(f"Failed to fetch catalogue structure: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.cat:
        try:
            cat = auth.get_catalogue(category_id=args.cat, page=args.page, page_size=24)
            items = cat.get("Items", [])
            total_items = cat.get("NumberOfItems", 0)
            total_pages = (total_items + 23) // 24 if total_items > 0 else 1
            
            print(f"{args.cat}  [{total_items} stavki, stranica {args.page}/{total_pages}]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for item in items:
                ref_id = item.get("ReferenceId", "")
                title = item.get("Title", "")
                t_type = get_item_type(item)
                print(f"  {ref_id:<36} {t_type:<8} {title}")
                
        except Exception as e:
            print(f"Failed to fetch category {args.cat}: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.search:
        try:
            payload = {
                "Query": args.search,
                "PageNumber": 1,
                "ItemsPerPage": 100
            }
            resp = auth.session.post(
                "https://hrti.hrt.hr/api/api/ott/Search",
                json=payload,
                headers=auth._api_headers(),
                timeout=15
            )
            resp.raise_for_status()
            items = resp.json().get("Result", [])
            total_items = len(items)
            
            print(f"Pretraga: {args.search}  [{total_items} stavki, stranica 1/1]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for item in items:
                ref_id = item.get("ReferenceId", "")
                title = item.get("Title", "")
                t_type = get_item_type(item)
                print(f"  {ref_id:<36} {t_type:<8} {title}")
                
        except Exception as e:
            print(f"Failed to search for {args.search}: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.series:
        try:
            payload = {"SeriesReferenceId": args.series}
            resp = auth.session.post(
                "https://hrti.hrt.hr/api/api/ott/GetSeasons",
                json=payload,
                headers=auth._api_headers(),
                timeout=15
            )
            resp.raise_for_status()
            seasons = resp.json().get("Result", [])
            
            episodes = []
            for season in seasons:
                season_uuid = season.get("ReferenceId")
                payload_ep = {
                    "SeriesReferenceId": args.series,
                    "SeasonReferenceId": season_uuid
                }
                resp_ep = auth.session.post(
                    "https://hrti.hrt.hr/api/api/ott/GetEpisodes",
                    json=payload_ep,
                    headers=auth._api_headers(),
                    timeout=15
                )
                resp_ep.raise_for_status()
                episodes.extend(resp_ep.json().get("Result", []))
                
            total_items = len(episodes)
            print(f"Serija {args.series}  [{total_items} stavki, stranica 1/1]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for ep in episodes:
                ref_id = ep.get("ReferenceId", "")
                title = ep.get("Title", "")
                print(f"  {ref_id:<36} {'episode':<8} {title}")
                
        except Exception as e:
            print(f"Failed to list series {args.series}: {e}", file=sys.stderr)
            sys.exit(1)
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
