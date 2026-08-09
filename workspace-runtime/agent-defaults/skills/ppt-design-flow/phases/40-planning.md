# Phase 40 — Planning

| | |
|---|---|
| **Preconditions** | 風格確認 (`style_locked`), 風格拆解確認 (`style_breakdown_confirmed`) |
| **Entry action** | `python3 scripts/stage.py enter planning --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` |
| **Exit gates** | 產生前確認 (`pre_generation_confirmed`) |

## Goal

Write the three planning files in the exact order below, then summarize and obtain `產生前確認`.

1. `design_spec.md` — **整體設計** (Overall Design): global deck rationale, confirmed visual system, deck-level continuity anchor.
2. `slide_blueprint.md` — **每頁規劃** (Per-Slide Plan): page-by-page intent, content payload, visual strategy.
3. `spec_lock.md` — **生成限制** (Generation Constraints): execution constraints and final generation guardrails.

When you mention these files in chat, lead with the Chinese name (e.g.「整體設計」), then the filename in parentheses. Do not show only `design_spec.md` to the user — that snake_case form is for the actual saved file, not for the chat label.

## Fast mode branch (REQUIRED when `flags.fast_mode == true`)

If `stage.py show` reports `fast_mode       : true`, write the planning files silently and continue to generation without asking the user for `產生前確認`.

- Write `slide_blueprint.md` and `spec_lock.md` with the same template fidelity as the detailed flow.
- Do not omit fields, skip sections, compress the page-by-page plan, or treat fast mode as permission to lower planning quality.
- Planning-file content quality is non-negotiable in fast mode; only the user confirmation step is suppressed.
- After both files are complete, silently run:

```bash
python3 scripts/stage.py pass pre_generation_confirmed --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter generation --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Authoring rules

- Use the confirmed breakdown (from `phases/30-style.md` 風格拆解確認) as the basis for `design_spec.md`. Trust the breakdown more than the raw original prompt.
- Use the content basis (`content_report.md` or skip-mode extraction) as the source of page content for `slide_blueprint.md`.
- `spec_lock.md` is always last. It locks what may change downstream and what may not.
- Write `design_spec.md`, `slide_blueprint.md`, and `spec_lock.md` under the user-facing run output folder `/workspace/<YYYY-MM-DD-title-slug>/`, not directly under `/workspace/`.
- Do not dump all three files to chat. After writing them, output a short pre-generation summary covering:
  - project overview
  - chosen style result
  - deck-level continuity anchor
  - page structure summary
  - execution readiness

## Confirmation gate — 產生前確認 (`pre_generation_confirmed`)

Use the root `Structured question tool rule` for explicit user approval:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-pre-generation-confirmation",
  "title": "請確認是否開始產生最終頁面",
  "questions": [
    {
      "id": "pre_generation_status",
      "label": "產生前確認",
      "type": "radio",
      "options": [
        "確認，開始產生",
        "需要修正規劃"
      ],
      "required": true
    },
    {
      "id": "planning_adjustments",
      "label": "修正內容",
      "type": "textarea",
      "placeholder": "如果需要修正規劃，請寫要改的地方；否則可留空"
    }
  ]
}
```
```

After the user approves through the form, run:

```bash
python3 scripts/stage.py pass pre_generation_confirmed --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter generation --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## References

Load these templates immediately before writing the matching file:

- `templates/design_spec_reference.md`
- `templates/slide_blueprint_reference.md`
- `templates/spec_lock_reference.md`
