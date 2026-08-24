---
name: agent-product-flow
description: Run a lean, risk-aware agent product-development flow from idea framing through research, design, implementation, independent review, and completion. Use when Codex is asked to take a product idea, feature, bug, technical change, or cross-functional initiative end to end; create or maintain an Initiative decision record; coordinate specialist agents; decide whether work is ready to build; or perform evidence-based delivery review.
---

# Agent Product Flow

Guide one initiative through six lifecycle states with one DRI, one core decision record, risk-based authority, and independent review. Minimize ceremony: perform work only when it resolves a blocking unknown, reduces a material risk, implements an acceptance criterion, or produces review evidence.

## Keep one Initiative record

Create exactly one Initiative record for each development initiative. Reuse and update it throughout the lifecycle. Treat it as the single core decision record, not the only artifact. Link source research, prototypes, pull requests, diffs, test logs, and other raw evidence instead of copying them into new phase documents.

Read [references/initiative-template.md](references/initiative-template.md) whenever creating or changing the Initiative. Number acceptance criteria `AC-1`, `AC-2`, and so on. Map implementation, tests, and review findings back to those identifiers.

Do not create separate research, design, implementation-summary, or retrospective files unless the user or project convention requires them.

## Maintain lifecycle semantics

Use only these formal states:

`idea -> shaping -> ready -> building -> reviewing -> done`

Apply these meanings:

- `idea`: Capture the request, DRI, desired outcome, and initial risk classification.
- `shaping`: Resolve blocking unknowns through proportionate research, product design, and technical validation.
- `ready`: Record that the Ready Gate passed and the work is approved for implementation, but implementation has not started.
- `building`: Implement and verify numbered acceptance criteria in small, reviewable slices.
- `reviewing`: Run an independent evidence-based review of the current version.
- `done`: Record the terminal resolution as `delivered`, `dropped`, or `deferred`.

Treat `blocked` as metadata, never as a lifecycle state. When blocked, retain the current state and record `blocked: true`, the blocker, its owner, and the next action. Clear the marker when resolved.

Use these transitions:

- Move `idea` to `shaping`, or directly to the Ready Gate when no blocking unknown exists.
- Move `shaping` to `ready` only after a Ready Gate `pass`.
- Move `ready` to `building` when implementation starts.
- Move `building` to `reviewing` when the diff and required evidence are ready.
- Move `reviewing` to `done` after `approve`.
- Move `reviewing` to `building` after `changes-requested`, unless the requested change alters a core decision; then move to `shaping`.
- On a decision to stop, move to `done` and set `resolution: dropped` or `deferred`.

## Route work by unknowns and risk

Define a blocking unknown as an unanswered question whose answer could materially change `Problem`, `Scope`, `Decision`, `Acceptance`, `Risk`, or whether the work can be implemented safely and verified.

Apply the rule mechanically:

- If any blocking unknown remains open, continue `shaping`.
- If no blocking unknown remains open, the work may enter the Ready Gate.

Do not use self-reported confidence to justify skipping work. Skip a research, design, or feasibility activity only when it resolves no blocking unknown and reduces no material risk. Record non-blocking unknowns as explicit assumptions with an owner or validation point.

Classify risk as `low`, `medium`, or `high`. Consider security, authentication and authorization, money or billing, privacy and sensitive data, data migration or loss, destructive or irreversible operations, production and external side effects, public APIs or persisted formats, availability, performance, and compliance. Treat a change as high risk when a failure in any relevant domain could cause material harm, or when safe rollback is uncertain.

## Coordinate roles on demand

Assign exactly one Lead Agent as DRI. Keep decision ownership with the DRI and activate specialists only when they have a concrete question or evidence target:

- Use a Research Agent to investigate users, competitors, repositories, and primary sources.
- Use a Product and Design Agent to shape journeys, scope, non-goals, and acceptance criteria.
- Use an Architecture Agent for interfaces, data, dependencies, migration, security, and operations.
- Use a Builder Agent to implement and verify acceptance criteria.
- Use a Reviewer Agent to perform the independent Review Gate.

Run independent research or feasibility work in parallel when the runtime permits it and the work has non-overlapping outputs. Otherwise execute roles sequentially. Do not activate a full team for a small, well-understood change.

## Run the Ready Gate

Verify that:

- The problem, affected user, and desired outcome are explicit.
- Evidence and assumptions are distinguishable.
- No blocking unknown remains open.
- Scope and non-goals are bounded.
- The selected decision and material alternatives are recorded.
- Acceptance criteria are numbered and verifiable.
- Risk domains, risk level, verification, and rollback needs are recorded.

Return exactly one result:

- `pass`: Set `status: ready`. Require human approval first when risk is high.
- `revise`: Keep or set `status: shaping` and name the unresolved blocking unknowns.
- `stop`: Set `status: done` and `resolution: dropped` or `deferred`, with rationale.

## Enforce authority boundaries

Allow agents to act autonomously only for:

- Reading and analyzing information within the authorized scope.
- Conducting research and recording sources.
- Creating or editing in-scope local documents, code, tests, and prototypes.
- Running non-destructive builds, tests, static checks, and local verification.
- Comparing options, decomposing work, and fixing review findings locally.
- Passing a low- or medium-risk Ready Gate when no higher-level instruction requires approval.

Require explicit human approval before:

- Passing any high-risk Ready Gate.
- Performing a destructive, irreversible, or difficult-to-recover operation.
- Deploying, releasing, merging, or changing a production environment.
- Writing to an external system, sending an external message, or triggering a real business workflow.
- Changing authentication, authorization, security controls, secrets, or network exposure.
- Accessing, transferring, modifying, or deleting private or sensitive data.
- Causing spending, billing, refunds, trades, or other financial effects.
- Executing a data migration whose rollback is uncertain.
- Introducing a breaking public API, protocol, schema, or persisted-format change.
- Accepting material residual risk or bypassing tests, security checks, or policy controls.

Treat approval as specific to the named action, target, and scope. Never treat approval of an Initiative or plan as approval to perform a later external or production action.

## Build without silent drift

Read the current Initiative before implementation. Implement small slices, keep changes within Scope and Decision, and attach verification evidence to each applicable `AC-*` item.

If implementation reveals a need to change `Problem`, `Scope`, `Decision`, `Acceptance`, or `Risk`:

1. Stop implementation.
2. Set `status: shaping`.
3. Record the discovery and its effect on existing work.
4. Update the Initiative.
5. Run the Ready Gate again.
6. Resume implementation only after another `pass` and any required human approval.

Keep local implementation choices inside `building` only when they do not materially alter those five core decision fields.

## Run an independent Review Gate

Read [references/review-rubric.md](references/review-rubric.md). Assign a Reviewer who did not author the version under review. Give the Reviewer only the current Initiative, diff, and tests or other evidence. Do not substitute the Builder's explanation for inspectable evidence.

Return exactly one result:

- `approve`: Every applicable acceptance criterion is supported by sufficient evidence, and no unresolved finding prevents delivery.
- `changes-requested`: State actionable findings and map each one to an `AC-*` item or risk.
- `escalate`: Request human judgment or authority because evidence, decision coverage, independence, or risk is insufficient.

If the Reviewer makes a substantive code change, disqualify that Reviewer from approving the changed version. Regenerate the diff and evidence, then assign a fresh independent Reviewer. If no independent Reviewer is available, disclose the limitation and return `escalate`, never `approve`.

## Complete the initiative

After approval, set `status: done` and `resolution: delivered`. Link the final change and evidence, note residual risks and follow-ups, and keep the summary short. Do not create a separate retrospective unless requested.
