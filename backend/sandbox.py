"""Restricted code execution with a Docker-first policy and safe fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


@dataclass
class ExecutionResult:
    passed: bool
    status: str
    output: str
    error: str
    duration_ms: int
    sandbox: str
    command: str
    failing_tests: list[str] = field(default_factory=list)
    assertion_error: str = ""
    traceback_snippet: str = ""
    passed_count: int = 0
    total_count: int = 0
    failure_details: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "output": self.output[-8000:],
            "error": self.error[-8000:],
            "duration_ms": self.duration_ms,
            "sandbox": self.sandbox,
            "command": self.command,
            "failing_tests": self.failing_tests,
            "assertion_error": self.assertion_error,
            "traceback_snippet": self.traceback_snippet,
            "passed_count": self.passed_count,
            "total_count": self.total_count,
            "failure_details": self.failure_details,
        }


def parse_unittest_telemetry(stdout: str, stderr: str) -> dict[str, Any]:
    """Extract granular test execution statistics and failure traces from unittest output."""
    combined = f"{stdout}\n{stderr}".strip()
    total_match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    total_count = int(total_match.group(1)) if total_match else 0

    failing_tests: list[str] = []
    failure_details: list[dict[str, str]] = []
    primary_assertion: str = ""
    primary_traceback: str = ""

    # Split on standard unittest error divider blocks
    sections = re.split(r"={40,}", combined)
    for section in sections[1:]:
        lines = [line.strip() for line in section.strip().splitlines() if line.strip()]
        if not lines:
            continue
        first_line = lines[0]
        header_match = re.match(r"(FAIL|ERROR):\s+([a-zA-Z0-9_]+)\s*(?:\((.*?)\))?", first_line)
        if header_match:
            kind, test_name, test_suite = header_match.groups()
            failing_tests.append(test_name)

            tb_lines = []
            in_tb = False
            for line in lines[1:]:
                if "Ran " in line or line.startswith("FAILED") or line.startswith("OK"):
                    break
                if line.startswith("---"):
                    continue
                if "Traceback (most recent call last):" in line:
                    in_tb = True
                if in_tb:
                    tb_lines.append(line)

            err_line = tb_lines[-1] if tb_lines else (lines[-1] if len(lines) > 1 else "")
            detail = {
                "kind": kind,
                "test": test_name,
                "suite": test_suite or "",
                "error": err_line,
                "traceback": "\n".join(tb_lines[-8:]),
            }
            failure_details.append(detail)
            if not primary_assertion:
                primary_assertion = err_line
                primary_traceback = "\n".join(tb_lines)

    test_status_matches = re.findall(
        r"^([a-zA-Z0-9_]+)\s+\((.*?)\)\s+\.\.\.\s+(ok|FAIL|ERROR)", combined, re.M
    )
    passed_tests = [m[0] for m in test_status_matches if m[2] == "ok"]
    failed_from_status = [m[0] for m in test_status_matches if m[2] in ("FAIL", "ERROR")]

    unique_failing: list[str] = []
    for t in failing_tests or failed_from_status:
        if t not in unique_failing:
            unique_failing.append(t)

    passed_count = (
        len(passed_tests)
        if passed_tests
        else (total_count - len(unique_failing) if total_count >= len(unique_failing) else 0)
    )
    if "OK" in combined and not unique_failing:
        passed_count = total_count

    return {
        "total_count": total_count,
        "passed_count": max(0, passed_count),
        "failing_tests": unique_failing,
        "failure_details": failure_details,
        "assertion_error": primary_assertion,
        "traceback_snippet": primary_traceback[-1200:] if primary_traceback else "",
    }


def _docker_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        probe = subprocess.run(
            [docker, "image", "inspect", "python:3.12-slim"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return probe.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _run_process(workdir: Path, command: list[str], display_command: str, sandbox: str) -> ExecutionResult:
    started = time.perf_counter()
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def limits() -> None:
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
        except (ImportError, OSError):
            pass

    try:
        process = subprocess.run(
            command,
            cwd=workdir,
            env=safe_env,
            capture_output=True,
            text=True,
            timeout=6,
            preexec_fn=limits if os.name == "posix" and sandbox != "docker" else None,
        )
        duration = int((time.perf_counter() - started) * 1000)
        telemetry = parse_unittest_telemetry(process.stdout, process.stderr)
        return ExecutionResult(
            passed=process.returncode == 0,
            status="passed" if process.returncode == 0 else "failed",
            output=process.stdout,
            error=process.stderr,
            duration_ms=duration,
            sandbox=sandbox,
            command=display_command,
            failing_tests=telemetry["failing_tests"],
            assertion_error=telemetry["assertion_error"],
            traceback_snippet=telemetry["traceback_snippet"],
            passed_count=telemetry["passed_count"],
            total_count=telemetry["total_count"],
            failure_details=telemetry["failure_details"],
        )
    except subprocess.TimeoutExpired as exc:
        duration = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            passed=False,
            status="timeout",
            output=exc.stdout or "",
            error="Execution exceeded the 6 second safety limit.",
            duration_ms=duration,
            sandbox=sandbox,
            command=display_command,
            assertion_error="TimeoutExpired: Execution exceeded 6 second limit",
        )
    except OSError as exc:
        duration = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            passed=False,
            status="error",
            output="",
            error=str(exc),
            duration_ms=duration,
            sandbox=sandbox,
            command=display_command,
            assertion_error=str(exc),
        )


def run_python_tests(code: str, tests: str) -> dict[str, Any]:
    """Run generated code against hidden tests, returning JSON-safe details."""

    with tempfile.TemporaryDirectory(prefix="bobbuilders-") as folder:
        workdir = Path(folder)
        (workdir / "main.py").write_text(code, encoding="utf-8")
        (workdir / "test_main.py").write_text(tests, encoding="utf-8")

        if _docker_available():
            command = [
                "docker", "run", "--rm", "--network", "none", "--read-only", "--cpus", "1",
                "--memory", "256m", "--pids-limit", "64", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
                "-v", f"{workdir}:/workspace:ro", "-w", "/workspace", "python:3.12-slim", "python", "-m",
                "unittest", "discover", "-s", ".", "-p", "test_main.py", "-v",
            ]
            display = "docker run --rm --network none --read-only python:3.12-slim python -m unittest"
            return _run_process(workdir, command, display, "docker").as_dict()

        result = _run_process(
            workdir,
            [sys.executable, "-I", "-m", "unittest", "discover", "-s", ".", "-p", "test_main.py", "-v"],
            f"{Path(sys.executable).name} -I -m unittest discover -p test_main.py",
            "local-restricted",
        )
        return result.as_dict()

