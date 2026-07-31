# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't create them speculatively. The
`domain-modeling` skill creates or sharpens them when canonical meanings or qualifying decisions
actually resolve.

## File structure

Knora currently has a single context and therefore uses one root `CONTEXT.md`. Introduce a
`CONTEXT-MAP.md` only when multiple lifecycle owners are demonstrated.

## Use the glossary's vocabulary

When output names a domain concept, use the term defined in `CONTEXT.md`. If a needed concept is
missing, record the gap for `domain-modeling` rather than silently introducing a synonym.

## Flag ADR conflicts

If output contradicts an existing ADR, surface the conflict explicitly rather than silently
overriding it.

