# Requirements Template

Use this document to describe what should be built before deciding exactly how to build it.

This is one of the most useful pre-code documents because it helps keep the problem, goals, and scope clear.

## Document Purpose

This template answers:

- What problem are we solving?
- Who is this for?
- What does success look like?
- What is in scope and out of scope?

## Title

Give the feature, system, or project a short name.

## Summary

Write a short paragraph describing the feature or project in plain language.

## Problem Statement

What pain point, limitation, or business need is driving this work?

## Goals

List the outcomes this work should achieve.

Examples:

- Users can reset their password securely
- Developers can deploy with one command
- Admins can export reports as CSV

## Non-Goals

List what this work will not try to solve.

This is important because it prevents scope creep.

## Users and Stakeholders

Who will use this feature or care about the outcome?

Examples:

- end users
- administrators
- support staff
- internal developers

## Functional Requirements

Describe the behaviors the system must support.

Use clear statements such as:

- The system must allow a user to request a password reset email
- The system must expire reset tokens after 15 minutes

## Non-Functional Requirements

These are quality constraints rather than features.

Examples:

- performance
- security
- reliability
- accessibility
- compliance

## Constraints

List important limitations or required conditions.

Examples:

- must use the existing database
- must work offline
- must support mobile browsers

## Assumptions

List things you currently believe to be true but may need validation.

## Risks

What could block success or create problems later?

## Open Questions

List questions that still need answers before implementation.

## Success Criteria

How will we know this work is successful?

Examples:

- users complete onboarding without support intervention
- API response times stay under 200ms for typical requests

## Notes

Add anything else that does not fit the sections above.
