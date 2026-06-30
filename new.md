[SOP_AUTOMATION_V2_COMPLETE_AUTONOMOUS_POC_IMPLEMENTATION]

You are operating in GitHub Copilot Agent mode inside the `SOPAutomationV2/` repository.

Your task is to implement, test, diagnose and document the complete SOP Automation V2 POC in one autonomous development session.

This prompt is the master implementation contract.

Do not stop after completing only one isolated component. Work through the ordered milestones below, run the required gates after each milestone, repair failures yourself, and continue automatically to the next milestone.

Do not ask the user to execute a sequence of commands for you.

Do not stop merely to report an intermediate test failure. Diagnose it, correct the implementation, rerun the affected tests and proceed.

Stop only when:

1. all acceptance criteria pass; or
2. a genuine external blocker prevents further implementation.

When blocked, provide the exact blocker, evidence and the smallest user action required. Do not provide another broad coding prompt.

# 1. REPOSITORY AND SCOPE RULES

Work only inside:

`SOPAutomationV2/`

Use the parent workspace only as read-only coding support.

Do not modify files outside `SOPAutomationV2/`.

Do not:

* install packages;
* commit;
* push;
* add Faststack to the product;
* access a real OneTrust tenant;
* use real credentials;
* hard-code a customer, tenant, URL, email address or DOM selector;
* redesign the repository into an unrelated architecture;
* create duplicate competing runtime, planner, locator, catalogue or workflow implementations;
* report an unexecuted test as passed.

Reuse and extend the current repository architecture.

Before implementing, inspect at least:

* existing README files;
* `pyproject.toml`;
* domain models;
* SOP interpretation and compilation services;
* task planner;
* RunManager;
* ActionDispatcher;
* LocatorService;
* browser/runtime host;
* persisted run artifacts;
* existing ToolDefinition and ToolBuildRequest models;
* existing CLI commands and stubs;
* existing tests and fixtures;
* current response reports.

Create an inventory in:

`response/complete_poc_implementation.md`

Document which existing components will be extended. Do not create a parallel architecture when an existing component can be corrected.

# 2. INITIAL USER INPUT CONTRACT

The user will place the SOP at the location documented in the README.

If the repository does not already define one canonical location, establish:

`SOP/inbox/`

The normal source may be TXT, MD or CSV if already supported.

Before coding, determine whether the following values are available from repository files:

* SOP source path;
* intended skill or business goal;
* target application ID;
* ordinary non-secret task inputs;
* capability to convert into a reusable tool.

Ask the user at most one compact set of questions and only for values that cannot safely be inferred.

Ask no more than these five fields:

```text
1. SOP source filename
2. intended goal or skill ID
3. ordinary non-secret inputs
4. capability to toolize
5. whether the browser should run headed
```

Do not ask for:

* passwords;
* tokens;
* OTPs;
* cookies;
* Run IDs;
* generated artifact filenames;
* shell environment variables.

If the user supplies no explicit toolization target, use a repository fixture capability named equivalently to:

`retrieve_production_script`

Do not toolize login, SSO, MFA or manual-authentication capabilities.

# 3. TARGET USER EXPERIENCE

The final normal operator workflow must be:

```text
Place or update the SOP in the documented folder
→ update one safe operator-input JSON when necessary
→ double-click Run_SOP_Automation.command on Mac
→ confirm the resolved task
→ browser opens
→ automation executes
→ operator completes manual SSO/MFA only when requested
→ same browser and run resume automatically
→ missing reusable tool is built through the supported generator boundary
→ candidate tool is validated and registered
→ workflow continues
→ final status and artifact path are displayed
```

The operator must not manually:

* process the SOP through several commands;
* search for an interpretation filename;
* compile the SOP separately;
* edit a generated TaskIntent;
* start the runtime host;
* keep multiple terminals open;
* submit a task separately;
* copy a Run ID;
* export environment variables;
* run status repeatedly;
* execute a separate continue command;
* manually create a ToolBuildRequest;
* manually register a generated tool;
* search several artifact files to determine the result.

Developer/debug commands may remain available, but the README must separate them from the normal operator path.

# 4. IMPLEMENTATION METHOD

Implement in the milestones below.

For each milestone:

1. write or update the implementation;
2. add focused tests;
3. run the focused tests;
4. fix all failures;
5. run relevant regression tests;
6. record exact results in `response/complete_poc_implementation.md`;
7. automatically continue to the next milestone.

Do not wait for user approval between milestones.

Do not weaken assertions merely to obtain passing tests.

Do not replace meaningful integration tests with mocks when the local fixture and Playwright can prove the real path.

# MILESTONE 0 — BASELINE AND CHANGE CONTROL

Before modifying product code:

1. record `git status --short`;
2. record the current test layout;
3. inspect existing uncommitted changes;
4. preserve valid existing work;
5. identify current failures or stubs;
6. locate existing credential-bearing artifacts and exclude them from tests.

Run a focused baseline suite when feasible.

Do not clean, revert or delete user work without evidence.

Create a milestone checklist in:

`response/complete_poc_implementation.md`

# MILESTONE 1 — GENERIC RELIABLE BROWSER RUNTIME

Implement a reliable, application-independent browser execution contract.

## 1.1 Preconditions and postconditions

Preserve the distinction:

```text
wait_condition
= pre-action readiness

postcondition
= post-action success
```

The action pipeline must be:

```text
evaluate precondition
→ resolve locator
→ verify actionability
→ execute action
→ perform private action-specific verification
→ evaluate explicit postcondition
→ mark completed
```

A visible textbox must never cause FILL to be skipped.

A visible button must never cause CLICK to be skipped.

Reconciliation may use only an explicit postcondition.

## 1.2 Locator resolution

Create or correct one generic locator resolution pipeline.

Candidate strategies may include, where applicable:

1. approved explicit locator from the compiled SOP;
2. role plus accessible name;
3. associated label;
4. exact visible text;
5. normalized visible text;
6. placeholder;
7. button semantics;
8. submit-input semantics;
9. approved `data-testid`;
10. approved SOP-provided CSS selector.

Do not:

* select `.first` from ambiguous matches;
* select hidden duplicates;
* special-case OneTrust;
* use JavaScript click as the default;
* use `force=True` as the normal route.

For every attempted candidate, retain structured non-secret evidence:

* strategy;
* description;
* match count;
* attached;
* visible;
* enabled;
* editable when applicable;
* actionable/stable;
* rejection reason.

## 1.3 Reliable action execution

For CLICK:

```text
precondition
→ locate
→ attached
→ visible
→ enabled
→ scroll into view
→ stable/actionable
→ bounded click
→ explicit postcondition
```

For FILL:

```text
precondition
→ locate
→ attached
→ visible
→ enabled
→ editable
→ fill
→ privately verify retained input value
→ explicit postcondition
```

FILL retention verification is mandatory even when another explicit postcondition exists.

Never persist either the expected or observed secret field value.

Apply explicit postconditions consistently to applicable actions, including:

* OPEN;
* CLICK;
* FILL;
* PRESS;
* SELECT;
* CHECK;
* UNCHECK;
* UPLOAD;
* DOWNLOAD;
* COPY;
* HANDLE_POPUP.

Do not silently ignore an explicitly supplied postcondition.

## 1.4 Bounded postcondition evaluation

Support generic conditions such as:

* URL equals;
* URL contains;
* URL matches approved pattern;
* element visible;
* element hidden;
* element detached/absent;
* element enabled;
* text equals;
* text contains;
* value equals;
* one of several approved page markers.

The evaluator must obey one overall declared timeout.

Do not multiply the timeout across locator strategies.

Hidden/absent evaluation must inspect all valid locator candidates. A role candidate returning zero must not produce false success when a label or placeholder candidate still matches a visible element.

## 1.5 Retry and reconciliation

Honour:

* `max_attempts`;
* `delay_seconds`;
* `retryable_error_codes`.

When `retryable_error_codes` is non-empty, retry only declared codes.

When empty, use one documented conservative default for legacy artifacts.

Do not automatically retry:

* locator ambiguity;
* invalid contracts;
* unsupported actions;
* value-resolution failure;
* authentication failure;
* browser closed.

Before retrying a potentially non-idempotent action:

```text
probe explicit postcondition once without normal polling delay
→ if satisfied, reconcile as completed
→ otherwise perform a permitted retry
```

The initial action must not wait for the full postcondition timeout before dispatch.

## 1.6 Generic authentication classification

Keep ordinary `BRANCH` generic.

Create or retain a distinct typed contract such as:

`AUTH_BRANCH`

Only `AUTH_BRANCH` may invoke authentication-page classification.

Support:

* `USERNAME_PASSWORD`;
* `PASSWORD_ONLY`;
* `SSO_REDIRECT`;
* `MANUAL_AUTH_REQUIRED`;
* `ALREADY_AUTHENTICATED`;
* `AUTHENTICATION_ERROR`;
* `UNKNOWN_PAGE`.

Remain application-independent.

Do not use a OneTrust URL, tenant, DOM ID or site-specific selector.

AUTH_BRANCH must declare compatible outcomes plus a safe default or full coverage.

Authentication error and unknown-page states must never silently complete successfully.

## 1.7 Manual authentication

Use a dedicated state such as:

`WAITING_FOR_AUTH`

or a semantically equivalent existing state.

The runtime must:

* retain the same browser;
* retain the same BrowserContext;
* retain the same page;
* retain the same Run ID;
* display a clear instruction;
* accept one simple operator confirmation;
* reconcile current state;
* resume automatically;
* avoid repeating completed email FILL or continuation CLICK actions.

`wait_condition` may confirm that the manual-auth page is ready.

`postcondition` must confirm that authentication was completed.

## 1.8 Secret-safe persistence

Create one canonical recursive sanitizer.

The runtime may retain complete values in memory for execution.

Persisted artifacts must never contain literal secrets.

Protect at least:

* `task_plan.json`;
* `run_state.json`;
* `events.jsonl`;
* clarification artifacts;
* route artifacts;
* diagnostics;
* postcondition signals;
* tool-build requests;
* generated-tool metadata;
* exception text.

Detect secret contexts including:

* password;
* passwd;
* credential;
* secret;
* token;
* OTP;
* cookie;
* authorization;
* API key;
* credential-like FILL element names.

Use fake values only in tests, such as:

* `test-user@example.invalid`;
* `fake-password-for-test-only`.

## 1.9 Diagnostics

Use typed failure categories such as:

* `LOCATOR_NOT_FOUND`;
* `LOCATOR_AMBIGUOUS`;
* `ELEMENT_DETACHED`;
* `ELEMENT_NOT_VISIBLE`;
* `ELEMENT_NOT_ENABLED`;
* `ELEMENT_NOT_EDITABLE`;
* `ELEMENT_NOT_ACTIONABLE`;
* `CLICK_INTERCEPTED`;
* `ACTION_TIMEOUT`;
* `NAVIGATION_TIMEOUT`;
* `POSTCONDITION_NOT_MET`;
* `BRANCH_NOT_RECOGNIZED`;
* `AUTHENTICATION_ERROR`;
* `BROWSER_CLOSED`;
* `RUNTIME_ERROR`.

Prefer typed exceptions/results over substring-only classification.

Operator-facing output must be understandable and concise.

Technical evidence belongs in artifacts.

## 1.10 Milestone 1 tests

Create route-level local Playwright fixtures covering:

1. identity/email page;
2. continuation button initially disabled;
3. enabled after input or blur validation;
4. role-based discovery;
5. submit-input discovery;
6. delayed identity-provider rendering;
7. URL transition before DOM transition;
8. DOM transition before URL update;
9. username/password branch;
10. password-only branch;
11. SSO redirect;
12. manual-auth checkpoint;
13. already authenticated;
14. authentication error;
15. unknown page;
16. ambiguous button;
17. temporarily intercepted/non-actionable click;
18. postcondition failure;
19. delayed-transition reconciliation;
20. resume without repeating identity FILL;
21. resume without repeating continuation CLICK;
22. same page and BrowserContext retained.

At least one full test must execute:

```text
RunManager
→ ActionDispatcher
→ LocatorService
→ Playwright
```

and reach terminal authenticated success.

Do not accept a test that stops merely when a password field appears.

Run the Milestone 1 focused tests and all applicable regressions before continuing.

# MILESTONE 2 — ONE-CLICK OPERATOR WORKFLOW

Implement a checkpointed Python orchestration layer using existing services.

Use a service such as:

* `OperatorSession`;
* `WorkflowOrchestrator`;
* or a clean combination without duplicate responsibility.

## 2.1 Safe input contract

Create:

`SOP/operator_input.json`

or an existing repository-approved equivalent.

It may include:

```json
{
  "sop_source": "SOP/inbox/example_sop.txt",
  "sop_id": "example_sop",
  "goal": "retrieve_data_domain_script",
  "application_id": "example_application",
  "toolize_capability_id": "retrieve_production_script",
  "headed": true,
  "inputs": {
    "target_website_url": "abc.com",
    "email_address": ""
  }
}
```

Never store:

* password;
* OTP;
* token;
* cookie;
* session value.

Collect missing ordinary values interactively.

Use manual-auth handling for credentials that are not securely supplied.

Display the resolved task and request one confirmation.

## 2.2 Workflow state

Persist state under:

`SOP/workflows/<workflow_id>/state.json`

Include:

* workflow ID;
* status;
* exact config path;
* SOP ID;
* goal;
* exact artifact paths;
* first Run ID;
* route ID;
* build-request ID;
* registered tool ID/version;
* second Run ID;
* timestamps;
* current checkpoint;
* safe error data;
* required user action.

Never locate artifacts by “newest file”.

Store exact paths in state.

## 2.3 Automated lifecycle

The orchestrator must automatically perform deterministic stages:

```text
load operator input
→ initialize workspace
→ prepare SOP
→ create interpretation request when required
→ validate interpretation result
→ compile SOP
→ validate compiled SOP
→ create deterministic TaskIntent
→ validate intent
→ run preflight
→ start runtime host
→ wait for readiness
→ submit task
→ retain Run ID internally
→ stream progress
→ handle manual authentication
→ stop runtime cleanly
→ show final summary
```

Call Python services directly where practical.

Do not implement the product workflow as a chain of its own CLI subprocesses.

The workflow must be idempotent.

Rerunning or resuming must not:

* duplicate compiled artifacts;
* create duplicate TaskIntents;
* resubmit completed runs;
* register the same tool twice.

## 2.4 Copilot handoff checkpoints

When an interpretation result or generated tool requires Copilot:

Create exactly one job file:

`SOP/workflows/<workflow_id>/copilot_job.md`

Include:

* authoritative files to read;
* expected output path;
* exact schema;
* prohibited modifications;
* validation requirements.

Persist the expected output path in workflow state.

Use explicit statuses such as:

* `WAITING_FOR_COPILOT_SOP`;
* `WAITING_FOR_COPILOT_TOOL`.

When resumed, inspect that exact expected path.

Do not search by modification time.

Do not pretend Copilot generation succeeded when no candidate exists.

## 2.5 Mac launcher

Create a thin root-level launcher:

`Run_SOP_Automation.command`

It must:

* resolve the repository root from its own location;
* use `.venv/bin/python`;
* not depend on the current working directory;
* print a clear missing-venv message;
* preserve the Python process exit code;
* support Finder double-click and terminal execution;
* keep the window open long enough to read the result when double-clicked;
* contain no business logic;
* contain no secrets.

The Python entrypoint should be equivalent to:

```text
python -m sop_automation operator run
```

Ensure executable permission is represented appropriately for the Mac transfer.

## 2.6 Operator output

Normal output should resemble:

```text
SOP Automation starting
Task: Retrieve production script
Target: abc.com

✓ Input validated
✓ SOP prepared
✓ SOP compiled
✓ Runtime started
✓ Browser opened
✓ Authentication completed
✓ Capability completed
✓ Route recorded
✓ Tool request prepared
✓ Tool registered
✓ Second run reused the tool

Task completed
First run: <id>
Second run: <id>
Artifacts: <path>
```

Failure output should identify:

* stopped step;
* typed reason;
* evidence path;
* one clear next action.

Do not expose a raw stack trace as the primary operator response.

## 2.7 Milestone 2 tests

Test:

* input loading;
* interactive collection of missing safe values;
* deterministic TaskIntent creation;
* workflow checkpoints;
* exact artifact-path reuse;
* idempotent resume;
* runtime host lifecycle;
* internal Run ID handling;
* manual-auth continuation;
* safe interruption;
* cleanup;
* final summary;
* launcher path resolution where testable.

Run all Milestone 2 tests and regressions before continuing.

# MILESTONE 3 — SKILL REGISTRY AND TOOL CATALOGUE

Keep these separate.

The architecture must remain:

```text
Agent/Planner
→ Skill Registry
→ selected Skill
→ required Capabilities
→ Tool Catalogue
→ validated executable Tool
```

## 3.1 Skill Registry

The Skill Registry answers:

```text
Which reusable business workflow matches this intent?
```

Use a lightweight repository file plus typed loader and validator.

Metadata should include:

* skill ID;
* name;
* description;
* supported intents/goals;
* SOP/skill location;
* required inputs;
* required capabilities;
* version;
* enabled state.

Register a fixture skill equivalent to:

`retrieve_data_domain_script`

Do not duplicate full SOP instructions into registry metadata.

The planner must select the skill through the registry, not scattered hard-coded intent checks.

## 3.2 Tool Catalogue

The Tool Catalogue answers:

```text
Which validated executable implementation provides this capability?
```

Use existing ToolDefinition models where possible.

Catalogue metadata should include:

* tool ID;
* version;
* application ID;
* capabilities provided;
* Python entrypoint;
* input schema;
* output schema;
* enabled state;
* validation state;
* generated/source status;
* registration timestamp;
* build identity/fingerprint;
* source route ID;
* source build-request ID.

The catalogue must:

* load only registered packages;
* ignore malformed/unregistered packages safely;
* match application and capability;
* verify compatible inputs/outputs;
* require active/validated status;
* perform deterministic version selection;
* report controlled ambiguity;
* never import arbitrary unregistered Python files.

## 3.3 Real CLI commands

Replace stubs with real commands for at least:

```text
tool list
tool validate-build-request
tool register
```

`tool list` must display:

* tool ID;
* version;
* application;
* capability;
* status;
* source route/build request.

Run Milestone 3 tests and regressions before continuing.

# MILESTONE 4 — SUCCESSFUL ROUTE TO AUTOMATIC TOOL BUILD

This is the core POC lifecycle.

## 4.1 Normal cold-start lifecycle

Implement:

```text
skill selected
→ capability required
→ catalogue checked
→ no compatible tool
→ capability executes through compiled SOP steps
→ capability succeeds
→ sanitized successful route is recorded
→ ToolBuildRequest is created
→ generator boundary is invoked
→ candidate tool is validated
→ candidate is registered atomically
→ catalogue refreshes
```

The next execution must:

```text
same skill/capability requested
→ catalogue finds registered tool
→ planner selects it
→ runtime invokes it
→ raw capability steps are not selected
→ declared output is returned
```

## 4.2 Exceptional unsupported-capability lifecycle

Keep this separate:

```text
raw capability cannot execute because the runtime does not support the action
→ create deferred ToolBuildRequest from capability/SOP contract
→ do not claim a successful route
```

Do not confuse a deferred contract-derived build request with a successful-route build request.

## 4.3 Successful route artifact

Persist under a structure equivalent to:

`SOP/routes/<application_id>/<capability_id>/<route_id>.json`

Include:

* route ID;
* application ID;
* capability ID;
* skill ID;
* SOP ID/version/hash;
* ordered successful steps;
* actions;
* normalized non-secret element descriptions;
* preconditions;
* postconditions;
* actual branch path;
* declared input names;
* declared output names;
* evidence references;
* timestamps.

Do not include:

* passwords;
* usernames classified as secret;
* tokens;
* OTPs;
* cookies;
* raw storage state;
* secret FILL values.

Use declared input placeholders in place of values.

## 4.4 ToolBuildRequest

Persist under:

`SOP/tool_build_requests/<request_id>/tool_build_request.json`

Include:

* request ID;
* application ID;
* skill ID;
* capability ID;
* capability description;
* source route ID, when available;
* SOP step references;
* input schema;
* output schema;
* success contract;
* failure contract;
* evidence requirements;
* allowed runtime interfaces;
* allowed dependencies;
* prohibited behaviour;
* target package path;
* required entrypoint;
* focused test requirements;
* hashes;
* timestamp.

Never include runtime credentials.

## 4.5 Generator adapter

Define a production generator interface.

Support:

* currently available GitHub Copilot CLI integration if it already exists and is reliable; or
* a resumable Copilot job-file handoff.

For automated tests, provide a deterministic fake generator adapter that creates a synthetic candidate package.

The fake adapter is test-only proof.

Do not represent it as live production generation.

When the live generator is unavailable:

```text
persist ToolBuildRequest
→ persist WAITING_FOR_COPILOT_TOOL
→ write exact copilot_job.md
→ exit or pause safely
→ resume when exact candidate path exists
```

## 4.6 Generated tool package

Use a structure equivalent to:

```text
SOP/tools/<tool_id>/<version>/
    tool_definition.json
    implementation.py
    tests/
    build_result.json
```

Expose one controlled async entrypoint, such as:

```python
async def execute(context, inputs) -> ToolExecutionResult:
    ...
```

The context must be narrow.

Do not expose arbitrary repository services, shell access or unrestricted imports.

## 4.7 Validation and registration

Before registration, verify:

* path is within the approved tool root;
* no path traversal;
* definition schema is valid;
* Python imports;
* required entrypoint exists;
* entrypoint shape is correct;
* declared capability matches;
* input schema is compatible;
* output schema is compatible;
* no forbidden imports;
* no subprocess/shell behaviour;
* no hard-coded credentials;
* bounded execution;
* structured result;
* focused tests pass;
* hashes/fingerprint are generated.

Registration must be atomic.

A failed candidate must not appear as active in the catalogue.

Preserve rejected candidates and validation reports for diagnosis.

## 4.8 Planner selection

Before expanding a tool-eligible capability into raw SOP steps:

```text
query Tool Catalogue
→ one compatible validated tool: create tool-backed plan
→ no tool: use raw compiled SOP steps
→ controlled ambiguity: safe failure or explicit resolution
```

Persist evidence:

* `TOOL_CATALOGUE_CHECKED`;
* `TOOL_SELECTED`;
* `TOOL_NOT_FOUND`;
* selected tool ID/version;
* fallback reason.

## 4.9 Controlled tool invocation

The runtime must:

* load only the selected registered entrypoint;
* pass only declared inputs;
* provide a narrow runtime/browser context;
* capture only declared outputs;
* enforce timeout;
* translate failures into typed runtime results;
* never persist secret values;
* not silently replay raw steps after partial tool execution unless an explicit safe policy permits it.

Persist:

* `TOOL_EXECUTION_STARTED`;
* `TOOL_EXECUTION_COMPLETED`;
* `TOOL_EXECUTION_FAILED`.

Run Milestone 4 tests and regressions before continuing.

# MILESTONE 5 — FULL END-TO-END LEARNING AND REUSE PROOF

Build one deterministic local fixture proof.

## First run

Assert:

```text
skill selected
→ capability required
→ catalogue checked
→ no tool found
→ raw compiled capability steps execute through real runtime
→ capability succeeds
→ sanitized route artifact exists
→ ToolBuildRequest exists
```

## Generator boundary

Use the deterministic test generator adapter to create a candidate.

Assert:

* candidate package exists;
* candidate validates;
* focused candidate tests pass;
* registration is atomic;
* catalogue lists it.

## Second run

Request the same skill and capability.

Assert:

```text
catalogue checked
→ registered tool selected
→ runtime invokes tool
→ raw capability steps are not selected
→ output is returned
→ terminal success
```

Evidence must prove the difference between first and second runs.

Required evidence includes:

* first Run ID;
* route ID;
* build-request ID;
* registered tool ID/version;
* second Run ID;
* first-run `TOOL_NOT_FOUND`;
* second-run `TOOL_SELECTED`;
* second-run tool execution events;
* raw step counter remains zero during the toolized capability on the second run.

## Workflow integration

Run the same proof through the operator/workflow orchestrator, not only isolated services.

The workflow state must end with:

* first Run ID;
* route ID;
* build-request ID;
* registered tool;
* second Run ID;
* final completed status;
* proof of registered-tool reuse.

# MILESTONE 6 — DOCUMENTATION AND NORMAL EXECUTION

Update README and Mac instructions.

The normal operator section must contain only:

```text
1. Place the SOP in the documented SOP input folder.
2. Update SOP/operator_input.json when ordinary task inputs change.
3. Double-click Run_SOP_Automation.command.
4. Complete manual authentication when prompted.
5. Read the final result shown by the launcher.
```

Move all developer/debug commands to a separate section.

Document:

* supported SOP formats;
* safe input policy;
* manual-auth behaviour;
* workflow checkpoints;
* Copilot-generation handoff;
* Skill Registry versus Tool Catalogue;
* route artifact;
* ToolBuildRequest;
* generated-tool validation;
* first-run versus second-run behaviour;
* limitations.

# 5. TEST EXECUTION CONTRACT

Use the existing environment.

Do not install packages.

Run focused tests after each milestone.

At final verification run:

```powershell
$env:PYTHONPATH='src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'

pytest -q -m "not playwright"
pytest -q -m playwright
python -m compileall -q src tests
git diff --check
```

Also run any repository-specific test command documented by the project.

If a test hangs:

1. identify the exact test with verbose bounded execution;
2. diagnose whether it is related to the changes;
3. fix related hangs;
4. report unrelated pre-existing hangs honestly;
5. do not describe a timed-out suite as passed.

If Playwright Chromium is unavailable:

* state `NOT EXECUTED`;
* do not claim success;
* continue implementing non-browser areas;
* provide the exact browser verification still required on Mac.

# 6. HARD ACCEPTANCE CRITERIA

The implementation is complete only when all applicable criteria below are proven.

## Runtime

1. Preconditions and postconditions are separate.
2. FILL is not skipped because a field is visible.
3. FILL retention is always verified privately.
4. CLICK completion is postcondition-driven.
5. Reconciliation is non-blocking.
6. Retried non-idempotent actions reconcile before repetition.
7. Declared retry error codes are honoured.
8. Postcondition timeout is bounded.
9. Ordinary BRANCH remains generic.
10. AUTH_BRANCH safely handles all supported states.
11. Authentication error and unknown page do not silently complete.
12. Manual authentication retains the same browser, page and run.
13. Completed identity and continuation actions are not repeated.
14. Persisted artifacts contain no literal test password.
15. Diagnostics are typed and useful.
16. No OneTrust-specific production logic exists.

## Operator workflow

17. One safe config starts the workflow.
18. TaskIntent is deterministic.
19. Exact artifact paths are persisted.
20. Resume is idempotent.
21. Runtime host is managed internally.
22. Run ID is managed internally.
23. Manual authentication resumes automatically.
24. One Mac launcher controls the normal flow.
25. Normal documentation does not require a command sequence.

## Skills and tools

26. Skill Registry exists.
27. Tool Catalogue remains separate.
28. Capability links skill and tool.
29. `tool list` is real.
30. Build-request validation is real.
31. Successful route is sanitized and persisted.
32. ToolBuildRequest is generated.
33. Generator adapter boundary exists.
34. Candidate tool validation rejects unsafe packages.
35. Registration is atomic.
36. Planner selects a matching registered tool.
37. Runtime invokes only registered tools.
38. Second run reuses the tool without regeneration.
39. Evidence proves raw steps were not selected for the toolized capability.

## Testing

40. Complete local authentication fixture route passes.
41. Operator workflow tests pass.
42. Skill and catalogue tests pass.
43. First-run and second-run reuse test passes.
44. Secret scans pass.
45. All executable non-Playwright tests pass.
46. All executable Playwright tests pass.
47. Compilation passes.
48. Diff check passes.
49. No real credentials are introduced.
50. No changes are made outside the product repository.

# 7. FINAL REPORT

Complete:

`response/complete_poc_implementation.md`

Include:

1. baseline inventory;
2. architecture reused;
3. milestone-by-milestone implementation;
4. files added;
5. files changed;
6. runtime contract;
7. authentication route proof;
8. secret-persistence scan;
9. OperatorSession/workflow design;
10. launcher behaviour;
11. Skill Registry design;
12. Tool Catalogue design;
13. route artifact example;
14. ToolBuildRequest example;
15. generated-tool validation;
16. first-run evidence;
17. registration evidence;
18. second-run tool-reuse evidence;
19. focused test results by milestone;
20. full non-Playwright results;
21. full Playwright results;
22. compile and diff-check results;
23. known verified limitations;
24. exact files to transfer to Mac;
25. minimal Mac verification steps.

Do not claim the live OneTrust site was tested.

Do not claim fake-generator execution is live Copilot generation.

At the end provide exactly one of:

`COMPLETE LOCAL POC IMPLEMENTATION PASSED — READY FOR MAC VERIFICATION`

or:

`COMPLETE LOCAL POC IMPLEMENTATION BLOCKED — <exact blocker>`

After the status line, include only this normal operator instruction:

`Double-click Run_SOP_Automation.command.`
