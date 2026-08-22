# Phase 10 — Resume completed session

Use the shared `ppt-design-flow` runtime from the sibling skill directory (`../../ppt-design-flow/` relative to this file).

List completed sessions when the target is unknown:

```bash
python3 scripts/stage.py list --all --workspace /workspace
```

Resume by exact or partial session id:

```bash
python3 scripts/stage.py resume <query> --workspace /workspace
```

Only continue when the session has passed `review_approved`. If it has not, direct the user back to `$ppt-design-flow` to complete the new-deck workflow.
