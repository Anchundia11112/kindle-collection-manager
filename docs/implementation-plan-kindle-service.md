# Kindle Service Implementation Plan

## Summary

This plan starts with a safe, read-first approach and delays risky Kindle write automation until the application has a solid local foundation.

## Preconditions

- Python project initialized
- Local development environment available
- A clear way to inspect Kindle web behavior during development
- Agreement that the first version is CLI-first, not service-first

## Phase 1: Project foundation

1. Initialize the Python project structure
2. Add local development tooling
3. Add configuration handling and logging
4. Set up a small SQLite database and initialization flow
5. Add CLI entry points for core actions

## Phase 2: Local domain model

1. Define models for books, collections, collection memberships, sync runs, and sync actions
2. Implement local collection planning operations
3. Implement search and matching logic for books
4. Add dry-run planning support

## Phase 3: Kindle read integration

1. Investigate the Amazon purchased-books page and personal-documents page
2. Identify how each page loads and paginates book metadata
3. Build a first Kindle adapter focused only on reading book data
4. Normalize imported books from both sources into the local schema
5. Add CLI commands for listing and querying imported books

## Phase 4: Collection planning

1. Add commands for creating desired collections locally
2. Add commands for attaching books to a collection plan
3. Add preview commands showing intended sync actions
4. Validate ambiguous book matches before sync

## Phase 5: Experimental sync

1. Choose one sync path:
   browser automation or replayed web requests
2. Implement sync in dry-run-first mode
3. Attempt a limited real sync for one collection
4. Record per-book and per-collection results

## Phase 6: Hardening

1. Add retry behavior
2. Add better error reporting
3. Improve session handling
4. Add manual recovery workflows for failed syncs

## Dependencies

- Kindle login session
- Research into how Amazon content-management pages expose purchased books and personal documents
- A consistent way to identify books

## Risks and Mitigations

- Risk: write automation is brittle
- Mitigation: keep write logic isolated and optional

- Risk: title matching is ambiguous
- Mitigation: use ASIN or combined metadata when possible

- Risk: sync failures create uncertainty
- Mitigation: make dry-run and logging first-class features

## Rollout Plan

- Start as a local developer tool
- Use read-only import first
- Test real sync only on small, disposable collections
- Expand to larger workflows after confidence improves

## Verification Plan

- Unit tests for local domain logic
- Integration-style tests for SQLite read and write operations
- Manual validation for Kindle read import
- Manual end-to-end tests for experimental sync

## Definition of Done for V1

- Local book import works
- Books can be searched and selected
- Local collection plans can be created
- Dry-run output is correct and understandable

## Definition of Done for V2

- At least one real sync path works for a small collection
- Sync results are logged clearly
- Failed actions can be retried safely
