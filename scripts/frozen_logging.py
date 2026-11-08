"""PyInstaller runtime hook: preserve startup tracebacks for windowed builds."""
import os
from pathlib import Path
import sys
import traceback

root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DDLAssistant" / "logs"
root.mkdir(parents=True, exist_ok=True)
path = root / (Path(sys.executable).stem + "-bootstrap.log")
if path.exists() and path.stat().st_size > 1_000_000:
    path.replace(path.with_suffix(".old.log"))
stream = path.open("a", encoding="utf-8", buffering=1)
if sys.stdout is None:
    sys.stdout = stream
if sys.stderr is None:
    sys.stderr = stream


def report(kind, value, tb):
    traceback.print_exception(kind, value, tb, file=stream)
    stream.flush()


sys.excepthook = report

# WinRT ships an older MSVCP140 beside its extension. Windows can select that
# copy before Qt's newer ABI-compatible runtime. Load Qt's runtime first, before
# PyInstaller's Qt hooks import Shiboken or any application code.
if os.name == "nt" and hasattr(sys, "_MEIPASS"):
    runtime = Path(sys._MEIPASS) / "PySide6" / "msvcp140.dll"
    if runtime.exists():
        import ctypes
        qt_msvc_runtime = ctypes.WinDLL(str(runtime))
