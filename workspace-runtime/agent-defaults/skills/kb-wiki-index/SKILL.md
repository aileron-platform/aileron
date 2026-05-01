---
name: kb-wiki-index
description: Index a Team Wiki knowledge base. Use when prompted with "Run the kb-wiki-index skill" along with a working directory under /knowledge/<mount_alias>.
license: MIT
---

# KB Wiki Index Workflow

Use this skill when asked to index or update a Team Wiki knowledge base mounted at `/knowledge/<alias>`.

## Working Directory Contract

All operations must stay within the working directory provided in the prompt (e.g., `/knowledge/my-kb`).

- Read source material from `raw/sources/` and `raw/assets/`.
- Write wiki pages only under `wiki/`.
- Read `AGENTS.md`, `purpose.md`, and `schema.md` before editing anything.
- Never delete files in `raw/`.
- Never write outside the KB working directory.

For path safety rules see `references/safe-paths.md`.

## Flow

### Stage 1 — Analysis

Read the KB context and source files, then produce a structured analysis. See `references/stage1-analysis.md` for the full analysis prompt.

### Stage 2 — Generation And File Writes

Using the Stage 1 analysis as context, generate wiki page content and immediately write it to disk with the Write or Edit tool. See `references/stage2-generation.md` for page planning and safe path rules.

### Stage 3 — Review Blocks

After writing wiki pages, emit REVIEW blocks for any ambiguities, contradictions, unreadable sources, or suggestions that need human attention. See `references/review-blocks.md` for the format.

## Output Contract

The skill MUST persist wiki updates to files under the KB working directory. Do not only print generated content.

1. Use Write or Edit to create or update every generated wiki page.
2. Write only under `wiki/` inside the KB working directory.
3. After all writes complete, output zero or more `---REVIEW:---` blocks for human-attention items.
4. If there are no review items, output a single short completion line: `KB wiki index updated.`

Do not output `---FILE:---` blocks as the final result. FILE blocks are not applied by the runtime.

## Frontmatter

Every wiki page MUST include valid YAML frontmatter. See `references/frontmatter.md` for required fields.

## Steps

1. Read `AGENTS.md`, `purpose.md`, and `schema.md`.
2. Read `wiki/index.md` and `wiki/overview.md` for current wiki state.
3. List all files under `raw/sources/` to identify sources to process.
4. For each unprocessed or changed source: run Stage 1 analysis (see `references/stage1-analysis.md`).
5. Using the analysis: plan Stage 2 page generation (see `references/stage2-generation.md`).
6. Use Write or Edit to persist generated pages under `wiki/`.
7. Always write updated `wiki/index.md`, `wiki/log.md`, and `wiki/overview.md`.
8. Emit REVIEW blocks for any flagged items (see `references/review-blocks.md`).
