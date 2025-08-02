from datetime import datetime
import json
import logging

class DataLogger:
    """A structured JSON logger for data projects."""

    def __init__(self, name: str, log_file: str = 'data_pipeline.log'):
        """
        Initializes the logger.

        Args:
            name (str): The name of the logger, usually __name__.
            log_file (str): The file to write logs to.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Avoid adding duplicate handlers
        if not self.logger.handlers:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(self, event_type: str, metadata: dict):
        """
        Logs a structured event.

        Args:
            event_type (str): The type of event (e.g., 'DATA_TRANSFORMATION', 'MODEL_TRAINING').
            metadata (dict): A dictionary of relevant metadata to log.
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'INFO',
            'event_type': event_type,
            'metadata': metadata
        }
        self.logger.info(json.dumps(log_entry))

    def log_error(self, event_type: str, error_message: str, metadata: dict):
        """
        Logs a structured error.

        Args:
            event_type (str): The type of event where the error occurred.
            error_message (str): The error message.
            metadata (dict): A dictionary of relevant context.
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'ERROR',
            'event_type': event_type,
            'error': error_message,
            'metadata': metadata
        }
        self.logger.error(json.dumps(log_entry))
