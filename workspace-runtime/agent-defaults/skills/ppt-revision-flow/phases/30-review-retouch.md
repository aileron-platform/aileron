# Phase 30 — Review and retouch

Build revision review from the current final page mapping:

```bash
python3 assets/canvas/build.py --phase=revision \
  --workspace /workspace \
  --session-id <YYYY-MM-DD-title-slug> \
  --revision-id <revision-id> \
  --asset-mode reference \
  --image-list /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json \
  --print-artifact
```

Use pasted `review-shell-v2` feedback exactly like the original review flow. Render markup locally, then use image edit or page regeneration for the selected slides. Do not patch final page visuals with deterministic overlays unless the user explicitly asks for that workaround.

Load the shared `references/subagent-generation-runtime.md` from `ppt-design-flow` before image retouch or page regeneration. Apply its explicit user authorization gate first. If authorization is missing, you must ask for authorization by using the shared subagent authorization question tool before dispatch. If authorization is denied or subagents are unavailable, stop the revision image work. All retouch/regeneration, including one selected page, must dispatch bounded single-image subagent workers with one selected page id, the current revision request, marked review image paths, continuity anchors, and one final-page adoption target. Spawn every image worker with `fork_context:false`. The main thread must never generate or edit revised page images directly.

Workers must call image generation/editing at most once and adopt exactly one revised image as a `final-page` asset before reporting success. Workers must write metadata to file-backed state and finish with one short user-safe sentence only. Worker final messages must not include JSON, internal paths, base64 payloads, data URLs, markdown image embeds, raw `imageGeneration` results, or raw `image_generation_call` results. Record every dispatch and accepted/rejected result in `subagent-runs.json`.

Worker metadata is internal. Follow the root `Internal JSON translation prompt`: do not paste worker JSON, raw worker summaries, adoption JSON, manifest update JSON, internal paths, manifests, or adopted-path lists into chat. Follow the root `User-facing language guardrail`: normal replies contain only the user-visible outcome, the next action, and the decision the user can make.

There is no single-page direct-generation exception. When exactly one selected page is being edited, dispatch one bounded single-image worker for that page and require immediate adoption into `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/`.

When asking whether the revised pages are approved, use the root `Structured question tool rule`:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-revision-approval",
  "title": "請確認修訂結果",
  "questions": [
    {
      "id": "revision_status",
      "label": "修訂結果",
      "type": "radio",
      "options": [
        "通過，準備重新匯出",
        "需要再修改，我會貼上審閱回饋"
      ],
      "required": true
    }
  ]
}
```
```
