# Phase 20 — Select revision pages

Revision mode can target one existing slide or multiple existing slides.

Enter revision mode with selected pages:

```bash
python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace --pages '["S03", "S07"]'
```

If the user has not selected pages, enter revision mode without `--pages` and use the revision review surface to collect page-level feedback.

Revision mode does not add, delete, reorder, or re-plan slides.
