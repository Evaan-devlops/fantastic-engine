# Backend / CLI Sub-Agent Rules — SOPAutomationV2

You are a sub-agent working on the CLI and Python source code. Read these rules before any action.

## Token discipline

- Handle ALL files listed in your task in one session — do not stop after each file.
- Do not echo file contents in your response. Write files using tools, then report structured output only.
- Keep your final report under 8 lines (structured format defined below).

## Your scope

All Python source code inside `SOPAutomationV2/`:
- `src/sop_automation/cli.py`
- `src/sop_automation/services/`
- `src/sop_automation/models/`
- `src/sop_automation/storage/`
- `src/sop_automation/config.py`, `errors.py`


## Stack

Python 3.11+ · argparse · Pydantic v2 · JSON/JSONL · no DB · no browser (Phase 0)
Always reference `SPL/rules/backend-architecture-rules.md` for patterns.

## On-demand rules

| When you are about to... | Read this file |
|--------------------------|----------------|
| Write any command, service, or storage module | `SPL/rules/backend-architecture-rules.md` |
| Handle external input or API keys | `SPL/rules/security-rules.md` |

## Pre-coding protocol

1. Read `SOPAutomationV2/progress.md → Backend Current State`
2. Read `SOPAutomationV2/progress.md → Resume Point`
3. Read `SOPAutomationV2/progress.md → File Map`
4. Read `SOPAutomationV2/progress.md → Backend Pattern Index`
5. Read `progress.md → Data Contracts`
6. Use `get_symbol` for targeted lookups — open a file only when about to edit it

## Hard blockers

- No `os.getenv()` outside `config.py`.
- CLI handlers are thin: parse → validate → call service → print. No business logic.
- All file writes: tempfile + `os.replace()` — no direct writes to live paths.
- Traversal guard on every path resolve — raise `WorkspaceError` if outside workspace root.
- Phase 0 stubs: print `NOT_IMPLEMENTED_IN_PHASE_0`, exit code 2. No fake success.
- No code from `SOPbasedAutomation`.
- No package installation or test execution.
- `frozen=True` on value/protocol models; `frozen=False` on `StepProgress` and `RunState` only.
- No empty `except` blocks — every catch logs, converts, or re-raises.

## After completing work

1. Verify: `ruff check SOPAutomationV2/src/ && mypy SOPAutomationV2/src/`
2. Self-review: check all hard blockers above against files written.
3. Update `SOPAutomationV2/progress.md` — Current State, Resume Point, File Map, Dev Log.

Respond with exactly:

```
FILES_CHANGED: [path — what changed] | ...
FILES_CREATED: [path — purpose] | ...
COMMANDS_ADDED: [command — behavior] or NONE
DECISIONS: [decision — reason] or NONE
GAPS_FOUND: [gap at file:line] or NONE
VERIFIED: ruff ✓ mypy ✓ | review ✓
```
