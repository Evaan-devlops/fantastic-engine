# Milestone 1 Final Sequential Completion

**Status: PARTIAL — tests written, not run on coding machine. Run on Mac.**

---

## Root Causes (ZIP-12 Defects)

| ID | Defect | Root Cause |
|----|--------|-----------|
| A | Secrets in persisted artifacts | `redact_mapping()` not applied before `task_plan.json`/`run_state.json` writes; list-of-dict items serialized as raw strings; `api_key` keyword missing |
| B | AUTH_BRANCH misclassification + no validation | Classifier checked SSO after body text (so "single sign-on" body text → MANUAL_AUTH); no AUTH_BRANCH-specific rules in SopValidateService |
| C | Fill retention skipped when explicit postcondition present | `if not step.postcondition:` guard before `_confirm_filled_value()` short-circuited retention check |
| D | retryable_error_codes field ignored | `_is_retryable_failure()` checked only a hard-coded default set, never inspected `step.retry_policy.retryable_error_codes` |
| E | Postcondition polling loop too slow | `_evaluate_once()` delegated to `_resolve_locator()` → `locate()` (2 s wait per iteration); should use `_probe_once()` → `candidate_locators()` (non-waiting) |
| F | Auth route tests incomplete | Tests only covered email → Next → classify; no password fill, submit, MANUAL_AUTH pause, signal_auth resume, branch coverage, or resilience |

---

## Files Changed

| # | File | Stage | What changed |
|---|------|-------|-------------|
| 1 | `src/sop_automation/runtime/diagnostics.py` | 1, 5 | `api_key`/`apikey` keywords; `redact_mapping()` list recursion; typed failure codes; `CandidateAttempt` dataclass |
| 2 | `src/sop_automation/runtime/run_manager.py` | 1, 2D, 3, 5 | `redact_mapping()` on all JSON writes; `_is_retryable_failure()` honours `retryable_error_codes`; BRANCH_NOT_RECOGNIZED on unmatched AUTH_BRANCH; `locator_attempts` in clarification_data |
| 3 | `src/sop_automation/runtime/action_dispatcher.py` | 2C, 2.4, 5 | Fill retention always checked; DOWNLOAD+COPY through `_with_postcondition`; `locator_attempts` populated from `LocatorError.attempts` |
| 4 | `src/sop_automation/runtime/postconditions.py` | 2E | `_evaluate_once()` delegates to `_probe_once()` (non-waiting) instead of `_resolve_locator()` |
| 5 | `src/sop_automation/runtime/auth_classifier.py` | 3 | SSO check precedes body text; email-type inputs in USERNAME_PASSWORD selector; deterministic precedence order |
| 6 | `src/sop_automation/services/sop_validate.py` | 3 | 6 AUTH_BRANCH contract rules: REQUIRES_OUTCOMES, UNKNOWN_VALUE, ERROR_MUST_FAIL, REQUIRES_ERROR_HANDLING, REQUIRES_UNKNOWN_PAGE_HANDLING |
| 7 | `src/sop_automation/runtime/locator_service.py` | 5 | `LocatorError.attempts: list[CandidateAttempt]`; `_collect_attempts()` probes each strategy after timeout |
| 8 | `src/sop_automation/models/runtime.py` | 5 | `StepResult.locator_attempts: list[dict]` field |
| 9 | `tests/unit/test_secret_persistence.py` | 1 | NEW — 8 gate tests verifying no secret in any persisted artifact |
| 10 | `tests/unit/test_runtime_reliability.py` | 2, 3, 5 | Stage 2.1 (fill retention), 2.2 (retry codes), 2.3 (timing), 3 (AUTH_BRANCH contract), 5 (structured diagnostics) — 18 new tests |
| 11 | `tests/unit/test_validation.py` | 3 | `TestAuthBranchValidation` — 5 gate tests |
| 12 | `tests/fixtures/local_fixture_app.py` | 4 | 4 new HTML templates + routes: sign-in, manual-waiting, authenticated, login-intercept |
| 13 | `tests/unit/test_auth_route_playwright.py` | 4 | 7 new Playwright auth-route tests; `_full_auth_plan()`; `_run_full_auth_with_manual_signal()` |
| 14 | `progress.md` | — | Milestone entry added |

---

## Stage-by-Stage Summary

### Stage 1 — Secret Persistence
- `run_manager.py`: `redact_mapping()` applied to `task_plan.json` and `run_state.json` before write
- `diagnostics.py`: `redact_mapping()` recurses into `list[dict]` items; adds `api_key`/`apikey`; typed failure codes
- Gate: 8 tests in `test_secret_persistence.py` — no secret appears in any artifact across task_plan, run_state, events, clarification, postcondition failure

### Stage 2 — Runtime Correctness
- **2C Fill retention**: removed `if not step.postcondition:` guard; `_confirm_filled_value()` always called
- **2D Retry codes**: `_is_retryable_failure()` checks `retryable_error_codes` when non-empty; `LOCATOR_AMBIGUOUS`/`BROWSER_CLOSED` never retried
- **2E Postcondition timing**: `_evaluate_once()` now uses `_probe_once()` (candidate_locators, non-waiting)
- **2.4 DOWNLOAD/COPY**: both run through `_with_postcondition`
- Gate: 7 tests — fill retention, retry listed/unlisted code, ambiguous never-retry, default set, timing bound

### Stage 3 — AUTH_BRANCH Contract
- **Classifier**: precedence order enforced — error → authenticated → SSO → username+password → password-only → manual auth → unknown
- **Validation**: 6 new rules in `SopValidateService`; safe default outcome satisfies all coverage requirements
- **Runtime**: BRANCH_NOT_RECOGNIZED failure emitted when no outcome matches
- Gate: 5 validation tests; 6 reliability tests

### Stage 4 — Auth Route Coverage (Playwright)
- `local_fixture_app.py`: sign-in page (submit → /auth/manual-waiting), manual-waiting, authenticated, login-intercept (overlay)
- `test_auth_route_playwright.py`: full 3-capability auth plan; complete email→password→manual_auth flow; no-secret artifact check; 6 fixture routes via classifier; auth error → FAILED; delayed IDP; no-repeat resume

### Stage 5 — Structured Diagnostics
- `CandidateAttempt` dataclass with `strategy`, `match_count`, `visible`, `enabled`, `editable`, `rejection_reason`, `to_dict()`
- `LocatorService._collect_attempts()`: probes each strategy once (non-waiting) after poll deadline
- `LocatorError.attempts: list[CandidateAttempt]` — populated on timeout; empty on ambiguity error
- `StepResult.locator_attempts: list[dict]` — filled from `exc.attempts` in ActionDispatcher LocatorError handler
- `clarification_request.json` includes `locator_attempts` list (runs through `redact_mapping()`)
- Gate: 6 tests — end-to-end clarification artifact check, secret absence, field preservation, LocatorService direct unit tests (zero-match → NO_MATCH, hidden → NOT_VISIBLE)

---

## Test Totals (written, not yet run on Mac)

| File | Tests | Scope |
|------|-------|-------|
| test_secret_persistence.py (new) | 8 | Stage 1 gate |
| test_runtime_reliability.py (Stage 2-5) | +18 | Stages 2.1-2.3, 3, 5 |
| test_validation.py (Stage 3) | +5 | AUTH_BRANCH validation rules |
| test_auth_route_playwright.py (Stage 4) | +7 | Full auth route (playwright-marked) |
| **Stage gate total** | **38** | |

---

## Constraints Honoured

- No test execution on coding machine
- No git commit/push
- No package installation
- All edits confined to `SOPAutomationV2/`
- No `os.getenv()` outside config.py
- Atomic writes for all JSON artifacts
- `redact_mapping()` applied at every persistence boundary
