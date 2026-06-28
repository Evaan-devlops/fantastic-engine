"""Foreground runtime host: watches command queue and drives Playwright."""
from __future__ import annotations

import asyncio
from pathlib import Path

from sop_automation.models.runtime import (
    AckStatus,
    CommandAcknowledgement,
    RuntimeCommand,
    RuntimeCommandType,
)
from sop_automation.runtime.command_queue import (
    consume_command,
    poll_commands,
    write_acknowledgement,
)
from sop_automation.storage.json_store import new_id, read_json, utc_now
from sop_automation.storage.paths import WorkspacePaths, resolve_path


class RuntimeHost:
    """Foreground host: owns Playwright, processes commands, runs one task at a time."""

    _POLL_INTERVAL = 0.2

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._paths = WorkspacePaths.from_root(workspace_root)
        self._active_run_id: str | None = None
        self._active_manager: object = None
        self._active_plan: object = None
        self._active_context: object = None
        self._active_page: object = None
        self._execution_task: asyncio.Task | None = None
        self._running = False

    async def run(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("playwright is not installed. Run: pip install playwright && playwright install chromium")
            return

        print("SOPAutomationV2 Runtime Host starting...")
        print(f"Workspace: {self._workspace_root}")
        print("Watching for commands. Press Ctrl+C to stop.")

        async with async_playwright() as pw:
            self._running = True
            try:
                await self._loop(pw)
            except asyncio.CancelledError:
                pass
            finally:
                await self._shutdown()

    async def _loop(self, pw: object) -> None:
        while self._running:
            commands_dir = self._paths.runtime_commands
            processed_dir = self._paths.runtime_processed
            failed_dir = self._paths.runtime_failed
            files = poll_commands(commands_dir)
            for cmd_file in files:
                try:
                    command = consume_command(cmd_file, processed_dir, failed_dir)
                    await self._handle_command(command, pw)
                except Exception as exc:
                    print(f"[HOST] Error processing command: {exc}")
            await asyncio.sleep(self._POLL_INTERVAL)

    async def _handle_command(self, command: RuntimeCommand, pw: object) -> None:
        acks_dir = self._paths.runtime_acks

        if command.command_type == RuntimeCommandType.START_RUN:
            if self._active_run_id is not None:
                ack = CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=None,
                    status=AckStatus.REJECTED,
                    message=f"A run is already active: {self._active_run_id}",
                    created_at=utc_now(),
                )
                write_acknowledgement(acks_dir, ack)
                return

            run_id = new_id()
            self._active_run_id = run_id
            ack = CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=AckStatus.STARTED,
                message=None,
                created_at=utc_now(),
            )
            write_acknowledgement(acks_dir, ack)

            self._execution_task = asyncio.create_task(
                self._execute_run(run_id, command, pw)
            )

        elif command.command_type == RuntimeCommandType.CONTINUE_RUN:
            run_id = command.payload.get("run_id", self._active_run_id)
            if run_id != self._active_run_id or self._active_manager is None:
                ack = CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message="No matching active run.",
                    created_at=utc_now(),
                )
                write_acknowledgement(acks_dir, ack)
                return

            from sop_automation.models.common import RunStatus
            from sop_automation.models.execution import RunState
            state_path = resolve_path(self._workspace_root, f"runs/{run_id}/run_state.json")
            try:
                state = RunState.model_validate(read_json(state_path))
            except Exception:
                ack = CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message="Could not read run state.",
                    created_at=utc_now(),
                )
                write_acknowledgement(acks_dir, ack)
                return

            if state.status != RunStatus.WAITING_FOR_AUTH:
                ack = CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message=f"Run is not waiting for auth (status: {state.status})",
                    created_at=utc_now(),
                )
                write_acknowledgement(acks_dir, ack)
                return

            manager = self._active_manager
            manager.signal_auth(True)  # type: ignore

            await asyncio.sleep(2.0)

            try:
                state2 = RunState.model_validate(read_json(state_path))
                if state2.status == RunStatus.WAITING_FOR_AUTH:
                    status_val = AckStatus.WAITING
                    msg = "AUTH_STILL_REQUIRED"
                else:
                    status_val = AckStatus.COMPLETED
                    msg = "AUTH_VERIFIED"
            except Exception:
                status_val = AckStatus.COMPLETED
                msg = "AUTH_VERIFIED"

            ack = CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=status_val,
                message=msg,
                created_at=utc_now(),
            )
            write_acknowledgement(acks_dir, ack)

        elif command.command_type == RuntimeCommandType.CANCEL_RUN:
            run_id = command.payload.get("run_id", self._active_run_id)
            if self._active_manager is not None:
                self._active_manager.cancel()  # type: ignore

            if self._execution_task is not None and not self._execution_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._execution_task), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    self._execution_task.cancel()

            await self._close_active_context()
            self._active_run_id = None
            self._active_manager = None
            self._active_plan = None
            self._execution_task = None

            ack = CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=AckStatus.COMPLETED,
                message="Run cancelled.",
                created_at=utc_now(),
            )
            write_acknowledgement(acks_dir, ack)

    async def _execute_run(
        self, run_id: str, command: RuntimeCommand, pw: object
    ) -> None:
        from sop_automation.models.task import TaskPlan
        from sop_automation.runtime.run_manager import RunManager
        from sop_automation.storage.json_store import read_json

        plan_path_str = command.payload.get("plan_path")
        if not plan_path_str:
            print("[HOST] START_RUN missing plan_path in payload")
            self._active_run_id = None
            return

        try:
            plan = TaskPlan.model_validate(read_json(Path(plan_path_str)))
        except Exception as exc:
            print(f"[HOST] Could not load TaskPlan: {exc}")
            self._active_run_id = None
            return

        run_dir = resolve_path(self._workspace_root, f"runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        profile_dir = run_dir / "browser_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            context = await pw.chromium.launch_persistent_context(  # type: ignore
                user_data_dir=str(profile_dir),
                headless=False,
            )
        except Exception as exc:
            print(f"[HOST] Could not launch browser: {exc}")
            self._active_run_id = None
            return

        page = context.pages[0] if context.pages else await context.new_page()
        self._active_context = context
        self._active_page = page

        manager = RunManager(run_dir)
        self._active_manager = manager
        self._active_plan = plan

        try:
            await manager.start_run(run_id, plan, page)
        except Exception as exc:
            print(f"[HOST] Run {run_id} failed with error: {exc}")
        finally:
            terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
            run_status = manager._state.status.value if manager._state else "FAILED"
            if run_status in terminal_statuses:
                await self._close_active_context()

            self._active_run_id = None
            self._active_manager = None
            self._active_plan = None
            self._active_page = None
            self._execution_task = None

    async def _close_active_context(self) -> None:
        if self._active_context is not None:
            try:
                await self._active_context.close()  # type: ignore
            except Exception:
                pass
            self._active_context = None

    async def _shutdown(self) -> None:
        print("\n[HOST] Shutting down...")
        if self._active_manager is not None:
            self._active_manager.cancel()  # type: ignore
        if self._execution_task is not None and not self._execution_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._execution_task), timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._execution_task.cancel()
        await self._close_active_context()
        print("[HOST] Stopped.")


async def run_host(workspace_root: Path) -> None:
    """Entry point for the foreground runtime host."""
    host = RuntimeHost(workspace_root)
    try:
        await host.run()
    except KeyboardInterrupt:
        pass
