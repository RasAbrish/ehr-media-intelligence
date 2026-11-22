# ADR-010: Use TanStack Router with validated search params

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

A search, its filters and the open patient must survive a reload and be shareable as a link. URL values are untrusted and hand-editable.

## Decision

Use TanStack Router. Each route has a `validateSearch` function that returns a typed object. The parsers use the Zod enums and date checks where they apply and drop an invalid value instead of failing the page (`features/search/search-params.ts`).

## Alternatives rejected

- **React Router.** Its search params are untyped strings.
- **Strict Zod parsing of the whole URL.** One bad parameter would replace the page with an error.

## Consequences

- Links, reload, Back and Forward restore the screen, and navigation is checked by TypeScript.
- A bad value disappears without a message.
- Search text is part of the browser URL and history, so a patient name typed there stays in history. The servers leave query strings out of their logs.
