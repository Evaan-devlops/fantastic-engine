"""Unit and integration tests for the CLI entry point."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


def _run(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run the CLI as a module via sys.executable for cross-platform portability."""
    return subprocess.run(
        [sys.executable, "-m", "sop_automation.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# 1. --help exits 0 and contains all command groups
# ---------------------------------------------------------------------------

class TestHelpCommand:
    def test_help_exits_zero(self) -> None:
        result = _run("--help")
        assert result.returncode == 0, f"Expected 0, got {result.returncode}\n{result.stderr}"

    def test_help_lists_workspace_group(self) -> None:
        result = _run("--help")
        assert "workspace" in result.stdout

    def test_help_lists_sop_group(self) -> None:
        result = _run("--help")
        assert "sop" in result.stdout

    def test_help_lists_task_group(self) -> None:
        result = _run("--help")
        assert "task" in result.stdout

    def test_help_lists_tool_group(self) -> None:
        result = _run("--help")
        assert "tool" in result.stdout


# ---------------------------------------------------------------------------
# 2. Stub commands exit with code 2 and print NOT_IMPLEMENTED_IN_POC
# ---------------------------------------------------------------------------

STUB_COMMANDS = [
    "tool list",
    "tool validate-build-request",
]

# Commands now implemented but require arguments — argparse exits 2 without args
PHASE1_COMMANDS_NEED_ARGS = [
    "sop prepare",
    "sop validate-result",
    "sop compile",
    "task plan",
    "task prepare-intent",
    "task validate-intent",
    "task submit",
    "task status",
    "task continue",
    "task cancel",
]

# All implemented commands — must NOT appear in STUB_COMMANDS
PHASE1_IMPLEMENTED_COMMANDS = {
    "sop prepare",
    "sop validate-result",
    "sop compile",
    "sop list",
    "task plan",
    "task prepare-intent",
    "task validate-intent",
    "task submit",
    "task status",
    "task continue",
    "task cancel",
}


class TestStubCommands:
    @pytest.mark.parametrize("command", STUB_COMMANDS)
    def test_stub_exits_with_code_2(self, command: str) -> None:
        result = _run(*command.split())
        assert result.returncode == 2, (
            f"Command '{command}' should return 2, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("command", STUB_COMMANDS)
    def test_stub_prints_not_implemented_message(self, command: str) -> None:
        result = _run(*command.split())
        assert "NOT_IMPLEMENTED_IN_POC" in result.stdout, (
            f"Command '{command}' stdout missing NOT_IMPLEMENTED_IN_POC:\n{result.stdout}"
        )


class TestPhase1CommandsAreNotStubs:
    """Verify implemented commands are not in the stub set."""

    def test_phase1_commands_not_in_stub_set(self) -> None:
        stub_set = set(STUB_COMMANDS)
        for cmd in PHASE1_IMPLEMENTED_COMMANDS:
            assert cmd not in stub_set, (
                f"Implemented command '{cmd}' must not be listed as a stub"
            )


class TestPhase1CommandsMissingArgs:
    """Implemented commands require arguments.
    Without args argparse prints usage to stderr and exits 2.
    """

    @pytest.mark.parametrize("command", PHASE1_COMMANDS_NEED_ARGS)
    def test_exits_nonzero_without_args(self, command: str) -> None:
        result = _run(*command.split())
        assert result.returncode != 0, (
            f"Command '{command}' without required args should exit non-zero, "
            f"got {result.returncode}"
        )


# ---------------------------------------------------------------------------
# 3. workspace init creates directories
# ---------------------------------------------------------------------------

class TestWorkspaceInit:
    def test_workspace_init_exits_zero(self, tmp_path: Path) -> None:
        result = _run("workspace", "init", "--workspace", str(tmp_path))
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\n{result.stderr}"
        )

    def test_workspace_init_creates_all_dirs(self, tmp_path: Path) -> None:
        _run("workspace", "init", "--workspace", str(tmp_path))
        expected = [
            "inbox", "sources", "compiled", "manifests", "runs",
            "resolutions", "routes", "tool_build_requests", "tools", "generated",
            "runtime", str(Path("runtime") / "commands"), str(Path("runtime") / "acknowledgements"),
        ]
        for subdir in expected:
            assert (tmp_path / subdir).is_dir(), f"Directory not created: {subdir}"

    def test_workspace_init_stdout_contains_created_tag(self, tmp_path: Path) -> None:
        result = _run("workspace", "init", "--workspace", str(tmp_path))
        assert "[CREATED]" in result.stdout

    def test_workspace_init_prints_success_message(self, tmp_path: Path) -> None:
        result = _run("workspace", "init", "--workspace", str(tmp_path))
        assert "initialized successfully" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 4. workspace init is idempotent
# ---------------------------------------------------------------------------

class TestWorkspaceInitIdempotency:
    def test_second_run_exits_zero(self, tmp_path: Path) -> None:
        _run("workspace", "init", "--workspace", str(tmp_path))
        result2 = _run("workspace", "init", "--workspace", str(tmp_path))
        assert result2.returncode == 0

    def test_second_run_output_contains_exists_tag(self, tmp_path: Path) -> None:
        _run("workspace", "init", "--workspace", str(tmp_path))
        result2 = _run("workspace", "init", "--workspace", str(tmp_path))
        assert "[EXISTS]" in result2.stdout

    def test_second_run_has_no_created_tag(self, tmp_path: Path) -> None:
        _run("workspace", "init", "--workspace", str(tmp_path))
        result2 = _run("workspace", "init", "--workspace", str(tmp_path))
        assert "[CREATED]" not in result2.stdout


# ---------------------------------------------------------------------------
# 5. workspace init stdout format — 13 directories (Phase 2 added runtime/)
# ---------------------------------------------------------------------------

class TestWorkspaceInitOutputFormat:
    _LINE_PATTERN = re.compile(r"^\[(CREATED|EXISTS|ERROR)\]\s+\S+")

    def test_output_lines_match_pattern(self, tmp_path: Path) -> None:
        result = _run("workspace", "init", "--workspace", str(tmp_path))
        lines = [
            line for line in result.stdout.splitlines()
            if line.strip() and not line.strip().startswith("Workspace")
        ]
        for line in lines:
            assert self._LINE_PATTERN.match(line), (
                f"Line does not match expected format: '{line}'"
            )

    def test_output_contains_thirteen_status_lines(self, tmp_path: Path) -> None:
        result = _run("workspace", "init", "--workspace", str(tmp_path))
        status_lines = [
            line for line in result.stdout.splitlines()
            if self._LINE_PATTERN.match(line)
        ]
        assert len(status_lines) == 13, (
            f"Expected 13 status lines, got {len(status_lines)}:\n{result.stdout}"
        )
