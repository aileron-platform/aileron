# Phase 60 — Review and retouch

| | |
|---|---|
| **Preconditions** | 產生前確認 (`pre_generation_confirmed`), flag `pages_ready=true` |
| **Entry action** | `python3 scripts/stage.py enter review --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` |
| **Exit gates** | 審閱確認 (`review_approved`, terminal) |

## Goal

Drive a review-and-retouch loop on the first-pass page visuals through the bundled review shell. Export the final PPT only after explicit approval.

## Fast-mode disclosure (REQUIRED when `flags.fast_mode == true`)

When `stage.py show` reports `fast_mode       : true`, prepend a short user-facing bullet list to the review-opening chat reply. It must state that the deck used the fast flow, that AI selected the style and planning, name the `fast_style_bucket` recorded in `design_spec.md`, and list these recovery command phrases:

- `重選風格` — return to the detailed style phase and choose the visual direction again.
- `重做頁規劃` — return to the detailed planning phase and rearrange the slide-by-slide content plan.

Do not include raw `stage.py` commands in the user-facing review-opening reply. Keep the internal action mapping in this skill only:

- `重選風格` — run `python3 scripts/stage.py set-flag fast_mode false --session-id <YYYY-MM-DD-title-slug> --workspace /workspace`, then `python3 scripts/stage.py reset --from style --session-id <YYYY-MM-DD-title-slug> --workspace /workspace`; continue through the detailed style phase.
- `重做頁規劃` — run `python3 scripts/stage.py set-flag fast_mode false --session-id <YYYY-MM-DD-title-slug> --workspace /workspace`, then `python3 scripts/stage.py reset --from planning --session-id <YYYY-MM-DD-title-slug> --workspace /workspace`; continue through the detailed planning phase.

Do not hide these command phrases behind a generic "tell me if you want changes" sentence. Prefer this shape:

```text
這份簡報使用快速 flow 產生，AI 已自動選擇風格與頁規劃。
目前風格：<fast_style_bucket>

可調整項目：
- 重選風格：回到詳細風格流程，重新選擇視覺方向
- 重做頁規劃：回到詳細頁規劃流程，重新安排每頁內容
```

Then use this question tool for the recovery choice:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-fast-mode-recovery",
  "title": "請選擇是否調整快速流程結果",
  "questions": [
    {
      "id": "fast_mode_recovery",
      "label": "快速流程調整",
      "type": "radio",
      "options": [
        "繼續審閱目前版本",
        "重選風格",
        "重做頁規劃"
      ],
      "required": true
    }
  ]
}
```
```

## Mandatory review shell

After the first full set of page visuals is ready, do NOT send a chat-only review message. Build the review shell first:

```bash
python3 assets/canvas/build.py --phase=review \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact --asset-mode reference \
  --image-list /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json
```

The builder will refuse to run unless 需求確認 / 風格確認 / 風格拆解確認 / 產生前確認 are all passed and `pages_ready=true`. Call `mcp__aileron__show_canvas_artifact` with the JSON arguments printed by the builder.

## Review user-facing message contract

When presenting the review stage to the user, follow the root `User-facing language guardrail`.

Prefer this user-facing wording:

```text
審閱頁已準備好。如果要修改，請在審閱頁上留下標註與文字，按「複製回饋內容」，回到聊天輸入框貼上並送出；如果已滿意，請用下方表單確認通過。
```

When asking whether the current review is approved, use the root `Structured question tool rule`:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-review-approval",
  "title": "請確認審閱結果",
  "questions": [
    {
      "id": "review_status",
      "label": "審閱結果",
      "type": "radio",
      "options": [
        "通過，準備匯出",
        "需要修改，我會貼上審閱回饋"
      ],
      "required": true
    }
  ]
}
```
```

## Review Image Binding Rule

After running `assets/canvas/build.py --phase=review`, verify that the review shell actually references the provided final page images.

Required checks:

- Confirm every current image listed in `generation/final-pages.json` is referenced in the review shell. With `--asset-mode reference`, adopted final-page images remain in the generation directory and are not copied under `review/images/`.
- Confirm `review/index.html` uses those referenced image paths in its page data, e.g. `generation/final-pages/S01.png`, `generation/final-pages/S02-v2.png`.
- Confirm no built-in placeholder slides, sample SVGs, or demo `data:image/svg+xml` entries remain active in the review page data.
- If the bundled review shell does not automatically bind the passed images, patch or regenerate the review page data before calling `mcp__aileron__show_canvas_artifact`.
- Do not tell the user the review page is ready until this binding check passes.

When you present the review stage to the user, tell them explicitly:

- If the current result is satisfactory, they should approve it through `ppt-review-approval` and the review stage can end.
- If not satisfactory, they should leave page-level notes and markings on the review surface so the platform review flow carries feedback back into the conversation.
- After clicking copy, they return to the chat input box, paste the copied feedback content into the input field, and send it.
- Do not merely say `paste the review data`; tell them concretely how to do it in one short sentence.

## Review HTML rules

The bundled review shell must:

- show every generated slide image
- keep page order visible
- support per-page review comments
- when the environment supports it, prefer visual annotations such as brush marks, boxes, arrows, or highlighted regions in addition to text comments
- preserve enough context that the agent can understand both the page and the marked region together
- copy lightweight `review-shell-v2` JSON with normalized coordinate markup for notes, rectangles, and pen strokes
- never include base64 images, data URLs, or full annotated preview images in the copied JSON

## Receiving review feedback

When the user pastes `review-shell-v2` feedback:

- Save the pasted JSON to a local file such as `review_feedback.json` (under `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/`).
- Run:

```bash
python3 scripts/render_review_markup.py review_feedback.json \
  --images <generated-page-image-directory> \
  --out <marked-review-directory>
```

- Use the rendered marked images plus separate page comments / note comments as the reference for retouching or regenerating pages.
- For review revisions, the input to the image edit/regeneration model is `(selected generated image, user feedback)`; do not patch the selected image with deterministic drawing code.
- Do not bake textual comments into the marked image by default; pass text feedback separately alongside the marked image.
- Do not skip the local marked-image restoration step and rely only on raw coordinate text when visual markup is present.
- If source images cannot be auto-located, create an image-map JSON from page IDs to local image paths and rerun the script with `--image-map`.

## Classify feedback before acting

- `full-page regeneration` — broader changes to composition, hierarchy, page concept, style intensity, overall mood.
- `local image edit` — targeted changes to a specific region, background element, rendered text area, spacing, emphasis object, small visual detail.
- `content/blueprint issue` — user is changing approved content, narrative structure, or page intent rather than only the rendered page.

Execution rules:

- Prefer an available image-editing path from the environment for local edits.
- Prefer full-page regeneration for broad / structural dissatisfaction instead of many small edits.
- Do not solve review feedback by adding unapproved PPT overlays.
- Do not treat the PPT file itself as the fast-turnaround retouch surface unless the user explicitly asks.
- If the revision would change approved content rather than only visuals, surface that explicitly before editing.
- After each retouch round, rebuild and reopen the review shell, repeating the same instruction about approving or copying feedback content back into the chat input.
- Repeat the loop until the user approves.

## Confirmation gate — 審閱確認 (`review_approved`)

When the user explicitly approves the reviewed pages through `ppt-review-approval`:

```bash
python3 scripts/stage.py pass review_approved --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Do not export before this gate.

## Output format selection (REQUIRED after `review_approved`)

Ask this output question only after `pass review_approved` succeeds. Asking before `review_approved` is forbidden.

Offer exactly these three choices:

- `.pptx` → `["pptx"]`
- `HTML 簡報` → `["html"]`
- `兩者都要` → `["pptx", "html"]`

Use the root `Structured question tool rule` for Output format selection:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-output-format",
  "title": "請選擇輸出格式",
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [
        ".pptx",
        "HTML 簡報",
        "兩者都要"
      ],
      "required": true
    }
  ]
}
```
```

After the user picks, run `stage.py set-flag output_formats '<json-list>'` before invoking any builder:

```bash
python3 scripts/stage.py set-flag output_formats '["pptx"]' --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Then dispatch the selected builder or builders:

```bash
python3 scripts/build_pptx_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
python3 scripts/build_html_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
python3 scripts/stage.py enter done --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

By default, final builders write user-facing outputs under `/workspace/<YYYY-MM-DD-title-slug>/`. `build_html_deck.py` writes `<deck>.html` plus `assets/slides/` inside that run folder so the main slides and thumbnails share one image copy. If the user explicitly needs a single portable HTML file, pass `--inline-assets`.

When `html` is selected, `build_html_deck.py` also publishes the final HTML deck as the active Web Canvas under the `html-export` bundle. After the HTML builder succeeds, call `mcp__aileron__show_canvas_artifact` with the builder output JSON arguments so the user can open the final HTML deck in Web Canvas.

The final artefacts must live under `/workspace/<YYYY-MM-DD-title-slug>/`, not directly under `/workspace/` and not under `/workspace/.aileron/`. The Web Canvas bundle is only the preview surface for the same final HTML artefact.

## Reference

- `references/preview-flow.md` — review shell layout and feedback flow detail.
