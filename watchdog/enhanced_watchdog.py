import os
import time
import subprocess
from pathlib import Path
from logging import getLogger

logger = getLogger(__name__)

def start_controller():
    # Launch the bootstrap script which sets env vars and starts the controller
    script_path = Path(__file__).parent.parent / "ledger" / "bootstrap.py"
    if not script_path.is_file():
        logger.error("Bootstrap script not found: %s", script_path)
        return
    subprocess.Popen(["python", str(script_path)], env=os.environ)
    logger.info("V91 controller started via bootstrap.")

def monitor():
    while True:
        # Simple health check – if the process is not running, restart
        # Here we assume the bootstrap launches the controller as a separate process
        # We'll just ensure the bootstrap script is alive; in real use you'd check a PID file.
        # For demo, we just sleep and log.
        time.sleep(30)
        logger.debug("Watchdog heartbeat – controller should be running.")

if __name__ == "__main__":
    start_controller()
    monitor()
