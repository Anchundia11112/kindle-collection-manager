# ADR Template

ADR stands for `Architecture Decision Record`.

This is a short document for recording one important technical decision.

You do not write an ADR for every tiny choice. You write one when the decision matters enough that future you or future teammates may ask:

- Why did we choose this?
- What alternatives did we consider?
- What tradeoffs did we accept?

## When to create an ADR

Use an ADR for decisions like:

- choosing a database
- choosing an authentication strategy
- introducing a message queue
- splitting a monolith into services
- adopting a framework or infrastructure pattern

## Title

Use a clear decision-oriented title.

Example:

`Use PostgreSQL for primary application storage`

## Status

Common values:

- proposed
- accepted
- deprecated
- superseded

## Context

Describe the situation that required a decision.

What constraints, problems, or goals led to this choice?

## Decision

State the decision clearly and directly.

This should be the single most important sentence in the document.

## Rationale

Explain why this option was chosen.

Mention the factors that mattered most, such as performance, team familiarity, hosting environment, cost, reliability, or simplicity.

## Alternatives Considered

List the main alternatives and why they were not selected.

## Consequences

Document the results of the decision.

Include both benefits and downsides.

Examples:

- easier local development
- stronger consistency guarantees
- higher hosting cost
- more operational complexity

## Related Documents

Link related requirements, architecture notes, or implementation plans here.
