import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows integration")


def test_native_identity_shortcut_has_aumid(tmp_path):
    from app.windows_identity import register_shortcut
    path = tmp_path / "DDL Assistant.lnk"
    register_shortcut(sys.executable, link_path=path, register_app=False)
    assert path.exists()
    # Shell-link property storage contains the UTF-16 application identity.
    assert "DDLAssistant.Desktop".encode("utf-16-le") in path.read_bytes()


def test_scheduler_xml_uses_interactive_user_and_escaped_paths(tmp_path):
    folder = tmp_path / "space & unicode 中文"
    folder.mkdir()
    for name in ("DDLAssistant.exe", "DDLAssistantReminder.exe"):
        (folder / name).touch()
    target = tmp_path / "task.xml"
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(Path("scripts/install_reminder.ps1").resolve()), "-ExeDirectory", str(folder),
                    "-ExportXml", str(target)], check=True, timeout=30)
    root = ET.parse(target).getroot()
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert root.find(".//t:Command", ns).text == str(folder / "DDLAssistantReminder.exe")
    assert root.find(".//t:LogonType", ns).text == "InteractiveToken"
    assert root.find(".//t:Interval", ns).text == "PT15M"
    assert root.find(".//t:LogonTrigger/t:UserId", ns).text.startswith("S-1-")


def test_reminder_imports_neither_ai_nor_qt():
    code = "import app.reminder.__main__,sys; assert not any(n.startswith(('ollama','PySide6','app.ai')) for n in sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True, timeout=20)


def test_frozen_runtime_hook_preloads_qt_compatible_msvc():
    code = """
import ctypes, pathlib, runpy, sys
root=pathlib.Path(sys.prefix)/'Lib'/'site-packages'
sys._MEIPASS=str(root)
runpy.run_path('scripts/frozen_logging.py')
ctypes.WinDLL(str(root/'winrt/msvcp140.dll'))
from PySide6.QtCore import QTimer
print('Qt ABI compatible')
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
