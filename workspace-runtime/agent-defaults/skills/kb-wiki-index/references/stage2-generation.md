# Stage 2 — Wiki Page Generation

Using the Stage 1 analysis as context, generate wiki pages as FILE blocks.

## FILE Block Format

```
---FILE: wiki/sources/example.md---
<full file content including YAML frontmatter>
---END FILE---
```

Rules:
- The path after `---FILE:` MUST be relative to the KB root.
- The path MUST start with `wiki/` — no other prefix is allowed.
- No `..` segments. No absolute paths. No paths starting with `/`.
- Always include valid YAML frontmatter (see `references/frontmatter.md`).
- One FILE block per wiki page. Do not split a page across multiple blocks.

## What to generate

For each processed source, always generate at minimum:

1. `wiki/sources/<slug>.md` — source summary page.
2. Update any relevant `wiki/entities/<slug>.md` pages (create if missing).
3. Update any relevant `wiki/concepts/<slug>.md` pages (create if missing).

Always generate at the end:

4. `wiki/index.md` — updated table of contents.
5. `wiki/log.md` — append today's ingest entry.
6. `wiki/overview.md` — updated high-level wiki summary.

## Do NOT

- Emit analysis prose outside FILE/REVIEW blocks.
- Emit preamble such as "Here are the files:" or "Based on the analysis...".
- Write to paths outside `wiki/`.
- Omit frontmatter from any wiki page.
