# Revision Runtime

`ppt-revision-flow` uses the shared runtime in the sibling skill directory (`../../ppt-design-flow/` relative to this file).

Shared files:

- `assets/stage_state.py`
- `scripts/stage.py`
- `assets/canvas/build.py`
- `scripts/adopt_imagegen_output.py`
- `scripts/render_review_markup.py`
- `scripts/build_pptx_deck.py`
- `scripts/build_html_deck.py`
- `references/subagent-generation-runtime.md`

Shared session state:

```text
/workspace/.aileron/canvases/ppt-design-flow/<session-id>/
```

The current final export input is always `generation/final-pages.json`.

## Subagent Revision Resume

Use bounded single-image subagent workers for all image retouch and regeneration after explicit user authorization, including one selected page. Every image worker must use `fork_context:false`, call image generation/editing at most once, adopt exactly one revised page image, write orchestration metadata only to file-backed state, and finish with one short user-safe sentence. Worker final messages must not contain JSON or internal paths. If authorization is missing, you must ask for authorization by using the shared subagent authorization question tool before dispatch. If authorization is denied or subagents are unavailable, stop revision image work. Resume revision work from file-backed state, not chat history:

1. Read selected page ids from the active revision state.
2. Match those page ids against the current revision request.
3. Read `generation/final-pages.json`, `imagegen-assets.json`, and `subagent-runs.json` when it exists from prior dispatches.
4. Verify that referenced adopted files still exist under `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/`.
5. Keep revised pages whose state entry and adopted files are valid for the current revision request.
6. Dispatch one bounded single-image subagent worker per selected page id that is missing, failed, or stale.
7. Record every worker dispatch and accepted/rejected result in `subagent-runs.json`.

There is no single-page direct-generation exception. All revision paths follow the shared forbidden-output rules: no base64 payloads, data URLs, markdown image embeds, raw `imageGeneration` results, or raw `image_generation_call` results.
