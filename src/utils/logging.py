import logging
import sys
from datetime import datetime

def setup_logger(name: str = "anomaly_detection", level: str = "INFO") -> logging.Logger:
    """
    Configure the application logger with console output.

    Prevents duplicate log messages by disabling propagation and clearing
    existing handlers before adding a new console handler.

    Args:
        name: Logger name (default: "anomaly_detection").
        level: Log level string (default: "INFO"). Uses standard names: DEBUG, INFO, WARNING, ERROR.

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Disable root logger to prevent duplicate messages
    logging.root.handlers = []
    logging.basicConfig(level=logging.WARNING)  # Set root to WARNING so it doesn't interfere
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Prevent duplicate logs by not propagating to root logger
    logger.propagate = False
    
    # Clear any existing handlers to prevent duplicates
    logger.handlers.clear()
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
