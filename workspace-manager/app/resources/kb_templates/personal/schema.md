# Wiki Schema — Personal Growth

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
| overview | wiki/ | High-level personal wiki summary |
| entity | wiki/entities/ | Named things: people, places, tools |
| concept | wiki/concepts/ | Ideas, principles, frameworks |
| source | wiki/sources/ | Articles, books, podcast notes |
| query | wiki/queries/ | Open questions under exploration |
| synthesis | wiki/synthesis/ | Cross-cutting insights |
| comparison | wiki/comparisons/ | Side-by-side analysis |
| goal | wiki/goals/ | Specific outcomes you are working toward |
| habit | wiki/habits/ | Recurring behaviours and their tracking |
| reflection | wiki/reflections/ | Periodic reviews and lessons learned |
| journal | wiki/journal/ | Freeform daily or session entries |

## Additional Frontmatter

Goal pages:
```yaml
target_date: YYYY-MM-DD
status: active | paused | achieved | abandoned
progress: 0-100
```

Habit pages:
```yaml
frequency: daily | weekly | monthly
status: active | paused | dropped
```
