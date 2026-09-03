import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType


def load_validator() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / ".agents"
        / "skills"
        / "validate-live-app"
        / "scripts"
        / "validate_live_app.py"
    )
    spec = importlib.util.spec_from_file_location("validate_live_app", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_isolated_browser_suite_uses_disposable_postgresql(
    monkeypatch,
    tmp_path,
):
    validator = load_validator()
    commands: list[tuple[list[str], dict[str, str] | None]] = []
    ports = iter((48123, 48124))

    def fake_run(
        command,
        *,
        cwd,
        env=None,
        capture_output=False,
        check=True,
    ):
        del cwd, capture_output, check
        commands.append((command, env))
        if any(argument.endswith("run_compose_acceptance.py") for argument in command):
            artifact_dir = Path(command[command.index("--artifact-dir") + 1])
            (artifact_dir / "compose-browser-summary.json").write_text(
                json.dumps([{"name": "journey", "status": "passed"}]),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(validator, "available_port", lambda: next(ports))
    monkeypatch.setattr(validator, "run", fake_run)
    monkeypatch.setattr(validator, "wait_for_http", lambda base_url: None)
    monkeypatch.setattr(validator, "require_executed_browser_tests", lambda report: 4)

    assert validator.validate_compose_stack(tmp_path, tmp_path) == (4, 1)

    db_start_index = next(
        index
        for index, (command, _) in enumerate(commands)
        if command[-4:] == ["up", "-d", "--wait", "db"]
    )
    pytest_index = next(
        index for index, (command, _) in enumerate(commands) if "pytest" in command
    )
    pytest_environment = commands[pytest_index][1]

    assert db_start_index < pytest_index
    assert pytest_environment is not None
    assert pytest_environment["DB_HOST"] == "127.0.0.1"
    assert pytest_environment["DB_PORT"] == "48124"
