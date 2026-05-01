# Required Frontmatter

Every wiki Markdown page MUST begin with a valid YAML frontmatter block.

## Minimum required fields

```yaml
---
title: Human-readable page title
type: <page-type>
sources: []
---
```

- `title`: non-empty string, human-readable.
- `type`: one of the types defined in the KB's `schema.md`.
- `sources`: list of raw source paths that contributed to this page (may be empty for index/log/overview).

## Common page types (base schema)

| type | directory |
|------|-----------|
| overview | wiki/ |
| entity | wiki/entities/ |
| concept | wiki/concepts/ |
| source | wiki/sources/ |
| query | wiki/queries/ |
| synthesis | wiki/synthesis/ |
| comparison | wiki/comparisons/ |

Template-specific types (e.g., `decision`, `character`, `thesis`) are defined in each KB's `schema.md`. Check `schema.md` before writing template-specific pages.

## Extended frontmatter

Source summary pages should also include:

```yaml
---
title: "Author Year: Title"
type: source
sources:
  - raw/sources/filename.pdf
authors: []
year: YYYY
url: ""
---
```

## Enforcement

Pages with missing or invalid frontmatter will be flagged by the structural lint check. The backend validates that `title`, `type`, and `sources` are present on every wiki page after ingest.
