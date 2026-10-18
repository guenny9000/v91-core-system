import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "v91") -> logging.Logger:
    """Return a pre‑configured rotating logger.
    Logs are written to a ``logs`` directory beside the script.
    Each file is limited to 10 MiB and kept for 5 backups.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(os.getenv("V91_LOG_LEVEL", "INFO"))
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{name}.log")
    handler = RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
