# Documentation Starter Kit

This folder is a simple starting point for planning software before or during implementation.

You can use these documents to think clearly, communicate decisions, and keep a record of why the code was built a certain way.

## How to use this folder

Pick the template that matches what you are trying to do, copy it for a specific feature or project, and fill in only the sections that are useful.

Examples:

- `requirements-template.md` -> `requirements-authentication.md`
- `architecture-template.md` -> `architecture-billing.md`
- `implementation-plan-template.md` -> `implementation-plan-user-search.md`

These templates are intentionally practical rather than formal. They are meant to help you move forward, not create paperwork for its own sake.

## When to use each template

### Requirements

Use this when you want to define what should be built and why.

This is useful before writing code because it helps separate the problem from the implementation.

### Architecture

Use this when you want to describe the high-level system design.

This is where you explain major components, boundaries, data flow, technology choices, and tradeoffs.

### Implementation Plan

Use this when you already know what to build and need a step-by-step execution plan.

This is especially useful for breaking a feature into safe, testable development tasks.

### ADR

ADR stands for `Architecture Decision Record`.

An ADR is a short document that captures one important technical decision, why it was made, and what consequences come with it.

Examples:

- choosing PostgreSQL instead of SQLite
- choosing JWT authentication instead of server sessions
- choosing a monorepo instead of separate repos

ADRs are helpful because months later you can look back and understand why a decision was made instead of guessing.

### API and Design Notes

Use this when you want to sketch request and response shapes, endpoints, data contracts, UI behavior, or interaction details.

This template is intentionally flexible because teams often use it for both backend and frontend design notes.

### Testing Plan

Use this when you want to decide how a feature will be verified before or during implementation.

This helps make testing intentional instead of something you remember at the end.

## Suggested workflow

For a new feature, a good lightweight flow is:

1. Start with `requirements-template.md`
2. Add `architecture-template.md` if the design has meaningful complexity
3. Add `adr-template.md` for important decisions
4. Add `implementation-plan-template.md` before coding
5. Add `testing-plan-template.md` so verification is clear

Not every task needs every document. Small changes may only need a requirements note and a short implementation plan.
