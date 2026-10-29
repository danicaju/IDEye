"""IDEye structured logging configuration.

Use ``get_logger(__name__)`` in modules that emit diagnostics. The level can be
controlled with ``IDEYE_LOG_LEVEL`` (DEBUG, INFO, WARNING, ERROR).
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def configure_logging(level: str | int | None = None) -> None:
    """Configures the root logger once without hijacking pytest's handlers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = level if level is not None else os.environ.get("IDEYE_LOG_LEVEL", "INFO")
    if isinstance(level_name, str):
        level_value = getattr(logging, level_name.upper(), logging.INFO)
    else:
        level_value = int(level_name)

    root = logging.getLogger()
    root.setLevel(level_value)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger after ensuring logging is configured."""
    configure_logging()
    return logging.getLogger(name)
