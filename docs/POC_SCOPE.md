# POC Scope — SOPAutomationV2

## Phase 0 — Clean Foundation and Contract Freeze

### Deliverables

- Domain model: all 6 model files in `src/sop_automation/models/` with full type hints, Pydantic v2 validation, and correct frozen/mutable configuration
- Storage foundation: atomic JSON/JSONL write/read, SHA-256 helpers, ID generation, traversal-guarded path resolution
- Configuration: `WorkspaceConfig` via pydantic-settings, `get_config()` singleton, `.env` support
- Error hierarchy: `SopAutomationError` base with typed subclasses for all failure categories
- CLI skeleton: all 14 commands registered via argparse; `workspace init` fully implemented; 13 stubs return exit code 2 with `NOT_IMPLEMENTED_IN_PHASE_0` message
- SOP directory structure: 9 subdirectories with `.gitkeep` files
- Documentation: PRD, Architecture, POC Scope, Copilot-Runtime Boundary, Domain Model, Acceptance Tests
- Unit tests written (not run): `test_models.py`, `test_storage.py`, `test_cli.py`
- Fixture JSON files: `sample_compiled_sop.json`, `sample_run_state.json`

### Phase 0 Exclusions

The following are explicitly out of scope for Phase 0:

- Natural-language SOP interpretation (no LLM calls, no Copilot API)
- Browser automation (no Playwright, no Selenium, no CDP)
- Task execution engine (no step runner, no retry loop, no branching)
- Clarification runtime (no blocking on ClarificationRequest, no Resume logic)
- Resolution reuse (no RememberedResolution lookup)
- Route learning (no execution route recording)
- Tool generation (no ToolBuildRequest dispatch, no code generation)
- Catalogue invocation (no tool selection at plan time)
- Any network activity (no HTTP, no browser)
- Mac-specific installation or validation

### Phase 1 Prerequisites

Before Phase 1 can begin:
- All Phase 0 acceptance tests must be status `WRITTEN_NOT_RUN` or `PASS`
- `CompiledSop` model must be stable (no breaking field changes)
- Storage helpers must be tested (AT-P0-005 through AT-P0-008)
- CLI skeleton must be complete with correct exit codes (AT-P0-009, AT-P0-010)
- `workspace init` must pass (AT-P0-011, AT-P0-012)
- `pyproject.toml` must install cleanly in a Python 3.11+ virtual environment

---

## Phase 1 — Natural-Language SOP Authoring and Compilation

### What Phase 1 Adds

- `sop prepare`: detects SOP source format, creates `InterpretationRequest`, writes to `SOP/manifests/`
- `sop validate-result`: reads an `InterpretationResult` JSON written by Copilot, validates against schema, writes a `SopSource` record
- `sop compile`: builds a `CompiledSop` from a validated `SopSource` + `InterpretationResult`, writes to `SOP/compiled/`
- `sop list`: lists all compiled SOPs with ID, version, goals, and creation date
- Copilot Chat integration: Copilot reads `InterpretationRequest` and writes `InterpretationResult`

### Phase 1 Requirements from Prior Phases

- Phase 0 domain models (especially `SopSource`, `InterpretationRequest`, `InterpretationResult`, `CompiledSop`)
- Phase 0 atomic JSON storage
- Phase 0 CLI skeleton

---

## Phase 2 — Task Planning and Foreground Browser Execution

### What Phase 2 Adds

- `task prepare-intent`: builds a `TaskIntent` from a natural-language goal and inputs
- `task plan`: builds a `TaskPlan` from a `TaskIntent` + `CompiledSop`
- `task start`: opens a Playwright browser and begins step execution; writes `RunState` after each step
- `task status`: reads and displays current `RunState`
- `task cancel`: sets `RunState.status = CANCELLED` and closes the browser
- Local fixture site for integration testing

### Phase 2 Requirements from Prior Phases

- Phase 1 compiled SOPs
- Phase 0 storage, models, workspace

---

## Phase 3 — Clarification, Remembered Resolutions, Resume, Partial Success

### What Phase 3 Adds

- `task resolve`: validates a `Resolution` JSON written by the user (via Copilot) and applies it to a paused run
- `task resume`: resumes a run that is `WAITING_FOR_CLARIFICATION` or `WAITING_FOR_AUTH`
- Automatic `RememberedResolution` lookup before raising new clarification
- `RememberedResolution` storage and `success_count` update
- `PARTIAL_SUCCESS` run status when some capabilities complete before an unrecoverable failure

### Phase 3 Requirements from Prior Phases

- Phase 2 task execution engine
- Phase 1 compiled SOPs
- Phase 0 models (ClarificationRequest, Resolution, RememberedResolution)

---

## Phase 4 — Capability Routes, Tool-Build Requests, Catalogue Registration

### What Phase 4 Adds

- Route recording: after a successful capability execution, record the route with SHA256 evidence
- `tool validate-build-request`: validates and writes a `ToolBuildRequest` for a completed route
- Copilot generates tool code from the `ToolBuildRequest`
- `tool list`: lists all registered `ToolDefinition` records
- Planner selects registered tools at `task plan` time, replacing SOP steps with tool invocations
- Tool health check: validate that a registered tool's entrypoint exists and passes a smoke test

### Phase 4 Requirements from Prior Phases

- Phase 3 run completion data
- Phase 2 execution engine
- Phase 1 compiled SOPs
- Phase 0 models (ToolDefinition, ToolBuildRequest)

---

## Phase 5 — Mac Installation, Local Fixture Validation, External Web-App POC

### What Phase 5 Adds

- Mac installation validation: `pip install -e ".[dev]"` runs cleanly on macOS 13+
- Full Phase 0–4 unit and integration test suite passes on macOS
- Local fixture site POC: end-to-end run from `sop prepare` → `task start` → `COMPLETED` using a local HTML fixture
- External web-application POC: one real-world workflow completes end-to-end (candidate: OneTrust or equivalent public-access application)
- Documentation for setting up the Mac development environment

### Phase 5 Requirements from Prior Phases

- All prior phases complete and tested
- Playwright browser dependencies installable on macOS
- At least one real compiled SOP exists for the external POC
