# Architecture Template

Use this document when a feature or system has enough complexity that you want to describe the structure before writing code.

Architecture is about the big picture: components, responsibilities, interactions, and tradeoffs.

## Document Purpose

This template answers:

- What are the main parts of the system?
- How do they interact?
- Why is the design shaped this way?
- What tradeoffs are we accepting?

## Title

Name of the feature or system.

## Context

Briefly describe the business or technical context around this design.

## Overview

Write a short explanation of the proposed architecture.

Keep this high level. Think "how the parts fit together."

## Goals

What is this architecture trying to optimize for?

Examples:

- simplicity
- scalability
- maintainability
- security
- low operational cost

## Non-Goals

What is this architecture not trying to optimize for?

## System Components

List the major pieces and what each one is responsible for.

Examples:

- web frontend
- API service
- background worker
- database
- cache

## Data Flow

Describe how data moves through the system.

For example:

1. User submits a request from the frontend
2. API validates input and writes to the database
3. Worker processes a background job
4. Client polls or receives the updated result

## Interfaces and Boundaries

Document important boundaries between parts of the system.

Examples:

- internal service APIs
- third-party integrations
- database access boundaries
- frontend/backend contracts

## Data Model Notes

Summarize important entities, relationships, or storage choices.

## Security Considerations

Note authentication, authorization, encryption, secret handling, audit logging, or abuse prevention concerns.

## Reliability Considerations

How will the system handle failures, retries, partial outages, and recovery?

## Performance Considerations

What are the expected load patterns or performance-sensitive paths?

## Tradeoffs

Every design involves tradeoffs. Record the most important ones here.

Example:

- We chose a simple synchronous flow first for faster delivery, accepting lower peak throughput

## Alternatives Considered

List other designs you considered and why they were not chosen.

## Open Questions

What still needs investigation or validation?
