import logging
import os

def setup_logging():
    log_dir = "/home/tim/receipt-printer/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(f"{log_dir}/app.log"),
            logging.StreamHandler()  # still try stdout too
        ]
    )
    return logging.getLogger(__name__)