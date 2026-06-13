import os
import sys
import time
import subprocess
import webbrowser
import socket
import logging
from pathlib import Path

# Load optional .env from project root
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Launcher")

def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            return True
        except socket.error:
            return False

def ensure_frontend_built(project_root: Path) -> None:
    """Vite build outputs to backend/static; build once if missing after fresh clone."""
    index = project_root / "backend" / "static" / "index.html"
    if index.exists():
        return
    frontend = project_root / "frontend"
    pkg = frontend / "package.json"
    if not pkg.exists():
        logger.warning("Frontend nije pronađen — API će raditi bez UI.")
        return
    if not (frontend / "node_modules").exists():
        logger.warning(
            "UI nije izgrađen. Prvo pokrenite: cd frontend && npm install && npm run build"
        )
        return
    logger.info("Frontend build nedostaje — pokrećem npm run build...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(frontend),
            check=True,
            shell=os.name == "nt",
        )
        if index.exists():
            logger.info("Frontend uspešno izgrađen u backend/static.")
        else:
            logger.warning("Build je završen ali backend/static/index.html još ne postoji.")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Automatski frontend build nije uspeo: %s", exc)
        logger.warning("Ručno: cd frontend && npm run build")


def main():
    host = os.environ.get("VIDEODOWNLOAD_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("VIDEODOWNLOAD_PORT", "8200"))
    except ValueError:
        logger.warning("VIDEODOWNLOAD_PORT nije validan broj; koristim 8200.")
        port = 8200
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    project_root = Path(__file__).resolve().parent

    ensure_frontend_built(project_root)

    logger.info("Starting Multi-Service Video Downloader API Server...")
    if host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "Server sluša na %s:%s. Za udaljeni pristup obavezno koristite API ključ i firewall pravila.",
            host,
            port,
        )
    
    # Run uvicorn as a subprocess in the root directory
    cmd = [
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", "info"
    ]
    
    process = None
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        
        # Wait until port is open (max 10 seconds)
        logger.info("Waiting for server to spin up...")
        started = False
        for _ in range(20):
            if is_port_open(browser_host, port):
                started = True
                break
            time.sleep(0.5)
            
        if started:
            url = f"http://{browser_host}:{port}"
            logger.info(f"Server is running! Opening browser to: {url}")
            webbrowser.open(url)
            
            # Keep python script alive while uvicorn is running
            while True:
                if process.poll() is not None:
                    # Process died
                    logger.warning("Uvicorn server exited unexpectedly.")
                    break
                time.sleep(1)
                
        else:
            logger.error("Failed to start Uvicorn server within timeout limit.")
            process.terminate()
            
    except KeyboardInterrupt:
        logger.info("\nShutting down launcher and stopping API server...")
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        logger.info("Shutdown completed.")
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        if process:
            process.kill()

if __name__ == "__main__":
    main()
