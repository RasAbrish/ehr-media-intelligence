# CLAUDE.md

@AGENTS.md

Claude Code specifics on top of `AGENTS.md`.

## Session start

1. Read `AGENTS.md`, then the docs it lists for the current phase.
2. Enter plan mode. Restate the phase acceptance criteria from `docs/01-SPEC.md`, list files to create or change, list tests to write. Wait for approval.
3. Implement test first. Run `make check` and `make security`. Use the code-review plugin, and for phases 4 to 6 also run `/security-review`, before the squash commit.
4. For phase 3 and any prompt change, run `make eval` and paste the before/after metrics into the commit body.

## Helpers to install once

| Helper | Command | Use |
|---|---|---|
| frontend-design (Anthropic) | `/plugin install frontend-design@claude-plugins-official` | Distinctive UI, avoids generic AI look |
| context7 | `/plugin install context7@claude-plugins-official` | Current docs for fhir.resources, chromadb, TanStack v9, shadcn v4 |
| code-review | `/plugin install code-review@claude-plugins-official` | Review each phase |
| shadcn MCP | `pnpm dlx shadcn@latest mcp init --client claude` (run in `frontend/`) | Browse and add components |
| Playwright MCP | `claude mcp add playwright -- npx @playwright/mcp@latest` | Screenshots for visual QA |
| getdesign refs | `npx getdesign@latest add linear.app` and `npx getdesign@latest add vercel.com` into `docs/design-refs/` | Reference only. `docs/06-UI-DESIGN.md` wins on conflict |

## Subagent use

- Use an Explore subagent for wide searches across the repo; keep the main context for implementation.
- For phases 3 and 5, run an independent review subagent that has not seen the implementation: give it the relevant spec sections and ask it to find gaps against the acceptance criteria.

## UI work

Read `docs/06-UI-DESIGN.md`, use the frontend-design skill and the shadcn MCP. Build tokens first, then primitives, then screens. After each screen, screenshot at 390, 1024 and 1440 px in light and dark with the Playwright MCP and fix issues before moving on.

## Never

- Edit generated shadcn files beyond theming.
- Change an endpoint without updating `docs/04-API-CONTRACT.md` first.
- Call the real Claude API in tests.
- Commit `data/generated/`, `.env`, `*.db`, Chroma dirs, model caches.
