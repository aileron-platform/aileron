---
name: canvas-review
description: Process Web Canvas review notes that reference selected rendered elements, multi-element selections, or selected areas. Use when a prompt includes a Canvas review note id, route path, target context, and edit instruction.
license: MIT
---

# Canvas Review Workflow

Use this workflow when the user sends a Canvas review request from Web Canvas.

## Rules

- Treat the persisted workspace files under `/workspace` as the source of truth.
- Do not treat iframe DOM edits, browser devtools edits, or injected overlay changes as persistent work.
- Preserve the repository's i18n rules. Do not hard-code new user-facing Chinese or English strings in frontend or backend code when an i18n key path exists or should be added.
- Use the review note id in your final response so the user can connect the work back to the Canvas note.
- Prefer stable source changes that explain the rendered selector context instead of patching generated build artifacts.
- If the selected target cannot be mapped to source confidently, inspect the route and ask for a narrower instruction only when necessary.
- After source edits, tell the user to use the existing Web Canvas Sync or Reload toolbar action if they need to verify the preview before marking the note applied.

## Steps

1. Read the Canvas review prompt for `noteId`, `routePath`, `targetType`, selector or area context, previews, and the user instruction.
2. Inspect `/workspace` source files that render the requested route.
3. Make the smallest source change that satisfies the instruction.
4. Add or update i18n keys for any user-facing text changes.
5. Run the relevant project checks when available in the container.
6. Summarize changed files and mention the review note id.
7. Mention that the existing Web Canvas Sync or Reload toolbar action can be used for preview verification, then ask whether the note should be marked applied.
