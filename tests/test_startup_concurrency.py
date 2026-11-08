import subprocess
import sys


def test_fresh_database_initialization_is_serialized(tmp_path):
    code = "from app.db.session import init_engine; import sys; init_engine(sys.argv[1])"
    for index in range(4):
        path = tmp_path / f"fresh{index}.db"
        children = [subprocess.Popen([sys.executable, "-c", code, str(path)], stderr=subprocess.PIPE) for _ in range(6)]
        results = [child.communicate(timeout=40)[1] for child in children]
        assert [child.returncode for child in children] == [0] * 6, results


def test_structured_times_do_not_accept_invented_timezone():
    import pytest
    from app.ai.schema import ExtractedTaskList
    with pytest.raises(ValueError):
        ExtractedTaskList.model_validate({"tasks": [{"title": "任务", "due_time": "20:00:00Z"}]})
