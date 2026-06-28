# Copilot Task Prompt

Exact prompt format for GitHub Copilot Chat to trigger SOP automation tasks.

## Request Format

```
Please run the following automation task:

goal=<goal_name>
<input_name>=<value>
<input_name2>=<value2>
```

Lines follow `key=value` format. Supported keys:
- `goal` — the goal name (required)
- `sop_id` — preferred SOP ID (optional, skips SOP selection scoring)
- `application` — application hint for SOP selection (optional, repeatable)
- `constraint` — execution constraint (optional, repeatable)
- Any other key — treated as an input to the task

## Example: Create a CRM Contact

```
Please run the following automation task:

goal=create_contact
email_address=john.doe@example.com
company_name=Acme Corp
```

## Example: Login with Preferred SOP

```
Please run the following automation task:

goal=login
sop_id=crm-login-sop
```

## Example: Submit Report with Application Hint

```
Please run the following automation task:

goal=submit_report
application=crm_app
report_date=2026-06-28
```

## Protocol After Submission

After Copilot receives the request:
1. `task prepare-intent` parses the request text into a TaskIntent
2. `task validate-intent` checks schema and input completeness
3. `task submit` queues the task for the runtime host
4. `task status` polls until terminal state or auth pause
5. `task continue` resumes after manual authentication
