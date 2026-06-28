# Product Requirements Document — SOPAutomationV2

## Overview

SOPAutomationV2 is a generic POC system that operates browser-based business applications by following validated Standard Operating Procedures (SOPs). The system bridges the gap between written human process knowledge and reliable automated execution.

## Target Users

Operations staff and business users at companies that use web-based business applications. These users know their processes but want to automate repetitive browser tasks without writing code or engaging engineering teams.

## User Stories

### Goal 1 — Register a SOP
As an operations user, I want to register a SOP (written in natural language, CSV, or XLSX) so that the system can interpret and compile it into an executable form.

**Acceptance criteria:**
- User can place a SOP file in `SOP/inbox/` and invoke `sop prepare`
- System detects format (natural language, CSV, XLSX) and creates an InterpretationRequest
- GitHub Copilot Chat interprets the request and writes an InterpretationResult JSON file
- System validates the result and stores a SopSource record

### Goal 2 — Compile a SOP
As an operations user, I want to compile a validated SOP interpretation into a structured, executable SOP so that the runtime can plan and execute tasks from it.

**Acceptance criteria:**
- User invokes `sop compile <source_id>`
- System validates the InterpretationResult, resolves capabilities and steps, and writes a CompiledSop JSON
- Compiled SOP SHA256 is stored and verified on load
- Duplicate or changed sources produce a new version

### Goal 3 — Execute a task
As an operations user, I want to start a task run from a compiled SOP and goal so that the system executes the steps in a real browser and reports results.

**Acceptance criteria:**
- User invokes `task prepare-intent` with a natural-language goal and optional inputs
- System builds a TaskPlan from the compiled SOP and persists it
- User invokes `task start <task_id>`
- System opens a browser, executes each step, and writes live RunState updates
- User can check progress with `task status <run_id>`

### Goal 4 — Resolve a clarification
As an operations user, I want to be notified when execution is blocked and provide a resolution so that the run can continue.

**Acceptance criteria:**
- When a step fails (element not found, timeout, unexpected state), the runtime writes a ClarificationRequest with screenshot, current URL, visible alternatives, and failure reason
- GitHub Copilot Chat surfaces the request to the user and collects a Resolution
- User invokes `task resolve <resolution_file>`
- Runtime validates the resolution and resumes the run with `task resume <run_id>`

### Goal 5 — Reuse a remembered resolution
As an operations user, I want the system to remember verified resolutions so that future runs do not block on the same issue.

**Acceptance criteria:**
- When a Resolution is marked `reusable: true` and applied successfully, a RememberedResolution is stored
- On subsequent runs, the runtime checks for a matching RememberedResolution before raising a new ClarificationRequest
- The `success_count` and `last_verified_at` are updated each time a remembered resolution is applied

### Goal 6 — Request a capability tool
As an operations user, I want the system to generate a deterministic tool for a capability that has been proven to work so that future runs execute that capability faster and more reliably.

**Acceptance criteria:**
- After a successful run, the runtime records the execution route with SHA256 evidence
- User (or Copilot) invokes `tool validate-build-request` to generate a ToolBuildRequest
- Copilot generates the tool code and registers a ToolDefinition in the catalogue
- On next run, the planner selects the registered tool instead of re-executing the SOP steps

### Goal 7 — List SOPs and tools
As an operations user, I want to list all compiled SOPs and registered tools so that I know what capabilities are available.

**Acceptance criteria:**
- `sop list` lists all compiled SOPs with their ID, version, goals, and creation date
- `tool list` lists all registered tools with their ID, application, capability, version, and health status

## Supported SOP Source Formats

| Format | Description |
|--------|-------------|
| NATURAL_LANGUAGE | Plain text or Markdown describing steps in prose |
| CSV | Tabular SOP with columns for step, action, element, value |
| XLSX | Spreadsheet SOP, same structure as CSV |
| BROWSER_OBSERVATION | Recorded browser session (Phase 5+) |

## Supported Browser Actions

All `ActionType` values are supported except iframe interaction and complex dynamic table handling:

| Action | Description |
|--------|-------------|
| OPEN | Navigate to a URL |
| CLICK | Click a button, link, or interactive element |
| FILL | Type text into a textbox or textarea |
| PRESS | Press a keyboard key (Enter, Tab, Escape, etc.) |
| SELECT | Choose an option from a dropdown |
| CHECK | Check a checkbox |
| UNCHECK | Uncheck a checkbox |
| UPLOAD | Upload a file via a file input |
| DOWNLOAD | Download a file and record its path |
| COPY | Copy a value from a page element to a variable |
| WAIT | Wait for a condition or fixed duration |
| VERIFY | Assert a condition on the page |
| HANDLE_POPUP | Dismiss or accept a browser dialog or modal |
| MANUAL_AUTH | Pause for the user to complete authentication |
| BRANCH | Branch based on a runtime condition |
| END_SUCCESS | Mark the run as successfully completed |
| END_FAILURE | Mark the run as failed with a reason |
| DEFERRED | Placeholder for a capability not yet implemented |

## Authentication Flow

Authentication is always manual in Phase 0–3. When a `MANUAL_AUTH` step is reached:
1. The runtime pauses the run and sets `status = WAITING_FOR_AUTH`
2. The user completes authentication in the open browser window
3. The user invokes `task resume <run_id>` to continue
4. The runtime verifies the authenticated state before proceeding

No credentials are stored by the runtime. The runtime never reads or writes passwords.

## Readiness Definition

A page is considered ready when:
1. The browser reports full page load (`load` event fired or `networkidle` condition met)
2. All SOP-defined wait conditions for the step are satisfied (e.g., element visible, text matches)

Timeout defaults are defined in the compiled SOP's `RetryPolicy`. Default timeout: implementation-defined per phase.

## Retry Policy

For each step:
1. On first failure: retry once (max_attempts=2 default)
2. If retryable_error_codes is non-empty, only retry for matching error codes
3. If the retry also fails: raise a `ClarificationRequest`

Only errors listed in `retryable_error_codes` are automatically retried. All other errors go immediately to clarification.

## Clarification Evidence

Every `ClarificationRequest` must include:
- `screenshot_path`: path to a screenshot taken at the moment of failure
- `current_url`: the page URL at failure
- `visible_candidates`: list of visible element labels that could be alternatives
- `failure_reason`: human-readable description of why the step failed
- `suggested_options`: optional list of suggested resolutions

## Remembered Resolutions and Automatic Reuse

A `RememberedResolution` is stored when:
- A `Resolution` is marked `reusable: true`
- The resolution is applied and the run continues successfully past the blocked step

On subsequent runs, before raising a `ClarificationRequest`, the runtime:
1. Computes a `page_signature` (URL pattern + step context)
2. Looks up a matching `RememberedResolution`
3. If found: applies the remembered resolution automatically and logs the reuse
4. If not found: raises a new `ClarificationRequest`

## Live Progress Display

During a run, the runtime writes `RunState` atomically after each step transition. The `task status` command reads the current `RunState` and displays:
- Overall run status
- Current capability and step being executed
- Per-step status summary (PENDING / RUNNING / COMPLETED / FAILED / SKIPPED)
- Any active clarification request ID

## Multi-Website Workflows

A single SOP may include steps targeting multiple web applications. Each `SopStep` has an `application_id` field. The runtime:
- Tracks the current browser context per application
- Opens new tabs or reuses existing ones as directed by the SOP
- Validates that each step's `application_id` matches the current page context before acting

## Partial Success

When a run encounters an unrecoverable failure after some capabilities have completed:
- The run status is set to `PARTIAL_SUCCESS` rather than `FAILED`
- The `produced_outputs` dict contains results from completed capabilities
- A per-capability ToolBuildRequest may still be generated for the completed portion

## Per-Capability Tool Requests

A `ToolBuildRequest` can be generated for any capability that completed successfully in a run, regardless of whether the overall run succeeded. This allows incremental automation of individual capabilities.

## GitHub Copilot Chat as User Entry Point (Phase 1+)

From Phase 1 onward, GitHub Copilot Chat is the primary user interface:
- Users describe their goal in natural language to Copilot
- Copilot invokes CLI commands and interprets their output
- Copilot writes JSON request files for the Python runtime to process
- Copilot displays RunState progress and ClarificationRequests to the user
- Copilot collects Resolution input from the user and writes it as a JSON file

The Python runtime never calls the Copilot API directly. The boundary is the filesystem and CLI.

## Generic Design

The system is designed for any web-based business application. No application names, URLs, selectors, or field names are hardcoded in the Python runtime. All application-specific knowledge lives in SOPs and compiled artifacts. OneTrust is mentioned only as a future Phase 5 external POC test case.
