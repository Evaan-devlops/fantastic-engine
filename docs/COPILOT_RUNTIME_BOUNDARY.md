# Copilot–Runtime Boundary

## Purpose

This document states the exact responsibilities of GitHub Copilot Chat and the Python runtime so there is no ambiguity about who owns what. Violations of this boundary are bugs, not design choices.

---

## Copilot Responsibilities

Copilot Chat is responsible for:

1. **Writing strict JSON request/result files** — Copilot produces `InterpretationResult`, `Resolution`, and tool code files. Each file must conform exactly to the schema the runtime will validate against.
2. **Invoking CLI commands** — Copilot invokes `sop`, `task`, and `tool` commands and reads their stdout and exit codes.
3. **Displaying status to the user** — Copilot reads `RunState` and `ClarificationRequest` files and presents their content to the user in a human-readable form.
4. **Collecting user input** — Copilot asks the user for goals, inputs, and resolution decisions, then encodes the user's response into the appropriate JSON file.
5. **Generating tool code** — When given a validated `ToolBuildRequest`, Copilot generates a Python module and writes it to the target path specified in the request.

---

## Python Runtime Responsibilities

The Python runtime is responsible for:

1. **Validating every Copilot-produced file** — before acting on any JSON file written by Copilot, the runtime validates it against the Pydantic model. Invalid files are rejected with a clear error message.
2. **Owning browser state and execution** — the runtime is the only component that opens, navigates, acts in, or closes the browser. Copilot never controls the browser.
3. **Managing all persistence** — all RunState, ClarificationRequest, Route, and ToolDefinition files are written atomically by the runtime. Copilot writes only its own output files (results, resolutions, tool code).
4. **Enforcing traversal safety** — every path the runtime resolves is checked to be inside the workspace root.
5. **Executing SOP steps** — the runtime runs each step, applies retry policy, and raises clarification when needed.

---

## The Filesystem Is the Contract

Python does not rely on Copilot's hidden memory or conversation history. Every piece of information the runtime needs is in a file:

- The compiled SOP → `SOP/compiled/<sop_id>.json`
- The task plan → `SOP/runs/<task_id>/plan.json`
- The run state → `SOP/runs/<run_id>/state.json`
- The clarification request → `SOP/resolutions/<request_id>/request.json`
- The resolution → `SOP/resolutions/<request_id>/resolution.json`
- The route → `SOP/routes/<route_id>.json`
- The build request → `SOP/tool_build_requests/<request_id>.json`
- The tool definition → `SOP/tools/<tool_id>.json`

If a file is missing or invalid, the runtime fails fast with a clear error. It never assumes Copilot remembers something.

---

## No Direct Copilot API Dependency

The Python runtime does not call any Copilot or LLM API. The integration boundary is:

- **Input to runtime**: files in the SOP workspace + CLI arguments
- **Output from runtime**: files in the SOP workspace + stdout/stderr + exit codes

This means:
- The runtime can run in a CI pipeline with no Copilot access
- Copilot can be replaced by any other agent or human that produces valid JSON files
- The runtime can continue a run already in progress with no Copilot interaction at all

---

## Autonomy After Validated Artifacts

Once the following artifacts are persisted and validated, the runtime can continue without any further Copilot interaction:

| Artifact | Runtime can continue from... |
|----------|------------------------------|
| `TaskIntent` | Plan and start a task run |
| `CompiledSop` | Build a TaskPlan and execute |
| `Resolution` | Resume a paused run |
| `ToolDefinition` | Select tool at plan time |

Copilot is required again only when:
- A new SOP needs to be interpreted (Phase 1+)
- A `ClarificationRequest` needs to be presented to the user and a `Resolution` collected
- A `ToolBuildRequest` needs a new tool generated

---

## Copilot Must Not Be Required for Run Continuation

A run that is `WAITING_FOR_CLARIFICATION` can be resumed by any agent or human that writes a valid `Resolution` JSON file and calls `task resolve` + `task resume`. Copilot is the typical agent that does this, but it is not architecturally required.

This rule ensures that:
- Automated testing can simulate resolutions without Copilot
- Runs can be resumed from a script or CI system
- The system is testable end-to-end without any LLM dependency
