# Testing Plan Template

Use this document to decide how a feature or system will be verified.

This helps you think about quality early instead of leaving testing until the end.

## Document Purpose

This template answers:

- What needs to be tested?
- At what level should it be tested?
- What risks need the most attention?
- What is manual versus automated?

## Title

Name of the feature or system being tested.

## Summary

Short description of what is being verified.

## Test Scope

List what is included in testing.

## Out of Scope

List what will not be tested in this effort.

## Risks to Cover

Identify the most important failure modes.

Examples:

- data loss
- authorization bugs
- broken upgrade path
- poor performance under load

## Test Levels

Describe which levels of testing will be used.

Examples:

- unit tests
- integration tests
- end-to-end tests
- manual exploratory testing

## Test Cases

List the core scenarios that must pass.

Examples:

- user can sign up with valid credentials
- duplicate email is rejected
- unauthorized user cannot access admin routes

## Test Data and Environments

What environments, fixtures, mocks, or seed data are needed?

## Tooling

List any test frameworks, runners, or support tools.

## Entry Criteria

What must be true before testing begins?

## Exit Criteria

What must be true before testing is considered complete?

## Monitoring and Follow-Up

After release, what should be watched to catch issues that testing may miss?
