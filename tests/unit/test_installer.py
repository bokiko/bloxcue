import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
INSTALLER = PROJECT_ROOT / "install.sh"


def run_installer(tmp_path, args=None, path_prefix=None):
    args = args or []
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{path_prefix}:{env['PATH']}" if path_prefix else env["PATH"]
    (tmp_path / "home").mkdir(exist_ok=True)
    return subprocess.run(
        [str(INSTALLER), "--auto", "--scope", "2", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installer_detects_installed_clients(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex", "gemini"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        exe.chmod(0o755)

    result = run_installer(tmp_path, path_prefix=bin_dir)

    assert result.returncode == 0
    assert "claude: installed" in result.stdout
    assert "codex:  installed" in result.stdout
    assert "gemini: installed" in result.stdout


def test_installer_detects_missing_clients(tmp_path):
    result = run_installer(tmp_path)

    assert result.returncode == 0
    assert "Detected clients:" in result.stdout
    assert "Codex (~/.codex/config.toml):" in result.stdout
    assert "Gemini CLI (~/.gemini/settings.json):" in result.stdout


def test_installer_prints_instructions_without_editing_configs_by_default(tmp_path):
    home = tmp_path / "home"
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"existing": true}\n', encoding="utf-8")

    result = run_installer(tmp_path, args=["--claude-hook"])

    assert result.returncode == 0
    assert "No client config was edited by default." in result.stdout
    assert json.loads(settings.read_text()) == {"existing": True}
    assert not list(settings.parent.glob("settings.json.backup.*"))


def test_installer_opt_in_mutation_creates_backup(tmp_path):
    home = tmp_path / "home"
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"existing": true}\n', encoding="utf-8")

    result = run_installer(tmp_path, args=["--claude-hook", "--mutate-config"])

    assert result.returncode == 0
    assert list(settings.parent.glob("settings.json.backup.*"))
    data = json.loads(settings.read_text())
    hook = data["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    assert hook["type"] == "command"
    assert "memory-retrieve.py" in hook["command"]
