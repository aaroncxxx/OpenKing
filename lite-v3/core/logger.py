"""帝国架构 v3.0 - 结构化日志"""
import logging
import os
from logging.handlers import RotatingFileHandler

_initialized = False
_log_dir = None


def _ensure_log_dir():
    global _log_dir
    if _log_dir is None:
        _log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    return _log_dir


def get_logger(name: str) -> logging.Logger:
    global _initialized
    log_dir = _ensure_log_dir()

    logger = logging.getLogger(f"empire.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 文件 handler
    fh = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=10 * 1024 * 1024, backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 控制台 handler（只显示 INFO 以上）
    if not _initialized:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("empire").addHandler(ch)
        _initialized = True

    return logger
