# Wiki Schema — Business / Team

## Required Frontmatter

```yaml
---
title: Page title
type: concept
sources: []
---
```

## Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| overview | wiki/ | High-level business wiki summary |
| entity | wiki/entities/ | Named things: people, teams, organisations, systems |
| concept | wiki/concepts/ | Ideas, techniques, business terms |
| source | wiki/sources/ | Documents, reports, articles |
| query | wiki/queries/ | Open questions under investigation |
| synthesis | wiki/synthesis/ | Cross-cutting summaries and conclusions |
| comparison | wiki/comparisons/ | Side-by-side analysis |
| decision | wiki/decisions/ | Architectural or strategic decisions (ADR-style) |
| project | wiki/projects/ | Project briefs, status, and retrospectives |
| meeting | wiki/meetings/ | Meeting notes, agendas, and action items |
| stakeholder | wiki/stakeholders/ | People, teams, and organisations involved |

## Naming Conventions

- Meetings: `YYYY-MM-DD-slug.md` (e.g., `2026-03-15-sprint-planning.md`)
- Decisions: `NNN-slug.md` (e.g., `001-adopt-typescript.md`)
- Projects: descriptive slug (e.g., `payments-redesign.md`)

## Additional Frontmatter

Decision pages:
```yaml
status: proposed | accepted | deprecated | superseded
deciders: []
date: YYYY-MM-DD
```

Project pages:
```yaml
status: planned | active | on-hold | complete | cancelled
owner: ""
start_date: YYYY-MM-DD
target_date: YYYY-MM-DD
```

Meeting pages:
```yaml
date: YYYY-MM-DD
attendees: []
action_items: []
```
