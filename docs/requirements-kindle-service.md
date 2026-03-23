# Kindle Service Requirements

## Summary

Kindle Service is a personal-use tool for organizing a large Kindle library into collections with less manual effort.

The main problem is that managing collections for 2,000 or more books through the Kindle app, Kindle website, or a physical Kindle device is slow and tedious. The goal of this project is to let the user choose one or more existing Kindle books and assign them to a named collection through a simpler workflow.

## Problem Statement

Current Kindle collection management is too manual for large libraries.

Pain points:

- selecting books one by one is tedious
- creating or updating large collections is slow
- different Kindle surfaces exist, but none are optimized for bulk organization
- there is no obvious official API for this use case

## Goals

- View or import the user's Kindle library metadata
- Search for books by title and related identifiers
- Select one or more books to group together
- Create a named collection plan from selected books
- Execute collection sync through a local script if technically possible
- Keep the tool personal, local, and practical rather than over-engineered

## Non-Goals

- Supporting other users or multi-user accounts
- Publishing this as a commercial SaaS product
- Handling ebook file conversion or DRM removal
- Perfectly stable automation against Amazon on day one
- Full mobile app support in the first version

## Users and Stakeholders

- Primary user: you
- Secondary stakeholder: future you maintaining the tool

## Functional Requirements

- The system must provide a local command or script to retrieve the current list of Kindle books available to the user
- The system must support importing both Amazon-purchased books and personal documents if they are exposed through different Kindle or Amazon account-management pages
- The system must allow searching or filtering books by title
- The system must support selecting multiple books for collection assignment
- The system must allow entering a target collection name
- The system must store or generate the intended mapping between collection names and selected books
- The system should support a dry-run mode that shows intended actions before any write operation
- The system should log sync attempts and outcomes for debugging
- The system should support re-running a sync after failures

## Non-Functional Requirements

- The system should be simple to run locally
- The system should prioritize maintainability over cleverness
- The system should avoid destructive actions when data is uncertain
- The system should be observable enough to debug changes in Amazon behavior
- The system should handle large libraries without becoming unusably slow
- The system should not require a separately installed database server for the first version

## Constraints

- Amazon does not provide a known official public API for personal Kindle collection management
- Any integration with Kindle may depend on reverse-engineered web flows or local metadata
- Amazon web flows may change without notice
- Authentication and session handling may be fragile
- The project should run locally in a personal development environment
- Purchased books and personal documents may exist on separate Amazon pages and require merged import logic

## Assumptions

- Amazon account-management pages expose enough data to discover both purchased books and personal documents
- A browser-based automation path is more realistic than a stable direct API integration
- Collection synchronization may be possible indirectly through the same web flows used by Amazon's UI
- Some operations may require a logged-in browser session
- SQLite is sufficient for the first version of local storage because it is built into Python

## Risks

- Amazon changes web requests or anti-bot protections
- Collection write actions may be harder than library read actions
- Matching books by title alone may be ambiguous
- Session expiration may make automation unreliable
- Device sync behavior may not happen immediately or consistently
- Purchased books and personal documents may expose different metadata shapes that require normalization

## Open Questions

- What Kindle web endpoints or UI actions expose collection management?
- Can library data be pulled more reliably from local Kindle state than from the web?
- What unique identifier is best for matching books: title, ASIN, author, or a combination?
- Does creating a collection through the web always sync to all Kindle devices?
- Should the first interaction model be a CLI only, or later include a minimal local UI?
- What metadata is available from the Amazon purchased-books page versus the personal-documents page?

## Success Criteria

- The tool can import or read the user's Kindle book list
- The user can select multiple books and assign them to a desired collection
- The tool can produce a correct, reviewable action plan
- At least one end-to-end sync path works for personal use, even if it is experimental
- The process is meaningfully faster than manual Kindle collection editing
