# REVIEW Block Format

Emit a REVIEW block when something needs human attention: a contradiction, an unreadable source, a suggested follow-up, etc.

## Format

```
---REVIEW: <type>, <page-path>, <one-line-detail>---
<optional multi-line context>
---END REVIEW---
```

- `<type>`: one of the six types below.
- `<page-path>`: the wiki page (or raw source path) that is most relevant. Use `raw/sources/foo.pdf` for unreadable sources.
- `<one-line-detail>`: a brief human-readable description of the issue.
- Optional multi-line context after the opening delimiter gives more detail (quoted passages, conflicting claims, etc.).

## Review types

| type | when to use |
|------|-------------|
| `contradiction` | Two sources or wiki pages make conflicting claims. |
| `duplicate` | This source appears to cover the same ground as an existing wiki page. |
| `missing_page` | A key entity or concept was mentioned but has no dedicated wiki page yet. |
| `suggestion` | A cross-reference, synthesis, or follow-up that would improve the wiki. |
| `confirm` | You are uncertain about a claim and want the user to verify it before filing. |
| `unreadable_source` | A raw source file could not be read (binary, corrupted, encrypted). |

## Examples

```
---REVIEW: contradiction, wiki/concepts/scaling-laws.md, Source A claims accuracy improves with scale; Source B argues it plateaus after 70B parameters---
Source A (wei-2022-cot.md, p. 4): "Scaling consistently improves performance across all tasks."
Source B (hoffmann-2022-chinchilla.md, p. 12): "Beyond 70B parameters, compute efficiency drops sharply."
---END REVIEW---
```

```
---REVIEW: unreadable_source, raw/sources/encrypted.pdf, File could not be read — possibly password-protected---
---END REVIEW---
```

```
---REVIEW: missing_page, wiki/entities/openai.md, Sam Altman mentioned frequently but has no dedicated entity page---
---END REVIEW---
```

## Limit

Emit at most 100 REVIEW blocks per ingest run. If more issues exist, consolidate the most important ones and note the cap in a `suggestion` block.
