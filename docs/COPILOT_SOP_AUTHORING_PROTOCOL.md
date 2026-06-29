# Copilot SOP Authoring Protocol

This document describes the 7-step pipeline for converting a natural-language, CSV, or XLSX SOP into a compiled, executable `CompiledSop` artifact.

---

## Responsibilities

| Actor | Responsibilities |
|-------|----------------|
| **Python CLI** | Preprocessing, validation, compilation, task planning, browser execution |
| **Copilot** | Interpreting source text into typed proposals (InterpretationResult) |

**Critical rules:**
- Copilot **never executes** any action against a live system.
- Python **never trusts** raw natural language — all Copilot output is validated.
- No Copilot API is called by Python. Copilot reads and writes files manually.
- **Never** place passwords, OTPs, tokens, cookies, MFA codes, or any secrets in any artifact.

---

## Step 1 — Python: `sop prepare`

**Command:**
```bash
sop sop prepare --source <path-to-sop-file> --sop-id <unique-id>
```

**What it does:**
- Reads the SOP source file (`.txt`, `.md`, `.csv`, `.xlsx`).
- Runs deterministic structural preprocessing (no NL inference).
- Writes `SOP/compiled/<sop_id>/interpretation_request.json`.

**Output:** Path to `interpretation_request.json`.

**Next:** Share the request file path with Copilot.

---

## Step 2 — Copilot: Read the Request

Copilot opens `interpretation_request.json`. This file is fully self-contained:
- `normalized_text` — the preprocessed SOP source text.
- `sections` — structurally detected sections (headings, numbered lists, etc.).
- `detected_urls`, `detected_placeholders`, `capability_hints` — deterministic hints.
- `possible_condition_lines`, `possible_deferred_lines` — candidate lines for branching/deferral.

No hidden context or memory is needed. The request carries everything required.

---

## Step 3 — Copilot: Write the Result

Copilot writes `interpretation_result.json` in the **same directory** as the request.

The result must conform exactly to the `InterpretationResult` JSON schema. Unknown fields will be rejected by `extra="forbid"`. See `COPILOT_SOP_AUTHORING_PROMPT.md` for the full schema.

**Key constraints:**
- `schema_version` must be `"1.0"`.
- All IDs (`result_id`, `capability_id`, `step_id`, `goal_id`, etc.) must be unique within the document.
- Use `{{input.name}}` format exactly for input placeholders.
- `MANUAL_AUTH` steps must not contain passwords, OTPs, tokens, cookies, MFA codes, or secrets.
- `wait_condition` is pre-action readiness only; `postcondition` proves action completion.
- Submission/navigation `CLICK` steps and `MANUAL_AUTH` steps require an explicit `postcondition`.
- Use `AUTH_BRANCH` for generic authentication-state classification; keep `BRANCH` for business branching.
- Deferred capabilities: set `is_deferred: true` and leave `steps: []`.
- Confidence values: floats in range `0.0–1.0`.
- `evidence_lines`: 1-based line numbers from the source.

---

## Step 4 — Python: `sop validate-result`

**Command:**
```bash
sop sop validate-result --result <path-to-interpretation_result.json>
```

**What it does:** Runs validation rules including:
1. `SCHEMA_VERSION` — must be `"1.0"`
2. `UNIQUE_CAPABILITY_IDS` — no duplicate capability IDs
3. `UNIQUE_STEP_IDS` — globally unique step IDs
4. `CAPABILITY_HAS_STEPS` — non-deferred capabilities must have steps
5. `VALID_ACTIONS` — each action must be a known `ActionType`
6. `VALID_ELEMENT_TYPES` — each element_type must be a known `ElementType`
7. `REQUIRED_FIELDS` — FILL needs value; CLICK/PRESS need element_name
8. `VALID_PLACEHOLDERS` — all `{{input.x}}` must be declared in `result.inputs`
9. `SEQUENCE_VALID` — positive, unique within capability
10. `DEPENDENCIES_RESOLVE` — deps must exist in the same capability
11. `MANUAL_AUTH_NO_CREDS` — no credential keywords in MANUAL_AUTH value
12. `BRANCH_DESTINATIONS_RESOLVE` — branch targets must exist
13. `NO_DEPENDENCY_CYCLES` — Kahn's algorithm per capability
14. `DEFERRED_NON_EXECUTABLE` — warning if deferred cap has steps
15. `GOAL_SAFE_TERMINAL` — each goal must have a terminal path
16. `SOURCE_HASH_PRESERVED` — sha256 must match the request

Additional Milestone 1 runtime-contract validation includes
`MANUAL_AUTH_POSTCONDITION_REQUIRED` for manual authentication completion and
`ACTION_POSTCONDITION_REQUIRED` for submission/navigation clicks.

**Output:** `PASS` or `FAIL` with all issues listed. Writes `validation_report.json`.

---

## Step 5 — Copilot: Fix Errors

Copilot reads `validation_report.json` and updates `interpretation_result.json` to address all `ERROR`-severity issues. Repeat steps 4–5 until the report shows `PASS`.

---

## Step 6 — Python: `sop compile`

**Command:**
```bash
sop sop compile --result <path-to-interpretation_result.json>
```

**Requires:** `validation_report.json` must exist and `passed: true`.

**What it does:**
- Builds `CompiledSop` from the validated `InterpretationResult`.
- Writes:
  - `SOP/compiled/<sop_id>/compiled_sop.json` — machine-readable compiled SOP
  - `SOP/manifests/<sop_id>.manifest.json` — lightweight index for discovery
  - `SOP/generated/<sop_id>.md` — human-readable Markdown documentation

**Output:** Paths to all three artifacts.

---

## Step 7 — Python: `task plan`

**Command:**
```bash
sop task plan --sop <sop_id> --goal <goal_id> [--input name=value ...]
```

**What it does:**
- Loads `compiled_sop.json`.
- Validates all required inputs are provided.
- Produces a dry-run execution plan (ordered steps, branch points, deferred capabilities).
- Writes the plan to `SOP/runs/dry_run_<sop_id>_<goal_id>_<timestamp>.json`.

**Output:** Readable plan printed to stdout + saved JSON path.

---

## Filesystem Contract

| File | Written by | Contains |
|------|-----------|---------|
| `SOP/compiled/<id>/interpretation_request.json` | Python (`sop prepare`) | Preprocessed source + structural hints |
| `SOP/compiled/<id>/interpretation_result.json` | Copilot (manual) | Typed capability/goal/step proposals |
| `SOP/compiled/<id>/validation_report.json` | Python (`sop validate-result`) | Pass/fail + all issues |
| `SOP/compiled/<id>/compiled_sop.json` | Python (`sop compile`) | Machine-readable compiled SOP |
| `SOP/manifests/<id>.manifest.json` | Python (`sop compile`) | Lightweight SOP index |
| `SOP/generated/<id>.md` | Python (`sop compile`) | Human-readable Markdown |
| `SOP/runs/dry_run_*.json` | Python (`task plan`) | Dry-run execution plan |
