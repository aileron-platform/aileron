# Wiki Schema — Research Deep-Dive

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
| overview | wiki/ | High-level project summary |
| entity | wiki/entities/ | Named things: people, tools, organisations, datasets |
| concept | wiki/concepts/ | Ideas, techniques, phenomena, frameworks |
| source | wiki/sources/ | Papers, articles, talks, books, blog posts |
| query | wiki/queries/ | Open questions under active investigation |
| synthesis | wiki/synthesis/ | Cross-cutting summaries and conclusions |
| comparison | wiki/comparisons/ | Side-by-side analysis of related entities |
| thesis | wiki/thesis/ | Working hypothesis and its evolution over time |
| methodology | wiki/methodology/ | Research methods, protocols, and study designs |
| finding | wiki/findings/ | Individual empirical results or observations |

## Naming Conventions

- Files: `kebab-case.md`
- Theses: hypothesis as slug (e.g., `scaling-improves-reasoning.md`)
- Methodologies: method name (e.g., `systematic-review.md`)
- Findings: descriptive slug (e.g., `larger-models-better-few-shot.md`)
- Sources: `author-year-slug.md`

## Additional Frontmatter

Thesis pages:
```yaml
confidence: low | medium | high
status: speculative | supported | refuted | settled
```

Finding pages:
```yaml
source: "[[source-slug]]"
confidence: low | medium | high
replicated: true | false | null
```
