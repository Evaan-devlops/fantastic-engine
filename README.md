# SOPAutomationV2

Generic POC that operates browser-based business applications from validated SOPs.

## Phase 0 — Clean foundation and contract freeze

Phase 0 establishes the domain model, storage foundation, and CLI skeleton.
No browser automation, LLM integration, or task execution is implemented in this phase.

## Stack

- Python 3.11+
- Pydantic v2 — domain model validation
- pydantic-settings — environment configuration
- argparse — CLI (stdlib, no extra deps)
- JSON / JSONL — persistence (atomic writes)

## Install (development)

```bash
pip install -e ".[dev]"
```

## Usage

```bash
sop workspace init [--workspace PATH]
sop --help
```

## CLI commands (Phase 0 status)

| Command | Phase 0 status |
|---------|---------------|
| `workspace init` | Implemented |
| `sop prepare` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `sop validate-result` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `sop compile` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `sop list` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task prepare-intent` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task plan` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task start` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task status` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task resolve` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task resume` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `task cancel` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `tool list` | NOT_IMPLEMENTED_IN_PHASE_0 |
| `tool validate-build-request` | NOT_IMPLEMENTED_IN_PHASE_0 |

## Project structure

See `docs/ARCHITECTURE.md` for full design documentation.

## Development phases

- Phase 0: Clean foundation and contract freeze ← current
- Phase 1: Natural-language SOP authoring and compilation
- Phase 2: Task planning and foreground browser execution
- Phase 3: Clarification, remembered resolutions, resume, partial success
- Phase 4: Capability routes, tool-build requests, catalogue registration
- Phase 5: Mac installation, local fixture validation, external web-app POC
