# Milestone 1 — Deadline Rescue Report

**Spec tag:** `[SOP_AUTOMATION_V2_DEADLINE_RESCUE_FINAL_FIX]`
**Date:** 2026-06-30

---

## 1. Exact Files Changed

| File | Change |
|------|--------|
| `src/sop_automation/runtime/diagnostics.py` | Added `_VALUE_KEYS` constant; added credential-context detection in `redact_mapping()` |
| `src/sop_automation/runtime/run_manager.py` | Moved reconciliation check inside `if attempt > 1:` guard |
| `tests/unit/test_runtime_reliability.py` | Updated 2 tests (F2 locator injection, F4 selector key); fixed existing reconciliation test; added `locator_attempts=[]` to `FakeResult` |
| `tests/unit/test_secret_persistence.py` | Added 2 new tests for postcondition expected_value redaction |

---

## 2. First-Attempt vs Retry/Resume Execution Rule

**Before (buggy):** `_execute_step()` ran the reconciliation check before every attempt, including attempt 1. If the postcondition was already true on attempt 1, the action was skipped entirely.

**After (correct):**
```python
for attempt in range(1, max_attempts + 1):
    if attempt > 1:
        reconciled, _ = await self._postcondition_satisfied(step, page)
        if reconciled:
            return ...   # skip re-dispatch, mark reconciled
    result = await self._dispatcher.execute(...)
```

- **First execution (attempt == 1):** Reconciliation is skipped. Action always dispatches.
- **Retry (attempt > 1):** Postcondition is probed first. If already satisfied (e.g., page transitioned after first attempt), re-dispatch is skipped.
- Global reconciliation is not disabled — it is correctly deferred.

---

## 3. FILL-Retention Proof

`test_fill_retention_required_even_with_explicit_url_postcondition` (F1):

- Page URL is `/auth/password`, matching the URL postcondition
- Before fix: reconciliation on attempt 1 → COMPLETED without dispatching FILL
- After fix: FILL dispatches on attempt 1 → `_IgnoreFillLocator.input_value()` returns `""` → POSTCONDITION_NOT_MET → WAITING_FOR_CLARIFICATION
- Test result: **PASS**

---

## 4. Postcondition Deadline Proof

`test_evaluate_loop_does_not_use_waiting_locate_for_element_postcondition` (F2):

**Root cause:** Test incorrectly injected `SlowLocateService` (2s `locate()`) into the action dispatcher's locator service. The CLICK itself took 2s before even reaching postcondition evaluation.

**Repair:** Fast locator (`FakeLocatorService({"Next": FakeLocator()})`) for action dispatch; `PostconditionEvaluator(slow_locator_service)` only for postconditions. Also set `max_attempts=1` to eliminate the 1.0s default retry delay.

**After repair:**
- CLICK dispatches instantly (fast locator)
- Postcondition evaluates via `candidate_locators()` (non-waiting) → polls 0.2s
- `elapsed < 1.5s` assertion passes (measured ≈ 0.25s)
- `postconditions.py` source unchanged — the evaluator was already correct

---

## 5. Recursive Secret Scan Result

**F3:** `test_postcondition_failure_does_not_expose_secret_expected_value`

**Root cause:** `redact_mapping()` only redacted keys whose names matched `_SECRET_KEYWORDS`. A postcondition dict with `element_name="Password"` and `expected_value="fake-password-for-test-only"` was not redacted because `"expected_value"` is not a secret keyword.

**Fix in `diagnostics.py`:**
```python
_VALUE_KEYS = frozenset({"expected_value", "observed_value", "value", "resolved_value"})

def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    element_name = data.get("element_name", "")
    is_credential_context = isinstance(element_name, str) and is_secret_field(element_name)

    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if is_secret_field(key):
            redacted[key] = "<redacted>"
        elif is_credential_context and key in _VALUE_KEYS:
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        ...
```

When `element_name` names a credential field (password, token, secret, etc.), all value-bearing keys in the same dict are also redacted. This covers `task_plan.json` (written via `redact_mapping(plan.model_dump())`).

**Non-credential case preserved:** A URL postcondition with `element_name="Page"` and `expected_value="/login"` passes the credential context check as `False` → `expected_value="/login"` is preserved in `task_plan.json`.

---

## 6. AUTH_BRANCH Validation and Runtime Defence

Already complete from the previous session (Stage 4 of the prior milestone):

- 6 validation rules in `SopValidateService`: REQUIRES_OUTCOMES, DESTINATION_NOT_FOUND, UNSUPPORTED_CONDITION, REQUIRES_ERROR_HANDLING, REQUIRES_UNKNOWN_PAGE_HANDLING, DUPLICATE_CONDITION
- `BRANCH_NOT_RECOGNIZED` runtime failure when no outcome matches at runtime
- 5 tests in `test_validation.py` all pass
- Runtime tests for AUTH_BRANCH coverage all pass

---

## 7. Classifier Failing Case and Correction

**F4:** `test_auth_classifier_detects_all_branch_values` — USERNAME_PASSWORD case

**Root cause:** The test fixture set the old short selector as the key:
```python
username_password.locators["input[type='text'], input[name*='user' i], input[id*='user' i]"] = FakeLocator()
```

The classifier uses a longer extended selector (added `input[type='email']` and email/login variants):
```python
_USERNAME_SELECTOR = (
    "input[type='text'], input[type='email'], "
    "input[name*='user' i], input[id*='user' i], "
    "input[name*='email' i], input[id*='email' i], "
    "input[name*='login' i], input[id*='login' i]"
)
```

`FakePage.locator()` does exact-string lookup, so the old key returned `count=0` → classifier fell through to `UNKNOWN_PAGE`.

**Fix:** Updated the test fixture to use the exact extended selector string. No `auth_classifier.py` source change needed.

---

## 8. Focused Test Totals

| Suite | Tests | Result |
|-------|-------|--------|
| `test_runtime_reliability.py` | 50 | 50 passed |
| `test_secret_persistence.py` | 13 | 13 passed |
| `test_validation.py` | 8 | 8 passed |
| **Focused total** | **71** | **71 passed** |

---

## 9. Full Non-Playwright Totals

```
414 passed, 1 skipped, 22 deselected (playwright-marked)
0 failed
```

Previous baseline: 408 passed, 4 failed.
Net change: +6 tests (2 new secret persistence tests; reconciliation test updated; 3 other tests fixed to pass).

---

## 10. compileall Result

```
python -m compileall -q src tests
```
Exit code: 0 — no errors.

---

## 11. diff-check Result

```
git diff --check
```
Exit code: 0 — no trailing whitespace issues.

---

## 12. Playwright Status

**NOT EXECUTED** — Playwright is not installed in this environment. Playwright-marked tests were deselected (`-m "not playwright"`). Route-level Playwright tests are preserved for execution on Mac.

---

## 13. Files to Transfer to Mac

```
SOPAutomationV2/src/sop_automation/runtime/diagnostics.py
SOPAutomationV2/src/sop_automation/runtime/run_manager.py
SOPAutomationV2/tests/unit/test_runtime_reliability.py
SOPAutomationV2/tests/unit/test_secret_persistence.py
SOPAutomationV2/response/milestone1_deadline_rescue.md
```

All other previously-transferred files (auth_classifier.py, postconditions.py, action_dispatcher.py, locator_service.py, sop_validate.py, models/runtime.py, test_validation.py, test_auth_route_playwright.py, fixtures/) remain unchanged.

---

## 14. Mac Test Files to Run Before Live Site Attempt

Run in this order:

```bash
# 1. Non-Playwright gate (reproduces Windows results)
PYTHONPATH=src python -m pytest -q -m "not playwright"

# 2. Focused stage gates
PYTHONPATH=src python -m pytest -q \
  tests/unit/test_runtime_reliability.py \
  tests/unit/test_secret_persistence.py \
  tests/unit/test_validation.py

# 3. Playwright auth route tests (Mac only)
PYTHONPATH=src python -m pytest -q -m "playwright" \
  tests/unit/test_auth_route_playwright.py

# 4. compileall
python -m compileall -q src tests
```

Required before live site: all non-Playwright + all Playwright auth route tests green.

---

DEADLINE RESCUE PASSED — READY FOR MAC PLAYWRIGHT GATE
