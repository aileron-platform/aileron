# Phase 40 — Complete revision and re-export

Follow the root `User-facing language guardrail`: normal replies contain only the user-visible outcome, the next action, and the decision the user can make. implementation details are internal.

After revised pages are approved through `ppt-revision-approval`, complete revision mode:

```bash
python3 scripts/stage.py complete-revision --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Reuse `output_formats` when present. If no output format is recorded, use the question tool below for exactly the existing three choices: `.pptx`, `HTML 簡報`, or `兩者都要`.

Use the root `Structured question tool rule` for Output format selection:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-revision-output-format",
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

Re-export with the shared final builders:

```bash
python3 scripts/build_pptx_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
python3 scripts/build_html_deck.py --workspace /workspace --session-id <YYYY-MM-DD-title-slug>
```
