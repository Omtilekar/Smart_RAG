"""Tests for src.logging_utils: level filtering, idempotent/reconfigurable
handler setup, structured fields, secret redaction, and exception
tracebacks. See conftest.py for the log_capture fixture and the autouse
logging-state reset that keeps these tests isolated from each other."""

import logging

from src.logging_utils import _HANDLER_NAME, configure_logging, get_logger, log_event


def test_info_level_hides_debug_shows_info_and_warning(log_capture):
    buf = log_capture("INFO")
    logger = get_logger("tests.logging.info")
    logger.debug("hidden debug message")
    logger.info("visible info message")
    logger.warning("visible warning message")
    out = buf.getvalue()
    assert "hidden debug message" not in out
    assert "visible info message" in out
    assert "visible warning message" in out


def test_debug_level_shows_debug(log_capture):
    buf = log_capture("DEBUG")
    logger = get_logger("tests.logging.debug")
    logger.debug("now visible debug message")
    assert "now visible debug message" in buf.getvalue()


def test_configure_logging_repeated_calls_single_handler():
    configure_logging("INFO")
    configure_logging("INFO")
    configure_logging("INFO")
    root = logging.getLogger()
    project_handlers = [h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME]
    assert len(project_handlers) == 1


def test_configure_logging_repeated_calls_single_message(log_capture):
    buf = log_capture("INFO")
    configure_logging("INFO")
    configure_logging("INFO")
    logger = get_logger("tests.logging.dup")
    logger.info("marker event once")
    assert buf.getvalue().count("marker event once") == 1


def test_reconfiguration_changes_level_without_new_handler():
    configure_logging("INFO")
    root = logging.getLogger()
    count_before = len([h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME])

    configure_logging("DEBUG")
    count_after = len([h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME])

    assert count_before == 1
    assert count_after == 1
    assert root.level == logging.DEBUG


def test_structured_fields_render_predictably(log_capture):
    buf = log_capture("INFO")
    logger = get_logger("tests.logging.structured")
    log_event(
        logger, logging.INFO, "test_event",
        stage="embedding", batch=3, elapsed_ms=12.5, success=True,
        note=None, spaced="hello world",
    )
    out = buf.getvalue()
    assert "event=test_event" in out
    assert "stage=embedding" in out
    assert "batch=3" in out
    assert "elapsed_ms=12.5" in out
    assert "success=true" in out
    assert "note=None" in out
    assert 'spaced="hello world"' in out


def test_secret_fields_are_redacted(log_capture):
    buf = log_capture("INFO")
    logger = get_logger("tests.logging.secrets")
    fake = "TEST_SECRET_VALUE_DO_NOT_EMIT"
    log_event(
        logger, logging.INFO, "provider_initialized",
        api_key=fake, token=fake, password=fake, authorization=fake,
        safe_field="visible_value",
    )
    out = buf.getvalue()
    assert fake not in out
    assert "[REDACTED]" in out
    assert "safe_field=visible_value" in out


def test_exception_traceback_preserved(log_capture):
    buf = log_capture("INFO")
    logger = get_logger("tests.logging.exc")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("operation failed")
    out = buf.getvalue()
    assert "operation failed" in out
    assert "ZeroDivisionError" in out
    assert "Traceback" in out
