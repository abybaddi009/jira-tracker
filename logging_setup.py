import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name="time_tracker"):
    """
    Configure and return a logger instance with rotating file handler.

    Args:
        name (str): Name of the logger. Defaults to "time_tracker"

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Configure logger
    logger = logging.getLogger(name)

    # Only add handlers if the logger doesn't already have them
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create rotating file handler
        log_file = os.path.join(logs_dir, "time_tracker.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )

        # Create formatter and add it to the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(file_handler)

    return logger
