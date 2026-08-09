# Phase 20 — Content basis

| | |
|---|---|
| **Preconditions** | 需求確認 (`needs_confirmed`) |
| **Entry action** | `python3 scripts/stage.py enter content-basis --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` |
| **Exit gates** | none (set flag `content_basis_ready=true` when done) |

## Goal

Create or extract an upstream content basis (`content_report.md`) so later previews and planning files have grounded source material instead of generic placeholders.

## Decision: 整理 vs 補強

- `整理但不擴寫` — user already supplied strong report-like content (full report, paper, project document, experiment record, full outline, or complete narrative); compress the work into extraction and structuring without extra expansion.
- `補強並整理成報告` — user only provided a topic, thin materials, partial materials, or scattered notes; expand into a small research-style report-like article.

If the material status is ambiguous and the user must choose, use the root `Structured question tool rule`:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-content-basis-mode",
  "title": "請選擇內容整理方式",
  "questions": [
    {
      "id": "content_basis_mode",
      "label": "處理方式",
      "type": "radio",
      "options": [
        "整理但不擴寫",
        "補強並整理成報告"
      ],
      "required": true
    },
    {
      "id": "supplement",
      "label": "補充限制",
      "type": "textarea",
      "placeholder": "可補充不要擴寫的範圍、必須保留的材料，或可留空"
    }
  ]
}
```
```

## Output

- Default artifact: `content_report.md` (user-facing — write under `/workspace/`).
- Show the user a synthesized judgment by default; do not dump the full report immediately unless asked.

The content report should include:

- source status and material status
- problem background / topic framing
- core problem or core objective
- narrative body with connected reasoning rather than only bullets
- section candidates and page-content candidates
- visualizable content candidates
- claim status and open questions

## Rules

- Do not turn this stage into a long questionnaire; at most one lightweight supplement question tool when the material status is ambiguous.
- Distinguish `user_provided`, `inferred`, and `needs_confirmation` for every claim.
- Do not invent precise data, experimental results, citations, rankings, or institutional conclusions without support.
- Even if the user says not to expand content, still run this stage as extraction/structuring rather than skipping the content basis entirely.
- Later previews should use this content basis rather than a fresh generic topic outline.

## Skip rule

When the user supplied a complete narrative that is strong enough to support page planning, you may skip writing `content_report.md`. In that case, still extract the same fields into your own working notes, then flip the flag:

```bash
python3 scripts/stage.py set-flag content_basis_ready true --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Transition

Once content basis is ready (either `content_report.md` written or skip rule used), enter `style`:

```bash
python3 scripts/stage.py set-flag content_basis_ready true --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
python3 scripts/stage.py enter style --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Reference

- `templates/content_report_reference.md` — load when authoring `content_report.md`.
