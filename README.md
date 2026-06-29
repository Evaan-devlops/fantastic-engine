# SOPAutomationV2 — Mac POC User Guide

> **Accuracy labels used in this document**
> - **Available now** — implemented and tested by automated tests
> - **Tested by automated tests only** — not yet manually verified on Mac
> - **Not yet available** — planned for a future phase

---

## A. What This Application Does

SOPAutomationV2 automates browser-based business applications using validated Standard Operating Procedures (SOPs) written in natural language.

- **GitHub Copilot Chat** reads natural-language SOPs and natural-language task requests, then writes strict structured JSON files that the Python runtime can execute. Copilot handles all language understanding.
- **The Python runtime** owns browser execution: it drives Playwright, manages execution state, handles retries, follows branching logic, pauses for manual authentication, and reports live status.
- **OneTrust** is used only as an example test case during development. The runtime is generic — it is not hardcoded for any single website.
- The runtime receives its instructions entirely from compiled SOP files and does not contain site-specific knowledge.

---

## B. Current POC Capabilities

### Available now (implemented, tested by automated tests)

- SOP source preparation: TXT, Markdown, CSV, XLSX
- File-based Copilot interpretation protocol (request/result JSON files)
- Deterministic SOP validation (30 rules)
- SOP compilation to typed TaskPlan
- Foreground runtime host (one process, one browser, one run at a time)
- Headed Chromium via Playwright (persistent browser context with user profile)
- Supported browser actions: `OPEN`, `CLICK`, `FILL`, `PRESS`, `SELECT`, `CHECK`, `UNCHECK`, `VERIFY`, `BRANCH`, `MANUAL_AUTH`, `DEFERRED`, `END_SUCCESS`, `END_FAILURE`
- Manual authentication pause: runtime pauses, user authenticates in browser, user signals `continue`
- One active run enforced: a second run is rejected while a first is active or paused
- Live status display via `task status`
- One retry attempt before recording clarification evidence
- Value template resolution: `{{input.x}}`, `{{output.x}}`, `{{steps.id.field}}`
- Local fixture HTTP server for integration testing (stdlib only, no external dependency)

### Not yet available

- Clarification resolution: `WAITING_FOR_CLARIFICATION` is recorded but the user cannot currently resolve it via CLI
- Remembered resolutions
- Route learning
- Generated capability tools
- SOP catalogue reuse
- iframe support
- Complex table support
- Multiple concurrent runs

---

## C. What Must Be Copied to the Mac

Copy the **complete `SOPAutomationV2/` folder** to the Mac. That folder is self-contained.

**Do NOT copy** any of the following from the parent coding workspace:

- Parent `.claude/`
- `faststack-mcp/`
- Parent `SPL/`
- Root `CLAUDE.md`
- Root `agents.md`
- Root `.mcp.json`
- Any other coding-harness files

The application does not require anything from the parent workspace.

---

## D. Mac Prerequisites

| Requirement | Notes |
|-------------|-------|
| macOS | Any recent version |
| Python 3.11 or newer | Check: `python3 --version` |
| Internet access | Required during initial pip install and Chromium download only |
| VS Code | For GitHub Copilot Chat |
| GitHub Copilot Chat extension | For natural-language SOP and task interpretation |
| Terminal | Standard macOS Terminal or iTerm2 |

---

## E. Exact Mac Installation Commands

Run these commands once after copying the folder:

```bash
cd SOPAutomationV2

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m playwright install chromium
```

There is one dependency set. Do not use `pip install -e ".[dev]"`, `.[stage]`, or `.[production]` — those profiles do not exist.

---

## F. Mandatory Test Order

Run these two test commands **before starting the runtime**. Both must pass.

**Step 1 — non-Playwright tests (unit and integration):**

```bash
.venv/bin/python -m pytest -q -m "not playwright"
```

**Step 2 — Playwright tests (includes the local runtime smoke test):**

```bash
.venv/bin/python -m pytest -q -m playwright
```

Rules:
- Do not start the runtime if either command fails.
- Save the full failure output before attempting any fix.
- Fix all failures before continuing.
- Review any skipped tests and confirm they are expected skips.
- The Playwright test command runs `test_runtime_smoke_manual_auth_same_context_and_single_branch` — this must pass.

---

## G. Workspace Initialization

Only after **both test groups pass**:

```bash
.venv/bin/python -m sop_automation workspace init
```

This creates the following directories under `SOPAutomationV2/SOP/`:

```
inbox/                    — place raw SOP source files here
sources/                  — preserved source copies
compiled/                 — compiled SOP output
manifests/                — SOP manifests
runs/                     — active and historical run state
resolutions/              — clarification resolutions (future)
routes/                   — route learning (future)
tool_build_requests/      — tool build requests (future)
tools/                    — generated tools (future)
generated/                — interpretation requests and results
runtime/                  — runtime command queue and acknowledgements
runtime/commands/         — pending runtime commands
runtime/acknowledgements/ — runtime command acknowledgements
runtime/processed/        — successfully consumed commands
runtime/failed/           — commands that failed validation
```

Repeated initialization is safe and idempotent. Running `workspace init` a second time reports `[EXISTS]` for all directories.

---

## H. Starting the Runtime

```bash
.venv/bin/python -m sop_automation runtime start
```

Important:

- Run this in **Terminal 1** and keep that terminal open.
- Do not append `&` — the runtime must run in the foreground.
- Do not close Terminal 1 while a task is running or paused.
- The runtime owns the live Playwright browser window.
- Stop the runtime with **Ctrl+C** only after the run has reached a terminal state or you have intentionally cancelled it.

---

## I. Using Copilot Chat and a Second Terminal

Use two workspaces:

- **Terminal 1**: the long-running `runtime start` command
- **GitHub Copilot Chat** (in VS Code): natural-language SOP and task interpretation
- **Terminal 2** (when needed): short CLI commands (`task submit`, `task status`, `task continue`, etc.)

**What Copilot Chat does in each workflow:**

- **SOP authoring**: reads `docs/COPILOT_SOP_AUTHORING_PROTOCOL.md`, then writes `interpretation_result.json` into `SOP/compiled/<sop-id>/` after `sop prepare` has created the request.
- **Task execution**: helps write the key-value `request.txt` file if the user needs assistance; the Python CLI (`task prepare-intent`) creates the `TaskIntent` directly from that file.
- Copilot never directly manipulates the browser, edits run state, or writes to `SOP/runs/`.

---

## J. Natural-Language SOP Authoring Flow

```
Natural-language SOP source file
  → sop prepare           (Python CLI)
  → interpretation_request.json
  → Copilot reads request, writes interpretation_result.json
  → sop validate-result   (Python CLI)
  → sop compile           (Python CLI)
  → compiled SOP + manifest + Markdown
```

**Step 1 — Place your SOP source in the inbox:**

```
SOP/inbox/MySOP.txt
```

**Step 2 — Prepare the interpretation request:**

```bash
.venv/bin/python -m sop_automation sop prepare \
  --source SOP/inbox/MySOP.txt \
  --sop-id MySOP
```

The CLI prints the path to the generated `interpretation_request.json`, which is written to `SOP/compiled/<sop-id>/interpretation_request.json`.

**Step 3 — Copilot writes the interpretation result:**

In Copilot Chat, ask it to read `docs/COPILOT_SOP_AUTHORING_PROTOCOL.md` and follow the protocol to write `interpretation_result.json` into the same `SOP/compiled/<sop-id>/` directory.

**Step 4 — Validate the result:**

```bash
.venv/bin/python -m sop_automation sop validate-result \
  --result SOP/compiled/<sop-id>/interpretation_result.json
```

Fix any reported issues before compiling.

**Step 5 — Compile:**

```bash
.venv/bin/python -m sop_automation sop compile \
  --result SOP/compiled/<sop-id>/interpretation_result.json
```

The compiled SOP output is written alongside the interpretation files in `SOP/compiled/<sop-id>/`.

---

## K. Natural-Language Task Flow

```
Key-value task request file (Copilot or user writes this)
  → task prepare-intent   (Python CLI creates the TaskIntent directly)
  → task validate-intent  (Python CLI)
  → task submit           (Python CLI)
  → runtime acknowledgement prints run ID
```

**Step 1 — Write your task request to a file:**

Copilot (or you manually) writes a key-value file describing the goal and inputs:

```
# request.txt
goal=create_contact
email_address=jane@example.com
```

**Step 2 — Prepare the task intent:**

```bash
.venv/bin/python -m sop_automation task prepare-intent \
  --request-file request.txt
```

`task prepare-intent` reads the request file and creates the `TaskIntent` directly. The CLI prints the path to the generated task intent file in `SOP/generated/`. No separate Copilot step is required after this.

**Step 3 — Validate the intent:**

```bash
.venv/bin/python -m sop_automation task validate-intent \
  --intent-file SOP/generated/<id>_task_intent.json
```

**Step 4 — Submit:**

```bash
.venv/bin/python -m sop_automation task submit \
  --intent-file SOP/generated/<id>_task_intent.json
```

- `task submit` prints the acknowledged run ID when the runtime accepts the run.
- **Save the run ID** — you will need it for `task status`, `task continue`, and `task cancel`.
- If the runtime is not running, `task submit` reports "Host not responding — command queued".

---

## L. Checking Task Status

```bash
.venv/bin/python -m sop_automation task status \
  --run-id <run-id>
```

Step progress symbols:

```
[✓]  completed
[→]  current
[ ]  pending
[⏸]  waiting (authentication or clarification required)
[!]  failed
[-]  skipped
```

---

## M. Manual Authentication

When the SOP includes a `MANUAL_AUTH` step, the runtime pauses and waits for you to complete login in the browser window.

**User flow:**

1. The runtime opens the browser and navigates to the application.
2. The runtime reaches the `MANUAL_AUTH` step and status becomes `WAITING_FOR_AUTH`.
3. You see a message in Terminal 1: `Authentication required. Complete login in browser.`
4. Switch to the browser window and manually enter your username and password.
5. Complete any required two-factor authentication or CAPTCHA.
6. Return to Terminal 2 and run:

```bash
.venv/bin/python -m sop_automation task continue \
  --run-id <run-id>
```

7. The runtime evaluates the post-authentication browser condition.
8. The runtime returns one of:
   - `AUTH_VERIFIED` — authentication succeeded; execution continues.
   - `AUTH_STILL_REQUIRED` — the condition was not met; complete authentication and run `task continue` again.

**Important:**
- The same browser context remains open throughout the pause. You do not need to reopen any page.
- Steps completed before the authentication pause are not repeated after `continue`.
- The runtime does not record, log, or transmit credentials, passwords, OTP values, cookies, or tokens.

---

## N. Cancelling a Task

```bash
.venv/bin/python -m sop_automation task cancel \
  --run-id <run-id>
```

Cancellation:
- Stops the active execution task.
- Closes the browser context safely.
- Preserves all run evidence under `SOP/runs/<run-id>/`.
- Frees the single active-run slot so a new run can start.

---

## O. Current Blocking States

| State | How to proceed |
|-------|---------------|
| `WAITING_FOR_AUTH` | Complete login in browser, then `task continue --run-id <id>` |
| `WAITING_FOR_CLARIFICATION` | Records clarification evidence in `SOP/runs/<run-id>/clarification_request.json`. **User resolution via CLI is not yet implemented.** Cancel and investigate the clarification file. |
| `WAITING_FOR_DEFERRED_CAPABILITY` | The referenced SOP capability has no executable implementation yet. Cancel the run. |

---

## P. Runtime Artifacts

All run artifacts are stored under:

```
SOP/runs/<run-id>/
  run_state.json             — current run status, step progress, branch decisions
  task_plan.json             — the compiled execution plan used for this run
  events.jsonl               — structured event log (one JSON object per line)
  clarification_request.json — present when WAITING_FOR_CLARIFICATION
  browser_profile/           — persistent Chromium user profile for this run
  screenshots/               — failure screenshots (credential steps excluded)
```

---

## Q. Troubleshooting

**`python3` not found**
Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/).

**Virtual environment creation fails**
Ensure the Python version is 3.11+: `python3 --version`. Try `python3.11 -m venv .venv` if multiple versions are installed.

**Editable install fails**
Run `pip install --upgrade pip` first, then retry `pip install -e .`.

**Chromium installation fails**
Check your internet connection. Retry: `.venv/bin/python -m playwright install chromium`.

**Runtime not running / command acknowledgement timeout**
Start the runtime: `.venv/bin/python -m sop_automation runtime start` in Terminal 1. Keep that terminal open.

**Browser not opening**
Verify Playwright installation: `.venv/bin/python -m playwright install chromium`. Check Terminal 1 for error messages.

**`AUTH_STILL_REQUIRED`**
The post-authentication condition was not satisfied. Complete the login fully in the browser (including any MFA steps), then run `task continue --run-id <id>` again.

**Test failures**
Do not start the runtime. Save the full test output. Fix all failures before continuing. Common causes: missing `playwright install chromium`, Python version mismatch.

**Stale runtime command files**
If the runtime crashed with commands in `SOP/runtime/commands/`, move them manually to `SOP/runtime/failed/` to clear the queue. Do not delete them unless you understand the evidence may be lost.

**Active-run conflict (`REJECTED — A run is already active`)**
Check `task status` to confirm the active run ID. Either wait for it to complete, or `task cancel --run-id <id>`.

**Clean runtime shutdown**
Press Ctrl+C in Terminal 1. Wait for the `[HOST] Stopped.` message before closing the terminal.

---

## R. First Mac Test Checklist

Work through this list in order. Do not skip any step.

```
[ ] Virtual environment created        (python3 -m venv .venv)
[ ] Project installed                  (pip install -e .)
[ ] Chromium installed                 (playwright install chromium)
[ ] Non-Playwright tests passed        (pytest -m "not playwright")
[ ] Playwright tests passed            (pytest -m playwright)
[ ] Workspace initialized              (workspace init)
[ ] Runtime host started in Terminal 1 (runtime start)
[ ] Local fixture browser opened       (smoke test confirms this)
[ ] Input placeholder resolved         ({{input.username}} replaced with test value)
[ ] Manual-auth state reached          (WAITING_FOR_AUTH logged in Terminal 1)
[ ] Same browser remained open         (context not closed during pause)
[ ] Continue verified authentication   (AUTH_VERIFIED returned)
[ ] Exactly one branch executed        (go_success branch only)
[ ] Run reached terminal success       (RunStatus.COMPLETED)
[ ] Runtime stopped cleanly            (Ctrl+C → [HOST] Stopped.)
```

---

## S. Accuracy Statement

This README describes the POC as implemented and tested by automated tests as of the Pre-Mac Round 1 Gate. The following has **not yet been manually verified on Mac**:

- Full end-to-end run against a real external web application (OneTrust or otherwise)
- Manual authentication pause and continue with a live MFA flow
- Download and report generation

Do not use statements such as "fully working", "production ready", or "verified on Mac" until Mac evidence exists.

All commands in this README exactly match the implemented CLI argument parser in `src/sop_automation/cli.py`.
**************************************

.venv/bin/python -m pytest -q tests/unit/test_textbox_locator_resolution.py

.venv/bin/python -m pytest -q tests/unit/test_runtime_textbox_playwright.py

.venv/bin/python -m pytest -q -m "not playwright"

.venv/bin/python -m pytest -q -m playwright