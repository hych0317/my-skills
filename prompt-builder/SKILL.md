---
name: prompt-builder
description: Create concise, reusable execution prompts or cross-session handoff prompts. Use when the user explicitly wants a structured execution contract, a prompt for another model or session, or a handoff that preserves decision-critical context. Do not use for ordinary prose editing, general brainstorming, a plain requirements summary, or a routine handoff to a person.
---

# Prompt Builder

Create either:

- **Requirement Contract**: Define a task for execution from the beginning.
- **Session Handoff**: Transfer decisions, progress, and non-recoverable context so a new session can continue existing work.

Define the result, boundaries, and pause conditions. Leave reasoning and implementation choices to the target model unless the method is a requirement.

## Select the Artifact

- Infer the artifact from the user's intended destination. Ask whether they are starting a new task or continuing existing work only when both interpretations are reasonable; do not ask for an internal mode name.
- When both are needed, settle the Requirement Contract first, then create the Session Handoff.
- For separate artifacts, make the handoff reference or embed the final contract only when needed; do not repeat it.
- For one paste-ready artifact, produce a Session Handoff and place the settled task goal and limits in `Objective` and `Boundaries`.

## Handle Information

Classify material information as confirmed, safe to infer, omittable, or requiring clarification.

- Clarify missing or conflicting information that would materially change the objective, deliverable, scope, risk, or approval. Ask at most 3 independent questions per round.
- Use conservative assumptions only when they do not materially narrow the user's options. Identify them in `Context`, `Constraints`, or `Checkpoint` instead of presenting them as confirmed facts.
- State each requirement once in the most specific section. Do not repeat an objective as an output format or a boundary as a checkpoint unless the pause condition adds information.
- Use the requested output language. Otherwise use the language of the user's instruction while preserving identifiers and domain terms that should not be translated.

Unless the user requests analysis, alternatives, or explanation, return only the finished artifact. Put necessary assumptions inside it.

## Requirement Contract

Resolve material ambiguity before drafting. Use all sections in this order:

```text
Context:
...

Request:
...

Output Format:
...

Constraints:
...

Checkpoint:
...
```

- **Context**: Role, situation, audience, source material, current stage, and relevant assumptions needed to understand the task. Do not pad simple background.
- **Request**: Result and quality bar. Specify the destination, not each reasoning or implementation step.
- **Output Format**: Required structure, language, length, data shape, or file boundary.
- **Constraints**: Scope, source limits, prohibited assumptions, and actions or decisions the model must not take.
- **Checkpoint**: Conditions under which execution must pause and request clarification or approval instead of making an assumption.

Put ordinary unresolved questions in `Context`. Put external verification in `Checkpoint` only when it requires unavailable access, user authorization, cost, or acceptance of a changed evidence base.

## Session Handoff

Treat project information as recoverable only when the destination is expected to have the same current project state, such as the same workspace or repository, saved files, persistent diffs or logs, and equivalent tool permissions.

When relevant tools and workspace are available, inspect only enough project state to distinguish recoverable facts from conversation-only context. Do not traverse broadly or read unrelated or sensitive files solely for the handoff. Without access, use the conversation and user-provided material.

Preserve information when recoverability is uncertain, or instruct the destination to verify it. Omit recoverable file inventories, code walkthroughs, command history, and implementation narration.

Include implementation details only when they are agreed constraints or non-recoverable facts that materially affect continuation. Otherwise let the next session inspect the project and choose the implementation.

Use only material sections, in this order:

```text
Objective:
...

Non-recoverable Context:
...

Boundaries:
...

Current Outcome:
...

Next Session:
...

Checkpoint:
...
```

- **Objective**: Intended result and completion criteria.
- **Non-recoverable Context**: Product intent, decisions, rationale, preferences, rejected options, external facts, and assumptions unavailable from the destination project state.
- **Boundaries**: Scope limits, prohibited assumptions or changes, and decisions that must remain stable.
- **Current Outcome**: Non-recoverable completed results, unresolved questions, blockers, and fragile state.
- **Next Session**: What to verify or continue, beginning with minimum relevant inspection when project access exists.
- **Checkpoint**: Conditions under which execution must pause for clarification or approval instead of making an assumption.

Omit empty handoff sections. Do not duplicate unresolved questions across `Non-recoverable Context`, `Current Outcome`, and `Checkpoint`.
