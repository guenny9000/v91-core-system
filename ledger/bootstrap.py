import os
import subprocess
from pathlib import Path

def main():
    # Ensure environment variables for production mode
    os.environ.setdefault("V91_ENABLE_REAL_ACTIONS", "1")
    os.environ.setdefault("V91_ALLOW_SCALE_DOWN", "1")
    # Optional: load additional .env file if present
    env_path = Path(__file__).parent / ".env"
    if env_path.is_file():
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    # Build command to launch the controller
    controller_path = Path(__file__).parent / "controller" / "runtime_control.py"
    cmd = ["python", str(controller_path)]
    # You may pass additional CLI args here, e.g., --watch
    subprocess.Popen(cmd, env=os.environ)
    print("V91 bootstrap launched with production flags.")

if __name__ == "__main__":
    main()
