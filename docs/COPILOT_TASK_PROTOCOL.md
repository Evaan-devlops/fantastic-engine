# Copilot Task Execution Protocol

GitHub Copilot Chat uses this 7-step protocol to trigger automation tasks via SOPAutomationV2.

## Prerequisites

- SOPAutomationV2 installed (`pip install -e .`)
- At least one compiled SOP in `SOP/compiled/`
- Runtime host running: `python -m sop_automation runtime start`

## Step 1 — Prepare Intent

```bash
python -m sop_automation task prepare-intent --request "goal=<goal_name>\n<key>=<value>"
```
Output: `SOP/generated/<intent_id>_task_intent.json`

## Step 2 — Validate Intent

```bash
python -m sop_automation task validate-intent --intent <intent_path>
```
Output: `PASS` or `FAIL` with validation issues listed.

## Step 3 — Select SOP (automatic)

The runtime host selects the best matching compiled SOP from `SOP/compiled/`.
Manual override: add `sop_id=<sop-id>` to the request text in Step 1.

## Step 4 — Submit Task

```bash
python -m sop_automation task submit --intent <intent_path>
```
Output: `run_id` assigned, command written to `SOP/runtime/commands/`.

## Step 5 — Monitor Status

```bash
python -m sop_automation task status --run <run_id>
```
Possible states: `CREATED`, `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_FOR_AUTH`, `WAITING_FOR_CLARIFICATION`, `CANCELLED`.

## Step 6 — Handle Auth Pause (if WAITING_FOR_AUTH)

1. Complete authentication in the headed browser window.
2. Resume:
```bash
python -m sop_automation task continue --run <run_id>
```

## Step 7 — Complete or Handle Clarification (if WAITING_FOR_CLARIFICATION)

Read `SOP/runs/<run_id>/clarification_request.json` for element details.
Options: update the compiled SOP and resubmit, or cancel the run.

## Terminal States

| State | Meaning |
|-------|---------|
| `COMPLETED` | All steps succeeded |
| `FAILED` | Exceeded retry limit — check `SOP/runs/<run_id>/events.jsonl` |
| `CANCELLED` | Cancelled by `task cancel --run <run_id>` |
