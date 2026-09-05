"""Validate HelixHealth through isolated tests and a disposable Compose stack."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ACCEPTANCE_PASSWORD_ENV = "HELIX_ACCEPTANCE_PASSWORD"


class ValidationError(RuntimeError):
    """Raised when the local live-validation environment is unavailable."""


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print(f"> {' '.join(command)}", flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def repository_root() -> Path:
    result = run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
        capture_output=True,
    )
    return Path(result.stdout.strip()).resolve()


def require_executed_browser_tests(report: Path) -> int:
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    executed = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)

    if executed == 0:
        raise ValidationError("The browser suite did not select any tests.")
    if skipped:
        raise ValidationError(f"The isolated browser suite skipped {skipped} test(s).")
    return executed


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_http(base_url: str, *, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base_url, timeout=2) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
        time.sleep(0.5)
    raise ValidationError(
        f"Compose web service did not become ready at {base_url}: {last_error}"
    )


def compose_environment() -> tuple[dict[str, str], str, str]:
    web_port = available_port()
    db_port = available_port()
    while db_port == web_port:
        db_port = available_port()

    project_name = f"helixhealth-validation-{secrets.token_hex(6)}"
    password = f"Acceptance-{secrets.token_urlsafe(24)}"
    environment = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": project_name,
        "DJANGO_ENVIRONMENT": "development",
        "DB_HOST": "127.0.0.1",
        "DB_NAME": "helixhealth_acceptance",
        "DB_USER": "helixhealth_acceptance",
        "DB_PASSWORD": password,
        "DB_PORT": str(db_port),
        "DJANGO_PORT": str(web_port),
        ACCEPTANCE_PASSWORD_ENV: password,
    }
    return environment, project_name, f"http://127.0.0.1:{web_port}"


def compose_command(project_name: str, *arguments: str) -> list[str]:
    if not project_name.startswith("helixhealth-validation-"):
        raise ValidationError(f"Unsafe Compose project name: {project_name}")
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        *arguments,
    ]


def validate_compose_stack(root: Path, artifact_dir: Path) -> tuple[int, int]:
    environment, project_name, base_url = compose_environment()
    succeeded = False
    try:
        run(
            compose_command(project_name, "build", "web"),
            cwd=root,
            env=environment,
        )
        run(
            compose_command(project_name, "up", "-d", "--wait", "db"),
            cwd=root,
            env=environment,
        )
        run(
            ["uv", "run", "python", "manage.py", "check"],
            cwd=root,
            env=environment,
        )
        report = artifact_dir / "isolated-browser-results.xml"
        run(
            [
                "uv",
                "run",
                "pytest",
                "-m",
                "browser",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={report}",
            ],
            cwd=root,
            env=environment,
        )
        isolated_count = require_executed_browser_tests(report)
        run(
            compose_command(
                project_name,
                "run",
                "--rm",
                "web",
                "python",
                "manage.py",
                "migrate",
                "--noinput",
            ),
            cwd=root,
            env=environment,
        )
        run(
            compose_command(
                project_name,
                "run",
                "--rm",
                "-e",
                ACCEPTANCE_PASSWORD_ENV,
                "web",
                "python",
                "manage.py",
                "seed_acceptance",
            ),
            cwd=root,
            env=environment,
        )
        run(
            compose_command(project_name, "up", "-d", "--wait", "web"),
            cwd=root,
            env=environment,
        )
        wait_for_http(base_url)
        run(
            compose_command(
                project_name,
                "exec",
                "-T",
                "web",
                "python",
                "manage.py",
                "check",
            ),
            cwd=root,
            env=environment,
        )
        run(
            [
                "uv",
                "run",
                "python",
                ".agents/skills/validate-live-app/scripts/run_compose_acceptance.py",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
            ],
            cwd=root,
            env=environment,
        )
        run(
            compose_command(
                project_name,
                "exec",
                "-T",
                "web",
                "python",
                "manage.py",
                "verify_acceptance",
            ),
            cwd=root,
            env=environment,
        )
        summary = artifact_dir / "compose-browser-summary.json"
        journey_results = json.loads(summary.read_text(encoding="utf-8"))
        succeeded = True
        return isolated_count, len(journey_results)
    finally:
        logs: subprocess.CompletedProcess[str] | None = None
        cleanup: subprocess.CompletedProcess[str] | None = None
        cleanup_error: OSError | None = None
        try:
            logs = run(
                compose_command(project_name, "logs", "--no-color", "web", "db"),
                cwd=root,
                env=environment,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            print(f"Unable to capture Compose logs: {error}", file=sys.stderr)
        try:
            cleanup = run(
                compose_command(
                    project_name,
                    "down",
                    "--rmi",
                    "local",
                    "--volumes",
                    "--remove-orphans",
                ),
                cwd=root,
                env=environment,
                check=False,
            )
        except OSError as error:
            cleanup_error = error
            print(f"Unable to run Compose cleanup: {error}", file=sys.stderr)
        cleanup_failed = cleanup_error is not None or (
            cleanup is not None and cleanup.returncode != 0
        )
        if not succeeded or cleanup_failed:
            log_output = (
                f"{logs.stdout}\n{logs.stderr}"
                if logs is not None
                else "Compose logs were unavailable."
            )
            try:
                (artifact_dir / "compose.log").write_text(
                    log_output,
                    encoding="utf-8",
                )
            except OSError as error:
                print(f"Unable to save Compose logs: {error}", file=sys.stderr)
            print(f"Compose validation artifacts: {artifact_dir}", file=sys.stderr)
        if cleanup_failed and succeeded:
            detail = (
                str(cleanup_error)
                if cleanup_error is not None
                else f"exit code {cleanup.returncode if cleanup is not None else 'unknown'}"
            )
            raise ValidationError(
                "Compose validation passed but cleanup failed for "
                f"{project_name}: {detail}."
            )


def main() -> int:
    root = repository_root()
    if not (root / "compose.yaml").is_file():
        raise ValidationError(f"compose.yaml was not found at repository root: {root}")

    artifact_dir = Path(
        tempfile.mkdtemp(prefix="helixhealth-live-validation-")
    ).resolve()
    succeeded = False
    try:
        isolated_count, compose_count = validate_compose_stack(root, artifact_dir)
        succeeded = True
    finally:
        if succeeded:
            shutil.rmtree(artifact_dir)
        else:
            print(f"Live validation artifacts: {artifact_dir}", file=sys.stderr)

    print(
        "Live application validation passed: "
        f"{isolated_count} isolated browser tests and "
        f"{compose_count} Compose browser journeys; 0 skipped.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, ValidationError) as error:
        print(f"Live application validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
