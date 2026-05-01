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

### Stage 2 — Generation

Using the Stage 1 analysis as context, write wiki pages using FILE blocks. See `references/stage2-generation.md` for the generation prompt and FILE block format.

### Stage 3 — Review Blocks

After generating wiki pages, emit REVIEW blocks for any ambiguities, contradictions, unreadable sources, or suggestions that need human attention. See `references/review-blocks.md` for the format.

## Output Contract

The skill output MUST contain only:

1. Zero or more `---FILE:---` blocks (wiki page content).
2. Zero or more `---REVIEW:---` blocks (human-attention items).
3. No other prose, preamble, or commentary outside these blocks.

Start immediately with the first FILE or REVIEW block. Do not add any introduction.

## Frontmatter

Every wiki page MUST include valid YAML frontmatter. See `references/frontmatter.md` for required fields.

## Steps

1. Read `AGENTS.md`, `purpose.md`, and `schema.md`.
2. Read `wiki/index.md` and `wiki/overview.md` for current wiki state.
3. List all files under `raw/sources/` to identify sources to process.
4. For each unprocessed or changed source: run Stage 1 analysis (see `references/stage1-analysis.md`).
5. Using the analysis: run Stage 2 generation, emitting FILE blocks (see `references/stage2-generation.md`).
6. Emit REVIEW blocks for any flagged items (see `references/review-blocks.md`).
7. Emit a FILE block for `wiki/index.md`, `wiki/log.md`, and `wiki/overview.md` with updated content.
