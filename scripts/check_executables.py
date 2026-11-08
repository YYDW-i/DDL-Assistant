"""Real frozen-process smoke checks, isolated from user data and notifications."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".pytest-tmp" / "frozen-smoke"
OUTPUT.mkdir(parents=True, exist_ok=True)
for filename in ("self-check.json", "reminder-diagnostics.json", "self-check.png"):
    (OUTPUT / "DDLAssistant" / filename).unlink(missing_ok=True)
env = dict(os.environ, LOCALAPPDATA=str(OUTPUT), QT_QPA_PLATFORM="offscreen")
for name, arguments in [("DDLAssistant.exe", ["--self-check"]),
                         ("DDLAssistantReminder.exe", ["--check-libraries"]),
                         ("DDLAssistantReminder.exe", ["--dry-run"])]:
    executable = ROOT / "dist" / name
    archive = CArchiveReader(str(executable))
    assert not any(Path(member).name.lower() == "icuuc.dll" for member in archive.toc), "A foreign ICU library was bundled"
    subprocess.run([str(executable), *arguments], env=env, check=True, timeout=120)
report = json.loads((OUTPUT / "DDLAssistant/self-check.json").read_text(encoding="utf-8"))
assert report["frozen"] and report["gui_ready"], report
assert json.loads((OUTPUT / "DDLAssistant/reminder-diagnostics.json").read_text())["notification_libraries_loaded"]
with sqlite3.connect(OUTPUT / "DDLAssistant/ddl_assistant.db") as connection:
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
print("Both EXEs passed isolated real-process startup checks:", OUTPUT)
