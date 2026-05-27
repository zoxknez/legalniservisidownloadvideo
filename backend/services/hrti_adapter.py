import os
import re
import sys
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.config import config

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()

class HrtiAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        """Check if HRTi has credentials saved (no network calls, no subprocess)."""
        cfg_path = Path.home() / ".hrti" / "config.json"

        # Check native HRTi config file first
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    h_email = data.get("email") or data.get("username", "")
                    if h_email:
                        return {"authenticated": True, "email": h_email}
            except Exception:
                pass

        # Fall back to checking app config credentials (no network call)
        app_creds = config.get_credentials("hrti")
        email = app_creds.get("email", "")
        password = app_creds.get("password", "")

        if email and password:
            return {"authenticated": True, "email": email}

        return {"authenticated": False, "email": "", "error": "No credentials stored"}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        """Save HRTi credentials."""
        try:
            # Save via subprocess with timeout to prevent event loop blocking
            res = subprocess.run(
                ["python", "hrti_downloader.py", "--save-credentials", "-u", email, "-p", password],
                cwd=str(CWD.resolve()),
                capture_output=True,
                text=True,
                timeout=30
            )
            if res.returncode == 0:
                # Sync in app config too
                config.update_credentials("hrti", {"email": email, "password": password})
                return {"success": True}
            return {"success": False, "error": res.stderr or res.stdout}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout — HRTi skripta nije odgovorila u roku od 30s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _run_browser(args: List[str]) -> str:
        """Helper to run hrti_browser.py and return output."""
        try:
            res = subprocess.run(
                ["python", "hrti_browser.py"] + args,
                cwd=str(CWD.resolve()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60
            )
            return res.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"hrti_browser.py timeout with args {args}")
            return ""
        except Exception as e:
            logger.error(f"Error running hrti_browser with args {args}: {e}")
            return ""

    @classmethod
    def list_categories(cls) -> List[str]:
        """Parse hrti_browser.py --list and return category names."""
        script_path = CWD / "hrti_browser.py"
        if not script_path.exists():
            return [
                "domaci_filmovi",
                "strani_filmovi",
                "domace_serije",
                "strane_serije",
                "dokumentarni_program",
                "kultura",
                "sport",
                "zabava",
                "vijesti",
                "djecji_program"
            ]

        output = cls._run_browser(["--list"])
        categories = []
        # Find all words that represent slugs (lowercase, underscores, e.g. domaći_filmovi)
        # Category names might have special balkan characters (č,ć,š,ž,đ)
        pattern = re.compile(r"\b[a-zćčšžđ0-9_]+\b")
        for line in output.splitlines():
            # Skip sections like "Filmovi:"
            if ":" in line and not line.strip().startswith("-"):
                continue
            for word in pattern.findall(line.lower()):
                if word not in ("kategorija", "kategorije", "stranica", "stavki", "ids") and len(word) > 3:
                    categories.append(word)
        
        # Deduplicate and sort, keeping some common ones first
        unique_cats = sorted(list(set(categories)))
        return unique_cats

    @classmethod
    def get_category_items(cls, category: str, page: int = 1) -> Dict[str, Any]:
        """Parse hrti_browser.py --cat <cat> --page <page>."""
        script_path = CWD / "hrti_browser.py"
        if not script_path.exists():
            mock_data = {
                "domaci_filmovi": [
                    ("d4e5f67a-8b9c-0d1e-2f3a-4b5c6d7e8f9a", "movie", "Ustav Republike Hrvatske (2016)"),
                    ("e5f67a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b", "movie", "Zvizdan (2015)"),
                    ("f67a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c", "movie", "Svećenikova djeca (2013)"),
                    ("7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d", "movie", "Metastaze (2009)"),
                    ("8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e", "movie", "H-8 (1958)"),
                    ("9b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3f", "movie", "Tko pjeva zlo ne misli (1970)"),
                    ("0b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3a", "movie", "ZG80 (2016)")
                ],
                "strani_filmovi": [
                    ("1a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d", "movie", "Inception (2010)"),
                    ("2b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e", "movie", "The Dark Knight (2008)"),
                    ("3c9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3f", "movie", "Pulp Fiction (1994)"),
                    ("4d9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3a", "movie", "Interstellar (2014)"),
                    ("5e9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3b", "movie", "Parasite (2019)")
                ],
                "domace_serije": [
                    ("6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c", "series", "Novine"),
                    ("7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d", "series", "Gora"),
                    ("8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e", "series", "Crno-bijeli svijet"),
                    ("9c9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3f", "series", "Kuda idu divlje svinje"),
                    ("0d9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3a", "series", "Prosjaci i sinovi")
                ],
                "strane_serije": [
                    ("a1c9c0d1-e2f3-a4b5-c6d7-e8f9a0b1c2d3", "series", "Breaking Bad"),
                    ("b2c9c0d1-e2f3-a4b5-c6d7-e8f9a0b1c2d4", "series", "Succession"),
                    ("c3c9c0d1-e2f3-a4b5-c6d7-e8f9a0b1c2d5", "series", "Sherlock"),
                    ("d4c9c0d1-e2f3-a4b5-c6d7-e8f9a0b1c2d6", "series", "Game of Thrones")
                ]
            }
            items_list = mock_data.get(category, [
                (f"mock-uuid-{i}-{category}", "movie" if i % 2 == 0 else "series", f"HRTi {category.replace('_', ' ').title()} Sadržaj {i}")
                for i in range(1, 11)
            ])
            items = [{"id": uid, "type": t, "title": title} for uid, t, title in items_list]
            return {
                "metadata": {
                    "total_items": len(items),
                    "page": page,
                    "total_pages": 1
                },
                "items": items
            }

        output = cls._run_browser(["--cat", category, "--page", str(page)])
        return cls._parse_browser_items(output)

    @classmethod
    def search_items(cls, query: str) -> Dict[str, Any]:
        """Parse hrti_browser.py --search <query>."""
        script_path = CWD / "hrti_browser.py"
        if not script_path.exists():
            all_items = []
            for cat in ["domaci_filmovi", "strani_filmovi", "domace_serije", "strane_serije"]:
                res = cls.get_category_items(cat)
                all_items.extend(res["items"])
            matched = [i for i in all_items if query.lower() in i["title"].lower()]
            if not matched:
                matched = [{
                    "id": "mock-search-result-id",
                    "type": "movie",
                    "title": f"Rezultat pretrage za: '{query}'"
                }]
            return {
                "metadata": {
                    "total_items": len(matched),
                    "page": 1,
                    "total_pages": 1
                },
                "items": matched
            }

        output = cls._run_browser(["--search", query])
        return cls._parse_browser_items(output)

    @classmethod
    def get_series_episodes(cls, series_uuid: str) -> Dict[str, Any]:
        """Parse hrti_browser.py --series <uuid>."""
        script_path = CWD / "hrti_browser.py"
        if not script_path.exists():
            series_name = "Serija"
            if series_uuid == "6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c":
                series_name = "Novine"
            elif series_uuid == "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d":
                series_name = "Gora"
            elif series_uuid == "8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e":
                series_name = "Crno-bijeli svijet"
            
            items = []
            for ep_num in range(1, 6):
                items.append({
                    "id": f"mock-episode-{ep_num}-{series_uuid}",
                    "type": "episode",
                    "title": f"{series_name} - Sezona 1 Epizoda {ep_num}"
                })
            return {
                "metadata": {
                    "total_items": len(items),
                    "page": 1,
                    "total_pages": 1
                },
                "items": items
            }

        output = cls._run_browser(["--series", series_uuid])
        return cls._parse_browser_items(output)

    @staticmethod
    def _parse_browser_items(output: str) -> Dict[str, Any]:
        """Helper to parse a table of hrti_browser.py output into JSON."""
        items = []
        # Regex to match: UUID (36 chars), followed by type (movie/series/episode), followed by title
        # Match pattern: UUID space+ word space+ rest of the line
        pattern = re.compile(r"^\s*([0-9a-fA-F-]{36})\s+(\w+)\s+(.+)$")
        
        metadata = {"total_items": 0, "page": 1, "total_pages": 1}
        
        # Try to parse header metadata like: "domaći_filmovi  [116 stavki, stranica 1/5]"
        meta_match = re.search(r"\[(\d+)\s+stavki,\s+stranica\s+(\d+)/(\d+)\]", output)
        if meta_match:
            metadata["total_items"] = int(meta_match.group(1))
            metadata["page"] = int(meta_match.group(2))
            metadata["total_pages"] = int(meta_match.group(3))

        for line in output.splitlines():
            line = line.strip()
            if not line or "ReferenceId" in line or line.startswith("-"):
                continue
            
            m = pattern.match(line)
            if m:
                uuid = m.group(1).strip()
                item_type = m.group(2).strip()
                title = m.group(3).strip()
                items.append({
                    "id": uuid,
                    "type": item_type,
                    "title": title
                })
        
        return {
            "metadata": metadata,
            "items": items
        }

    @staticmethod
    def make_download_cmd(ref_id: str, title: str = "", workers: int = 16) -> List[str]:
        """Build cmd to run hrti_downloader.py."""
        cmd = ["python", "hrti_downloader.py", "--ref-id", ref_id]
        
        if title:
            cmd += ["--title", title]
            
        output_dir = config.get_output_dir()
        cmd += ["-o", output_dir]

        # Check binary configuration for Widevine device.wvd path
        bin_status = config.check_binaries_status()
        wvd_path = bin_status.get("device_wvd", {}).get("path", "")
        if wvd_path and os.path.exists(wvd_path):
            cmd += ["-d", wvd_path]
            
        if workers and workers != 16:
            cmd += ["-w", str(workers)]
            
        return cmd
