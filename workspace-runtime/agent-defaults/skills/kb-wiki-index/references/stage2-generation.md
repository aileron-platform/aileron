# Stage 2 — Wiki Page Generation

Using the Stage 1 analysis as context, generate wiki pages and write them to disk.

## Write Contract

Use Write or Edit for each generated page. The file path passed to the tool MUST be inside the KB working directory.

Example target:

`<KB_ROOT>/wiki/sources/example.md`

Rules:
- The relative path MUST start with `wiki/` — no other prefix is allowed.
- No `..` segments. No absolute paths from generated relative paths.
- Always include valid YAML frontmatter (see `references/frontmatter.md`).
- Write the full page content in one operation whenever possible.
- Create parent directories before writing new pages.

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

- Only print generated pages without writing them.
- Emit `---FILE:---` blocks as the final result.
- Emit preamble such as "Here are the files:" or "Based on the analysis...".
- Write to paths outside `wiki/`.
- Omit frontmatter from any wiki page.
