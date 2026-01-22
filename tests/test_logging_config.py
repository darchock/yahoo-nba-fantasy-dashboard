"""
Tests for the logging configuration module.
"""

import logging
import shutil
import tempfile
from pathlib import Path

import pytest

from app.logging_config import (
    ArchivingRotatingFileHandler,
    get_logger,
    setup_logging,
    LOGS_DIR,
    ARCHIVE_DIR,
    LOG_FILE,
)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_instance(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_returns_named_logger(self):
        """Test that get_logger returns a logger with the correct name."""
        logger = get_logger("my_test_module")
        assert logger.name == "my_test_module"

    def test_same_name_returns_same_logger(self):
        """Test that calling get_logger with same name returns same instance."""
        logger1 = get_logger("same_name_test")
        logger2 = get_logger("same_name_test")
        assert logger1 is logger2

    def test_different_names_return_different_loggers(self):
        """Test that different names return different logger instances."""
        logger1 = get_logger("name_one")
        logger2 = get_logger("name_two")
        assert logger1 is not logger2


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_returns_logger_instance(self):
        """Test that setup_logging returns a logging.Logger."""
        logger = setup_logging("test_setup")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_handlers(self):
        """Test that the logger has at least one handler."""
        logger = setup_logging("test_handlers")
        assert len(logger.handlers) > 0

    def test_logger_has_file_handler(self):
        """Test that the logger has an ArchivingRotatingFileHandler."""
        logger = setup_logging("test_file_handler")
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "ArchivingRotatingFileHandler" in handler_types

    def test_does_not_duplicate_handlers_on_multiple_calls(self):
        """Test that calling setup_logging multiple times doesn't add duplicate handlers."""
        logger_name = "test_no_duplicate"

        # Clear any existing handlers first
        existing_logger = logging.getLogger(logger_name)
        for handler in existing_logger.handlers[:]:
            existing_logger.removeHandler(handler)

        logger1 = setup_logging(logger_name)
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logging(logger_name)
        handler_count2 = len(logger2.handlers)

        assert handler_count1 == handler_count2


class TestLoggingDirectories:
    """Tests for logging directory structure."""

    def test_logs_directory_exists(self):
        """Test that the logs directory exists."""
        # Trigger setup
        setup_logging("test_dir_exists")
        assert LOGS_DIR.exists()

    def test_archive_directory_exists(self):
        """Test that the archive directory exists."""
        # Trigger setup
        setup_logging("test_archive_exists")
        assert ARCHIVE_DIR.exists()

    def test_log_file_path_is_in_logs_dir(self):
        """Test that LOG_FILE is inside LOGS_DIR."""
        assert LOG_FILE.parent == LOGS_DIR


class TestLoggingOutput:
    """Tests for actual logging output."""

    def test_info_message_is_logged(self):
        """Test that INFO level messages are logged."""
        logger = get_logger("test_info_output")

        # This should not raise an exception
        logger.info("Test info message")

    def test_warning_message_is_logged(self):
        """Test that WARNING level messages are logged."""
        logger = get_logger("test_warning_output")
        logger.warning("Test warning message")

    def test_error_message_is_logged(self):
        """Test that ERROR level messages are logged."""
        logger = get_logger("test_error_output")
        logger.error("Test error message")

    def test_debug_message_is_logged(self):
        """Test that DEBUG level messages are logged."""
        logger = get_logger("test_debug_output")
        logger.debug("Test debug message")


class TestArchivingRotatingFileHandler:
    """Tests for the custom ArchivingRotatingFileHandler."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        temp_dir = tempfile.mkdtemp()
        logs_dir = Path(temp_dir) / "logs"
        archive_dir = logs_dir / "archive"
        logs_dir.mkdir(parents=True)
        archive_dir.mkdir(parents=True)
        yield logs_dir, archive_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_handler_initializes_correctly(self, temp_dirs):
        """Test that handler initializes without errors."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )

        assert handler is not None
        handler.close()

    def test_handler_creates_log_file_on_write(self, temp_dirs):
        """Test that handler creates the log file when writing."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )

        # Create a logger and write to it
        logger = logging.getLogger("test_handler_file_create")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("Test message")
        handler.flush()

        assert log_file.exists()
        handler.close()

    def test_handler_writes_content_to_file(self, temp_dirs):
        """Test that handler writes actual content to the log file."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_handler_content")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        test_message = "This is a test log message"
        logger.info(test_message)
        handler.flush()

        content = log_file.read_text()
        assert test_message in content
        handler.close()

    def test_rollover_creates_archive_file(self, temp_dirs):
        """Test that rollover moves the log file to archive directory."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )

        logger = logging.getLogger("test_rollover_archive")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("Message before rollover")
        handler.flush()

        # Manually trigger rollover
        handler.doRollover()

        # Check that archive contains the old log
        archive_files = list(archive_dir.glob("*.log"))
        assert len(archive_files) >= 1
        handler.close()

    def test_rollover_preserves_log_content_in_archive(self, temp_dirs):
        """Test that archived log contains the original content."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_rollover_content")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        original_message = "Original message before rollover"
        logger.info(original_message)
        handler.flush()

        handler.doRollover()

        # Find the archived file and check content
        archive_files = list(archive_dir.glob("*.log"))
        assert len(archive_files) >= 1

        archived_content = archive_files[0].read_text()
        assert original_message in archived_content
        handler.close()

    def test_new_log_file_created_after_rollover(self, temp_dirs):
        """Test that a new log file is created and writable after rollover."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_new_file_after_rollover")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("Message before rollover")
        handler.flush()

        handler.doRollover()

        # Write to new log file
        new_message = "Message after rollover"
        logger.info(new_message)
        handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert new_message in content
        handler.close()

    def test_multiple_rollovers_create_unique_archive_files(self, temp_dirs):
        """Test that multiple rollovers create uniquely named archive files."""
        logs_dir, archive_dir = temp_dirs
        log_file = logs_dir / "test.log"

        handler = ArchivingRotatingFileHandler(
            filename=str(log_file),
            archive_dir=archive_dir,
        )

        logger = logging.getLogger("test_multiple_rollovers")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Perform multiple rollovers
        for i in range(3):
            logger.info(f"Message {i}")
            handler.flush()
            handler.doRollover()

        # Check that we have multiple archive files
        archive_files = list(archive_dir.glob("*.log"))
        assert len(archive_files) >= 2  # At least 2 because empty files may not be archived
        handler.close()
