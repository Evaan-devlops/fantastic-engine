"""CLI entry point — all commands wired via argparse."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sop_automation.config import get_config
from sop_automation.errors import NotImplementedInPhase0Error
from sop_automation.services.workspace import WorkspaceService


def _not_implemented(command: str) -> None:
    """Print the stub message and exit with code 2."""
    raise NotImplementedInPhase0Error(command)


# ---------------------------------------------------------------------------
# workspace commands
# ---------------------------------------------------------------------------

def cmd_workspace_init(args: argparse.Namespace) -> int:
    """Create all required SOP directories in the workspace."""
    config = get_config()
    root = Path(args.workspace) if args.workspace else config.sop_workspace

    service = WorkspaceService()
    results = service.init(root)

    has_error = False
    for rel_path, status in results:
        tag = f"[{status}]"
        # Pad tag to 9 chars for alignment: [CREATED] / [EXISTS]  / [ERROR]
        print(f"{tag:<9} {rel_path}")
        if status == "ERROR":
            has_error = True

    if has_error:
        print("\nWorkspace initialisation completed with errors.")
        return 1

    print("\nWorkspace initialized successfully.")
    return 0


# ---------------------------------------------------------------------------
# sop commands
# ---------------------------------------------------------------------------

def cmd_sop_prepare(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.sop_prepare import SopPrepareService
    config = get_config()
    try:
        result = SopPrepareService().prepare(
            workspace_root=config.sop_workspace,
            source_path=Path(args.source),
            sop_id=args.sop_id,
        )
        print(f"Preprocessing: {args.source}")
        print(f"Interpretation request: {result.request_path}")
        print(
            "Next: ask Copilot to read the request and write interpretation_result.json "
            "in the same directory."
        )
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_sop_validate_result(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.sop_validate import SopValidateService
    config = get_config()
    try:
        result = SopValidateService().validate(
            result_path=Path(args.result),
            workspace_root=config.sop_workspace,
        )
        status = "PASS" if result.report.passed else "FAIL"
        print(f"Validation: {status}")
        for issue in result.report.issues:
            loc = f" [{issue.location}]" if issue.location else ""
            print(f"  [{issue.severity}] {issue.rule_id}{loc}: {issue.message}")
        print(f"Validation report: {result.report_path}")
        return 0 if result.report.passed else 1
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_sop_compile(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.sop_compile import SopCompileService
    config = get_config()
    try:
        result = SopCompileService().compile(
            result_path=Path(args.result),
            workspace_root=config.sop_workspace,
        )
        print(f"Compiled SOP: {result.compiled_sop_path}")
        print(f"Manifest:     {result.manifest_path}")
        print(f"Markdown:     {result.markdown_path}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_sop_list(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.sop_list import SopListService
    config = get_config()
    try:
        entries = SopListService().list_sops(workspace_root=config.sop_workspace)
        if not entries:
            print("No compiled SOPs found.")
            return 0
        print(f"{'SOP ID':<30}  {'Title':<40}  {'Goals':<30}  Compiled At")
        print("-" * 110)
        for e in entries:
            goals_str = ", ".join(e.goals[:3])
            if len(e.goals) > 3:
                goals_str += f" (+{len(e.goals) - 3})"
            print(
                f"{e.sop_id:<30}  {e.title:<40}  {goals_str:<30}  "
                f"{e.compiled_at.isoformat()}"
            )
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# task commands
# ---------------------------------------------------------------------------

def cmd_task_plan(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.task_plan import TaskPlanService
    config = get_config()
    # Parse --input name=value pairs
    inputs: dict[str, str] = {}
    for item in getattr(args, "input", []) or []:
        if "=" not in item:
            print(
                f"Error: --input must be in name=value format, got: {item!r}",
                file=sys.stderr,
            )
            return 1
        name, _, value = item.partition("=")
        inputs[name.strip()] = value.strip()
    try:
        result = TaskPlanService().plan(
            workspace_root=config.sop_workspace,
            sop_id=args.sop,
            goal_id=args.goal,
            inputs=inputs,
        )
        plan = result.plan
        print(f"Task Plan: {plan.sop_id} / {plan.goal_id}")
        if inputs:
            print(f"Inputs: {', '.join(f'{k}={v}' for k, v in inputs.items())}")
        for cap in plan.capabilities:
            if cap.is_deferred:
                continue
            for step in cap.steps:
                val_part = f" -> '{step.value}'" if step.value else ""
                wait_part = (
                    f" (wait: {step.wait_condition.type if step.wait_condition else ''})"
                    if step.wait_condition else ""
                )
                print(
                    f"  {step.sequence}. [{cap.name}] "
                    f"{step.action} {step.element_name} "
                    f"({step.element_type}){val_part}{wait_part}"
                )
        for bp in plan.branch_points:
            print(f"Branch point: {bp.step_id} ({len(bp.outcomes)} outcomes)")
        for d in plan.deferred_destinations:
            print(f"Deferred (not executable): {d}")
        print(f"Plan saved: {result.plan_path}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_prepare_intent(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.services.task_intent import TaskIntentService
    config = get_config()
    try:
        source = Path(args.request_file)
        if not source.exists():
            print(f"Error: file not found: {source}", file=sys.stderr)
            return 1
        request_text = source.read_text(encoding="utf-8")
        result = TaskIntentService().prepare_intent(
            request_text=request_text,
            workspace_root=config.sop_workspace,
            sop_id=getattr(args, "sop_id", None),
        )
        print(f"TaskIntent created: {result.intent_path}")
        print(f"Goal: {result.intent.requested_goal}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_validate_intent(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.models.task import TaskIntent
    from sop_automation.services.task_intent import TaskIntentService
    from sop_automation.storage.json_store import read_json
    config = get_config()
    try:
        intent = TaskIntent.model_validate(read_json(Path(args.intent_file)))
        result = TaskIntentService().validate_intent(
            intent=intent,
            workspace_root=config.sop_workspace,
        )
        status = "PASS" if result.passed else "FAIL"
        print(f"Intent validation: {status}")
        for issue in result.report.issues:
            print(f"  [{issue.severity}] {issue.rule_id}: {issue.message}")
        return 0 if result.passed else 1
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_submit(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.models.runtime import RuntimeCommand, RuntimeCommandType
    from sop_automation.models.task import TaskIntent
    from sop_automation.services.sop_selector import SopSelectorService
    from sop_automation.services.task_plan import TaskPlanService
    from sop_automation.runtime.command_queue import submit_command
    from sop_automation.storage.json_store import new_id, read_json, utc_now
    from sop_automation.storage.paths import WorkspacePaths
    config = get_config()
    try:
        intent = TaskIntent.model_validate(read_json(Path(args.intent_file)))
        selection = SopSelectorService().select(intent, config.sop_workspace)
        plan_result = TaskPlanService().plan(
            workspace_root=config.sop_workspace,
            sop_id=selection.sop_id,
            goal_id=selection.goal_id,
            inputs=intent.inputs,
        )
        paths = WorkspacePaths.from_root(config.sop_workspace)
        command = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.START_RUN,
            payload={"plan_path": str(plan_result.plan_path)},
            created_at=utc_now(),
        )
        submit_command(paths.runtime_commands, command)
        print(f"Command submitted: {command.command_id}")
        print(f"SOP: {selection.sop_id} / Goal: {selection.goal_id}")
        print(f"Plan: {plan_result.plan_path}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_status(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.models.execution import RunState
    from sop_automation.storage.json_store import read_json
    from sop_automation.storage.paths import resolve_path
    config = get_config()
    try:
        state_path = resolve_path(config.sop_workspace, f"runs/{args.run_id}/run_state.json")
        if not state_path.exists():
            print(f"Run not found: {args.run_id}", file=sys.stderr)
            return 1
        state = RunState.model_validate(read_json(state_path))
        print(f"Run: {state.run_id}")
        print(f"Status: {state.status}")
        print(f"Current capability: {state.current_capability_id or 'N/A'}")
        print(f"Current step: {state.current_step_id or 'N/A'}")
        completed = [k for k, v in state.step_progress.items() if v.status.value == "COMPLETED"]
        failed = [k for k, v in state.step_progress.items() if v.status.value == "FAILED"]
        print(f"Steps completed: {len(completed)}, failed: {len(failed)}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_continue(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.models.common import RunStatus
    from sop_automation.models.execution import RunState
    from sop_automation.models.runtime import RuntimeCommand, RuntimeCommandType
    from sop_automation.runtime.command_queue import submit_command
    from sop_automation.storage.json_store import new_id, read_json, utc_now
    from sop_automation.storage.paths import WorkspacePaths, resolve_path
    config = get_config()
    try:
        state_path = resolve_path(config.sop_workspace, f"runs/{args.run_id}/run_state.json")
        if not state_path.exists():
            print(f"Run not found: {args.run_id}", file=sys.stderr)
            return 1
        state = RunState.model_validate(read_json(state_path))
        if state.status != RunStatus.WAITING_FOR_AUTH:
            print(f"Run is not waiting for auth (status: {state.status})", file=sys.stderr)
            return 1
        paths = WorkspacePaths.from_root(config.sop_workspace)
        command = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.CONTINUE_RUN,
            payload={"run_id": args.run_id},
            created_at=utc_now(),
        )
        submit_command(paths.runtime_commands, command)
        print(f"Continue command submitted: {command.command_id}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_task_cancel(args: argparse.Namespace) -> int:
    from sop_automation.errors import SopAutomationError
    from sop_automation.models.runtime import RuntimeCommand, RuntimeCommandType
    from sop_automation.runtime.command_queue import submit_command
    from sop_automation.storage.json_store import new_id, utc_now
    from sop_automation.storage.paths import WorkspacePaths
    config = get_config()
    try:
        paths = WorkspacePaths.from_root(config.sop_workspace)
        command = RuntimeCommand(
            command_id=new_id(),
            command_type=RuntimeCommandType.CANCEL_RUN,
            payload={"run_id": args.run_id},
            created_at=utc_now(),
        )
        submit_command(paths.runtime_commands, command)
        print(f"Cancel command submitted: {command.command_id}")
        return 0
    except SopAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# runtime commands
# ---------------------------------------------------------------------------

def cmd_runtime_start(args: argparse.Namespace) -> int:
    import asyncio
    from sop_automation.runtime.host import run_host
    config = get_config()
    try:
        asyncio.run(run_host(config.sop_workspace))
        return 0
    except KeyboardInterrupt:
        return 0


# ---------------------------------------------------------------------------
# stub handler
# ---------------------------------------------------------------------------

def _stub(command: str) -> int:
    """Standard stub response."""
    print(f"NOT_IMPLEMENTED_IN_POC: '{command}' will be available in a future phase.")
    return 2


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sop",
        description="SOPAutomationV2 — operate browser-based apps from validated SOPs.",
    )
    sub = parser.add_subparsers(dest="group", metavar="<group>")
    sub.required = True

    # ---- workspace ----
    ws = sub.add_parser("workspace", help="Manage the SOP workspace.")
    ws_sub = ws.add_subparsers(dest="command", metavar="<command>")
    ws_sub.required = True

    ws_init = ws_sub.add_parser(
        "init",
        help="Create all required SOP directories in the workspace.",
    )
    ws_init.add_argument(
        "--workspace",
        metavar="PATH",
        default=None,
        help="Override workspace root (default: SOP_WORKSPACE env or ./SOP).",
    )

    # ---- sop ----
    sop = sub.add_parser("sop", help="Manage SOPs.")
    sop_sub = sop.add_subparsers(dest="command", metavar="<command>")
    sop_sub.required = True

    sop_prepare = sop_sub.add_parser(
        "prepare",
        help="Prepare a SOP source for interpretation.",
    )
    sop_prepare.add_argument(
        "--source",
        metavar="PATH",
        required=True,
        help="Path to the SOP source file (.txt, .md, .csv, .xlsx).",
    )
    sop_prepare.add_argument(
        "--sop-id",
        metavar="ID",
        dest="sop_id",
        required=True,
        help="Unique SOP identifier (alphanumeric, hyphens, underscores, 1-64 chars).",
    )

    sop_validate = sop_sub.add_parser(
        "validate-result",
        help="Validate an interpretation result.",
    )
    sop_validate.add_argument(
        "--result",
        metavar="PATH",
        required=True,
        help="Path to interpretation_result.json written by Copilot.",
    )

    sop_compile = sop_sub.add_parser(
        "compile",
        help="Compile a validated SOP.",
    )
    sop_compile.add_argument(
        "--result",
        metavar="PATH",
        required=True,
        help="Path to interpretation_result.json (must have passed validation).",
    )

    sop_sub.add_parser("list", help="List compiled SOPs.")

    # ---- task ----
    task = sub.add_parser("task", help="Manage task execution.")
    task_sub = task.add_subparsers(dest="command", metavar="<command>")
    task_sub.required = True

    task_prepare_intent = task_sub.add_parser(
        "prepare-intent",
        help="Prepare a task intent from a request file.",
    )
    task_prepare_intent.add_argument(
        "request_file",
        metavar="REQUEST_FILE",
        help="Path to a text file describing the task goal and inputs.",
    )
    task_prepare_intent.add_argument(
        "--sop-id",
        metavar="ID",
        dest="sop_id",
        default=None,
        help="Optional preferred SOP ID.",
    )

    task_validate_intent = task_sub.add_parser(
        "validate-intent",
        help="Validate a task intent JSON file.",
    )
    task_validate_intent.add_argument(
        "intent_file",
        metavar="INTENT_FILE",
        help="Path to a task_intent.json file.",
    )

    task_submit = task_sub.add_parser(
        "submit",
        help="Submit a task intent to the runtime for execution.",
    )
    task_submit.add_argument(
        "intent_file",
        metavar="INTENT_FILE",
        help="Path to a task_intent.json file.",
    )

    task_plan = task_sub.add_parser(
        "plan",
        help="Build a dry-run task plan from a compiled SOP.",
    )
    task_plan.add_argument(
        "--sop",
        metavar="SOP_ID",
        required=True,
        help="SOP ID to plan from.",
    )
    task_plan.add_argument(
        "--goal",
        metavar="GOAL_ID",
        required=True,
        help="Goal ID within the compiled SOP.",
    )
    task_plan.add_argument(
        "--input",
        metavar="NAME=VALUE",
        action="append",
        dest="input",
        help="Input value (repeatable). Format: name=value.",
    )

    task_status = task_sub.add_parser(
        "status",
        help="Show the status of a task run.",
    )
    task_status.add_argument(
        "run_id",
        metavar="RUN_ID",
        help="Run ID to query.",
    )

    task_continue = task_sub.add_parser(
        "continue",
        help="Continue a run that is waiting for authentication.",
    )
    task_continue.add_argument(
        "run_id",
        metavar="RUN_ID",
        help="Run ID to continue.",
    )

    task_cancel = task_sub.add_parser(
        "cancel",
        help="Cancel a running task.",
    )
    task_cancel.add_argument(
        "run_id",
        metavar="RUN_ID",
        help="Run ID to cancel.",
    )

    # ---- runtime ----
    runtime = sub.add_parser("runtime", help="Manage the foreground browser runtime.")
    runtime_sub = runtime.add_subparsers(dest="command", metavar="<command>")
    runtime_sub.required = True

    runtime_sub.add_parser(
        "start",
        help="Start the foreground runtime host (watches for commands and drives the browser).",
    )

    # ---- tool ----
    tool = sub.add_parser("tool", help="Manage the capability tool catalogue.")
    tool_sub = tool.add_subparsers(dest="command", metavar="<command>")
    tool_sub.required = True

    tool_sub.add_parser("list", help="List registered tools.")
    tool_sub.add_parser(
        "validate-build-request",
        help="Validate a tool build request.",
    )

    return parser


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_STUB_COMMANDS: set[tuple[str, str]] = {
    ("tool", "list"),
    ("tool", "validate-build-request"),
}


def main() -> int:
    """CLI entry point — returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args()

    group: str = args.group
    command: str = args.command

    if (group, command) in _STUB_COMMANDS:
        return _stub(f"{group} {command}")

    if group == "workspace" and command == "init":
        return cmd_workspace_init(args)
    if group == "sop" and command == "prepare":
        return cmd_sop_prepare(args)
    if group == "sop" and command == "validate-result":
        return cmd_sop_validate_result(args)
    if group == "sop" and command == "compile":
        return cmd_sop_compile(args)
    if group == "sop" and command == "list":
        return cmd_sop_list(args)
    if group == "task" and command == "plan":
        return cmd_task_plan(args)
    if group == "task" and command == "prepare-intent":
        return cmd_task_prepare_intent(args)
    if group == "task" and command == "validate-intent":
        return cmd_task_validate_intent(args)
    if group == "task" and command == "submit":
        return cmd_task_submit(args)
    if group == "task" and command == "status":
        return cmd_task_status(args)
    if group == "task" and command == "continue":
        return cmd_task_continue(args)
    if group == "task" and command == "cancel":
        return cmd_task_cancel(args)
    if group == "runtime" and command == "start":
        return cmd_runtime_start(args)

    # Unreachable if _STUB_COMMANDS is complete, but guards against future gaps.
    print(f"NOT_IMPLEMENTED_IN_POC: '{group} {command}'")
    return 2


if __name__ == "__main__":
    sys.exit(main())
