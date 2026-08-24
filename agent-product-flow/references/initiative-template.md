# Initiative Template

Create one copy for an initiative and keep it current. Remove instructional comments when they no longer add value. Use stable links for raw evidence.

```markdown
---
title: ""
status: idea
resolution:
owner: ""
risk: low
risk_domains: []
blocked: false
blocker:
blocker_owner:
next_action:
reviewers: []
updated: YYYY-MM-DD
---

# Problem

State who experiences what problem, in which context, and why it matters.

# Evidence

- E-1: Fact and source link.
- E-2: Fact and source link.

## Assumptions

- A-1: Assumption; validation owner or point.

# Blocking Unknowns

- BU-1: Open question; owner; resolving action.

Write `None` before requesting the Ready Gate. An unknown is blocking when its answer could materially change Problem, Scope, Decision, Acceptance, Risk, or safe verifiability.

# Outcome

Describe the observable user or business outcome and its success signal.

# Scope

## In Scope

- ...

## Out of Scope

- ...

# Decision

Describe the selected product and technical approach and the decisive tradeoffs.

## Alternatives

- Option: reason not selected.

# Risk

- Level: low | medium | high
- Domains: security | permissions | money | privacy | migration | irreversible | production | external-side-effect | public-api | availability | performance | compliance
- Failure impact:
- Mitigations:
- Verification:
- Rollback:
- Required human approvals:

# Acceptance

- AC-1: Verifiable condition.
- AC-2: Verifiable condition.

# Ready Gate

- Decision: pass | revise | stop
- Decider:
- Date:
- Open blocking unknowns:
- Human approval, if required:
- Rationale:

# Delivery

- Change or diff:
- AC-1 evidence:
- AC-2 evidence:
- Build-to-Shape returns:

# Review

- Reviewer:
- Independence confirmed: yes | no
- Decision: approve | changes-requested | escalate
- AC-1 result and evidence:
- AC-2 result and evidence:
- Risk findings:
- Required changes or escalation:

# Completion

- Resolution: delivered | dropped | deferred
- Outcome:
- Residual risks:
- Follow-ups:

# References

- Research:
- Design or prototype:
- Pull request or diff:
- Test results:
- Operational evidence:
```
