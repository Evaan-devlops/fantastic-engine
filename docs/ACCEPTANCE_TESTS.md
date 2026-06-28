# Acceptance Tests — SOPAutomationV2

## Phase 0 Tests

| Field | Value |
|---|---|
| ID | AT-P0-001 |
| Phase | 0 |
| Name | Model serialization round-trip |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | All models (CompiledSop, TaskPlan, RunState, ClarificationRequest, ToolDefinition) serialize to JSON via model_dump() and deserialize back to an equal instance via model_validate() |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-002 |
| Phase | 0 |
| Name | Enum validation |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | ActionType("CLICK"), RunStatus("RUNNING"), StepStatus("PENDING") succeed; ActionType("INVALID"), RunStatus("INVALID"), StepStatus("INVALID") raise ValueError |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-003 |
| Phase | 0 |
| Name | Invalid model rejection |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | Passing an extra field to a FrozenModel raises ValidationError; passing wrong type (step_id=123) raises ValidationError |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-004 |
| Phase | 0 |
| Name | Frozen model mutation rejected |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | Building a CompiledSop then attempting sop.sop_id = "new" raises ValidationError (or TypeError from Pydantic frozen) |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-005 |
| Phase | 0 |
| Name | Atomic JSON write/read round-trip |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | write_json_atomic writes data; read_json reads it back equal; no .tmp file remains after write |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-006 |
| Phase | 0 |
| Name | JSONL append accumulates lines |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | append_jsonl called 3 times produces a file with 3 lines, each valid JSON |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-007 |
| Phase | 0 |
| Name | SHA256 helper deterministic output |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | sha256_of_str("hello") returns same value on two calls; sha256_of_str("hello") != sha256_of_str("world"); sha256_of_file matches sha256_of_str for same content |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-008 |
| Phase | 0 |
| Name | Path traversal rejection |
| Level | unit |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | resolve_path(tmp_dir, "../../etc/passwd") raises WorkspaceError; resolve_path(tmp_dir, "sub/file.json") succeeds and returns a path inside tmp_dir |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-009 |
| Phase | 0 |
| Name | CLI --help exits 0 and lists all command groups |
| Level | integration |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | python -m sop_automation.cli --help exits with code 0; stdout contains "workspace", "sop", "task", "tool" |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-010 |
| Phase | 0 |
| Name | Each Phase 0 stub exits with code 2 |
| Level | integration |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | All 13 stub commands (sop prepare, sop validate-result, sop compile, sop list, task prepare-intent, task plan, task start, task status, task resolve, task resume, task cancel, tool list, tool validate-build-request) exit with code 2 and print NOT_IMPLEMENTED_IN_PHASE_0 |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-011 |
| Phase | 0 |
| Name | workspace init creates all 9 SOP directories |
| Level | integration |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | sop workspace init --workspace <tmp> exits 0; all 9 subdirs (inbox, sources, compiled, manifests, runs, resolutions, routes, tool_build_requests, tools) exist under tmp |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

| Field | Value |
|---|---|
| ID | AT-P0-012 |
| Phase | 0 |
| Name | workspace init is idempotent |
| Level | integration |
| Prerequisites | pyproject.toml installed in dev mode |
| Expected result | Running workspace init twice on the same path: both exit 0; second run output contains [EXISTS] for all directories |
| Playwright required | No |
| Mac required | No |
| Status | WRITTEN_NOT_RUN |

---

## Phase 1 Tests

| Field | Value |
|---|---|
| ID | AT-P1-001 |
| Phase | 1 |
| Name | Natural-language SOP text is interpreted into a valid InterpretationResult |
| Level | integration |
| Prerequisites | Phase 0 complete; Copilot Chat accessible |
| Expected result | sop prepare on a .txt SOP file produces an InterpretationRequest; Copilot writes a valid InterpretationResult; sop validate-result exits 0 |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P1-002 |
| Phase | 1 |
| Name | InterpretationResult with schema_version mismatch is rejected |
| Level | unit |
| Prerequisites | Phase 0 complete |
| Expected result | An InterpretationResult JSON with a mismatched schema_version value causes sop validate-result to exit non-zero with a clear error message |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P1-003 |
| Phase | 1 |
| Name | CSV SOP source is compiled into a valid CompiledSop |
| Level | integration |
| Prerequisites | Phase 0 complete; Phase 1 sop prepare implemented |
| Expected result | sop prepare on a .csv SOP file succeeds; sop compile produces a valid CompiledSop JSON with correct SHA256 |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P1-004 |
| Phase | 1 |
| Name | XLSX SOP source is compiled into a valid CompiledSop |
| Level | integration |
| Prerequisites | Phase 0 complete; Phase 1 sop prepare implemented |
| Expected result | sop prepare on a .xlsx SOP file succeeds; sop compile produces a valid CompiledSop JSON with correct SHA256 |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P1-005 |
| Phase | 1 |
| Name | CompiledSop SHA256 matches content |
| Level | unit |
| Prerequisites | Phase 1 compile implemented |
| Expected result | The compiled_sha256 field of a CompiledSop equals sha256_of_str(json.dumps(sop.model_dump())) |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

---

## Phase 2 Tests

| Field | Value |
|---|---|
| ID | AT-P2-001 |
| Phase | 2 |
| Name | TaskIntent is built from a natural-language request |
| Level | integration |
| Prerequisites | Phase 1 complete |
| Expected result | task prepare-intent with a natural-language goal string produces a valid TaskIntent JSON |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-002 |
| Phase | 2 |
| Name | TaskPlan is built from a TaskIntent and a CompiledSop |
| Level | integration |
| Prerequisites | Phase 1 complete; AT-P2-001 passes |
| Expected result | task plan produces a TaskPlan JSON with ordered_capability_ids and ordered_step_ids matching the CompiledSop |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-003 |
| Phase | 2 |
| Name | workspace init runs successfully and browser launches headless |
| Level | integration |
| Prerequisites | Playwright installed; Python 3.11+ |
| Expected result | task start opens a headless browser session without error |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-004 |
| Phase | 2 |
| Name | OPEN action navigates to a URL on a local fixture site |
| Level | integration |
| Prerequisites | Local fixture site running; Playwright installed |
| Expected result | A SOP step with action=OPEN navigates the browser to the fixture URL and RunState reflects the new current_url |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-005 |
| Phase | 2 |
| Name | FILL action populates a text field on a local fixture site |
| Level | integration |
| Prerequisites | AT-P2-004 passes |
| Expected result | A SOP step with action=FILL fills a text input with the specified value; the field value is confirmed via VERIFY step |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-006 |
| Phase | 2 |
| Name | CLICK action clicks a button on a local fixture site |
| Level | integration |
| Prerequisites | AT-P2-005 passes |
| Expected result | A SOP step with action=CLICK clicks a button; the resulting page change is reflected in RunState current_url |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P2-007 |
| Phase | 2 |
| Name | RunState is persisted atomically after each step transition |
| Level | integration |
| Prerequisites | Phase 2 execution engine implemented |
| Expected result | After each step, the RunState JSON file is updated; no intermediate state is visible; the file is always valid JSON |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

---

## Phase 3 Tests

| Field | Value |
|---|---|
| ID | AT-P3-001 |
| Phase | 3 |
| Name | Missing element raises a ClarificationRequest with screenshot |
| Level | integration |
| Prerequisites | Phase 2 complete; local fixture site with a missing element scenario |
| Expected result | When a step targets an element that does not exist, a ClarificationRequest JSON is written with screenshot_path, current_url, and failure_reason populated |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P3-002 |
| Phase | 3 |
| Name | Resolution is written, validated, and applied to resume the run |
| Level | integration |
| Prerequisites | AT-P3-001 passes |
| Expected result | A valid Resolution JSON causes task resolve + task resume to continue the run past the blocked step |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P3-003 |
| Phase | 3 |
| Name | RememberedResolution is applied automatically on second run |
| Level | integration |
| Prerequisites | AT-P3-002 passes; resolution marked reusable=true |
| Expected result | On the second run, the same step does not raise a ClarificationRequest; the RememberedResolution is applied and logged |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P3-004 |
| Phase | 3 |
| Name | Partial success is recorded when some capabilities complete before failure |
| Level | integration |
| Prerequisites | Phase 2 + Phase 3 complete; multi-capability SOP fixture |
| Expected result | When the first capability completes and the second fails irrecoverably, RunState.status = PARTIAL_SUCCESS and produced_outputs contains the first capability's outputs |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

---

## Phase 4 Tests

| Field | Value |
|---|---|
| ID | AT-P4-001 |
| Phase | 4 |
| Name | Completed route is recorded with SHA256 evidence |
| Level | integration |
| Prerequisites | Phase 3 complete; successful run |
| Expected result | After a successful run, a route JSON is written to SOP/routes/ with a valid SHA256 digest |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P4-002 |
| Phase | 4 |
| Name | ToolBuildRequest is generated from a completed route |
| Level | integration |
| Prerequisites | AT-P4-001 passes |
| Expected result | tool validate-build-request produces a valid ToolBuildRequest JSON in SOP/tool_build_requests/ |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P4-003 |
| Phase | 4 |
| Name | Generated tool is validated and registered in the catalogue |
| Level | integration |
| Prerequisites | AT-P4-002 passes; Copilot generates tool code |
| Expected result | A ToolDefinition JSON is written to SOP/tools/; tool list exits 0 and includes the new tool |
| Playwright required | No |
| Mac required | No |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P4-004 |
| Phase | 4 |
| Name | Registered tool is selected on second run instead of re-executing the SOP |
| Level | integration |
| Prerequisites | AT-P4-003 passes |
| Expected result | task plan selects the registered tool for the capability; task start invokes the tool module instead of the SOP steps; run completes faster |
| Playwright required | Yes |
| Mac required | No |
| Status | PLANNED |

---

## Phase 5 Tests

| Field | Value |
|---|---|
| ID | AT-P5-001 |
| Phase | 5 |
| Name | Package installs and CLI runs on macOS without errors |
| Level | integration |
| Prerequisites | macOS 13+; Python 3.11+; pip |
| Expected result | pip install -e ".[dev]" succeeds; sop --help exits 0 |
| Playwright required | No |
| Mac required | Yes |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P5-002 |
| Phase | 5 |
| Name | Full Phase 0 unit tests pass on macOS |
| Level | unit |
| Prerequisites | AT-P5-001 passes |
| Expected result | pytest tests/unit/ exits 0 with all tests passing on macOS |
| Playwright required | No |
| Mac required | Yes |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P5-003 |
| Phase | 5 |
| Name | Local fixture site POC — full workflow completes |
| Level | e2e |
| Prerequisites | AT-P5-001 passes; local fixture site available on macOS |
| Expected result | workspace init → sop prepare → sop compile → task prepare-intent → task plan → task start completes with RunState.status = COMPLETED |
| Playwright required | Yes |
| Mac required | Yes |
| Status | PLANNED |

| Field | Value |
|---|---|
| ID | AT-P5-004 |
| Phase | 5 |
| Name | External web-application POC — one real workflow completes end-to-end |
| Level | e2e |
| Prerequisites | AT-P5-003 passes; access to external web application |
| Expected result | A real workflow on an external web application completes end-to-end with RunState.status = COMPLETED |
| Playwright required | Yes |
| Mac required | Yes |
| Status | PLANNED |
