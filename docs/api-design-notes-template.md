# API and Design Notes Template

Use this document for detailed design thinking that does not fit neatly into requirements or architecture.

This is often used for backend API design, frontend interaction notes, request and response shapes, validation rules, or domain modeling details.

## Document Purpose

This template answers:

- What are the detailed contracts or interactions?
- What inputs and outputs should exist?
- What edge cases need to be handled?

## Title

Name of the API area, UI flow, or design topic.

## Context

Briefly explain what this note is supporting.

## Scope

Describe what this design note covers and what it does not cover.

## Endpoints or Interaction Points

If this is an API, list the endpoints.

Examples:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /users/:id`

If this is frontend-focused, list screens, components, or flows instead.

## Request Shape

Document the important request fields, parameters, or user inputs.

## Response Shape

Document the response body, UI states, or resulting system behavior.

## Validation Rules

What rules should be enforced on input or behavior?

## Error Cases

List expected failure cases and how they should be handled.

Examples:

- invalid credentials
- missing required field
- rate limit exceeded
- network timeout

## State Transitions or Flow Notes

Describe any important lifecycle or interaction flow behavior.

## Examples

Add example payloads, sample user journeys, or edge-case scenarios.

## Open Questions

List anything still undecided.
