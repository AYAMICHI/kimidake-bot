# src/logging_config.py
import logging
from pathlib import Path

LOG_FILE = Path("kimidake.log")

def setup_logger():
    logger = logging.getLogger("kimidake")
    logger.setLevel(logging.INFO)

    # 多重ハンドラ防止
    if logger.handlers:
        return logger

    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s  %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger
