import os
import sys
import time
import subprocess
import webbrowser
import socket
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Launcher")

def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            return True
        except socket.error:
            return False

def main():
    host = "127.0.0.1"
    port = 8000
    
    logger.info("Starting Multi-Service Video Downloader API Server...")
    
    # Run uvicorn as a subprocess in the root directory
    cmd = [
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", "info"
    ]
    
    process = None
    try:
        process = subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Wait until port is open (max 10 seconds)
        logger.info("Waiting for server to spin up...")
        started = False
        for _ in range(20):
            if is_port_open(host, port):
                started = True
                break
            time.sleep(0.5)
            
        if started:
            url = f"http://{host}:{port}"
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
