# Wiki Schema

## Required Frontmatter

```yaml
---
title: Page title
type: overview
sources: []
---
```

## Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| overview | wiki/ | High-level summary (wiki/overview.md) |
| entity | wiki/entities/ | Named things: people, tools, organisations, datasets |
| concept | wiki/concepts/ | Ideas, techniques, phenomena, frameworks |
| source | wiki/sources/ | Papers, articles, talks, books, blog posts |
| query | wiki/queries/ | Open questions under active investigation |
| synthesis | wiki/synthesis/ | Cross-cutting summaries and conclusions |
| comparison | wiki/comparisons/ | Side-by-side analysis of related entities |

## Naming Conventions

- Files: `kebab-case.md`
- Entities: match official name where possible (e.g., `openai.md`)
- Concepts: descriptive noun phrases (e.g., `chain-of-thought.md`)
- Sources: `author-year-slug.md` (e.g., `wei-2022-cot.md`)

## Cross-referencing

- Use `[[page-slug]]` syntax to link between wiki pages
- Every entity and concept should appear in `wiki/index.md`
