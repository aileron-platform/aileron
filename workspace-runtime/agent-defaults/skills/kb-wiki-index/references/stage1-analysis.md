# Stage 1 — Source Analysis

Read each source file in `raw/sources/` that has not been processed yet (or that has changed since last ingest), and produce a structured analysis.

## What to produce

For each source, answer these questions:

1. **Summary**: What is the source about? (2-4 sentences)
2. **Key entities**: What named things appear? (people, organisations, tools, datasets)
3. **Key concepts**: What ideas, techniques, or frameworks are discussed?
4. **Connections**: Does this source contradict, confirm, or extend existing wiki pages?
5. **Source type**: Is this a paper, article, meeting note, data file, web clip, etc.?
6. **Action plan**: Which wiki pages should be created or updated based on this source?
   - Always include `wiki/sources/<slug>.md` (source summary page)
   - List any entity or concept pages to create or update
   - Note any updates needed in `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`

## How to handle unreadable sources

If a source file cannot be read (binary, corrupted, encrypted), do not stop. Continue with other sources and emit a `---REVIEW: unreadable_source---` block for the unreadable file.

## Output

The analysis is for your internal context only. Do NOT emit the analysis as output — emit FILE and REVIEW blocks only (see Stage 2 and review-blocks.md).
