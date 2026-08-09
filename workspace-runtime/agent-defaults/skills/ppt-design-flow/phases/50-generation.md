# Phase 50 — Generation

| | |
|---|---|
| **Preconditions** | 產生前確認 (`pre_generation_confirmed`) |
| **Entry action** | `python3 scripts/stage.py enter generation --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` |
| **Exit gates** | none (set flag `pages_ready=true` once final pages exist) |

## Goal

Produce the final page visuals (single-candidate or multi-candidate path), then hand off to `phases/60-review.md`.

Before any image work, load `references/subagent-generation-runtime.md`. Final deck generation and candidate generation MUST use bounded single-image subagent workers. The main orchestration thread must not call image-generation tools directly.

Apply the runtime's explicit user authorization gate before dispatching workers. If the current conversation does not already include explicit authorization for subagents, delegation, or parallel agent work, use the authorization question tool in `references/subagent-generation-runtime.md` and wait. If authorization is missing or denied, stop; do not generate images in the main thread.

## Branch question

Before the first full generation pass, use the root `Structured question tool rule`:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-generation-branch",
  "title": "請選擇最終頁產生方式",
  "questions": [
    {
      "id": "candidate_mode",
      "label": "產生方式",
      "type": "radio",
      "options": [
        "每頁 1 張，直接進審閱",
        "每頁多張候選，先挑再審閱"
      ],
      "required": true
    },
    {
      "id": "candidates_per_slide",
      "label": "每頁候選數",
      "type": "radio",
      "options": [
        "2 張",
        "3 張",
        "4 張"
      ],
      "required": false
    }
  ]
}
```
```

- If multi-candidate, read `candidates_per_slide` from the same form.
- If single-candidate, skip the candidate-picker stage entirely.
- If the user gives no clear preference, default to one final image per slide and go directly into review.

Record the choice:

```bash
python3 scripts/stage.py set-flag candidate_mode <single|multi> --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Image-first policy

Final page visuals MUST be produced with `imagegen` or an approved raster image-generation/editing path. Preview-only SVG (selected by the user during `phases/30-style.md`) does NOT carry into generation or review. Specifically:

- Use an available image-generation toolchain from the environment (tool / MCP server / skill) to produce page visuals.
- If no file-backed `imagegen` output is available, stop and report the blocker before doing anything else. Do not substitute SVG, HTML screenshots, canvas, PIL, PPT shapes, or deterministic vector rendering for final pages unless the user explicitly approves that fallback after the blocker is explained.
- Do not silently fall back to a traditional element-by-element PPT workflow when image generation is available.
- Do not assemble the final deck only from default PPT shapes, text boxes, layout primitives, custom-drawn vectors, SVG-like code, or programmatic page reconstruction unless the user explicitly asks for that approach.
- Treat generated page visuals as complete outputs by default, not as underlays for a second design pass. Post-generation overlays default to zero.
- Do not silently switch to textless or background-only images just to dodge text-rendering problems.
- For visible-content changes (titles, labels, annotations, captions, metrics), handle via image edit/regeneration; not deterministic overlays.
- If image edit/regeneration is unavailable or unsuitable, stop and tell the user before using any deterministic overlay method.
- PIL/Pillow may be used only for mechanical review markup, format conversion, dimension checks, or packaging support; never to create, replace, correct, or overlay audience-facing content.
- Unless the user explicitly requests another presentation ratio, generate in `16:9`.

## Deck-level continuity anchor

Before writing per-slide prompts, extract the confirmed direction into one explicit deck-level continuity anchor. Every slide prompt must inherit that anchor first, then add only page-role and content-specific variation. Do not write slide prompts as independent style descriptions. If a slide would naturally become darker, brighter, flatter, glossier, or more atmospheric than the rest, test that change against the allowed variation range before keeping it.

## Prompt metadata isolation

- Maintain slide IDs, candidate codes, filenames, and generation batch labels in a separate mapping table or local variables.
- Do not concatenate those identifiers into the text prompt sent to the image model.
- The prompt body should contain only audience-facing slide content, page role, visual direction, continuity anchor, layout intent, and any visible labels that should actually appear in the slide.
- After generation, reconnect outputs to slide IDs through filenames or the external mapping table — never through text embedded in the image prompt.

## Single-candidate path

- Generate one final image per slide using bounded single-image subagent workers, even when the deck has only one slide.
- Assign exactly one final slide image to each worker and spawn every image worker with `fork_context:false`.
- The main thread must never directly generate or edit final page images.
- Each worker must follow `references/subagent-generation-runtime.md`, call image generation/editing at most once, adopt exactly one file before reporting success, write orchestration metadata to file-backed state only, and finish with one short user-safe sentence.
- Record every worker dispatch and accepted/rejected result in `subagent-runs.json`.
- Skip the candidate-picker stage.
- After each image generation, locate the new file-backed output with `scripts/find_imagegen_output.py` using the generation start timestamp and the session `imagegen-assets.json` as `--exclude-manifest`; do not use `find | sort | tail` shell scans.
- Adopt each generated slide immediately with `scripts/adopt_imagegen_output.py --slot final-page --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --name <slide-id>.png --slide-id <slide-id>`. Do not pass `--copy` unless the user explicitly needs the original generated-image source preserved. The helper updates `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json`, which is the authoritative current mapping for review and final exports.
- If a slide is regenerated after an interruption or review round, adopt it with a non-overwriting filename such as `<slide-id>-v2.png` and the same `--slide-id <slide-id>`. Older image files may remain on disk, but they must not enter review or export unless `final-pages.json` points to them.
- To resume, read `generation/final-pages.json`, verify every adopted path exists, then dispatch workers only for missing or failed slide ids.
- Once all pages are produced, verify `generation/final-pages.json` contains one current entry per intended slide, then flip the flag and move on:

```bash
python3 scripts/stage.py set-flag pages_ready true --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter review --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Multi-candidate path

- Generate the requested number of final candidates for each slide using bounded single-image subagent workers. Each worker handles exactly one candidate image using the approved page prompt; keep variation inside one approved direction.
- Spawn every candidate image worker with `fork_context:false` and record dispatch/result status in `subagent-runs.json`.
- Locate each generated candidate with `scripts/find_imagegen_output.py` before adoption; do not use `find | sort | tail` shell scans.
- Adopt every generated candidate immediately with `scripts/adopt_imagegen_output.py --slot final-candidate --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --name <slide-id>-<candidate-code>.png`. Do not pass `--copy` unless the user explicitly needs the original generated-image source preserved. Candidate picker inputs must be adopted paths under `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/candidates/`.
- Maintain a candidate mapping outside the image-generation prompt body. To resume, verify candidate mapping entries and referenced files, then dispatch workers only for missing candidate slots.
- Workers must write compact metadata only to file-backed state as described in `references/subagent-generation-runtime.md`; they must not return JSON, internal paths, base64 payloads, data URLs, markdown image embeds, raw `imageGeneration` results, or raw `image_generation_call` results in final messages.
- Worker metadata is internal. Follow the root `Internal JSON translation prompt`: do not paste worker JSON, adoption JSON, manifest update JSON, or `wait_agent` payloads into user-facing chat; summarize completion in user-facing prose and keep detailed paths in workflow state files.
- Build the candidate-picker shell:

```bash
python3 assets/canvas/build.py --phase=candidate-picker \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact --asset-mode reference \
  --image <candidate-images>...
```

- Call `mcp__aileron__show_canvas_artifact` with the JSON arguments printed by the builder.
- Tell the user to finish the selection inside the canvas page and click `複製全部編號`, then return to the chat input box, paste the copied codes, and send them.
- Wait for the returned selection codes before entering the review HTML stage.
- Once the codes arrive, map them to the selected page images, adopt those selected images as `final-page` with stable `--slide-id` values, and use `generation/final-pages.json` as the review input.

When the selected set is ready:

```bash
python3 scripts/stage.py set-flag pages_ready true --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter review --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```
