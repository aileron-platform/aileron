# Subagent Generation Runtime

Use this runtime whenever `ppt-design-flow` or `ppt-revision-flow` needs any `imagegen` / raster image generation or image editing: final slide generation, candidate generation, imagegen style preview, image retouching, page regeneration, or single-page revision. The goal is to keep the main orchestration thread small while bounded subagent workers perform exactly one image operation, immediately adopt the file-backed output into the active workspace session, and write compact metadata only to file-backed state.

## Non-negotiable subagent requirement

All `imagegen` / raster image-generation and image-editing work MUST be performed by bounded subagent workers. The main orchestration thread is allowed to plan prompts, prepare context, dispatch workers, validate worker metadata, verify adopted files, and publish canvas surfaces, but it MUST NOT call image-generation or image-editing tools directly.

If subagents are unavailable, unauthorized, denied by the user, fail to write file-backed metadata, or produce image files that cannot be adopted into the active `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/` tree, stop the workflow. Do not continue by generating images in the main thread. Do not use a "direct path" fallback. Do not mark preview or generation as ready until worker-adopted files exist in the session tree.

## Payload Containment Rule

Treat one `imagegen` / image-editing call as the maximum payload size for one worker session. This is mandatory because Codex session logs record raw image-generation payloads in the worker jsonl.

- Spawn one worker per generated or edited image.
- Set `fork_context:false` for every image worker. Never fork the full main conversation into an image worker.
- A worker MUST call image generation or image editing at most once.
- A worker MUST adopt exactly one output file before reporting `completed`.
- A worker MUST return only compact metadata for that one adopted file.
- Do not assign a preview set, candidate set, slide range, or multi-page revision batch to one worker.
- The main thread may dispatch multiple single-image workers in parallel, then aggregate their metadata from `wait_agent` results and file-backed manifests.
- If a worker needs to retry generation after a failed or unusable image, close that worker and spawn a new single-image worker for the retry. Do not perform a second image-generation call inside the same worker session.

## Authorization Gate

Subagent tool use requires explicit user authorization. Before image-heavy generation, candidate generation, multi-page retouch, or page regeneration, confirm that the user has explicitly asked for subagents, delegation, or parallel agent work in the current conversation.

If that authorization is missing, you must ask for authorization by using this question tool before any image generation work:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-subagent-authorization",
  "title": "請確認圖片產生方式",
  "questions": [
    {
      "id": "subagent_authorization",
      "label": "圖片產生方式",
      "type": "radio",
      "options": [
        "允許使用 subagent / parallel agents",
        "停止產圖流程"
      ],
      "required": true
    }
  ]
}
```
```

Do not start image generation while waiting for the answer. If the user authorizes subagents, dispatch bounded workers. If the user refuses or selects `停止產圖流程`, stop the workflow and explain that this skill cannot continue image generation without subagent workers.

## Worker Boundary

- Use bounded subagent workers for all final deck generation.
- Use bounded subagent workers for imagegen style preview generation; preview_mode=svg stays in the main thread because it does not create native image payloads.
- Assign exactly one final slide image to one worker.
- Assign exactly one candidate image to one worker in multi-candidate mode.
- Assign exactly one style-preview image to one worker. A style direction's `首頁 / 目錄頁 / 內容頁` preview set requires three separate workers.
- Assign exactly one revised page image to one worker for retouch or regeneration.
- The main agent prepares planning context, continuity anchors, output paths, and resume state; workers perform image generation, file discovery, adoption, and compact reporting.
- There is no single-page direct-generation exception.

## Worker Input

The worker input contract is:

Pass only the context needed for the assigned work:

- `session_id`: the active `<YYYY-MM-DD-title-slug>`.
- `mode`: `style-preview`, `final`, `candidate`, or `revision`.
- `slide_id`: exactly one final slide id, candidate slide id, or revision slide id.
- `preview_page_role`: exactly one of `cover`, `toc`, or `content`, required only for style-preview mode.
- `style_direction_id`: required only for style-preview mode.
- `candidate_id`: required only for candidate mode.
- `revision_id`: required only for revision mode.
- `workspace_root`: `/workspace`.
- `output_root`: `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/`.
- `continuity_anchor`: compact deck-level visual anchor from the approved design.
- `slide_blueprint_excerpt`: the content and layout intent for only the assigned slide or preview role.
- `style_references`: adopted workspace paths only; do not inline image content.
- `resume_state`: known adopted path, missing slide id, failed candidate slot, stale selected page id, or retry reason for this one image.

## Worker Completion Signal

Worker final messages may be visible in the user interface. Therefore the worker final message MUST be user-safe and must not contain internal orchestration data.

The worker completion contract is:

- The worker writes or lets adoption helpers write internal metadata to file-backed state: `imagegen-assets.json`, `generation/final-pages.json` when relevant, and `subagent-runs.json`.
- The worker final message is only one short user-safe sentence, for example: `已完成分配的單張圖片。`
- The worker final message MUST NOT contain JSON, object literals, arrays, code blocks, markdown tables, internal paths, manifest paths, `session_id`, `mode`, `slide_id`, `candidate_id`, `style_direction_id`, `preview_page_role`, `adopted_path`, `manifest_path`, or `errors`.
- The main thread MUST NOT parse worker final messages for orchestration data.
- The main thread MUST validate completion only from file-backed state: `subagent-runs.json`, `imagegen-assets.json`, candidate mapping, and `generation/final-pages.json`.

For failures, the worker final message is still user-safe and short, for example: `這張圖片未完成，已記錄失敗狀態。` Store short technical error details only in `subagent-runs.json`.

The main agent may read file-backed metadata, validate adopted files, update state, and decide what to do next. Do not paste worker JSON, object literals, raw worker summaries, adoption JSON, manifest update JSON, or `wait_agent` payloads into the user-facing chat. Follow the root `Internal JSON translation prompt`. Summarize completion in user-facing prose, for example: `預覽頁已準備好，你可以比較每套方向的首頁、目錄頁、內容頁後選定風格。`

## Forbidden Output

Never place these values in chat replies, planning artifacts, mapping files, manifests, `subagent-runs.json`, worker final messages, or worker summaries:

- base64 image payloads
- data URL values
- markdown image embeds for generated images
- raw `imageGeneration` result payloads
- raw `image_generation_call` result payloads
- binary image content copied from an adopted file

Adopted workspace paths may appear only in internal file-backed state. They must not appear in worker final messages or normal user-facing replies.

## Adoption Requirement

Workers must adopt files before reporting success.

For final pages:

```bash
python3 scripts/adopt_imagegen_output.py \
  --source <path-from-imagegen> \
  --workspace /workspace \
  --session-id <session-id> \
  --slot final-page \
  --name <slide-id>.png \
  --slide-id <slide-id>
```

For candidates:

```bash
python3 scripts/adopt_imagegen_output.py \
  --source <path-from-imagegen> \
  --workspace /workspace \
  --session-id <session-id> \
  --slot final-candidate \
  --name <slide-id>-<candidate-code>.png
```

For style previews, adopt as `style-preview`:

```bash
python3 scripts/adopt_imagegen_output.py \
  --source <path-from-imagegen> \
  --workspace /workspace \
  --session-id <session-id> \
  --slot style-preview \
  --name <style-direction-id>-<page-role>.png
```

For revised pages, adopt as `final-page` with the original slide id and a non-overwriting revision filename such as `<slide-id>-rev001.png`.

Normal generation must not pass `--copy`. The adoption helper records adopted files in `imagegen-assets.json`; final-page adoption updates `generation/final-pages.json`.

## State Files

- `generation/final-pages.json`: authoritative current final slide mapping for review and export.
- `generation/candidates/`: adopted candidate image directory.
- candidate mapping: local slide-to-candidate table used to connect candidate codes to adopted candidate paths.
- `imagegen-assets.json`: internal adopted asset manifest.
- `subagent-runs.json`: required worker ledger for dispatch id, worker id, mode, slide id, candidate id, style direction id, preview page role, status, adopted path, timestamps, retry-of worker id, and short errors. This ledger is diagnostic and auditable only; it must not replace `final-pages.json`.

The main thread MUST update `subagent-runs.json` after each worker dispatch and after each worker result is accepted or rejected. Keep the ledger compact and path-based; never store prompt text, base64, data URLs, raw image-generation payloads, or copied file contents.

## Resume Algorithm

On resume, trust file-backed state, not chat history:

1. Read the intended slide ids or selected page ids from the current workflow state.
2. Read `generation/final-pages.json`, candidate mapping, `imagegen-assets.json`, and required `subagent-runs.json` when it exists from prior dispatches.
3. Verify that every referenced `adopted_path` still exists under `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/`.
4. For final generation, dispatch one-image workers only for slide ids missing from valid `final-pages.json` entries.
5. For candidate generation, dispatch one-image workers only for missing candidate slots from the candidate mapping.
6. For style preview, dispatch one-image workers only for missing `<style-direction-id>-<preview-page-role>` slots.
7. For revision, dispatch one-image workers only for selected page ids that are missing, failed, or stale for the current revision request.
8. Accept partial worker success when the adopted files and manifest entries are valid.

## Worker Prompt Checklist

Each worker prompt must include:

- You are not alone in the workspace; do not revert or overwrite unrelated files.
- You are a single-image worker: call image generation or image editing at most once, adopt exactly one output, update file-backed state, then stop.
- Generate or edit only the assigned slide id, candidate slot, revision page, or style-preview page role.
- Keep prompt metadata isolation: slide ids, candidate codes, filenames, and batch labels stay outside the image model prompt body.
- Locate new imagegen output with `scripts/find_imagegen_output.py`.
- Adopt files before reporting success.
- Do not return orchestration metadata in the final message; write it to `subagent-runs.json` and adoption manifests instead.
- Final message must be one short user-safe sentence with no JSON and no internal paths.
- Do not return base64, data URL, markdown image embeds, raw `imageGeneration`, or raw `image_generation_call` payloads.
