---
name: aileron-web-canvas-review
description: Process Aileron Web Canvas review notes that reference selected rendered elements, multi-element selections, or selected areas, then sync and re-announce the canvas through the aileron-web-canvas contract. Use when a prompt includes a Canvas review note id, route path, target context, and edit instruction.
license: MIT
metadata:
  author: aileron
  version: "1.0"
---

# Aileron Web Canvas Review Workflow

Use this workflow when the user sends a Canvas review request from Aileron Web Canvas. This skill shares the `aileron-web-canvas` contract: edits land under `/workspace`, the canvas is declared by `/workspace/.aileron/canvas.json`, and the canvas artifact is synced and announced through the Aileron MCP tools instead of leaving preview refresh to the user.

## Rules

- Treat the persisted workspace files under `/workspace` as the source of truth.
- Do not treat iframe DOM edits, browser devtools edits, or injected overlay changes as persistent work.
- Preserve the repository's i18n rules. Do not hard-code new user-facing Chinese or English strings in frontend or backend code when an i18n key path exists or should be added.
- Use the review note id in your final response so the user can connect the work back to the Canvas note.
- Prefer stable source changes that explain the rendered selector context instead of patching generated build artifacts.
- If the selected target cannot be mapped to source confidently, inspect the route and ask for a narrower instruction only when necessary.
- Follow the Canvas edit instruction flow: edit `/workspace` source files, preserve i18n requirements, and never treat iframe DOM changes as persistent state.
- After finishing an edit, sync the canvas renderer yourself instead of only telling the user to click Sync: send a `POST` request to `$AILERON_CANVAS_API_URL/sync` (this is the same endpoint the Web Canvas toolbar Sync action calls).
- Re-announce the canvas by calling `mcp__aileron__show_canvas_artifact` with the reviewed route, matching the `aileron-web-canvas` ending contract.
- If the Canvas tab was already open before this edit, its iframe does not auto-reload from a background sync; tell the user to use the toolbar Sync action if the preview still looks stale after the announcement.

## Steps

1. Read the Canvas review prompt for `noteId`, `routePath`, `targetType`, selector or area context, previews, and the user instruction.
2. Inspect `/workspace` source files that render the requested route.
3. Make the smallest source change that satisfies the instruction.
4. Add or update i18n keys for any user-facing text changes.
5. Run the relevant project checks when available in the container.
6. `POST` to `$AILERON_CANVAS_API_URL/sync` to rebuild or reuse the canvas renderer for the edited route.
7. Call `mcp__aileron__show_canvas_artifact` with `title` and the reviewed `route` to re-announce the canvas.
8. Summarize changed files, mention the review note id, note that the toolbar Sync action can also be used if an already-open preview looks stale, then ask whether the note should be marked applied.
