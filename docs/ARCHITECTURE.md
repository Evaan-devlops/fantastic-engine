# Architecture — SOPAutomationV2

## System Overview

SOPAutomationV2 consists of two collaborating layers that communicate exclusively through the filesystem and CLI:

1. **Copilot Interaction Layer** — GitHub Copilot Chat running in the IDE
2. **Python Runtime** — a CLI application that validates, plans, and executes

There is no direct API call between the two layers. All state lives in files.

---

## Copilot Interaction Layer

### Responsibilities
- Authors SOPs from user natural-language descriptions
- Writes strict JSON request/result files that conform to the runtime's schema
- Invokes CLI commands (`sop`, `task`, `tool`) and reads their stdout/stderr
- Displays RunState progress and ClarificationRequest details to the user
- Collects Resolution input from the user and writes it as a validated JSON file
- Generates tool code when given a validated ToolBuildRequest

### What Copilot does NOT do
- Copilot does not own browser state
- Copilot does not persist runtime state
- Copilot is not required for a run already in progress to continue
- Copilot has no hidden memory that the runtime depends on — all state is in files

---

## Python Runtime

### Responsibilities
- Validates every file produced by Copilot before acting on it
- Owns the browser lifecycle (open, navigate, act, close)
- Executes all SOP steps in order according to the TaskPlan
- Manages all persistence (JSON/JSONL, atomic writes)
- Raises ClarificationRequests when execution is blocked
- Applies Resolutions and RememberedResolutions
- Records execution routes as evidence for tool generation
- Validates and registers ToolDefinitions in the catalogue

### Runtime owns browser state
The runtime is the only component that can open, navigate, or close the browser. Copilot never controls the browser directly.

---

## Key Domain Concepts

### SOP — Standard Operating Procedure
A structured description of a goal and the ordered steps required to achieve it in a web application. A SOP is the source of truth for what the system should do. It is interpreted from human-readable source (natural language, CSV, XLSX) and compiled into a machine-executable `CompiledSop`.

### Capability
A named, reusable sub-sequence of SOP steps that achieves one coherent sub-goal (e.g., "Log in", "Search for record", "Submit form"). Capabilities are the unit of reuse, tool generation, and partial success reporting.

### Tool
A generated, deterministic Python module that implements a validated capability with no runtime ambiguity. A tool is produced by Copilot from a completed execution route and registered in the catalogue. Once registered, the runtime selects the tool instead of re-executing the SOP steps, making execution faster and more reliable.

### Catalogue
The registry of all validated tools, indexed by application and capability. Stored as JSON in `SOP/tools/`. The planner consults the catalogue before building a TaskPlan to determine whether a tool can replace a capability's SOP steps.

### TaskIntent
A validated user request specifying a goal and optional inputs. TaskIntent is immutable once created. It is the contract between the user's request and the system's execution plan.

### TaskPlan
An ordered execution plan derived from a TaskIntent and a compiled SOP. The plan specifies which capabilities and steps to execute, in what order, and where branch points exist. TaskPlan is immutable once created.

### RunState
The mutable, persisted state of a single task execution. RunState is written atomically after each step transition. It records the current status, per-step progress, branch decisions, produced outputs, and any active clarification request. RunState is the single source of truth for a run's current condition.

### Clarification
A structured pause-and-ask cycle raised when execution is blocked. The runtime writes a `ClarificationRequest` (with screenshot, URL, visible candidates, failure reason) and sets the RunState to `WAITING_FOR_CLARIFICATION`. Copilot surfaces this to the user. The user provides a `Resolution`. The runtime validates and applies it, then resumes.

### Route
A recorded successful execution path through a SOP — the sequence of steps executed, URLs visited, elements interacted with, and screenshots taken. A route is stored with a SHA256 digest as evidence of validity. Routes are the input to tool generation.

### Build Request
A `ToolBuildRequest` is a validated, Copilot-addressed request to generate a tool from a route. It specifies the capability, route, required inputs, expected outputs, and postcondition evidence. Copilot reads the build request, generates code, and registers a `ToolDefinition`.

---

## Data Flow

```
User (via Copilot)
    │
    ▼
SOP source file  ──►  sop prepare  ──►  InterpretationRequest (JSON)
                                              │
                                              ▼
                                    Copilot Chat  ──►  InterpretationResult (JSON)
                                              │
                                              ▼
                                    sop compile  ──►  CompiledSop (JSON)
                                              │
                                              ▼
                           task prepare-intent  ──►  TaskIntent (JSON)
                                              │
                                              ▼
                                task plan  ──►  TaskPlan (JSON)
                                              │
                                              ▼
                               task start  ──►  RunState (JSON, atomic updates)
                                              │
                              [blocked?]  ──►  ClarificationRequest (JSON)
                                              │
                                     Copilot  ──►  Resolution (JSON)
                                              │
                              task resolve  ──►  validated + applied
                               task resume  ──►  RunState continues
                                              │
                            [completed?]  ──►  Route (JSON)
                                              │
                    tool validate-build-request  ──►  ToolBuildRequest (JSON)
                                              │
                                     Copilot  ──►  ToolDefinition + code
```

---

## Storage Layout

```
SOP/
├── inbox/              # Raw SOP source files dropped by users
├── sources/            # SopSource records (validated registrations)
├── compiled/           # CompiledSop JSON files
├── manifests/          # InterpretationRequest and InterpretationResult pairs
├── runs/               # RunState JSON files (one per run_id)
├── resolutions/        # ClarificationRequest and Resolution pairs
├── routes/             # Recorded execution routes
├── tool_build_requests/ # ToolBuildRequest JSON files
└── tools/              # ToolDefinition JSON files (the catalogue)
```

---

## Persistence Rules

- **All writes are atomic**: tempfile + `os.replace()`. No partial writes reach the live path.
- **All writes stay inside the workspace**: every path is resolved and checked with `resolve_path()`.
- **RunState is persisted after every step transition**: the system can resume from any step.
- **No in-memory-only state**: anything the runtime needs to survive a restart is in a file.

---

## Dependency Boundary

The Python runtime has no runtime dependency on:
- GitHub Copilot or any LLM API
- Any cloud service
- Any external network (execution uses a local browser against the target application)

The only network activity is the browser navigating to the target web application.

---

## Phase 0 Architecture Scope

Phase 0 establishes:
- Domain model (all models in `src/sop_automation/models/`)
- Storage foundation (atomic JSON/JSONL, path resolution, traversal guard)
- Configuration (`WorkspaceConfig` via pydantic-settings)
- CLI skeleton (all 14 commands registered; 13 are stubs returning exit code 2)
- `workspace init` — the one fully implemented command

No browser, no LLM, no Playwright, no execution engine is present in Phase 0.
