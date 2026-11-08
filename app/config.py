"""全局配置：路径、常量。

所有运行时数据放在 %LOCALAPPDATA%\\DDLAssistant 下，避免污染源码目录。
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "DDL Assistant"
APP_DIR_NAME = "DDLAssistant"

# 数据库文件
DB_FILENAME = "ddl_assistant.db"
# 日志目录
LOG_DIRNAME = "logs"
# 备份目录
BACKUP_DIRNAME = "backups"


def _local_appdata() -> Path:
    """返回 Windows %LOCALAPPDATA% 路径；非 Windows 时回退到用户目录。"""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / ".local" / "share"


def data_dir() -> Path:
    """应用数据根目录，不存在则创建。"""
    p = _local_appdata() / APP_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def log_dir() -> Path:
    p = data_dir() / LOG_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_dir() -> Path:
    p = data_dir() / BACKUP_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


# 业务常量
# 临近 DDL 阈值（小时）：在该窗口内且未完成的任务标记为“临近”
URGENT_SOON_HOURS = 24
