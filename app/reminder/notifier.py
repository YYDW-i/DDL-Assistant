"""Windows-Toasts integration with a stable application identity."""
import hashlib
import logging
import threading
import time
from uuid import uuid4

logger = logging.getLogger(__name__)
APP_ID = "DDLAssistant.Desktop"


def show_toast(title: str, body: str, tag=None) -> bool:
    try:
        from windows_toasts import Toast, WindowsToaster
        from winrt.windows.ui.notifications import ToastNotificationManager
        toaster = WindowsToaster(APP_ID)
        # NotificationSetting.ENABLED == 0. Disabled notifications must remain retryable.
        if int(toaster.toastNotifier.setting) != 0:
            logger.warning("Windows notifications disabled for %s", APP_ID)
            return False
        failed = threading.Event()
        toast = Toast(text_fields=[title, body])
        toast.tag = hashlib.sha256((tag or uuid4().hex).encode()).hexdigest()[:16]
        toast.group = "ddl"
        toast.on_failed = lambda _: failed.set()
        toaster.show_toast(toast)
        # show() is asynchronous. Confirm the OS stored the notification, rather
        # than treating absence of an immediate failure callback as delivery.
        deadline = time.monotonic() + 3
        while not failed.is_set() and time.monotonic() < deadline:
            history = ToastNotificationManager.history.get_history_with_id(APP_ID)
            if any(item.tag == toast.tag and item.group == toast.group for item in history):
                return True
            failed.wait(.05)
        logger.warning("Windows did not confirm notification storage")
        return False
    except Exception as exc:
        logger.warning("Windows notification failed: %s", exc)
        return False
