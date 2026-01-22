"""
Centralized logging configuration for the application.

- Development: logs to console AND file
- Production: logs to file only
- Daily rotation with previous logs archived to logs/archive/
"""

import logging
import shutil
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.config import settings, BASE_DIR

# Logging directories
LOGS_DIR = BASE_DIR / "logs"
ARCHIVE_DIR = LOGS_DIR / "archive"
LOG_FILE = LOGS_DIR / "app.log"

# Log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Third-party loggers to silence (set to WARNING to reduce noise)
NOISY_LOGGERS = [
    "sqlalchemy",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "sqlalchemy.orm",
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "watchfiles",
    "multipart",
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "starlette",
]


class ArchivingRotatingFileHandler(TimedRotatingFileHandler):
    """
    Custom handler that rotates logs daily and moves old logs to archive folder.
    """

    def __init__(self, filename: str, archive_dir: Path, **kwargs):
        self.archive_dir = archive_dir
        super().__init__(filename, when="midnight", interval=1, backupCount=0, **kwargs)

    def doRollover(self) -> None:
        """Perform rollover and move the old log to archive."""
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # Get the current log file path
        current_log = Path(self.baseFilename)

        if current_log.exists() and current_log.stat().st_size > 0:
            # Generate archive filename with date
            timestamp = datetime.now().strftime("%Y-%m-%d")
            archive_filename = f"app_{timestamp}.log"
            archive_path = self.archive_dir / archive_filename

            # Ensure archive directory exists
            self.archive_dir.mkdir(parents=True, exist_ok=True)

            # Handle case where archive file already exists (multiple rollovers same day)
            counter = 1
            while archive_path.exists():
                archive_filename = f"app_{timestamp}_{counter}.log"
                archive_path = self.archive_dir / archive_filename
                counter += 1

            # Move the log file to archive
            try:
                shutil.move(str(current_log), str(archive_path))
            except OSError:
                # If move fails, try copy and delete
                shutil.copy2(str(current_log), str(archive_path))
                current_log.unlink()

        # Open new log file
        self.stream = self._open()


def setup_logging(
    name: str | None = None,
    level: int | None = None,
) -> logging.Logger:
    """
    Configure and return a logger with the appropriate handlers.

    Args:
        name: Logger name (default: root logger)
        level: Log level (default: DEBUG in dev, INFO in prod)

    Returns:
        Configured logger instance
    """
    # Determine log level
    if level is None:
        level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Create logs directory if needed
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # File handler (always active) - with daily rotation and archiving
    file_handler = ArchivingRotatingFileHandler(
        filename=str(LOG_FILE),
        archive_dir=ARCHIVE_DIR,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (development only)
    if settings.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    silence_noisy_loggers()

    return logger


def silence_noisy_loggers() -> None:
    """
    Set third-party loggers to WARNING level to reduce noise.

    Call this after uvicorn/FastAPI startup to ensure their loggers are silenced.
    """
    for noisy_logger_name in NOISY_LOGGERS:
        noisy_logger = logging.getLogger(noisy_logger_name)
        noisy_logger.setLevel(logging.WARNING)
        # Prevent propagation to root logger
        noisy_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Usage:
        from app.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Message here")

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    # Ensure root logger is configured
    setup_logging()

    # Return child logger
    return logging.getLogger(name)


# Initialize root logger on module import
_root_logger = setup_logging()
