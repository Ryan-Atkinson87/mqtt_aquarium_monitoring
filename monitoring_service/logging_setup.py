"""
logging_setup.py

Configure application logging using a root logger with console and rotating
file handlers. The log level is set from the provided configuration value.
"""

import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir="log", log_file_name="monitoring_service.log", log_level="INFO"):
    """
    Configure the root logger with console and rotating file handlers.

    The log directory is created if it does not exist. If handlers are already
    configured on the root logger, no additional handlers are added.

    Args:
        log_dir (str): Directory where log files are stored.
        log_file_name (str): Name of the log file.
        log_level (str): Logging level name.

    Returns:
        logging.Logger: The root logger instance.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_file_name)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if not logger.hasHandlers():
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
