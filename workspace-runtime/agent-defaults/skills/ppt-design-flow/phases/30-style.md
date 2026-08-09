# Phase 30 — Style

| | |
|---|---|
| **Preconditions** | 需求確認 (`needs_confirmed`) |
| **Entry action** | `python3 scripts/stage.py enter style --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` |
| **Exit gates** | 風格確認 (`style_locked`), then 風格拆解確認 (`style_breakdown_confirmed`) |

## Goal

Align style boundaries with the user, propose multiple style directions, generate `首頁 / 目錄頁 / 內容頁` previews for each, refine if needed, and lock the chosen direction with a confirmed breakdown of stable features.

This phase wraps the previous Stages 1.5 (boundary), 2 (proposal), 2.5 (refinement), and 2.75 (breakdown). Treat them as sub-steps inside this single phase; gate transitions are programmatic.

## Fast mode branch (REQUIRED when `flags.fast_mode == true`)

If `stage.py show` reports `fast_mode       : true`, this branch replaces the detailed style-preview flow below.

- Do not invoke `assets/canvas/build.py --phase=preview`.
- Do not invoke `imagegen` for style preview purposes.
- Consult `references/fast_style_defaults.md` and pick exactly one defaults bucket using its `Decision algorithm`.
- Write `design_spec.md` in full. It must include `fast_mode_used: true` and `fast_style_bucket: <bucket-name>`, plus the intake evidence that justified the bucket.
- The `Preview-first` Hard Rule in `SKILL.md` is intentionally relaxed only in this branch because the user opted into fast flow during intake.
- After `design_spec.md` is complete, silently run:

```bash
python3 scripts/stage.py pass style_locked --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py pass style_breakdown_confirmed --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter planning --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Do not ask for style confirmation or style-breakdown confirmation in fast mode; those confirmations are deferred to the review phase recovery commands.

## Sub-step 1 — Boundary alignment (formerly 1.5)

Ask the 4 style-boundary questions with a single question tool. Do not ask these questions as plain prose.

Use the root `Structured question tool rule` for style-boundary alignment when the user has not already provided clear answers:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-style-boundaries",
  "title": "請選擇風格預覽邊界",
  "questions": [
    {
      "id": "brightness",
      "label": "整體色系",
      "type": "radio",
      "options": [
        "偏亮色系",
        "中間態",
        "偏暗色系"
      ],
      "required": true
    },
    {
      "id": "design_route",
      "label": "設計路線",
      "type": "radio",
      "options": [
        "一般專業路線",
        "明顯風格化路線"
      ],
      "required": true
    },
    {
      "id": "proposal_count",
      "label": "風格方向數量",
      "type": "radio",
      "options": [
        "2 套",
        "3 套",
        "4 套",
        "5 套"
      ],
      "required": true
    },
    {
      "id": "preview_mode",
      "label": "預覽方式",
      "type": "radio",
      "options": [
        "SVG 快速預覽",
        "imagegen 高擬真預覽"
      ],
      "required": true
    }
  ]
}
```
```

Helper notes:

- Q2: `如果你沒有特別偏好，預設選「一般專業路線」就行；只有當你明確想要更強設計感時，再選「明顯風格化路線」。`
- Q3: `預設推薦先看 3 套，通常足夠比較；如果你只想快速收斂，也可以選 2 套，如果你想多看一些方向，也可以選 4 或 5 套。`
- Q4: `SVG 快速預覽速度快、適合先比較方向；imagegen 高擬真預覽更接近最終視覺，但生成時間會明顯更久。預設先用 SVG 快速預覽，定方向後再用 imagegen 生成最終頁面。`

Rules:

- Keep it short; do not expand into a design questionnaire.
- Do not ask raw V1-V8 questions; do not branch into subtype follow-ups if the user allows the stylized route.
- Use answers as boundary conditions for later proposals, not a full style definition.
- Defaults when the user gives no clear answer outside the form: Q1 → `中間態` (unless context strongly suggests otherwise), Q2 → `一般專業路線`, Q3 → `3 套`, Q4 → `SVG 快速預覽` (mention `imagegen` remains available for higher-fidelity refinement).

Record the preview mode choice:

```bash
python3 scripts/stage.py set-flag preview_mode <svg|imagegen> --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Sub-step 2 — Style proposal and preview (formerly 2)

- Derive style vectors internally.
- Use the existing content basis (`content_report.md` or extracted notes) as the source for preview content; never substitute a fresh generic topic outline.
- Propose the user-requested number of style directions as lightweight proposal cards (default 3).
- For each direction, generate `首頁`, `目錄頁`, `內容頁` previews using the chosen preview mode.
- If preview mode is `imagegen`, load `references/subagent-generation-runtime.md`, apply its explicit user authorization gate, and dispatch one single-image style-preview worker per preview image. The main thread must not call image generation directly. If subagent authorization is missing/denied or workers fail to adopt file-backed previews, stop and report the blocker; do not continue with main-thread image generation. A style direction's `首頁 / 目錄頁 / 內容頁` set requires three separate workers, each spawned with `fork_context:false`, one `style_direction_id`, and exactly one `preview_page_role`. Each worker generates one preview image, adopts it immediately with `scripts/adopt_imagegen_output.py --slot style-preview --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --name <proposal-page-stable-name>.<ext>`, records dispatch/result status in `subagent-runs.json`, and finishes with one short user-safe sentence only. Worker final messages must not contain JSON or internal paths. Pass only adopted `/workspace/.aileron/.../style/candidates/...` paths into the preview shell with `assets/canvas/build.py --asset-mode reference`. Keep worker metadata internal per `references/subagent-generation-runtime.md`.
- If preview_mode=svg, keep the preview generation in the main thread; SVG quick previews do not use native image generation and do not require subagent dispatch.

Each proposal must include:

- proposal name
- one-line positioning
- cover direction
- content-page visual grammar
- suitable scenarios
- risk note

Place proposal cards plus previews inside the bundled preview shell and publish:

```bash
python3 assets/canvas/build.py --phase=preview \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact --asset-mode reference \
  --image <preview-images>...
```

Call `mcp__aileron__show_canvas_artifact` with the JSON arguments printed by the builder so Web Canvas opens the active surface. Previews must be content-bearing — empty shells, placeholder copy, or mostly blank scaffolds are not acceptable.

## Preview Image Binding Rule

After running `assets/canvas/build.py --phase=preview`, verify the preview page actually references the generated preview images before announcing it.

Required checks:

- Confirm every active preview image slot has a generated `首頁 / 目錄頁 / 內容頁` image for its style direction.
- Confirm every referenced image file exists and is readable from the workspace.
- Confirm the preview page source references the generated image paths, not only the original template image placeholders.
- Confirm no placeholder preview images, demo `data:image/svg+xml` entries, or blank image slots remain active for directions shown to the user.
- Do not tell the user the preview page is ready until this check passes.

## Proposal count fidelity rule

The bundled `assets/canvas/preview_shell/index.html` ships with three `<section class="scheme" data-scheme>` blocks (proposal A / B / C). The shell honours the user-requested proposal count via the `data-active` attribute, NOT by removing or duplicating sections. Rules:

- If the user asks for N proposals (N may be 1, 2, 3, or more), the agent fills exactly N sections with distinct content drawn from the content basis.
- For any leftover section in the 3-section template (`N < 3`), set `data-active="false"` on the `<section class="scheme">` element. The CSS rule `.scheme[data-active="false"] { display: none; }` hides it. Active sections may keep `data-active="true"` or omit the attribute entirely.
- If `N > 3`, append additional `<section class="scheme" data-scheme>` blocks to the proposals container, each with its own distinct content.
- Do NOT duplicate proposal B into proposal C, do NOT fabricate a filler proposal, do NOT leave the original template placeholder ("方案 A｜穩妥商務科技" etc.) inside an active section.
- Each active section's `首頁 / 目錄頁 / 內容頁` images must be unique to that proposal; never reuse the same generated image across two active sections.

## Preview presentation message contract

Every chat reply that publishes a preview set (initial proposals in Sub-step 2 OR refinement results in Sub-step 3) MUST include the canvas artifact tool arguments and a question tool for ALL THREE valid next paths. A reply that offers only "confirm or list adjustments" is invalid — it hides the regeneration option and forces the user to discover it.

## Preview progress message contract

Use this user-visible prompt whenever the preview work is being prepared but not yet published:

> What will the user see next, and what decision can they make next?

implementation details are internal. Do not describe tools, files, templates, publishing, copying, adoption, binding, or other assembly steps in normal chat replies. If the draft reply explains how the preview page is being built, rewrite it so it describes only the upcoming user-visible preview and choice.

Use wording like:

> 我正在整理風格候選，接著會把每套方向配上首頁、目錄頁、內容頁預覽，讓你直接比較後選定方向。

The user-facing preview progress message should mention only what the user will see next and what decision they can make next.

The reply MUST include this question tool after the required `mcp__aileron__show_canvas_artifact` call. Do not ask the next-path question in plain prose:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-style-preview-action",
  "title": "請選擇風格預覽下一步",
  "questions": [
    {
      "id": "style_action",
      "label": "下一步",
      "type": "radio",
      "options": [
        "直接確認這個方向",
        "調整目前方向",
        "沿某個方向再推一輪預覽"
      ],
      "required": true
    },
    {
      "id": "target_direction",
      "label": "目標方向",
      "type": "text",
      "placeholder": "例如：A、B、C，或寫要混合的方向"
    },
    {
      "id": "adjustments",
      "label": "調整內容",
      "type": "textarea",
      "placeholder": "如果要調整或再推一輪，請寫希望改的地方"
    }
  ]
}
```
```

Do NOT present a two-option prompt such as「請回覆確認或直接指出要調整的項目」 — that wording fails this contract because path 3 (and the regenerate-vs-defer branch inside path 2) is missing.

## Regeneration confirmation rule

After any preview set has been shown to the user, the previews are treated as the source of truth for that direction. If the user then says anything that would change a direction's look — colour, density, hierarchy, mood, decoration, container grammar, brightness, contrast, restraint level, theme anchor, "再亮一點", "更剋制", "字多一點", and so on — the assistant MUST NOT silently regenerate or carry the adjustment into 風格確認 / 風格拆解確認 without confirmation. Use this question tool first:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-style-regeneration-decision",
  "title": "請選擇調整處理方式",
  "questions": [
    {
      "id": "regeneration_decision",
      "label": "處理方式",
      "type": "radio",
      "options": [
        "當場重新出一輪預覽",
        "先記下，下一輪一起套",
        "取消這個調整"
      ],
      "required": true
    }
  ]
}
```
```

Use the user's answer to choose:

- **Regenerate now** — rerun the preview generation for the affected direction(s), republish the preview shell with the new images, and only then continue.
- **Defer / record** — note the adjustment as a pending tweak, do not call the model, do not republish, and do not pretend the new state matches the prior images.
- **Cancel** — drop the adjustment entirely.

Do not auto-regenerate, do not auto-defer, do not skip the question tool. This rule applies to both Sub-step 2 (initial proposals) and Sub-step 3 (refinement rounds), and to any tweak suggested by the assistant itself.

## Sub-step 3 — Style refinement (formerly 2.5, optional)

If the user is not ready to confirm a final direction, run refinement rounds before the lock gate. Every refinement round begins with the regeneration confirmation rule above. If the user confirms regeneration:

- Let the user pick one current direction as the base using a question tool. Replace the placeholder options with the active direction labels:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-style-refinement-base",
  "title": "請選擇要延伸的風格方向",
  "questions": [
    {
      "id": "base_direction",
      "label": "基底方向",
      "type": "radio",
      "options": [
        "方向 A",
        "方向 B",
        "方向 C"
      ],
      "required": true
    },
    {
      "id": "refinement_goal",
      "label": "延伸目標",
      "type": "textarea",
      "placeholder": "請寫希望延伸或調整的重點"
    }
  ]
}
```
```

- Before deriving more options, run a short refinement-time breakdown on that base: read the `首頁 / 目錄頁 / 內容頁` together with the original prompt and summarize what the direction actually became in the generated images. Surface what is stable vs. one-off.
- If the user has not already specified adjustments in the form, use another question tool instead of a prose question.
- Derive the user-requested number of new candidate directions from that base (default 3).
- Regenerate the same `首頁 / 目錄頁 / 內容頁` preview set for each derived direction and republish the preview shell.
- If regenerated with `imagegen`, use the same style-preview worker rule from Sub-step 2, adopt each regenerated preview into `style-preview` with new stable filenames before publishing the shell with `--asset-mode reference`, and keep worker metadata internal. Never reuse or overwrite prior candidate filenames.

Lightweight tweak options you may include in a question tool (as cues, not a rigid checklist):

- `對比度高一點`、`色彩再鮮豔一點`、`更剋制一點`、`更有高階感一點`、`資訊感更強一點`、`畫面更輕一點`、`文字多一點還是圖片多一點`

When presenting refinement results, follow the **Preview presentation message contract** above — list all three paths (confirm / adjust → regenerate-or-defer / continue refining). Do not collapse the message to just「繼續沿某個方向再推一輪 vs. 結束風格階段」; that wording omits the in-place adjustment path and violates the contract.

## Confirmation gate — 風格確認 (`style_locked`)

When the user picks (or mixes) a final direction through `ppt-style-preview-action`, run:

```bash
python3 scripts/stage.py pass style_locked --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Sub-step 4 — Style breakdown (formerly 2.75)

After 風格確認, run one short breakdown pass on the chosen previews:

- Read the chosen `首頁 / 目錄頁 / 內容頁` as visual evidence; do not treat the original prompt as the whole truth.
- Compare actual images with the original prompt and identify what the model really produced.
- Extract stable repeated style facts: brightness range, palette role usage, material feel, lighting/depth behavior, container grammar, edge treatment, decoration grammar, information density, text-image balance, restraint level.
- Also extract theme-specific elements that matter (school emblems, campus buildings, company marks, laboratory context, domain imagery, devices, chart language).
- Distinguish across-set consistency from one-off local flourishes.

Present the breakdown as three groups, not as an open interview:

- `明確應延續的`
- `效果好但需要確認是否整套延續的`
- `只在目前圖裡偶然成立，不建議直接鎖死的`

Let the user confirm, remove, or promote items between groups using a question tool. If they give no correction, keep the first group by default and do not auto-lock the second.

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-style-breakdown-confirmation",
  "title": "請確認風格拆解",
  "questions": [
    {
      "id": "breakdown_status",
      "label": "拆解結果",
      "type": "radio",
      "options": [
        "確認，照這樣延續",
        "需要調整分類"
      ],
      "required": true
    },
    {
      "id": "breakdown_adjustments",
      "label": "分類調整",
      "type": "textarea",
      "placeholder": "如果需要調整，請寫要移除、提升為整套延續，或不要鎖死的項目"
    }
  ]
}
```
```

## Confirmation gate — 風格拆解確認 (`style_breakdown_confirmed`)

When breakdown is confirmed, run:

```bash
python3 scripts/stage.py pass style_breakdown_confirmed --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter planning --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## References

- `references/style-system.md` — load when deriving proposal cards or interpreting V1-V8 internally.
- `references/preview-flow.md` — load before building the preview shell.
