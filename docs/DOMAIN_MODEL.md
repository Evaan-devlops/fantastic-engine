# Domain Model — SOPAutomationV2

## Immutability Rule

> Definition and protocol models are immutable after creation. Execution-state models are mutable only through runtime service methods and are persisted atomically after each state transition.

This rule is enforced by Pydantic's `frozen=True` (`FrozenModel`) and `frozen=False` (`MutableModel`) configurations. Attempting to mutate a frozen model raises a `ValidationError`.

---

## Entity Catalogue

### `SopSource` — `models/sop.py`
A raw SOP source file registered in the system.

| Field | Type | Description |
|-------|------|-------------|
| source_id | str | Unique ID for this source record |
| sop_id | str | Logical SOP this source belongs to |
| format | SourceFormat | Detected format (NATURAL_LANGUAGE, CSV, XLSX, BROWSER_OBSERVATION) |
| path | str | Workspace-relative path to the source file |
| application_ids | list[str] | Web applications this SOP targets |
| created_at | datetime | UTC timestamp of registration |
| sha256 | str | SHA-256 hex digest of the source file content |

**Frozen**: Yes (FrozenModel)

---

### `InterpretationRequest` — `models/sop.py`
Request sent to Copilot to interpret a SOP source into structured form.

| Field | Type | Description |
|-------|------|-------------|
| request_id | str | Unique request ID |
| sop_id | str | SOP being interpreted |
| source_id | str | Source record being interpreted |
| source_text | str \| None | Full text content of the source (for natural language) |
| source_reference | str \| None | Path or URL reference (for file-based sources) |
| detected_sections | list[str] | Sections the runtime detected in the source |
| detected_urls | list[str] | URLs detected in the source |
| detected_placeholders | list[str] | Template placeholders detected |
| required_output_schema_version | str | Schema version Copilot must produce |

**Frozen**: Yes (FrozenModel)

---

### `InterpretationResult` — `models/sop.py`
Structured SOP interpretation produced by Copilot and validated by the runtime.

| Field | Type | Description |
|-------|------|-------------|
| request_id | str | Matches the originating InterpretationRequest |
| schema_version | str | Must match required_output_schema_version |
| application_ids | list[str] | Applications identified in the SOP |
| goals | list[str] | High-level goals this SOP achieves |
| capabilities | list[dict] | Capability definitions (pre-validation raw form) |
| steps | list[dict] | Step definitions (pre-validation raw form) |
| assumptions | list[str] | Assumptions Copilot made during interpretation |
| unresolved_items | list[str] | Items Copilot could not interpret |

**Frozen**: Yes (FrozenModel)

---

### `CompiledSop` — `models/sop.py`
A validated, compiled SOP ready for task planning and execution.

| Field | Type | Description |
|-------|------|-------------|
| sop_id | str | Logical SOP identifier |
| version | str | Version string (incremented on recompile) |
| source_id | str | Source record this was compiled from |
| application_ids | list[str] | Target applications |
| goals | list[str] | High-level goals |
| capabilities | list[CapabilityDefinition] | Named, reusable capability definitions |
| steps | list[SopStep] | Ordered executable steps |
| inputs | list[str] | Required inputs for the SOP |
| outputs | list[str] | Produced outputs |
| created_at | datetime | Compilation timestamp |
| source_sha256 | str | SHA-256 of the source file at compile time |
| compiled_sha256 | str | SHA-256 of the compiled JSON content |

**Frozen**: Yes (FrozenModel)

---

### `SopStep` — `models/sop.py`
A single executable step within a compiled SOP.

| Field | Type | Description |
|-------|------|-------------|
| step_id | str | Unique step identifier |
| sequence | int | Execution order within the SOP |
| application_id | str | Target application |
| capability_id | str | Owning capability |
| action | ActionType | Browser action to perform |
| element_name | str | Human-readable name of the target element |
| element_type | ElementType | UI element category |
| value | str \| None | Value to fill, key to press, option to select, etc. |
| wait_condition | str \| None | Optional readiness condition checked before the action |
| postcondition | str \| None | Optional completion condition checked after the action |
| expected_outcomes | list[OutcomeRule] | Conditional branch outcomes |
| dependencies | list[str] | Step IDs that must complete first |
| retry_policy | RetryPolicy | Retry configuration |
| screenshot_policy | str | When to capture screenshots |
| notes | str \| None | Human-authored notes |
| source_reference | str \| None | Reference back to source material |

**Frozen**: Yes (FrozenModel)

---

### `CapabilityDefinition` — `models/sop.py`
A named, reusable sub-sequence of SOP steps.

| Field | Type | Description |
|-------|------|-------------|
| capability_id | str | Unique capability identifier |
| application_id | str | Target application |
| name | str | Short human-readable name |
| purpose | str | What this capability achieves |
| step_ids | list[str] | Ordered step IDs in this capability |
| required_inputs | list[str] | Inputs this capability needs |
| produced_outputs | list[str] | Outputs this capability produces |
| dependencies | list[str] | Other capability IDs that must run first |
| is_tool_candidate | bool | Whether a tool should be generated for this |
| is_deferred | bool | Whether this capability is not yet implemented |
| manual_checkpoint_allowed | bool | Whether a MANUAL_AUTH pause is expected |

**Frozen**: Yes (FrozenModel)

---

### `TaskIntent` — `models/task.py`
A validated user request to execute a goal using a SOP.

| Field | Type | Description |
|-------|------|-------------|
| intent_id | str | Unique intent identifier |
| raw_request_hash | str | SHA-256 of the user's raw natural-language request |
| requested_goal | str | Normalised goal string |
| preferred_sop_id | str \| None | User-specified SOP preference |
| application_hints | list[str] | Application IDs the user mentioned |
| inputs | dict[str, Any] | Named input values |
| constraints | dict[str, Any] | Execution constraints (timeouts, retries, etc.) |

**Frozen**: Yes (FrozenModel)

---

### `TaskPlan` — `models/task.py`
An ordered execution plan derived from a TaskIntent and a compiled SOP.

| Field | Type | Description |
|-------|------|-------------|
| task_id | str | Unique plan identifier |
| intent_id | str | Originating intent |
| sop_id | str | SOP this plan was built from |
| selected_goal | str | Goal selected from the SOP's goals list |
| ordered_capability_ids | list[str] | Capabilities to execute, in order |
| ordered_step_ids | list[str] | Steps to execute, in order |
| required_inputs | list[str] | Inputs the plan requires |
| branch_points | dict[str, list[str]] | Step ID → list of possible next step IDs |
| created_at | datetime | Plan creation timestamp |

**Frozen**: Yes (FrozenModel)

---

### `RunState` — `models/execution.py`
The mutable state of a single task execution.

| Field | Type | Description |
|-------|------|-------------|
| run_id | str | Unique run identifier |
| task_id | str | Originating task plan |
| status | RunStatus | Current lifecycle state |
| current_capability_id | str \| None | Capability currently executing |
| current_step_id | str \| None | Step currently executing |
| step_progress | dict[str, StepProgress] | Per-step execution records |
| branch_decisions | dict[str, str] | Step ID → selected outcome ID |
| inputs | dict[str, Any] | Runtime input values |
| produced_outputs | dict[str, Any] | Outputs accumulated so far |
| clarification_request_id | str \| None | Active clarification request (if any) |
| created_at | datetime | Run creation timestamp |
| updated_at | datetime | Last update timestamp |

**Frozen**: No (MutableModel) — updated through runtime service methods only

---

### `StepProgress` — `models/execution.py`
Mutable execution record for a single SOP step within a run.

| Field | Type | Description |
|-------|------|-------------|
| step_id | str | Step being tracked |
| status | StepStatus | Current step state |
| started_at | datetime \| None | When execution began |
| completed_at | datetime \| None | When execution ended |
| attempt_count | int | Number of attempts made |
| current_url | str \| None | Page URL at last action |
| screenshot_paths | list[str] | Paths to captured screenshots |
| error_code | str \| None | Error code from last failure |
| error_message | str \| None | Human-readable failure message |
| selected_outcome_id | str \| None | Outcome rule applied at this step |

**Frozen**: No (MutableModel)

---

### `ClarificationRequest` — `models/clarification.py`
A request for human input raised when execution is blocked.

**Frozen**: Yes (FrozenModel) — written once at block time, never modified

---

### `Resolution` — `models/clarification.py`
A human-provided resolution to a clarification request.

**Frozen**: Yes (FrozenModel) — written once by user/Copilot, validated and applied by runtime

---

### `RememberedResolution` — `models/clarification.py`
A verified resolution stored for automatic reuse.

**Frozen**: Yes (FrozenModel) — a new record is written when success_count is incremented (immutable update pattern)

---

### `ToolDefinition` — `models/tools.py`
A registered deterministic capability tool in the catalogue.

**Frozen**: Yes (FrozenModel)

---

### `ToolBuildRequest` — `models/tools.py`
A validated request for Copilot to generate a capability tool.

**Frozen**: Yes (FrozenModel)

---

## Entity Relationships

```
SopSource ──► InterpretationRequest ──► InterpretationResult
                                              │
                                              ▼
                                        CompiledSop
                                         ├── CapabilityDefinition[]
                                         └── SopStep[]
                                              │
                                              ▼
                                         TaskIntent
                                              │
                                              ▼
                                          TaskPlan
                                              │
                                              ▼
                                          RunState
                                         ├── StepProgress[] (one per step)
                                         └── clarification_request_id?
                                              │
                                              ▼
                                    ClarificationRequest
                                              │
                                              ▼
                                          Resolution
                                              │
                                              ▼
                                   RememberedResolution (if reusable)
                                              │
                           (route recorded after successful run)
                                              │
                                              ▼
                                      ToolBuildRequest
                                              │
                                              ▼
                                       ToolDefinition (catalogue)
```

---

## RunStatus State Machine

```
                    ┌─────────┐
                    │ CREATED │
                    └────┬────┘
                         │ task start
                         ▼
                    ┌─────────┐
                    │ RUNNING │◄────────────────────────────┐
                    └────┬────┘                             │
          ┌──────────────┼──────────────────┐              │
          │              │                  │              │
          ▼              ▼                  ▼              │
  WAITING_FOR_   WAITING_FOR_      WAITING_FOR_           │
    AUTH       CLARIFICATION    DEFERRED_CAPABILITY       │
          │              │                  │              │
          └──────────────┴──────────────────┘              │
                         │ task resume / task resolve       │
                         └─────────────────────────────────┘
                         │ (or continues directly)
          ┌──────────────┼──────────────────┐
          │              │                  │
          ▼              ▼                  ▼
    COMPLETED    PARTIAL_SUCCESS         FAILED
                                            │
                                            ▼
                                        CANCELLED
                                    (from any non-terminal state)
```

Valid transitions to `CANCELLED`: from `RUNNING`, `WAITING_FOR_AUTH`, `WAITING_FOR_CLARIFICATION`, `WAITING_FOR_DEFERRED_CAPABILITY`.

---

## StepStatus State Machine

```
PENDING ──► RUNNING ──► COMPLETED
                   └──► FAILED
                   └──► WAITING (mid-step pause, e.g. MANUAL_AUTH)
PENDING ──► SKIPPED (branch bypassed this step)
```

`WAITING` transitions back to `RUNNING` when `task resume` is called.
`FAILED` is terminal for the step (the run may raise clarification or transition to FAILED/PARTIAL_SUCCESS).

---

## Frozen vs Mutable — Summary

| Model | Frozen | Rationale |
|-------|--------|-----------|
| FrozenModel base | Yes | All value objects and protocol artifacts |
| MutableModel base | No | Runtime state only |
| SopSource | Yes | Immutable registration record |
| InterpretationRequest | Yes | Protocol artifact sent to Copilot |
| InterpretationResult | Yes | Protocol artifact received from Copilot |
| CompiledSop | Yes | Validated definition; never changes after compile |
| SopStep | Yes | Part of CompiledSop |
| CapabilityDefinition | Yes | Part of CompiledSop |
| OutcomeRule | Yes | Part of SopStep |
| RetryPolicy | Yes | Part of SopStep |
| TaskIntent | Yes | Immutable user request |
| TaskPlan | Yes | Immutable execution plan |
| RunState | No | Mutable — updated after every step transition |
| StepProgress | No | Mutable — updated as step executes |
| ClarificationRequest | Yes | Written once at block time |
| Resolution | Yes | Written once by user/Copilot |
| RememberedResolution | Yes | New record written on each reuse (immutable update) |
| ToolDefinition | Yes | Immutable catalogue entry |
| ToolBuildRequest | Yes | Immutable Copilot-addressed request |
