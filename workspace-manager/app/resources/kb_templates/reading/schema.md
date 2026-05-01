# Wiki Schema — Reading a Book

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
| overview | wiki/ | High-level book summary |
| entity | wiki/entities/ | Named things: settings, objects, events |
| concept | wiki/concepts/ | Ideas, motifs, symbolic threads |
| source | wiki/sources/ | Reference material and research |
| query | wiki/queries/ | Open questions and unresolved plot threads |
| synthesis | wiki/synthesis/ | Cross-cutting analysis and conclusions |
| comparison | wiki/comparisons/ | Side-by-side analysis |
| character | wiki/characters/ | People and figures in the book |
| theme | wiki/themes/ | Recurring ideas, motifs, symbolic threads |
| plot-thread | wiki/plot-threads/ | Storylines or narrative arcs being tracked |
| chapter | wiki/chapters/ | Per-chapter notes and summaries |

## Naming Conventions

- Characters: character name in kebab-case (e.g., `elizabeth-bennet.md`)
- Themes: thematic noun phrase (e.g., `social-class-mobility.md`)
- Plot threads: arc description (e.g., `darcys-redemption-arc.md`)
- Chapters: `ch-NN-slug.md` (e.g., `ch-01-opening-scene.md`)

## Additional Frontmatter

Character pages:
```yaml
first_appearance: "Ch. N"
role: protagonist | antagonist | supporting | minor
```

Chapter pages:
```yaml
chapter: N
pages: "1-24"
```
