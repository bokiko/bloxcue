import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
HOOK_PATH = PROJECT_ROOT / "hooks" / "memory-retrieve.py"


def run_hook(payload):
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=data,
        capture_output=True,
        text=True,
        check=False,
    )


def load_hook_module():
    spec = importlib.util.spec_from_file_location("memory_retrieve", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_malformed_json_continues():
    result = run_hook("{bad json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["result"] == "continue"


def test_missing_user_prompt_continues():
    result = run_hook({"not_prompt": "deployment"})
    assert result.returncode == 0
    assert json.loads(result.stdout)["result"] == "continue"


def test_short_prompt_continues():
    result = run_hook({"user_prompt": "hi"})
    assert result.returncode == 0
    assert json.loads(result.stdout)["result"] == "continue"


def test_shell_metacharacters_are_text():
    hook = load_hook_module()
    prompt = hook.sanitize_prompt("deploy $(touch /tmp/nope); `whoami`")
    assert "$(touch /tmp/nope)" in prompt
    assert "`whoami`" in prompt


def test_successful_valid_hook_json_output():
    result = run_hook({"user_prompt": "deployment production migrations"})
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["result"] == "continue"
    assert "message" in payload
    assert "BloxCue" in payload["message"]


def test_missing_indexer_continues(monkeypatch, capsys, tmp_path):
    hook = load_hook_module()
    monkeypatch.setattr(hook, "indexer_path", lambda: tmp_path / "missing-indexer.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"user_prompt": "deployment context please"})))

    hook.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"result": "continue"}
