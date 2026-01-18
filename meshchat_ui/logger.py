import logging
import os

def get_logger(name, debug_mode: bool = False):
    logger = logging.getLogger(name)
    
    if debug_mode:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicate output
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a file handler
    log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_error.log")
    handler = logging.FileHandler(log_file_path)
    
    if debug_mode:
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)

    # Create a logging format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(handler)

    return logger
