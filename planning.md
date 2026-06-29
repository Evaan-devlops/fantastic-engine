# Planning — SOPAutomationV2 Deadline Rescue Final Fix

**Spec tag:** `[SOP_AUTOMATION_V2_DEADLINE_RESCUE_FINAL_FIX]`
**Scope:** `SOPAutomationV2/` only. No Milestone 2, no installs, no commits/pushes.
**Starting baseline:** 408 non-Playwright tests pass, 4 fail.

---

## Verified Failing Tests (4)

| # | Test | Root Cause |
|---|------|-----------|
| F1 | `test_fill_retention_required_even_with_explicit_url_postcondition` | Reconciliation runs on attempt 1; URL postcondition already true → FILL skipped, returns COMPLETED instead of WAITING_FOR_CLARIFICATION |
| F2 | `test_evaluate_loop_does_not_use_waiting_locate_for_element_postcondition` | Slow locator injected into action dispatch as well as postcondition — action itself takes 2 s, exceeds 1.5 s assertion |
| F3 | `test_postcondition_failure_does_not_expose_secret_expected_value` | `expected_value` key in postcondition spec not in `_SECRET_KEYWORDS`; `redact_mapping()` leaves it intact in `task_plan.json` |
| F4 | `test_auth_classifier_detects_all_branch_values` | USERNAME_PASSWORD case sets the old short selector key; classifier uses a longer key after Stage 3 edit; `FakePage.locator()` exact-key lookup returns count=0 |

---

## Stage 1 — First-Execution Versus Reconciliation

**Files:** `src/sop_automation/runtime/run_manager.py`, `tests/unit/test_runtime_reliability.py`

### Change

In `RunManager._execute_step()`, move the reconciliation check from "before every attempt" to "before attempt 2+":

```python
# BEFORE (buggy — runs on attempt 1 too)
for attempt in range(1, max_attempts + 1):
    reconciled, _ = await self._postcondition_satisfied(step, page)
    if reconciled:
        return ...

# AFTER (correct)
for attempt in range(1, max_attempts + 1):
    if attempt > 1:
        reconciled, _ = await self._postcondition_satisfied(step, page)
        if reconciled:
            return ...
```

This fixes F1.

### Tests to add/correct

Update `test_reconciliation_completes_satisfied_postcondition_without_reclick`:
- Currently: asserts `execute.await_count == 0` (dispatch never called, postcondition pre-satisfied)
- After fix: first dispatch ALWAYS happens; update to `await_count == 1`

Add 3 new tests:
1. FILL dispatches even when URL postcondition is pre-satisfied ← already exists as F1 (will now pass)
2. CLICK dispatches even when an unrelated postcondition is already true
3. Reconciliation fires before the second attempt — after a first-attempt failure the page transitions; second attempt is skipped via reconcile (dispatch_count == 1)

---

## Stage 2 — Postcondition Deadline (Already Fixed — Test Needs Repair)

**Files:** `tests/unit/test_runtime_reliability.py`

### Problem

`test_evaluate_loop_does_not_use_waiting_locate_for_element_postcondition` (F2) injects the slow locator service into BOTH the action dispatcher and the postcondition evaluator. The 2 s locator wait dominates the action dispatch, not the postcondition loop. The postcondition evaluator is already correct (uses `_probe_once()` → `candidate_locators()`, non-waiting).

### Change

Repair the test so that:
- `manager._dispatcher._locator_svc` = fast `FakeLocatorService({"Next": FakeLocator()})` (action dispatch is quick)
- `manager._dispatcher._postconditions` and `manager._postconditions` = `PostconditionEvaluator(slow_locator_service)` (only postcondition evaluation uses slow locator)

After repair:
- Action dispatch completes instantly
- Postcondition polling runs for 0.2 s with non-waiting candidates (fast)
- Total elapsed < 1.5 s

`postconditions.py` implementation is correct — no source change needed.

---

## Stage 3 — Remove Remaining Secret Persistence

**Files:** `src/sop_automation/runtime/diagnostics.py`, `tests/unit/test_secret_persistence.py`

### Problem

`redact_mapping()` redacts top-level secret-keyed fields (e.g., `inputs.password`) but does not redact `expected_value` inside postcondition specs — even when the postcondition targets a credential element such as `element_name="Password"`.

A `TaskPlan` containing:
```json
{"postcondition": {"element_name": "Password", "expected_value": "fake-password-for-test-only"}}
```
survives `redact_mapping()` intact, leaking the secret into `task_plan.json`.

### Change — `redact_mapping()` context-aware extension

Add credential-context detection inside `redact_mapping()`:

```python
def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    # If this dict describes a credential-targeting spec, redact value-carrying keys too
    element_name = data.get("element_name", "")
    is_credential_context = isinstance(element_name, str) and is_secret_field(element_name)

    VALUE_KEYS = frozenset({"expected_value", "observed_value", "value", "resolved_value"})

    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if is_secret_field(key):
            redacted[key] = "<redacted>"
        elif is_credential_context and key in VALUE_KEYS:
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        ...
    return redacted
```

This fixes F3 and satisfies the "generic value-bearing keys must not bypass protection when inside a credential context" requirement.

`postconditions._value_result()` already emits `{comparison_performed, value_match}` for secret contexts — no change needed there.

### Tests to add

Add 2 tests to `test_secret_persistence.py`:
1. `test_expected_value_in_postcondition_spec_is_redacted` — task_plan.json must not contain raw secret even when it is the `expected_value` of a postcondition
2. `test_non_credential_expected_value_is_preserved` — `expected_value` in a non-credential postcondition (e.g., URL) is NOT redacted

---

## Stage 4 — AUTH_BRANCH Safe by Construction (Already Complete)

From the previous session: 6 validation rules added to `SopValidateService`, `BRANCH_NOT_RECOGNIZED` runtime defense in `RunManager`. No further changes needed.

Verify that `TestAuthBranchValidation` (5 tests) and Stage 3 runtime tests still pass.

---

## Stage 5 — Repair Auth Classifier Coverage

**Files:** `tests/unit/test_runtime_reliability.py`, `src/sop_automation/runtime/auth_classifier.py`

### Problem

F4: `test_auth_classifier_detects_all_branch_values` — the USERNAME_PASSWORD case sets:
```python
username_password.locators["input[type='text'], input[name*='user' i], input[id*='user' i]"] = FakeLocator()
```
But the classifier now uses:
```python
_USERNAME_SELECTOR = (
    "input[type='text'], input[type='email'], "
    "input[name*='user' i], input[id*='user' i], "
    "input[name*='email' i], input[id*='email' i], "
    "input[name*='login' i], input[id*='login' i]"
)
```
`FakePage.locator()` does exact-string lookup, so the old key returns `count=0`. Classifier falls through to `UNKNOWN_PAGE`.

### Change

Update the USERNAME_PASSWORD fixture in `test_auth_classifier_detects_all_branch_values` to use the exact selector string the classifier uses:

```python
username_password = FakePage()
username_password.locators[
    "input[type='text'], input[type='email'], "
    "input[name*='user' i], input[id*='user' i], "
    "input[name*='email' i], input[id*='email' i], "
    "input[name*='login' i], input[id*='login' i]"
] = FakeLocator()
username_password.locators["input[type='password']"] = FakeLocator()
```

No `auth_classifier.py` source change needed — the classifier logic is already correct.

---

## Stage 6 — Non-Playwright Release Gate

After Stages 1–5, run:

```powershell
$env:PYTHONPATH='src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'

python -m pytest -q tests/unit/test_runtime_reliability.py tests/unit/test_secret_persistence.py tests/unit/test_validation.py
python -m pytest -q -m "not playwright"
python -m compileall -q src tests
git diff --check
```

Required: zero failures, compileall clean, diff-check clean.

---

## Report

Write `response/milestone1_deadline_rescue.md` containing:
1. Exact files changed
2. First-attempt vs retry/resume execution rule
3. FILL-retention proof
4. Postcondition deadline proof (measured elapsed times)
5. Recursive secret scan result
6. AUTH_BRANCH validation and runtime defence
7. Classifier failing case and correction
8. Focused test totals
9. Full non-Playwright totals
10. compileall result
11. diff-check result
12. Playwright status: `NOT EXECUTED` (no Playwright in this environment)
13. Files to transfer to Mac
14. Mac test files to run before live site attempt

---

## Constraints

- All edits inside `SOPAutomationV2/`
- No package installs, no commits, no pushes
- No runtime redesign — only targeted fixes
- Preserve the 408 currently-passing tests
- `response/milestone1_deadline_rescue.md` is the authoritative completion marker
