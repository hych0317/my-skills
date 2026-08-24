# Independent Review Rubric

Use this rubric only in `reviewing`. Judge the submitted version from the current Initiative, diff, and tests or other inspectable evidence. Do not rely on the Builder's undocumented intent.

## Establish independence

- Confirm that the Reviewer did not author the version under review.
- Confirm that the inputs identify a stable diff or revision.
- Return `escalate` if no independent Reviewer is available.
- If the Reviewer makes a substantive code change, invalidate the current review and assign a new Reviewer for the changed version.

## Trace acceptance

For every `AC-*` item, record:

| Acceptance | Relevant change | Evidence | Result |
|---|---|---|---|
| AC-1 | File, component, or diff link | Test, check, or observation | pass / fail / insufficient |

Do not return `approve` while any applicable criterion is `fail` or `insufficient`.

## Inspect required dimensions

Check only dimensions relevant to the change, but never omit a relevant material risk:

- Requirements: The diff matches Problem, Scope, Decision, and every acceptance criterion.
- Correctness: Normal, boundary, error, retry, concurrency, and state-transition behavior are sound where applicable.
- Tests: Evidence is current, reproducible, and proportionate to the change.
- Security and permissions: Trust boundaries, authorization, input handling, secrets, and dependency risks are addressed.
- Privacy and data: Collection, access, retention, migration, deletion, and rollback are safe.
- Compatibility: Public APIs, schemas, protocols, persisted formats, and clients remain compatible or have an approved migration.
- Operations: Observability, failure handling, rollout, rollback, performance, and production impact are addressed.
- Maintainability: The solution is no more complex than required and follows repository conventions.
- Scope integrity: The diff contains no unexplained scope expansion or unrelated changes.

## Select one decision

- Return `approve` only when all applicable `AC-*` items pass and no unresolved finding prevents delivery.
- Return `changes-requested` for actionable defects that can be corrected within the approved Initiative. Identify location, impact, required change, and related `AC-*` item or risk.
- Return `escalate` when human authority is required, a core Initiative decision must change, residual risk needs acceptance, evidence is unavailable, or review independence is compromised.

When a finding requires changing Problem, Scope, Decision, Acceptance, or Risk, require a return to `shaping` and a new Ready Gate instead of approving a silent change.

## Write the review record

Keep the result concise and evidence-based:

```markdown
Decision: approve | changes-requested | escalate
Reviewer: ...
Revision: ...
Independence: confirmed | compromised

Acceptance:
- AC-1: pass | fail | insufficient — evidence

Findings:
- Severity; location; impact; required change; AC or risk mapping

Residual risks:
- ...
```
