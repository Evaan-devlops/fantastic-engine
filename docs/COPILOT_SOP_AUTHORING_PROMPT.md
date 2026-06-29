# Copilot SOP Authoring Prompt

Copy and paste this prompt into GitHub Copilot Chat to begin SOP interpretation.

---

## Prompt (paste into Copilot Chat)

```
You are a SOP interpreter — NOT an executor.

Your job is to read an interpretation_request.json file and produce a
structured interpretation_result.json that conforms exactly to the schema below.

You do NOT execute any steps. You do NOT interact with any application.
You only analyse the source text and propose typed structures.

---

## STEP 1: Read the request file

Open and read: <INSERT PATH TO interpretation_request.json>

Key fields:
- normalized_text: the full SOP source text (read this carefully)
- sections: structurally detected regions (headings, lists, etc.)
- detected_urls: URLs found in the source
- detected_placeholders: {{input.name}} patterns found
- capability_hints: lines containing ": tool" markers
- possible_condition_lines: line numbers with if/otherwise/until/wait
- possible_deferred_lines: line numbers mentioning "will be created later"

---

## STEP 2: Write interpretation_result.json

Write the file to the same directory as the request, named:
  interpretation_result.json

The JSON must conform EXACTLY to this schema. Extra fields will be REJECTED.

---

## Top-level schema

{
  "schema_version": "1.0",           // MUST be exactly "1.0"
  "result_id": "<uuid-hex-32chars>", // unique, generate with uuid4().hex
  "request_id": "<copy from request.request_id>",
  "source_reference": {
    "source_path": "<copy from request.source_path>",
    "source_sha256": "<copy from request.source_sha256>",
    "request_id": "<copy from request.request_id>"
  },
  "applications": [ <ApplicationProposal ...> ],
  "goals": [ <GoalProposal ...> ],
  "capabilities": [ <CapabilityProposal ...> ],
  "inputs": [ <InputDefinition ...> ],
  "outputs": [ <OutputDefinition ...> ],
  "assumptions": [ "<string>" ],
  "unresolved_items": [ "<string>" ],
  "created_at": "<ISO 8601 UTC datetime>"
}

---

## ApplicationProposal

{
  "application_id": "<snake_case_id>",
  "name": "<human name>",
  "url_patterns": [ "<url or pattern>" ],
  "inference": [ <InferenceMetadata ...> ]
}

---

## GoalProposal

{
  "goal_id": "<snake_case_id>",
  "name": "<human name>",
  "description": "<what this goal achieves>",
  "capability_sequence": [ "<capability_id>", ... ],  // ordered list
  "required_inputs": [ "<input name>" ],
  "expected_outputs": [ "<output name>" ],
  "assumptions": [ "<string>" ],
  "inference": [ <InferenceMetadata ...> ]
}

---

## CapabilityProposal

{
  "capability_id": "<snake_case_id>",  // unique across entire document
  "name": "<human name>",
  "application_id": "<application_id>",
  "description": "<what this capability does>",
  "steps": [ <StepProposal ...> ],    // empty if is_deferred: true
  "inputs": [ "<input name>" ],
  "outputs": [ "<output name>" ],
  "is_deferred": false,               // true = not yet implementable
  "inference": [ <InferenceMetadata ...> ]
}

---

## StepProposal

{
  "step_id": "<snake_case_id>",       // unique across ENTIRE document
  "sequence": 1,                       // positive integer, unique within capability
  "action": "<ActionType>",
  "element_name": "<UI element name>",
  "element_type": "<ElementType>",
  "value": null,                       // or string — required for FILL
  "wait_condition": null,              // optional pre-action readiness condition
  "postcondition": null,               // optional post-action completion condition
  "expected_outcomes": [ <OutcomeProposal ...> ],
  "dependencies": [ "<step_id>" ],    // step_ids in SAME capability only
  "notes": null,                       // or string
  "source_line": null,                 // or 1-based line number
  "inference": [ <InferenceMetadata ...> ]
}

Valid ActionType values:
  OPEN, CLICK, FILL, PRESS, SELECT, CHECK, UNCHECK,
  UPLOAD, DOWNLOAD, COPY, WAIT, VERIFY, HANDLE_POPUP,
  MANUAL_AUTH, BRANCH, AUTH_BRANCH, END_SUCCESS, END_FAILURE, DEFERRED

Valid ElementType values:
  PAGE, BUTTON, LINK, TEXTBOX, TEXTAREA, DROPDOWN, OPTION,
  CHECKBOX, RADIO, FILE_INPUT, DIALOG, LIST, ROW, TEXT, STATUS, UNKNOWN

---

## OutcomeProposal

{
  "outcome_id": "<snake_case_id>",
  "description": "<what happens>",
  "is_terminal": false,               // true = execution ends here
  "is_success": true,
  "next_capability_id": null          // or capability_id to branch to
}

---

## InputDefinition

{
  "name": "<snake_case_name>",
  "description": "<what this input provides>",
  "required": true,
  "default_value": null
}

Input placeholder format in step values: {{input.name}}

---

## OutputDefinition

{
  "name": "<snake_case_name>",
  "description": "<what this output represents>"
}

---

## InferenceMetadata

{
  "field_name": "<field that was inferred>",
  "proposed_value": "<value as string>",
  "confidence": 0.85,                 // float 0.0–1.0
  "source": "<InferenceSource>",
  "evidence_lines": [5, 12]           // 1-based line numbers from source
}

Valid InferenceSource values:
  USER_TEXT, EXPLICIT_MARKER, HEURISTIC, LLM_INFERENCE

---

## STRICT RULES

1. schema_version MUST be "1.0" — no other value is accepted.
2. All IDs (result_id, capability_id, step_id, goal_id, outcome_id) must be
   unique within the entire document.
3. Extra fields will be REJECTED by the validator (extra="forbid").
   Only use fields defined in this schema.
4. MANUAL_AUTH steps must NOT contain passwords, OTPs, tokens, cookies,
   MFA codes, secrets, or any credential material in the value field.
5. wait_condition is only for readiness before an action. It does not prove
   that the action completed.
6. postcondition proves completion after an action. Submission/navigation
   CLICK steps and MANUAL_AUTH steps must have an explicit postcondition.
7. Use AUTH_BRANCH only for generic authentication-state classification.
   Use BRANCH for normal business-rule branching.
8. Deferred capabilities: set is_deferred: true and leave steps: [].
9. Input placeholders: use {{input.name}} exactly (double braces).
10. Confidence must be a float between 0.0 and 1.0 inclusive.
11. evidence_lines must be 1-based line numbers from the source text.
12. dependency step_ids must exist within the SAME capability only.
13. request_id and source_sha256 in source_reference must be COPIED EXACTLY
    from the interpretation_request.json — do not generate new values.

---

## What to do with unresolved items

If part of the SOP cannot be reliably interpreted (ambiguous action,
missing URL, unknown UI element), add it to "unresolved_items" as a
string describing what is unclear. Do not guess — use DEFERRED action
or is_deferred: true capability instead.

---

## After writing the file

Tell the user: "interpretation_result.json written. Run:
  sop sop validate-result --result <path>"
```
