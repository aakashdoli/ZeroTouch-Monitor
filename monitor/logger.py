import logging
import os
import sys

def setup_logger(name="ZeroTouch-Monitor", level=logging.INFO):
    """Set up and return a logger with standard formatting."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Create file handler
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(os.path.join(log_dir, "monitor.log"))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
