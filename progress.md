# Backend Progress — SOPAutomationV2

> **CLI/Backend sub-agent memory.** Read this at the start of every backend task.
> Do NOT read source files to orient — this file has everything you need.
> Open a source file only when you are about to edit it.
> Update after every milestone.

---

## Backend Current State

**Last updated:** 2026-06-28 (Phase 2 COMPLETE)

```
BE-APP: SOPAutomationV2 — Python CLI automation POC
BE-STACK: Python 3.11+ | argparse | Pydantic v2 | JSON/JSONL | Playwright async (Phase 2)
BE-ENTRY: scripts/run.py  →  src/sop_automation/cli.py
BE-ROOT: SOPAutomationV2/   (this folder = backend/ in SPL terms)

BE-MODULES DONE:
  M1 — Project scaffold (pyproject.toml, README, scripts, __init__, SOP dirs, tests scaffold)
  M1.2 — Config + errors + storage (config.py, errors.py, storage/paths.py, storage/json_store.py)
  M2 — Domain models (common, sop, task, execution, clarification, tools, __init__)
  M3 — Services + CLI (services/workspace.py, cli.py — 14 commands, 1 implemented, 13 stubs)
  M4 — Documentation (6 docs + implementation_plan.md)
  M5 — Tests + response (test_models.py, test_storage.py, test_cli.py, fixtures, response.md)
  M6 — Phase 1 tests, fixtures, response (63 tests, 6 fixtures)
  M7 — Phase 1 correction pass (models clean schema, services hash verification, typed plans)
  M8 — Phase 1 correction pass tests + fixtures + response (COMPLETE)
  M9 — Phase 2 Wave 1: models + storage extensions (GoalDefinition, TaskIntent, RuntimeCommand, WorkspacePaths x13)
  M10 — Phase 2 Wave 2: services (SopCompileService, SopValidateService +6 rules, SopSelectorService, TaskIntentService, TaskPlanService)
  M11 — Phase 2 Wave 3: runtime package + CLI (command_queue, condition_evaluator, page_preparation, locator_service, action_dispatcher, run_manager, host, 6 task commands)
  M12 — Phase 2 Wave 4: tests fixed + new test files written
  M13 — Phase 2 Wave 5: documentation (COPILOT_TASK_PROTOCOL, COPILOT_TASK_PROMPT, MAC_POC_RUNBOOK)

BE-ACTIVE: Phase 2 COMPLETE — all waves done

BE-NEXT: Phase 3 planning — clarification resolution flow, remembered resolutions, resume after partial success

BE-ENV:
  SOP_WORKSPACE = (optional — default workspace root, read only via config.py)

BE-PATTERNS:
  CLI handlers     → thin: parse args → call service → print output. No business logic.
  Services         → business logic, no formatting, no os.getenv()
  Preprocessing    → deterministic structural detection only. No NL inference.
  Storage          → atomic writes (tempfile + os.replace), traversal guard on every path
  Config           → config.py WorkspaceConfig only — no os.getenv() elsewhere
  Models           → FrozenModel for value objects, MutableModel for runtime state
  Validation rules → 30 rules in SopValidateService (24 Phase 1 + 6 Phase 2); Kahn's algorithm for cycle detection
  Runtime          → async Playwright host; one-active-run enforcement; retry 2 attempts; MANUAL_AUTH pause
  Phase 0 stubs    → print NOT_IMPLEMENTED_IN_POC, sys.exit(2)
```

---

## Resume Point

**Active task:** Phase 3 planning (not started)
**Last file written:** docs/MAC_POC_RUNBOOK.md (Phase 2 Wave 5 docs complete)

**Done within Phase 0:**
- [x] M1 T1.1: directory tree + pyproject.toml + README + scripts/run.py + __init__.py + SOP/ .gitkeeps
- [x] M1 T1.2: config.py + errors.py + storage/paths.py + storage/json_store.py
- [x] M2 T2.1: models/common.py (FrozenModel, MutableModel, all enums)
- [x] M2 T2.2: models/sop.py
- [x] M2 T2.3: models/task.py
- [x] M2 T2.4: models/execution.py
- [x] M2 T2.5: models/clarification.py
- [x] M2 T2.6: models/tools.py
- [x] M3 T3.1: services/workspace.py + cli.py (14 commands — 1 impl, 13 stubs)
- [x] M4 T4.1: docs/ (6 docs: PRD, ARCH, SCOPE, BOUNDARY, DOMAIN, ACCEPTANCE)
- [x] M4 T4.2: implementation_plan.md
- [x] M5 T5.1: tests/unit/ (written, not run)
- [x] M5 T5.2: response.md + fixture JSONs

**Done within Phase 1:**
- [x] M6 T6.1: tests/unit/test_preprocessing.py (19 tests)
- [x] M6 T6.2: tests/unit/test_validation.py (15 tests)
- [x] M6 T6.3: tests/unit/test_compilation.py (9 tests)
- [x] M6 T6.4: tests/unit/test_task_plan.py (7 tests)
- [x] M6 T6.5: tests/unit/test_phase1_cli.py (13 tests)
- [x] M6 T6.6: tests/fixtures/ (6 fixture files)
- [x] M6 T6.7: test_cli.py + test_models.py updated for Phase 1
- [x] M6 T6.8: response.md overwritten with full Phase 1 response
- [x] M7–M8: Phase 1 correction pass (models, services, preprocessing, tests, fixtures)

**Done within Phase 2:**
- [x] Wave 1 — Models + Storage:
  - GoalDefinition compiled model (entry_capability_id, capability_ids, aliases)
  - GoalProposal updated: capability_sequence → entry_capability_id + capability_ids
  - WaitConditionSpec typed model with 11 WaitConditionType values
  - ConditionSpec.expected_value: str | None → Union[str, int, float, bool, None]
  - is_default: bool = False added to OutcomeProposal, OutcomeRule, PlannedOutcome
  - PlannedCapability model grouping steps by capability
  - TaskPlan updated: entry_capability_id field, capabilities: list[PlannedCapability]
  - TaskIntent model: schema_version, created_at, inputs, constraints
  - RuntimeCommand, CommandAcknowledgement, StepResult in models/runtime.py
  - WorkspacePaths extended to 13 directories (runtime, runtime_commands, runtime_acks)
  - pyproject.toml: single flat dependency list, removed [project.optional-dependencies]
- [x] Wave 2 — Services:
  - SopCompileService: produces typed GoalDefinition objects
  - SopValidateService: 6 new rules (GOAL_REACHABILITY, GOAL_CYCLE_DETECTION, OUTCOME_DEFAULT_SINGLE, OUTCOME_CONDITION_REQUIRED, OUTCOME_TERMINAL_NO_NEXT, OUTCOME_NONTERMINAL_HAS_NEXT); branch edge bug fixed
  - SopSelectorService (new): selects compiled SOP from TaskIntent with scoring
  - TaskIntentService (new): parses request text, validates TaskIntent
  - TaskPlanService: graph-safe edge construction, PlannedCapability groups, entry_capability_id routing
- [x] Wave 3 — Runtime Package + CLI:
  - runtime/command_queue.py: atomic read/write for runtime commands
  - runtime/condition_evaluator.py: safe dot-path evaluation, 7 operators, no eval()
  - runtime/page_preparation.py: canonical pre-action wait using WaitConditionSpec
  - runtime/locator_service.py: 4-strategy locator chain with LocatorError
  - runtime/action_dispatcher.py: all 17 ActionType handlers
  - runtime/run_manager.py: retry (2 attempts), screenshot suppression, MANUAL_AUTH pause, events.jsonl
  - runtime/host.py: foreground async host, one-active-run enforcement, Ctrl+C shutdown
  - CLI: runtime start command; 6 task commands (prepare-intent, validate-intent, submit, status, continue, cancel)
  - CLI: removed phase labels, NOT_IMPLEMENTED_IN_POC replaces NOT_IMPLEMENTED_IN_PHASE_0
- [x] Wave 4 — Tests (written, NOT run):
  - Fixed 2 failing tests (branch edge, directory count)
  - Updated fixture JSONs: valid_interpretation_result.json, sample_compiled_sop.json, deferred_branch.json, invalid_dependency_cycle.json
  - Updated existing tests: test_models.py, test_validation.py, test_compilation.py, test_phase1_cli.py
  - New tests: test_condition_evaluator.py, test_command_queue.py, test_sop_selector.py, test_task_intent.py, test_run_manager.py, test_runtime_host.py, test_page_preparation.py, test_action_dispatcher.py, test_fixture_app.py, test_playwright_fixture.py
  - tests/fixtures/local_fixture_app.py: stdlib HTTP fixture server (no third-party deps)
- [x] Wave 5 — Documentation:
  - docs/COPILOT_TASK_PROTOCOL.md (new)
  - docs/COPILOT_TASK_PROMPT.md (new)
  - docs/MAC_POC_RUNBOOK.md (new)

**Blockers:** none

---

## File Map

```
SOPAutomationV2/
  src/sop_automation/
    __init__.py             — __version__ = "0.1.0"
    cli.py                  — main(), argparse app, all commands (runtime + 6 task commands added)
    config.py               — WorkspaceConfig(BaseSettings): SOP_WORKSPACE; get_config()
    errors.py               — SopAutomationError, StorageError, ValidationError,
                              WorkspaceError, NotImplementedInPocError
    models/
      __init__.py           — re-exports all public model classes
      common.py             — FrozenModel, MutableModel, SourceFormat, ActionType,
                              ElementType, RunStatus, StepStatus, ClarificationType,
                              ToolHealth, WaitConditionType
      sop.py                — Phase 1+2: all SOP models; GoalDefinition (new);
                              WaitConditionSpec (new); ConditionSpec.expected_value widened;
                              is_default on OutcomeRule/OutcomeProposal
      task.py               — TaskIntent (new), PlannedCapability (new), TaskPlan updated;
                              PlannedOutcome +is_default; entry_capability_id in TaskPlan
      validation.py         — ValidationSeverity, ValidationIssue, ValidationReport
                              (+request_sha256, +result_sha256)
      execution.py          — StepProgress (mutable), RunState (mutable)
      clarification.py      — ClarificationRequest, Resolution, RememberedResolution
      tools.py              — ToolDefinition, ToolBuildRequest
      runtime.py            — RuntimeCommand, CommandAcknowledgement, StepResult [NEW]
    preprocessing/
      __init__.py
      text_preprocessor.py
      csv_preprocessor.py
      xlsx_preprocessor.py
    services/
      __init__.py
      workspace.py          — WorkspaceService.init(root) → list[tuple[str, str]]
      sop_prepare.py        — SopPrepareService.prepare()
      sop_validate.py       — SopValidateService.validate() (30 rules)
      sop_compile.py        — SopCompileService.compile() → GoalDefinition objects
      sop_list.py           — SopListService.list_sops()
      sop_selector.py       — SopSelectorService.select() [NEW]
      task_intent.py        — TaskIntentService.parse() + validate() [NEW]
      task_plan.py          — TaskPlanService.plan() → PlannedCapability groups
    runtime/               [NEW PACKAGE]
      __init__.py
      command_queue.py      — atomic read/write for RuntimeCommand
      condition_evaluator.py — safe dot-path eval, 7 operators, no eval()
      page_preparation.py   — pre-action wait using WaitConditionSpec
      locator_service.py    — 4-strategy locator chain with LocatorError
      action_dispatcher.py  — all 17 ActionType handlers
      run_manager.py        — retry (2 attempts), MANUAL_AUTH pause, events.jsonl
      host.py               — foreground async host, Ctrl+C shutdown
    storage/
      __init__.py
      paths.py              — WorkspacePaths (13 dirs), resolve_path(), traversal guard
      json_store.py         — write_json_atomic(), write_bytes_atomic(), read_json(),
                              append_jsonl(), sha256_of_file(), sha256_of_str(),
                              utc_now(), new_id()
  tests/
    unit/
      __init__.py
      test_models.py             — updated for Phase 2 schemas
      test_storage.py
      test_cli.py                — updated: runtime + task commands
      test_preprocessing.py
      test_validation.py         — updated + 6 Phase 2 rule tests
      test_compilation.py        — updated: GoalDefinition output
      test_task_plan.py          — updated: PlannedCapability groups
      test_phase1_cli.py         — updated: hash fields, NOT_IMPLEMENTED_IN_POC
      test_condition_evaluator.py [NEW]
      test_command_queue.py      [NEW]
      test_sop_selector.py       [NEW]
      test_task_intent.py        [NEW]
      test_run_manager.py        [NEW]
      test_runtime_host.py       [NEW]
      test_page_preparation.py   [NEW]
      test_action_dispatcher.py  [NEW]
      test_fixture_app.py        [NEW]
      test_playwright_fixture.py [NEW — requires playwright installed]
    fixtures/
      sample_nl_sop.txt
      sample_sop.csv
      sample_sop_data.json
      valid_interpretation_result.json  — updated for Phase 2
      invalid_dependency_cycle.json     — updated for Phase 2
      deferred_branch.json              — updated for Phase 2
      sample_compiled_sop.json          — updated for Phase 2
      local_fixture_app.py              — stdlib HTTP fixture server [NEW]
  docs/
    PRODUCT_REQUIREMENTS.md
    ARCHITECTURE.md
    POC_SCOPE.md
    ACCEPTANCE_TESTS.md
    COPILOT_RUNTIME_BOUNDARY.md
    DOMAIN_MODEL.md
    COPILOT_TASK_PROTOCOL.md  [NEW — Phase 2 Wave 5]
    COPILOT_TASK_PROMPT.md    [NEW — Phase 2 Wave 5]
    MAC_POC_RUNBOOK.md        [NEW — Phase 2 Wave 5]
  SOP/
    inbox/ sources/ compiled/ manifests/ runs/ resolutions/ routes/
    tool_build_requests/ tools/ generated/ runtime/ runtime/commands/ runtime/acks/
    — all .gitkeep
  scripts/run.py
  pyproject.toml
  README.md
  implementation_plan.md
  response.md
```

---

## Backend Pattern Index

| Pattern | Rule | get_symbol command |
|---------|------|--------------------|
| CLI handler | parse args → validate via Pydantic → call service → print. No logic. | `get_symbol SOPAutomationV2/src/sop_automation/cli.py main` |
| Service result | Returns structured data — never formatted strings | `get_symbol SOPAutomationV2/src/sop_automation/services/workspace.py WorkspaceService` |
| Config access | `from sop_automation.config import get_config` — nowhere else | `get_symbol SOPAutomationV2/src/sop_automation/config.py get_config` |
| Atomic write | `write_json_atomic(path, data)` — tempfile + os.replace | `get_symbol SOPAutomationV2/src/sop_automation/storage/json_store.py write_json_atomic` |
| Traversal guard | `resolve_path(root, rel)` raises WorkspaceError if outside root | `get_symbol SOPAutomationV2/src/sop_automation/storage/paths.py resolve_path` |
| POC stub | print NOT_IMPLEMENTED_IN_POC, sys.exit(2) | `get_symbol SOPAutomationV2/src/sop_automation/cli.py main` |
| Preprocessing | preprocess_text/csv/xlsx → PreprocessedSource. Structural only, no NL inference. | `get_symbol SOPAutomationV2/src/sop_automation/preprocessing/text_preprocessor.py preprocess_text` |
| Validation rules | SopValidateService.validate() — 30 rules, Kahn's cycle detection | `get_symbol SOPAutomationV2/src/sop_automation/services/sop_validate.py SopValidateService` |
| Compilation | SopCompileService.compile() — GoalDefinition output; hash verification required | `get_symbol SOPAutomationV2/src/sop_automation/services/sop_compile.py SopCompileService` |
| SOP selection | SopSelectorService.select(intent) — scoring against compiled SOPs | `get_symbol SOPAutomationV2/src/sop_automation/services/sop_selector.py SopSelectorService` |
| Task intent | TaskIntentService.parse(text) → TaskIntent; validate() → issues list | `get_symbol SOPAutomationV2/src/sop_automation/services/task_intent.py TaskIntentService` |
| Runtime host | async foreground host; one-active-run; Ctrl+C shutdown | `get_symbol SOPAutomationV2/src/sop_automation/runtime/host.py` |
| Condition eval | condition_evaluator.py — safe dot-path, 7 operators, no eval() | `get_symbol SOPAutomationV2/src/sop_automation/runtime/condition_evaluator.py` |
| Copilot protocol | 7-step task execution pipeline | `docs/COPILOT_TASK_PROTOCOL.md` |
| Frozen model | Inherit FrozenModel — all value/protocol objects | `get_symbol SOPAutomationV2/src/sop_automation/models/common.py FrozenModel` |
| Mutable model | Inherit MutableModel — StepProgress, RunState only | `get_symbol SOPAutomationV2/src/sop_automation/models/common.py MutableModel` |

---

## Backend Dev Log

<!-- Add entries after each milestone. Keep last 3. -->

**2026-06-28 — Phase 2 Wave 5 COMPLETE — documentation**
3 new docs written: COPILOT_TASK_PROTOCOL.md (7-step task execution protocol), COPILOT_TASK_PROMPT.md (exact Copilot Chat prompt format with examples), MAC_POC_RUNBOOK.md (macOS install + end-to-end run guide). response.md overwritten with full Phase 2 summary. progress.md updated to mark Phase 2 COMPLETE. Phase 3 planning is next.

**2026-06-28 — Phase 2 Wave 4 COMPLETE — tests written (not run)**
Fixed 2 failing tests (branch edge, directory count). Updated 4 existing test files and 4 fixture JSONs. Added 10 new test files: test_condition_evaluator, test_command_queue, test_sop_selector, test_task_intent, test_run_manager, test_runtime_host, test_page_preparation, test_action_dispatcher, test_fixture_app, test_playwright_fixture. Added tests/fixtures/local_fixture_app.py (stdlib HTTP server, no third-party deps).

**2026-06-28 — Phase 2 Waves 1–3 COMPLETE — models, services, runtime, CLI**
Wave 1: GoalDefinition, WaitConditionSpec, TaskIntent, RuntimeCommand, PlannedCapability, WorkspacePaths x13, pyproject.toml flat deps. Wave 2: SopCompileService GoalDefinition output, SopValidateService +6 rules, SopSelectorService (new), TaskIntentService (new), TaskPlanService PlannedCapability groups. Wave 3: full runtime/ package (7 modules), CLI runtime start + 6 task commands, NOT_IMPLEMENTED_IN_POC label.

**2026-06-28 — Phase 1 correction pass — tests, fixtures, response (M8 COMPLETE)**
Tests updated for clean schemas: test_task_plan rewritten (typed PlannedStep/BranchPoint/CapabilityEdge, no Phase 0 fields); test_compilation _make_passing_report + _make_failing_report now include request_sha256/result_sha256; test_validation +6 tests; test_preprocessing +5 tests; test_models +8 new tests; test_phase1_cli SRC_PATH fixed; fixtures: sample_compiled_sop.json rewritten, valid_interpretation_result.json updated, deferred_branch.json updated; response.md overwritten.
