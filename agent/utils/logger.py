# -*- coding: utf-8 -*-
"""
基于 loguru 的统一日志模块。

控制台全量 DEBUG+ 输出，同时写入 debug/backend_YYYY-MM-DD.log 带轮转。
"""

import sys

from loguru import logger as _logger

from utils.proj_path import DEBUG_DIR

FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
CONSOLE_FORMAT = "<level>{time:HH:mm:ss.SSS} | {level: <5} | {message}</level>"

_logger.remove()

# 控制台全量
_logger.add(sys.stderr, format=CONSOLE_FORMAT, colorize=True, level="DEBUG")

# File rotation must follow the project root, not the interface.json CWD.
log_dir = DEBUG_DIR
log_dir.mkdir(parents=True, exist_ok=True)
_logger.add(
    log_dir / "backend_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="14 days",
    compression="zip",
    level="DEBUG",
    format=FILE_FORMAT,
    encoding="utf-8",
    enqueue=True,
    backtrace=True,
    diagnose=False,
)

logger = _logger
