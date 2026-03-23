# Implementation Plan Template

Use this document after the problem and design are reasonably clear.

An implementation plan turns an idea into a sequence of concrete development steps.

## Document Purpose

This template answers:

- What work needs to happen first?
- How should the feature be broken down?
- What are the dependencies and risks?
- How will we know each phase is done?

## Title

Name of the feature or task.

## Summary

One short paragraph describing what will be implemented.

## Preconditions

List anything that must already exist before implementation starts.

Examples:

- design approved
- schema finalized
- access to third-party API credentials

## Work Breakdown

Break the work into steps or phases.

Example structure:

1. Add database schema changes
2. Build backend endpoints
3. Add frontend UI
4. Add tests
5. Roll out and monitor

## Dependencies

List other tasks, people, systems, or decisions this work depends on.

## Risks and Mitigations

For each important risk, note how you plan to reduce it.

Example:

- Risk: third-party API rate limits may block testing
- Mitigation: build against a mock service first

## Rollout Plan

Explain how the feature will be introduced.

Examples:

- release all at once
- behind a feature flag
- internal testing first
- phased rollout

## Verification Plan

Describe how each part of the implementation will be checked.

Examples:

- unit tests
- integration tests
- manual QA
- staging validation

## Definition of Done

Describe the conditions that must be true before the work is considered complete.

Examples:

- code merged
- tests passing
- docs updated
- monitoring added

## Post-Launch Follow-Up

List any cleanup, metrics review, or future improvements expected after launch.
