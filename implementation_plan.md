# Implementation Plan — SOPAutomationV2

---

## Phase 1 Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | Extend models/sop.py + add models/validation.py + update models/__init__.py | DONE |
| M2 | Create preprocessing package (text, csv, xlsx) | DONE |
| M3 | Create services: sop_prepare, sop_validate, sop_compile, sop_list, task_plan | DONE |
| M4 | Storage update (paths.py + json_store.py), __main__.py, cli.py Phase 1 wiring, pyproject.toml | DONE |
| M5 | Docs: COPILOT_SOP_AUTHORING_PROTOCOL.md + COPILOT_SOP_AUTHORING_PROMPT.md | DONE |
| M6 | Phase 1 unit tests | PENDING |

### Phase 1 Files Created

| File | Purpose |
|------|---------|
| `src/sop_automation/models/validation.py` | ValidationSeverity, ValidationIssue, ValidationReport |
| `src/sop_automation/models/__main__.py` | `python -m sop_automation` entry point |
| `src/sop_automation/preprocessing/__init__.py` | Package init |
| `src/sop_automation/preprocessing/text_preprocessor.py` | TXT/MD structural preprocessing |
| `src/sop_automation/preprocessing/csv_preprocessor.py` | CSV normalization |
| `src/sop_automation/preprocessing/xlsx_preprocessor.py` | XLSX normalization (openpyxl, lazy) |
| `src/sop_automation/services/sop_prepare.py` | SopPrepareService |
| `src/sop_automation/services/sop_validate.py` | SopValidateService (18 rules) |
| `src/sop_automation/services/sop_compile.py` | SopCompileService |
| `src/sop_automation/services/sop_list.py` | SopListService |
| `src/sop_automation/services/task_plan.py` | TaskPlanService |
| `docs/COPILOT_SOP_AUTHORING_PROTOCOL.md` | 7-step Copilot authoring protocol |
| `docs/COPILOT_SOP_AUTHORING_PROMPT.md` | Ready-to-paste Copilot prompt with full schema |
| `SOP/generated/.gitkeep` | Generated Markdown directory |

### Phase 1 Files Modified

| File | Change |
|------|--------|
| `src/sop_automation/models/sop.py` | Added Phase 1 enums + models; replaced InterpretationRequest/Result; extended SopSource, OutcomeRule, SopStep, CapabilityDefinition, CompiledSop |
| `src/sop_automation/models/task.py` | Added Phase 1 fields to TaskPlan |
| `src/sop_automation/models/__init__.py` | Added 15 new exports |
| `src/sop_automation/storage/paths.py` | Added generated: Path to WorkspacePaths |
| `src/sop_automation/storage/json_store.py` | Added write_text_atomic() |
| `src/sop_automation/cli.py` | Removed 5 Phase 0 stubs; added args + handlers for sop prepare/validate-result/compile/list + task plan |
| `pyproject.toml` | Added openpyxl>=3.1 dependency |
| `tests/unit/test_models.py` | Updated fixtures for Phase 1 model schema |
| `tests/unit/test_cli.py` | Updated stub list; added Phase1CommandsMissingArgs; updated dir count (9→10) |

---

## Phase 0

## Phase 0 Scope Summary

Phase 0 delivers the clean foundation and contract freeze:
- All domain models with Pydantic v2 validation
- Atomic JSON/JSONL storage layer
- Typed error hierarchy
- Environment-based configuration
- CLI skeleton with 1 implemented command and 13 stubs
- Full documentation suite
- Unit tests written (not run in Phase 0)
- 9-directory SOP workspace structure

No browser code, LLM integration, or task execution exists in Phase 0.

---

## Ordered Task List

### M1 — Project Scaffold

| Task | Files | Done Criteria |
|------|-------|---------------|
| M1.1 Create pyproject.toml | `pyproject.toml` | Pydantic>=2.6, pydantic-settings>=2.2, dev extras, sop entrypoint declared |
| M1.1 Create README.md | `README.md` | Install instructions, CLI table with Phase 0 status |
| M1.1 Create scripts/run.py | `scripts/run.py` | Entry point wrapper calls cli.main |
| M1.1 Create src/__init__.py | `src/sop_automation/__init__.py` | Version string set |
| M1.1 Create SOP directories | `SOP/*/gitkeep` | 9 subdirectories with .gitkeep |
| M1.1 Create test scaffolding | `tests/__init__.py`, `tests/unit/__init__.py`, `tests/fixtures/.gitkeep` | Empty init files and fixture placeholder |
| M1.2 Create config.py | `src/sop_automation/config.py` | WorkspaceConfig with sop_workspace field, get_config() singleton |
| M1.2 Create errors.py | `src/sop_automation/errors.py` | 5 typed error classes, no empty excepts |
| M1.2 Create storage/__init__.py | `src/sop_automation/storage/__init__.py` | Empty |
| M1.2 Create storage/paths.py | `src/sop_automation/storage/paths.py` | WorkspacePaths dataclass, resolve_path() with traversal guard |
| M1.2 Create storage/json_store.py | `src/sop_automation/storage/json_store.py` | Atomic write, read, append_jsonl, sha256 helpers, utc_now, new_id |

### M2 — Domain Models

| Task | Files | Done Criteria |
|------|-------|---------------|
| M2.1 Create models/common.py | `src/sop_automation/models/common.py` | FrozenModel, MutableModel, all 7 enums |
| M2.2 Create models/sop.py | `src/sop_automation/models/sop.py` | SopSource, InterpretationRequest, InterpretationResult, OutcomeRule, RetryPolicy, SopStep, CapabilityDefinition, CompiledSop |
| M2.3 Create models/task.py | `src/sop_automation/models/task.py` | TaskIntent, TaskPlan |
| M2.4 Create models/execution.py | `src/sop_automation/models/execution.py` | StepProgress (MutableModel), RunState (MutableModel) |
| M2.5 Create models/clarification.py | `src/sop_automation/models/clarification.py` | ClarificationRequest, Resolution, RememberedResolution |
| M2.6 Create models/tools.py | `src/sop_automation/models/tools.py` | ToolDefinition, ToolBuildRequest |
| M2.7 Create models/__init__.py | `src/sop_automation/models/__init__.py` | All 27 exports in __all__ |

### M3 — Services + CLI

| Task | Files | Done Criteria |
|------|-------|---------------|
| M3.1 Create services/__init__.py | `src/sop_automation/services/__init__.py` | Empty |
| M3.2 Create services/workspace.py | `src/sop_automation/services/workspace.py` | WorkspaceService.init() returns list of (rel, status) tuples |
| M3.3 Create cli.py | `src/sop_automation/cli.py` | 14 commands wired; workspace init returns 0; 13 stubs return 2 |

### M4 — Documentation

| Task | Files | Done Criteria |
|------|-------|---------------|
| M4.1 PRODUCT_REQUIREMENTS.md | `docs/PRODUCT_REQUIREMENTS.md` | 7 user stories, formats, actions, auth, retry, clarification evidence |
| M4.2 ARCHITECTURE.md | `docs/ARCHITECTURE.md` | Copilot layer, Python runtime, all 10 key concepts |
| M4.3 POC_SCOPE.md | `docs/POC_SCOPE.md` | Phase 0 deliverables and exclusions; one section per future phase |
| M4.4 COPILOT_RUNTIME_BOUNDARY.md | `docs/COPILOT_RUNTIME_BOUNDARY.md` | Responsibilities, filesystem contract, autonomy rule |
| M4.5 DOMAIN_MODEL.md | `docs/DOMAIN_MODEL.md` | All entities, relationships, state machines, immutability rule verbatim |
| M4.6 ACCEPTANCE_TESTS.md | `docs/ACCEPTANCE_TESTS.md` | 12 Phase 0 tests (WRITTEN_NOT_RUN), 5+7+4+4+4 future tests (PLANNED) |

### M5 — Tests + Response

| Task | Files | Done Criteria |
|------|-------|---------------|
| M5.1 test_models.py | `tests/unit/test_models.py` | 5 test categories, fixtures, parametrize where applicable |
| M5.2 test_storage.py | `tests/unit/test_storage.py` | 8 test categories covering all storage helpers |
| M5.3 test_cli.py | `tests/unit/test_cli.py` | --help, 13 stubs parametrized, workspace init, idempotency, stdout format |
| M5.4 Fixture JSONs | `tests/fixtures/sample_compiled_sop.json`, `tests/fixtures/sample_run_state.json` | Valid minimal instances loadable by their model |
| M5.5 response.md | `response.md` | Truthful Phase 0 completion report |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validation framework | Pydantic v2 | Strong typing, JSON serialization, frozen models, settings |
| CLI framework | argparse (stdlib) | No extra dependencies; sufficient for Phase 0 |
| Persistence format | JSON + JSONL | Human-readable, debuggable, no database dependency |
| Write strategy | tempfile + os.replace() | Atomic; no partial writes on crash |
| Configuration | pydantic-settings | .env support, type coercion, env var override |
| Frozen models | All except RunState, StepProgress | Value objects and protocol artifacts must not change |
| Mutable models | RunState, StepProgress only | Runtime state must be updatable in-place |
| Error hierarchy | SopAutomationError base | Typed catches; no empty excepts |
| Path safety | resolve_path() traversal guard | Security; all resolved paths checked against workspace root |
| ID generation | uuid4().hex | Collision-resistant, URL-safe, no external dependency |
| os.getenv() isolation | Only in config.py | Single place for env reads; testable |

---

## Exclusions

The following are explicitly excluded from Phase 0:

- Playwright or any browser automation
- LLM or Copilot API calls
- HTTP client or network requests
- Task execution engine (step runner, retry loop, branching)
- Clarification runtime (block, wait, resume)
- Resolution reuse logic
- Route recording
- Tool generation dispatch
- Catalogue tool selection at plan time
- Mac-specific installation testing
- Any integration test that requires a running process

---

## Acceptance Checklist

| Test ID | Name | Status |
|---------|------|--------|
| AT-P0-001 | Model serialization round-trip | WRITTEN_NOT_RUN |
| AT-P0-002 | Enum validation | WRITTEN_NOT_RUN |
| AT-P0-003 | Invalid model rejection | WRITTEN_NOT_RUN |
| AT-P0-004 | Frozen model mutation rejected | WRITTEN_NOT_RUN |
| AT-P0-005 | Atomic JSON write/read round-trip | WRITTEN_NOT_RUN |
| AT-P0-006 | JSONL append accumulates lines | WRITTEN_NOT_RUN |
| AT-P0-007 | SHA256 helper deterministic output | WRITTEN_NOT_RUN |
| AT-P0-008 | Path traversal rejection | WRITTEN_NOT_RUN |
| AT-P0-009 | CLI --help exits 0 and lists all command groups | WRITTEN_NOT_RUN |
| AT-P0-010 | Each Phase 0 stub exits with code 2 | WRITTEN_NOT_RUN |
| AT-P0-011 | workspace init creates all 9 SOP directories | WRITTEN_NOT_RUN |
| AT-P0-012 | workspace init is idempotent | WRITTEN_NOT_RUN |

---

## Phase 1 Handoff Requirements

Phase 1 may begin when:

1. All 12 Phase 0 acceptance tests have status `WRITTEN_NOT_RUN` or `PASS` (none may be `BLOCKED` or `FAILED`)
2. `CompiledSop` model is stable — no breaking field changes may be made after Phase 1 begins
3. Storage helpers are tested — AT-P0-005 through AT-P0-008 must pass
4. CLI skeleton is complete — AT-P0-009 and AT-P0-010 must pass
5. `workspace init` passes — AT-P0-011 and AT-P0-012 must pass
6. `pyproject.toml` installs cleanly: `pip install -e ".[dev]"` exits 0 in a Python 3.11+ virtual environment
7. All documentation files exist and are internally consistent
