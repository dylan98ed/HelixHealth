"""Run HelixHealth's browser suite against its real local application stack."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


class ValidationError(RuntimeError):
    """Raised when the local live-validation environment is unavailable."""


def run(
    command: list[str],
    *,
    cwd: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(f"> {' '.join(command)}", flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
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


def running_compose_services(root: Path) -> set[str]:
    result = run(
        ["docker", "compose", "ps", "--services", "--status", "running"],
        cwd=root,
        capture_output=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def require_executed_browser_tests(report: Path) -> None:
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    executed = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)

    if executed == 0:
        raise ValidationError("The browser suite did not select any tests.")
    if skipped:
        raise ValidationError(
            f"The browser suite skipped {skipped} test(s); live validation is incomplete."
        )


def main() -> int:
    root = repository_root()
    if not (root / "compose.yaml").is_file():
        raise ValidationError(f"compose.yaml was not found at repository root: {root}")

    db_was_running = "db" in running_compose_services(root)

    try:
        run(["docker", "compose", "up", "-d", "--wait", "db"], cwd=root)
        run(["uv", "run", "python", "manage.py", "check"], cwd=root)
        with tempfile.TemporaryDirectory(prefix="helixhealth-live-validation-") as tmp:
            report = Path(tmp) / "browser-results.xml"
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
            )
            require_executed_browser_tests(report)
    finally:
        if not db_was_running:
            run(["docker", "compose", "stop", "db"], cwd=root)

    print("Live application validation passed.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, ValidationError) as error:
        print(f"Live application validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
