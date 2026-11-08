"""Check an existing backup by migrating an isolated copy. Never modify the source."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = Path(sys.argv[1]).resolve()
destination = ROOT / ".pytest-tmp" / "upgrade-check" / "copy.db"
destination.parent.mkdir(parents=True, exist_ok=True)

def records(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        return {table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                for table in ("tasks", "notification_log")}

before = records(source)
with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
    src.backup(dst)
from app.db.session import init_engine, reset_engine_for_tests
init_engine(destination)
reset_engine_for_tests()
after = records(destination)
assert before == after, "Existing task or notification rows changed during migration"
assert records(source) == before, "Source backup changed"
print(json.dumps({"migration_preserved_all_rows": True, "task_count": len(before["tasks"]),
                  "notification_count": len(before["notification_log"]), "copy": str(destination)}))
