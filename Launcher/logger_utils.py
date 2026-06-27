from __future__ import annotations

import logging
from pathlib import Path


class LoggerManager:
    def __init__(self, log_dir: Path, enabled: bool = True) -> None:
        self.log_dir = log_dir
        self.enabled = enabled
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._loggers: dict[str, logging.Logger] = {}

    def get_logger(self, name: str, file_name: str) -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(f"schoolerp.{name}")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not self.enabled:
            logger.addHandler(logging.NullHandler())
            self._loggers[name] = logger
            return logger

        file_path = self.log_dir / file_name
        handler = logging.FileHandler(file_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
        self._loggers[name] = logger
        return logger
