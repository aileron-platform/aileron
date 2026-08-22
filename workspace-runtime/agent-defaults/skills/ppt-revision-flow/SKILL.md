---
name: ppt-revision-flow
description: Revise one or more pages in a completed PPT deck created by ppt-design-flow. Use when the user asks to modify an already completed deck, fix a specific slide, regenerate selected pages, retouch reviewed output, or re-export a revised PPTX/HTML deck.
---

# PPT Revision Flow

Use this skill for completed deck revision. It is not a new deck creation flow.

`ppt-revision-flow` shares the `ppt-design-flow` runtime. The active session, state, page image mapping, review shell, image adoption helpers, and deck builders live under:

```text
/workspace/.aileron/canvases/ppt-design-flow/<session-id>/
```

The shared runtime commands are executed from the sibling `ppt-design-flow` skill directory (`../ppt-design-flow/` relative to this skill).

Image retouch and regeneration reuse the shared subagent runtime in `references/subagent-generation-runtime.md`. Every revision image edit or regeneration, including a single page, MUST use bounded single-image subagent workers after explicit user authorization. Each image worker must use `fork_context:false`, call image generation/editing at most once, adopt exactly one revised page image, write orchestration metadata only to file-backed state, and finish with one short user-safe sentence. Worker final messages must not include JSON, internal paths, base64 payloads, data URLs, markdown image embeds, raw `imageGeneration` results, or raw `image_generation_call` results. If authorization is missing or denied, the revision flow must use the shared subagent authorization question tool and stop when authorization is not granted. The main thread must never generate or edit revised page images directly.

## User-facing language guardrail

Use the same `ppt-design-flow` User-facing language guardrail for every normal reply:

> Can the user see it, choose it, or act on it? If not, keep it internal.

Normal user-facing replies should contain only the user-visible outcome, the next action, and the decision the user can make. implementation details are internal unless the user explicitly asks for debugging or exact commands. Do not explain tools, file paths, data structures, runtime state, worker metadata, or orchestration steps in normal chat.

worker metadata is internal. Do not paste worker JSON, raw worker summaries, internal paths, manifests, or adopted-path lists into chat. Summarize revision completion in user-facing prose, for example: `已完成指定頁面的修改，審閱頁已更新，你可以再檢查一次，滿意後用下方表單確認通過。`

### Internal JSON translation prompt

Use this prompt before sending any normal chat reply:

> Does this look like an internal JSON object? If yes, translate it into a user-facing sentence and do not paste the JSON.

This applies to worker results, adoption results, manifest updates, mapping updates, and command output shaped like JSON. Objects with keys such as `session_id`, `mode`, `updated_pages`, `manifest_updated`, `adopted_path`, `path`, `slot`, `operation`, or `errors` are internal unless the user explicitly asks for debug output.

Example internal object shape to translate, not paste: `mode: final single-candidate`, `updated_pages`, `manifest_updated`.

User-facing rewrite example: `已完成 S09 和 S10 的更新，審閱頁已準備好，你可以再檢查一次，滿意後用下方表單確認通過。`

## Structured question tool rule

Use `mcp__aileron__ask_user_question` for every user-facing question, confirmation, authorization, or small explicit option set. After calling the tool, end the turn immediately with no assistant prose.

Use question tools for:

- Subagent authorization when image retouch/regeneration needs delegated workers.
- Revision approval when the user is choosing whether revised pages are approved.
- Output format selection when revision re-export needs the user to choose `.pptx`, `HTML 簡報`, or `兩者都要`.

Do not use question tools for free-form revision feedback, slide annotations, pasted review payloads, debugging, or cases where the user already gave a clear answer. In those cases, use normal chat or the review page. Do not ask plain prose questions as a fallback for these excluded cases; state the next action or instruction instead.

## Scope

Revision mode is for existing-slide visual changes in a completed deck. It can revise one page or multiple pages in one round.

It does not add, delete, reorder, or re-plan slides. If the user asks for page count, order, or narrative structure changes, explain that the request is outside revision mode and should return to the new-deck/planning workflow.

## Entry Procedure

1. Resume or list completed sessions:

   ```bash
   python3 scripts/stage.py list --all --workspace /workspace
   python3 scripts/stage.py resume <query> --workspace /workspace
   ```

2. Confirm the target session has passed `review_approved`.

3. Enter revision mode. If pages are known, pass them as JSON:

   ```bash
   python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace --pages '["S03"]'
   ```

   Without explicit pages:

   ```bash
   python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
   ```

## Revision Review

Build the revision review surface from the current final page mapping:

```bash
python3 assets/canvas/build.py --phase=revision \
  --workspace /workspace \
  --session-id <YYYY-MM-DD-title-slug> \
  --revision-id <revision-id> \
  --asset-mode reference \
  --image-list /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json \
  --print-artifact
```

The revision review surface uses the existing `review-shell-v2` feedback format. When the user pastes feedback, save it under the active revision directory and use the shared marked-image renderer before retouching or regenerating selected pages.

## Page Adoption

For any revision image edit/regeneration, dispatch bounded single-image subagent workers with one selected page id, current revision request, marked review references, and one final-page adoption target. Each worker must immediately adopt exactly one revised file before reporting success.

There is no single-page direct-generation exception. If only one page is selected, dispatch one bounded single-image worker for that page. If multiple pages are selected, dispatch one worker per revised page. Spawn every image worker with `fork_context:false` and record dispatch/result status in `subagent-runs.json`. If subagents cannot be used, stop the revision image work.

Adopt revised page images as `final-page` assets with the original slide id:

```bash
python3 scripts/adopt_imagegen_output.py \
  --source <path-from-imagegen> \
  --workspace /workspace \
  --session-id <YYYY-MM-DD-title-slug> \
  --slot final-page \
  --name S03-rev001.png \
  --slide-id S03
```

This updates only the selected slide entry in `generation/final-pages.json`. Older image files may remain on disk, but final exports use only the current mapping.

## Completion And Re-export

When the revised pages are approved through the revision approval question tool:

```bash
python3 scripts/stage.py complete-revision --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

If `output_formats` is already set, rerun those final builders. If it is empty, use the existing output question tool for `.pptx`, `HTML 簡報`, or `兩者都要`.

Use the shared builders:

```bash
python3 scripts/build_pptx_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
python3 scripts/build_html_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
```
