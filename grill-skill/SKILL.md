---
name: grill-skill
description: Confirm unclear requirements through focused questioning before execution. Use when the user explicitly asks to grill, clarify, confirm, or stress-test a request, or when the agent is unsure about the user's goal, scope, acceptance criteria, constraints, or intended execution approach.
---

# Grill

Clarify the request until the work can be executed with shared understanding.

Use the user's current language by default.

## Process

1. Inspect available local context first when it can answer a question directly.
2. Ask focused questions about the remaining uncertainty.
3. If questions depend on each other, ask the upstream decision first and defer downstream questions until the dependency is resolved.
4. Ask multiple independent questions when useful.
5. For complex or high-impact questions, provide candidate answer options as lettered bullet points (A, B, C, etc.). Clearly mark the recommended option when appropriate.
6. Continue questioning when the answer is incomplete, ambiguous, or changes the likely execution path.
7. Prefer concrete tradeoffs, edge cases, constraints, and acceptance signals over abstract discussion.
8. Do not proceed past unresolved uncertainty that would materially affect the result, unless a safe default can be stated explicitly.

## Completion

Ensure consensus is reached before execution. Once the requirements are clear and agreed upon, summarize them with:

- A brief confirmation summary
- A complete requirement statement
- An execution plan

