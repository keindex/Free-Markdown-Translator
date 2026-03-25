from __future__ import annotations

import contextlib
import contextvars
import logging

from colorlog import ColoredFormatter


_log_context: contextvars.ContextVar[str] = contextvars.ContextVar("log_context", default="")


class _SuppressHttpRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        return not (isinstance(message, str) and message.startswith("HTTP Request:"))


class _TaskContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.task_context = _log_context.get("")
        return True


@contextlib.contextmanager
def log_task_context(label: str):
    token = _log_context.set(f"[{label}] " if label else "")
    try:
        yield
    finally:
        _log_context.reset(token)


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    if getattr(configure_logging, "_configured", False):
        root_logger.setLevel(level)
        return

    formatter = ColoredFormatter(
        "%(blue)s%(asctime)s %(log_color)s[%(levelname)-7s]%(reset)s %(blue)s%(task_context)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(_SuppressHttpRequestLogFilter())
    handler.addFilter(_TaskContextFilter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    for logger_name in ("openai", "openai._base_client", "httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    configure_logging._configured = True
