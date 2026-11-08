"""Bound log size for long-running desktop and scheduled processes."""
import logging
from logging.handlers import RotatingFileHandler
from . import config


def setup_logging(name="app"):
    handler = RotatingFileHandler(config.log_dir() / f"{name}.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[handler])
