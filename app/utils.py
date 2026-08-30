import os
import re
import logging

def get_logger(name: str) -> logging.Logger:
    """Configures and returns a logger that logs to both console and logs/app.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = get_logger("newspaper_bot")

def get_safe_newspaper_dir(date_str: str) -> str:
    """
    Validates the date format and returns a safe absolute path for saving images.
    Prevents path traversal vulnerabilities.
    """
    # Strict regex check for date: YYYY-MM-DD
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'newspapers'))
    os.makedirs(base_dir, exist_ok=True)

    target_dir = os.path.abspath(os.path.join(base_dir, date_str))

    # Security check: Ensure target_dir is strictly inside base_dir
    # Adding trailing separator prevents partial folder name bypasses (e.g. /data/newspapers-malicious)
    base_check = base_dir + os.path.sep
    if not target_dir.startswith(base_check) and target_dir != base_dir:
        raise PermissionError(f"Path traversal detected: {target_dir} is outside the allowed base {base_dir}")

    os.makedirs(target_dir, exist_ok=True)
    return target_dir
