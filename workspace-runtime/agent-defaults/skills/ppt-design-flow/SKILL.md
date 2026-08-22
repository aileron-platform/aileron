---
name: ppt-design-flow
description: Run a staged, proposal-style design flow for PPT / slides / decks. Use when the user asks to build a PPT, slides, or deck — including 答辯稿, 募資簡報, 產品介紹 PPT, 彙報 PPT, or any "幫我做 PPT" / "把這份報告整理成演示稿" / "做一個產品介紹 deck" request — and especially when only a topic or rough materials exist and structure, style, and page plan must be clarified before generation.
---

# PPT Design Flow

A phase-driven design workflow that turns a vague PPT request into a generation-ready, preview-confirmed new deck. State is tracked by `scripts/stage.py`; canvas surfaces are built by `assets/canvas/build.py`. Both refuse to advance when phase preconditions are unmet.

This skill is the new deck entrance. If the user wants to revise an already completed deck, route them to `$ppt-revision-flow` instead of expanding this creation flow. `$ppt-revision-flow` uses the same runtime state under `/workspace/.aileron/canvases/ppt-design-flow/<session-id>/`.

## I/O Contract

- Input: a PPT topic, rough goal, existing notes/materials, or complete report-like narrative for a new deck.
- Optional anchors: audience, page count or duration, school/company/lab/course/brand identity, use occasion, source files, and style constraints.
- Output: confirmed content basis, visual style previews or fast-mode style defaults, deck planning files, generated page visuals, review surface, and final `.pptx` and/or standalone `.html` deck after approval.
- Confirmation gates (in order): 需求確認 (`needs_confirmed`), 風格確認 (`style_locked`), 風格拆解確認 (`style_breakdown_confirmed`), 產生前確認 (`pre_generation_confirmed`), 審閱確認 (`review_approved`). The bracketed snake_case is the gate id used by `stage.py pass <gate_id>`.
- Default ratio: generate preview images and final page visuals in `16:9` unless the user explicitly requests another ratio.

## State-First Directive

State is the single source of truth. Every `stage.py` and `build.py` invocation MUST include `--workspace /workspace` explicitly; do not rely on `WORKSPACE_DIR` or implicit cwd. Always inspect state when entering a phase or when state is uncertain.

When entering a new conversation, or when the active session id is unknown, resume discovery is the first action:

```bash
python3 scripts/stage.py resume --workspace /workspace
```

Use `python3 scripts/stage.py resume <query> --workspace /workspace` when the user gives a title slug or partial session id. Use `python3 scripts/stage.py list --workspace /workspace` to inspect unfinished sessions and `python3 scripts/stage.py list --all --workspace /workspace` when completed sessions may be relevant. If `resume` returns exactly one session, continue with that `session_id`, `current_phase`, and `phase_file`. If it returns multiple candidates, use `ppt-session-selection` from `phases/00-overview.md` so the user chooses the exact `session_id`; do not guess.

Use one run slug as the session id for the entire deck: `<YYYY-MM-DD-title-slug>`. Derive it from the local date and deck title/topic before `init`, then reuse that exact value for every `--session-id`, `.aileron` path, and final export in the run. Do not use generic session ids such as `default`, `deck_001`, or `s1` in real workflows.

### Phase entry procedure

When the session id is known, use this procedure for every phase, in order:

1. Inspect state:
   ```bash
   python3 scripts/stage.py show --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
   ```
2. If `show` reports that `state.json` does not exist (fresh session), initialize first:
   ```bash
   python3 scripts/stage.py init --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
   ```
   `init` lands the session at `intake` automatically; do not run `enter intake` afterwards.
3. If `current_phase` already equals the target phase, treat the phase as active and skip `enter`. Re-running `enter <current_phase>` raises `cannot re-enter`.
4. If `current_phase` differs from the target, advance only when the required gates / flags are satisfied:
   ```bash
   python3 scripts/stage.py enter <target-phase> --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
   ```
5. Successful mutation output from `init`, `pass`, `enter`, `set-flag`, or `reset` renders the updated state. Treat that mutation output as the confirmation; call `show` again only for error recovery or uncertainty.
6. Load the matching phase file from `phases/`. Use the canonical names listed below; do not guess (e.g. `01-intake.md` is wrong, the file is `10-intake.md`).

### Canonical phase files

```
phases/00-overview.md
phases/10-intake.md
phases/20-content-basis.md
phases/30-style.md
phases/40-planning.md
phases/50-generation.md
phases/60-review.md
```

If unsure, list them first:
```bash
ls phases
```

`assets/canvas/build.py --phase=...` refuses to run when preconditions are unmet; its stderr names the missing gate and the exact `stage.py` command to run next. Always pass `--workspace /workspace` to `build.py` as well.

## Hard Rules

- Preview-first: final style confirmation is based on generated `首頁 / 目錄頁 / 內容頁` previews, not text-only choices. This rule is intentionally relaxed only when `flags.fast_mode == true`; `phases/30-style.md` `Fast mode branch` is the authoritative description.
- Use the bundled shells (`assets/canvas/preview_shell/`, `assets/canvas/candidate_picker_shell/`, `assets/canvas/review_shell/`) as the base UIs for their stages. Do not author replacement shells.
- Preview may use SVG quick previews only when selected by the user. Final page visuals used for generation and review MUST be produced with `imagegen` or an approved raster image-generation/editing path. If no file-backed `imagegen` output is available, stop and report the blocker; do not substitute SVG, HTML screenshots, canvas, PIL, PPT shapes, or deterministic vector rendering for final pages unless the user explicitly approves that fallback after the blocker is explained.
- File-backed `imagegen` outputs that will be referenced by preview shells, candidate pickers, review shells, or final decks MUST be adopted into `/workspace` immediately after generation, before any workflow file references them. Use `scripts/adopt_imagegen_output.py`; do not leave referenced assets only under `$CODEX_HOME/generated_images/...`.
- Treat generated page visuals as complete by default; post-generation overlays default to zero unless they are traceable to approved blueprint fields.
- User-requested edits to visible text (adding, replacing, correcting, supplementing labels / titles / annotations) are image-generation/editing tasks. Do not use PIL, Pillow, canvas, SVG, HTML screenshots, PPT native text boxes, or deterministic overlays to patch final page visuals unless the user explicitly asks for a code/PPT-overlay workaround.
- Keep slide identifiers, candidate codes, filenames, and generation batch labels outside the image-generation prompt body. They live in mapping tables, filenames, review UI, and chat instructions — not in the prompt sent to the image model.
- Review payloads carry lightweight coordinate markup, not base64 preview images. When a user pastes review JSON with markup, render marked review images locally via `scripts/render_review_markup.py` before using them as retouch references.
- All `imagegen` / raster image-generation or image-editing work MUST run through bounded single-image subagent workers. This includes `imagegen` style previews, final page generation, candidate generation, review retouching, page regeneration, and single-page revisions. The main orchestration thread MUST NOT call image generation or image editing tools directly. Load `references/subagent-generation-runtime.md` before any image work; it defines the explicit user authorization gate required before worker dispatch. Every image worker must use `fork_context:false`, call image generation/editing at most once, adopt exactly one file-backed output, write orchestration metadata only to file-backed state, and finish with one short user-safe sentence. If subagents are unavailable, unauthorized, denied, or fail to adopt file-backed outputs, stop the workflow and report the blocker; do not continue by generating images in the main thread. Worker final messages must not contain JSON, internal paths, base64 payloads, data URLs, markdown image embeds, raw `imageGeneration` results, or raw `image_generation_call` results.
- Use `python3` for every Python command shown or executed by this skill. Do not use `python` in command examples, chat instructions, or subprocess guidance.

## User-facing language guardrail

Use this simple prompt before every normal chat reply:

> Can the user see it, choose it, or act on it? If not, keep it internal.

Normal user-facing replies must contain only:

- the user-visible outcome
- the next action
- the decision the user can make

implementation details are internal unless the user explicitly asks for debugging or exact commands. Do not explain tools, file paths, data structures, runtime state, or orchestration steps in normal chat. If a draft reply mentions how the workflow builds, copies, adopts, binds, publishes, dispatches, parses, or stores something, rewrite it from the user's perspective.

Use plain product words such as `預覽頁`, `候選選擇頁`, `審閱頁`, `回饋內容`, `已準備好`, and `產出檔案`.

When canvas artifact tool arguments are emitted for the platform, call `mcp__aileron__show_canvas_artifact` with those arguments and do not explain the internal publishing mechanism to the user.

### Internal JSON translation prompt

Use this prompt before sending any normal chat reply:

> Does this look like an internal JSON object? If yes, translate it into a user-facing sentence and do not paste the JSON.

This applies to worker results, adoption results, manifest updates, mapping updates, and command output shaped like JSON. Objects with keys such as `session_id`, `mode`, `updated_pages`, `manifest_updated`, `adopted_path`, `path`, `slot`, `operation`, or `errors` are internal unless the user explicitly asks for debug output.

Example internal object shape to translate, not paste: `mode: final single-candidate`, `updated_pages`, `manifest_updated`.

User-facing rewrite example: `已完成 S09 和 S10 的更新，審閱頁已準備好，你可以再檢查一次，滿意後用下方表單確認通過。`

## Structured question tool rule

Use `mcp__aileron__ask_user_question` for every user-facing question, confirmation, authorization, or small explicit option set. After calling the tool, end the turn immediately with no assistant prose. If a phase requires a non-question disclosure in the same first reply, place the disclosure before the tool call and no prose after it. Keep labels user-facing and concise.

Use question tools for:

- Intake essentials.
- Session selection when resume has multiple candidates.
- Needs confirmation.
- Flow choice: `詳細 flow` or `快速 flow`.
- Content-basis mode when the user must choose extraction vs. expansion.
- Style-boundary alignment before style previews: brightness, design route, preview count, and preview mode.
- Style preview action choices, style-regeneration decisions, refinement base selection, and style-breakdown confirmation.
- Pre-generation confirmation.
- Final generation branch selection: single final page vs. multi-candidate pages.
- Subagent authorization when image generation needs delegated workers.
- Fast-mode recovery choice during review.
- Review approval when the user is choosing whether the current pages are approved.
- Output format selection: `.pptx`, `HTML 簡報`, or `兩者都要`.

Do not use question tools for free-form review feedback, slide annotations, pasted review payloads, debugging, or cases where the user already gave a clear answer. In those cases, use normal chat or the review page. Do not ask plain prose questions as a fallback for these excluded cases; state the next action or instruction instead.

Minimal pattern:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-choice",
  "title": "請選擇下一步",
  "questions": [
    {
      "id": "choice",
      "label": "選項",
      "type": "radio",
      "options": [
        "選項 A",
        "選項 B"
      ],
      "required": true
    }
  ]
}
```
```

## Output Hierarchy

- `content_report.md` — upstream content basis when the user did not provide complete report-like material.
- `design_spec.md` — 整體設計 (Overall Design): global deck rationale and confirmed visual system.
- `slide_blueprint.md` — 每頁規劃 (Per-Slide Plan): page-by-page intent and content plan.
- `spec_lock.md` — 生成限制 (Generation Constraints): execution constraints and final generation guardrails.

When speaking to the user, lead with the Chinese name (e.g. 「整體設計」) and put the snake_case filename in parentheses or backticks; do not show only the snake_case to the user.
- `.aileron/canvas.json` — Aileron Canvas manifest declaring the single active canvas surface.
- `.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/<phase>/` — static shell bundle for style preview, candidate picker, or review.
- `.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json` — current slide-to-image mapping used by review and final exports.
- `.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/state.json` — phase-machine state (managed only via `scripts/stage.py`).
- `/workspace/<YYYY-MM-DD-title-slug>/<deck-name>.pptx` — final PowerPoint deck when `output_formats` contains `pptx`.
- `/workspace/<YYYY-MM-DD-title-slug>/<deck-name>.html` — standalone browser-presentable deck when `output_formats` contains `html`.
- `/workspace/<YYYY-MM-DD-title-slug>/assets/slides/` — copied slide images for the default HTML export.
- Fast-mode default filenames append `-ai-generated` before the extension.

`content_report.md` supports the three core planning files; it does not replace them. `spec_lock.md` is always the last core planning file.

## File Placement

- User-facing files (final `.pptx`, final `.html`, HTML asset folders, exported review images the user explicitly asked to inspect, and planning files) live under `/workspace/<YYYY-MM-DD-title-slug>/`.
- Final deck artefacts must not be written directly under `/workspace/` and must never be written under `/workspace/.aileron/`.
- Internal workflow files (shell bundles, copied preview assets, candidate images, marked review images, mapping JSON, session state, non-delivery manifests) live under `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/...`.
- Do not leave temporary images, intermediate JSON, builder staging files, or shell bundles in the `/workspace` root.

## Imagegen Output Adoption

The built-in `image_gen` tool does not provide reliable direct destination-path control. Treat every file-backed `imagegen` result as an external source that must be adopted once into the active `/workspace` session tree before it is referenced.

Use the bundled helper for all adopted raster assets:

```bash
python3 scripts/find_imagegen_output.py \
  --root ${CODEX_HOME:-$HOME/.codex}/generated_images \
  --after <generation-start-epoch> \
  --exclude-manifest /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/imagegen-assets.json

python3 scripts/adopt_imagegen_output.py \
  --source <path-from-imagegen> \
  --workspace /workspace \
  --session-id <YYYY-MM-DD-title-slug> \
  --slot <style-preview|final-page|final-candidate|review-export> \
  --name <stable-file-name.png>
```

Default behavior is `move`, not copy, to avoid duplicate generated-image staging. Do not pass `--copy` during normal generation. Pass `--copy` only when the user explicitly needs the original source preserved for a separate user-visible reason. The helper refuses unsupported image formats, non-image files, path traversal, and overwrites; pick a new stable filename instead of replacing an existing asset.

Slot destinations:

- `style-preview` → `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/style/candidates/`
- `final-page` → `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages/`
- `final-candidate` → `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/candidates/`
- `review-export` → `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/review/exports/`

The adoption helper records every adoption in `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/imagegen-assets.json`. Keep this internal manifest under `.aileron`; do not create a user-facing output manifest in the run folder. Use adopted paths when passing `--image <preview-images>...` to `assets/canvas/build.py` or when collecting final page visuals for deck export.

For `final-page` adoptions, the helper also updates `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json`. This file is the current mapping for review and final exports. If a slide is regenerated, adopt the new file with `--slide-id <slide-id>` so the mapping points to the latest image while older image files can remain on disk without entering the final deck.

## Progressive Loading

- Start of session: `SKILL.md` + `phases/00-overview.md` + `references/runtime-quickstart.md`.
- Entering any phase: `phases/<NN>-<phase>.md`.
- Entering generation: `phases/50-generation.md` + `references/subagent-generation-runtime.md`.
- Style proposal / refinement: `references/preview-flow.md`, `references/style-system.md`.
- Intake conversation: `references/conversation_framework.md`.
- Writing a planning file: matching `templates/<file>_reference.md`.
