import logging
import os
from datetime import datetime
from typing import Optional

class SessionLogger:
    """
    Logger that writes logs to a specific file for a chat session.
    """
    def __init__(self, log_dir: str, conversation_id: Optional[str]):
        self.conversation_id = conversation_id or "unknown"
        self.log_dir = log_dir
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Generate filename logic:
        # Search for existing file: {timestamp}_{conversation_id}.log
        # If found, reuse it. If not, create new.
        
        existing_file = None
        if self.conversation_id != "unknown":
            for f in os.listdir(self.log_dir):
                if f.endswith(f"_{self.conversation_id}.log"):
                    existing_file = f
                    break
        
        if existing_file:
            self.filename = existing_file
            # Extract timestamp from filename for logger name uniqueness if needed
            # But logger name just needs to be unique enough to not conflict in this process
            # or reused if we want.
            # Using conversation_id is good enough for logger name if we handle handlers correctly.
            ts_suffix = existing_file.split('_')[0] 
        else:
            # {date_hours_minute}_{conversation_id}.log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            self.filename = f"{timestamp}_{self.conversation_id}.log"
            ts_suffix = timestamp
            
        self.filepath = os.path.join(self.log_dir, self.filename)
        
        # Create a logger. 
        # CAUTION: If we reuse logger name, we might get duplicate handlers if not cleaned up.
        # We assume close() is always called.
        # But to be safe, let's include a random component or ID in logger name, 
        # because we only care about writing to the FILE.
        # Or we can check if logger already has handlers.
        
        logger_name = f"session.{self.conversation_id}.{datetime.now().timestamp()}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Do not propagate to root logger (avoid duplicate in console)
        
        # File handler
        fh = logging.FileHandler(self.filepath, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
    def info(self, msg: str):
        self.logger.info(msg)
        
    def error(self, msg: str):
        self.logger.error(msg)
        
    def warning(self, msg: str):
        self.logger.warning(msg)
        
    def close(self):
        """
        Clean up handlers to release file locks and memory.
        """
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)
