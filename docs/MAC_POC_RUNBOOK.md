# Mac POC Runbook

Install and run the SOPAutomationV2 POC on macOS.

## Prerequisites

- macOS 12+ (Monterey or later)
- Python 3.11+

## Install

```bash
cd SOPAutomationV2
pip install -e .
playwright install chromium
```

## Initialize Workspace

```bash
python -m sop_automation workspace init
```

Creates `SOP/` with all required subdirectories.

## Compile a SOP

Prepare a source file (`sop.txt`, `sop.csv`, or `sop.xlsx`), then:

```bash
# Prepare (Phase 0 — stores source, creates request)
python -m sop_automation sop prepare --source sop.txt --sop-id my-sop

# Interpret (Phase 1 — LLM step, produces interpretation_result.json)
# ... (via Copilot Chat in VS Code)

# Validate
python -m sop_automation sop validate-result --result SOP/compiled/my-sop/interpretation_result.json

# Compile
python -m sop_automation sop compile --result SOP/compiled/my-sop/interpretation_result.json
```

## Start Runtime Host

In a dedicated terminal (keeps the browser open):

```bash
python -m sop_automation runtime start
```

Press `Ctrl+C` to stop and close the browser.

## Run a Task

In a second terminal:

```bash
# Prepare intent
python -m sop_automation task prepare-intent \
  --request "goal=create_contact
email_address=user@example.com"

# Validate
python -m sop_automation task validate-intent \
  --intent SOP/generated/<intent_id>_task_intent.json

# Submit
python -m sop_automation task submit \
  --intent SOP/generated/<intent_id>_task_intent.json

# Monitor
python -m sop_automation task status --run <run_id>
```

## Handle Authentication Pause

When status shows `WAITING_FOR_AUTH`:
1. Complete login in the Chromium window
2. `python -m sop_automation task continue --run <run_id>`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Browser does not launch | Run `playwright install chromium` |
| Task stays in CREATED | Confirm `runtime start` is running |
| WAITING_FOR_CLARIFICATION | Read `SOP/runs/<run_id>/clarification_request.json` |
| Import error for playwright | Install with `pip install playwright` |
