# ADR-001: Use a local canonical model with browser-first Kindle automation and SQLite storage

## Status

Proposed

## Context

The project needs to organize Kindle books into collections for personal use.

There is no known official public API for personal Kindle collection management. That means the project needs to choose between:

- directly replaying unofficial web requests
- automating the visible Kindle web experience in a browser
- reading local Kindle data
- or combining these approaches

The biggest risk is that any Kindle-specific integration may change without notice.

## Decision

The system will use a local canonical data model for books and collection plans, prefer browser-first automation for write operations before attempting direct unofficial API writes, and use SQLite for first-version local storage.

## Rationale

This decision separates the stable parts of the project from the unstable parts.

The stable part is the internal model:

- what books exist
- what collections are desired
- what actions need to happen

The unstable part is how Kindle is actually read or written.

Browser-first automation is preferred for write operations because:

- it follows the same visible path a user would take
- it may be easier to debug than replaying hidden requests
- it avoids over-coupling the project to undocumented request formats too early

Direct unofficial request replay may still be useful later, especially for reads, but it should not define the whole architecture.

SQLite storage is preferred for the first version because:

- it requires no separate database server
- it supports cleaner querying for large book libraries
- it keeps the tool lightweight while avoiding an early storage migration

## Alternatives Considered

### Use unofficial request replay for everything

Pros:

- may be faster
- may support bulk actions more efficiently

Cons:

- brittle
- strongly coupled to undocumented request details
- harder to maintain when Amazon changes behavior

### Use only local Kindle files or app state

Pros:

- avoids network request reverse engineering

Cons:

- uncertain data availability
- uncertain write capability
- may vary by device or operating system

### Build no local model and act directly against Kindle every time

Pros:

- simpler initial prototype

Cons:

- weaker observability
- harder retries
- poor separation of concerns

### Use JSON from the beginning

Pros:

- easiest possible manual inspection
- less schema work while prototyping

Cons:

- awkward for querying and relationships
- likely to require migration sooner

## Consequences

Positive:

- safer architecture
- easier debugging
- better support for dry-run behavior
- future flexibility if the adapter changes
- easier local development with minimal setup

Negative:

- more up-front design work
- browser automation may be slower than direct requests
- some effort may later be duplicated if direct requests become practical
- some schema work is required up front

## Related Documents

- `docs/requirements-kindle-service.md`
- `docs/architecture-kindle-service.md`
- `docs/implementation-plan-kindle-service.md`
