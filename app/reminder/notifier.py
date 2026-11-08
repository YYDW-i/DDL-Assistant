"""Windows 系统通知封装。在非 Windows 或通知不可用时静默降级。"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def show_toast(title: str, body: str) -> bool:
    """弹出 Windows 通知，返回是否成功。"""
    try:
        from windows_toasts import (
            Toast,
            ToastText1,
            ToastText2,
            WindowsToaster,
        )
    except Exception as e:  # pragma: no cover
        logger.warning("windows-toasts 不可用：%s", e)
        return False

    try:
        toaster = WindowsToaster("DDL Assistant")
        toast = Toast()
        toast.text_fields = [ToastText2(title), ToastText1(body)]
        toaster.show_toast(toast)
        return True
    except Exception as e:  # pragma: no cover
        logger.warning("通知发送失败：%s", e)
        return False
