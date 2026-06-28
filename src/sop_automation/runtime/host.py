"""Foreground runtime host: watches command queue and drives Playwright."""
from __future__ import annotations

import asyncio
from pathlib import Path

from sop_automation.models.common import RunStatus
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

_TERMINAL_RUN_STATUSES = frozenset({
    RunStatus.COMPLETED.value,
    RunStatus.PARTIAL_SUCCESS.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
})


class RuntimeHost:
    """Foreground host: owns Playwright, processes commands, runs one task at a time."""

    _POLL_INTERVAL = 0.2
    _AUTH_POLL_TIMEOUT = 10.0
    _AUTH_POLL_STEP = 0.1

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
                write_acknowledgement(acks_dir, CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=None,
                    status=AckStatus.REJECTED,
                    message=f"A run is already active: {self._active_run_id}",
                    created_at=utc_now(),
                ))
                return

            run_id = new_id()
            self._active_run_id = run_id  # claim slot before task starts
            self._execution_task = asyncio.create_task(
                self._execute_run(run_id, command, pw, acks_dir)
            )

        elif command.command_type == RuntimeCommandType.CONTINUE_RUN:
            run_id = command.payload.get("run_id", self._active_run_id)
            if run_id != self._active_run_id or self._active_manager is None:
                write_acknowledgement(acks_dir, CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message="No matching active run.",
                    created_at=utc_now(),
                ))
                return

            from sop_automation.models.execution import RunState
            state_path = resolve_path(self._workspace_root, f"runs/{run_id}/run_state.json")
            try:
                state = RunState.model_validate(read_json(state_path))
            except Exception:
                write_acknowledgement(acks_dir, CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message="Could not read run state.",
                    created_at=utc_now(),
                ))
                return

            if state.status != RunStatus.WAITING_FOR_AUTH:
                write_acknowledgement(acks_dir, CommandAcknowledgement(
                    command_id=command.command_id,
                    run_id=run_id,
                    status=AckStatus.REJECTED,
                    message=f"Run is not waiting for auth (status: {state.status})",
                    created_at=utc_now(),
                ))
                return

            manager = self._active_manager
            manager.signal_auth()  # type: ignore — wakes run_manager to re-evaluate page

            # Poll for state change (up to 10s); run_manager writes state after condition eval
            loop = asyncio.get_event_loop()
            deadline = loop.time() + self._AUTH_POLL_TIMEOUT
            state2 = state
            while loop.time() < deadline:
                await asyncio.sleep(self._AUTH_POLL_STEP)
                try:
                    state2 = RunState.model_validate(read_json(state_path))
                    if state2.status != RunStatus.WAITING_FOR_AUTH:
                        break
                except Exception:
                    break

            if state2.status == RunStatus.WAITING_FOR_AUTH:
                status_val = AckStatus.WAITING
                msg = "AUTH_STILL_REQUIRED"
            else:
                status_val = AckStatus.COMPLETED
                msg = "AUTH_VERIFIED"

            write_acknowledgement(acks_dir, CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=status_val,
                message=msg,
                created_at=utc_now(),
            ))

        elif command.command_type == RuntimeCommandType.CANCEL_RUN:
            run_id = command.payload.get("run_id", self._active_run_id)
            if self._active_manager is not None:
                self._active_manager.cancel()  # type: ignore — sets CANCELLED, wakes auth wait

            if self._execution_task is not None and not self._execution_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._execution_task), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    self._execution_task.cancel()

            # Ensure cleanup even if execution task did not finish cleanly
            await self._close_active_context()
            self._active_run_id = None
            self._active_manager = None
            self._active_plan = None
            self._active_page = None
            self._execution_task = None

            write_acknowledgement(acks_dir, CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=AckStatus.COMPLETED,
                message="Run cancelled.",
                created_at=utc_now(),
            ))

    async def _execute_run(
        self, run_id: str, command: RuntimeCommand, pw: object, acks_dir: Path
    ) -> None:
        from sop_automation.models.task import TaskPlan
        from sop_automation.runtime.run_manager import RunManager

        def _ack(status: AckStatus, msg: str | None = None) -> None:
            write_acknowledgement(acks_dir, CommandAcknowledgement(
                command_id=command.command_id,
                run_id=run_id,
                status=status,
                message=msg,
                created_at=utc_now(),
            ))

        # Stage 1: Load plan
        plan_path_str = command.payload.get("plan_path")
        if not plan_path_str:
            _ack(AckStatus.REJECTED, "START_RUN missing plan_path")
            self._active_run_id = None
            return

        try:
            plan = TaskPlan.model_validate(read_json(Path(plan_path_str)))
        except Exception as exc:
            _ack(AckStatus.FAILED, f"Could not load TaskPlan: {exc}")
            self._active_run_id = None
            return

        # Stage 2: Validate plan entry capability
        if not plan.entry_capability_id:
            _ack(AckStatus.FAILED, "TaskPlan has no entry_capability_id")
            self._active_run_id = None
            return

        # Stage 3: Create run directory
        try:
            run_dir = resolve_path(self._workspace_root, f"runs/{run_id}")
            run_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            _ack(AckStatus.FAILED, f"Could not create run directory: {exc}")
            self._active_run_id = None
            return

        profile_dir = run_dir / "browser_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Stage 4: Launch browser context
        try:
            context = await pw.chromium.launch_persistent_context(  # type: ignore
                user_data_dir=str(profile_dir),
                headless=False,
            )
        except Exception as exc:
            _ack(AckStatus.FAILED, f"Could not launch browser: {exc}")
            self._active_run_id = None
            return

        # Stage 5: Get active page
        try:
            page = context.pages[0] if context.pages else await context.new_page()
        except Exception as exc:
            await self._close_context(context)
            _ack(AckStatus.FAILED, f"Could not get browser page: {exc}")
            self._active_run_id = None
            return

        # Stage 6: Attach RunManager and store active state
        manager = RunManager(run_dir)
        self._active_context = context
        self._active_page = page
        self._active_manager = manager
        self._active_plan = plan

        # Stage 7: Send STARTED — all startup stages passed
        _ack(AckStatus.STARTED)

        try:
            await manager.start_run(run_id, plan, page)
        except Exception as exc:
            print(f"[HOST] Run {run_id} error: {exc}")
        finally:
            run_status = (
                manager._state.status.value  # type: ignore
                if manager._state  # type: ignore
                else RunStatus.FAILED.value
            )
            if run_status in _TERMINAL_RUN_STATUSES:
                await self._close_active_context()
                self._active_run_id = None
                self._active_manager = None
                self._active_plan = None
                self._active_page = None
                self._execution_task = None
            # Nonterminal pause (WAITING_FOR_AUTH, WAITING_FOR_CLARIFICATION,
            # WAITING_FOR_DEFERRED_CAPABILITY): keep all state alive so the host
            # continues rejecting new runs and can handle future commands.

    async def _close_context(self, context: object) -> None:
        """Close an arbitrary context object without touching _active_context."""
        try:
            await context.close()  # type: ignore
        except Exception:
            pass

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
