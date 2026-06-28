# Authentication Smoke and README Accuracy Patch — M15

**Status: PARTIAL**
Tests not run on the coding machine. All changes confirmed present by source inspection only.

---

## Files Changed (9)

| # | File | What changed |
|---|------|-------------|
| 1 | `src/sop_automation/services/sop_validate.py` | New validation rule `MANUAL_AUTH_POSTCONDITION_REQUIRED` |
| 2 | `src/sop_automation/runtime/run_manager.py` | Fail-closed auth condition + auth context write |
| 3 | `tests/unit/test_runtime_smoke.py` | Real fixture authentication in smoke test |
| 4 | `tests/unit/test_runtime_host.py` | New `TestRuntimeHostContinuation` class |
| 5 | `README.md` | COPILOT_SOP_AUTHORING_PROTOCOL.md ref, compiled paths, task flow |
| 6 | `src/sop_automation/cli.py` | `cmd_task_status` per-step symbol display |
| 7 | `tests/unit/test_cli.py` | `timeout=20` in `subprocess.run()` |
| 8 | `tests/unit/test_phase1_cli.py` | `timeout=20` in `subprocess.run()` |
| 9 | `progress.md` | M15 milestone added |

---

## New Validation Rule

**Rule ID:** `MANUAL_AUTH_POSTCONDITION_REQUIRED`
**Location:** `src/sop_automation/services/sop_validate.py` — inserted after rule R12 (MANUAL_AUTH_NO_CREDS block)
**Severity:** ERROR

Every `MANUAL_AUTH` step must have a `wait_condition`. Allowed `wait_condition.type` values:

- `URL_CONTAINS`
- `URL_EQUALS`
- `ELEMENT_VISIBLE`
- `ELEMENT_TEXT_CONTAINS`
- `ELEMENT_TEXT_EQUALS`

Two sub-cases raise the rule:
1. `step.wait_condition is None` — no condition provided at all.
2. `step.wait_condition.type.value not in _ALLOWED_AUTH_WAIT_TYPES` — type provided but not in the allowed set.

---

## How the Smoke Test Performs Real Authentication

**File:** `tests/unit/test_runtime_smoke.py`
**Test:** `TestRuntimeSmoke.test_runtime_smoke_manual_auth_same_context_and_single_branch`

The `step_auth` step now carries a real `WaitConditionSpec`:

```python
step_auth = _step(
    "step_auth", "login_cap", 3,
    ActionType.MANUAL_AUTH, "auth_gate", ElementType.PAGE,
    wait_condition=WaitConditionSpec(
        type=WaitConditionType.URL_CONTAINS,
        expected_value="/dashboard",
    ),
)
```

Inside `_smoke_inner`, before calling `manager.signal_auth()`, the test now performs the full login sequence against the local fixture app:

```python
await page.fill("input[name='password']", "testpass")
await page.click("button[type='submit']")
await page.wait_for_url("**/dashboard**", timeout=5000)
manager.signal_auth()
```

The fixture app (`tests/fixtures/local_fixture_app.py`) handles `POST /login` by redirecting to `/dashboard`. Playwright follows the redirect automatically, so `wait_for_url` resolves after the submit click.

After the run completes, the test asserts:

```python
auth_prog = final_state.step_progress.get("step_auth")
assert auth_prog is not None
assert auth_prog.status.value == "COMPLETED"

auth_ctx = manager._context["steps"].get("step_auth")
assert auth_ctx is not None
assert auth_ctx["success"] is True
assert "/dashboard" in auth_ctx["current_url"]
```

---

## RuntimeHost Continuation Test

**File:** `tests/unit/test_runtime_host.py`
**Class:** `TestRuntimeHostContinuation`
**Test:** `test_host_retains_state_during_waiting_for_auth_and_continues`

Uses a `FakeManager` (no real Chromium). The test verifies:

1. While a run is `WAITING_FOR_AUTH`, a second `START_RUN` command is rejected (`AckStatus.REJECTED`).
2. A `CONTINUE_RUN` command calls `signal_auth()` on the active manager exactly once and returns `AckStatus.COMPLETED` with message `"AUTH_VERIFIED"`.
3. `host._active_manager` remains the same `FakeManager` instance throughout both sub-tests.

---

## README Path and Protocol Corrections

**Section I (Terminal workflow description):**
- Copilot's role split: for SOP authoring it writes `interpretation_result.json` into `SOP/compiled/<sop-id>/`; for task execution it helps write `request.txt` only — the CLI creates the TaskIntent directly.

**Section J (SOP authoring flow):**
- Protocol file reference corrected: `COPILOT_SOP_PROTOCOL.md` → `COPILOT_SOP_AUTHORING_PROTOCOL.md` (the actual file that exists in `docs/`).
- Path corrected: Copilot writes `interpretation_result.json` into `SOP/compiled/<sop-id>/` (not `SOP/generated/`).
- `sop prepare` output path corrected: written to `SOP/compiled/<sop-id>/interpretation_request.json`.

**Section K (Task flow):**
- Removed the incorrect Step 3 that said "Copilot writes the TaskIntent JSON".
- Flow is now 4 steps: write request.txt → `task prepare-intent` → `task validate-intent` → `task submit`.
- Added: "task prepare-intent reads the request file and creates the TaskIntent directly. No separate Copilot step is required after this."

---

## `task status` Per-Step Output Correction

**File:** `src/sop_automation/cli.py` — `cmd_task_status`

`task status` now reads `task_plan.json` to enumerate all planned steps (including pending ones not yet in `step_progress`), then prints each with a status symbol:

```
[✓]  completed
[→]  current (RUNNING)
[ ]  pending
[⏸]  waiting (WAITING_FOR_AUTH or WAITING_FOR_CLARIFICATION)
[!]  failed
[-]  skipped
```

Example output:

```
Run ID : abc-123
Status : RUNNING
Started: 2026-06-28T10:00:00Z

Steps:
  [✓] step_open                     (login_cap)
  [→] step_fill_user                (login_cap)
  [ ] step_auth                     (login_cap)
  [ ] step_click_submit             (login_cap)

Completed: 1  |  Failed: 0  |  Skipped: 0  |  Waiting: 0
```

---

## Subprocess Timeout Additions

Both CLI test helpers now pass `timeout=20` to `subprocess.run()` to prevent indefinite hangs:

- `tests/unit/test_cli.py` — `_run()` helper, line 19
- `tests/unit/test_phase1_cli.py` — `run_cli()` helper, line 34

---

## Mac Test Commands

Run after copying `SOPAutomationV2/` to the Mac and installing:

```bash
# Step 1 — non-Playwright tests
.venv/bin/python -m pytest -q -m "not playwright"

# Step 2 — Playwright tests (includes the smoke test)
.venv/bin/python -m pytest -q -m playwright
```

The smoke test that must pass:

```
tests/unit/test_runtime_smoke.py::TestRuntimeSmoke::test_runtime_smoke_manual_auth_same_context_and_single_branch
```

Expected: real fixture login (`/dashboard` URL reached), `step_auth` in COMPLETED, `_context["steps"]["step_auth"]["success"] == True`.

---

## Not Run

No tests were executed on this coding machine. All verification was done by source inspection only.
