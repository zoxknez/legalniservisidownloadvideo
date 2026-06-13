import os
import shutil
import zipfile
from pathlib import Path

def sync_dir(src: Path, dest: Path, ignore_patterns=None):
    if not src.exists():
        return
    if not dest.exists():
        dest.mkdir(parents=True, exist_ok=True)
        
    # Build list of active files in source
    src_items = {}
    for item in src.iterdir():
        if ignore_patterns and any(item.name == pat or item.match(pat) for pat in ignore_patterns):
            continue
        src_items[item.name] = item

    # Delete items in destination that are not in source (excluding ignored/local ones)
    if dest.exists():
        for item in dest.iterdir():
            if ignore_patterns and any(item.name == pat or item.match(pat) for pat in ignore_patterns):
                continue
            if item.name not in src_items:
                print(f"Removing outdated item from portable: {item}")
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    # Copy/sync from source to destination
    for name, item in src_items.items():
        dest_item = dest / name
        if item.is_dir():
            sync_dir(item, dest_item, ignore_patterns)
        else:
            # Copy if dest doesn't exist or is older
            if not dest_item.exists() or dest_item.stat().st_mtime < item.stat().st_mtime:
                print(f"Copying {item} -> {dest_item}")
                # Ensure parent dir exists
                dest_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_item)

def main():
    root = Path(__file__).resolve().parent.parent
    winportabl_dir = root / "winportabl"
    
    print("Syncing backend directory...")
    backend_ignore = ["__pycache__", ".venv", ".videodownload", "output", "temp", "*.pyc", "*.pyo", "device.wvd"]
    sync_dir(root / "backend", winportabl_dir / "backend", backend_ignore)
    
    print("Syncing userscripts directory...")
    sync_dir(root / "userscripts", winportabl_dir / "userscripts")
    
    print("Copying root files...")
    root_files = [
        "run.py",
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
        "ytdlp_downloader.py",
        "PokreniAplikaciju.bat"
    ]
    for filename in root_files:
        src_file = root / filename
        dest_file = winportabl_dir / filename
        if src_file.exists():
            print(f"Copying {src_file} -> {dest_file}")
            shutil.copy2(src_file, dest_file)
            
    print("Creating VideoDownloadServisi-Portable.zip...")
    zip_path = root / "VideoDownloadServisi-Portable.zip"
    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception as e:
            print(f"Warning: could not delete existing zip: {e}")
    
    # We want to zip the 'winportabl' directory under the name 'winportabl/' in the zip file
    zip_exclude = {
        ".venv",
        ".videodownload",
        "output",
        "temp",
        "device.wvd",
        "__pycache__"
    }
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for r, dirs, files in os.walk(winportabl_dir):
            # Modify dirs in-place to prevent os.walk from traversing excluded directories
            dirs[:] = [d for d in dirs if d not in zip_exclude]
            
            for file in files:
                if file.endswith(('.pyc', '.pyo')) or file == 'device.wvd':
                    continue
                file_path = Path(r) / file
                # Write with relative path starting with winportabl/
                rel_path = Path("winportabl") / file_path.relative_to(winportabl_dir)
                zip_file.write(file_path, rel_path)
                
    print(f"Successfully packaged release at {zip_path}")

if __name__ == "__main__":
    main()
