# Phase Overview

This file is the operational map of the skill. The agent reads it once on every new session and refers back to it to know which phase document to load next.

## Phase order and gates

```
intake ──需求確認──> content-basis ──> style ──風格確認──> style ──風格拆解確認──> planning ──產生前確認──> generation ──> review ──審閱確認──> done
                       │                                              ▲
                       └─(skip if user gave complete narrative)────────┘
                       fast_mode=true: style/planning confirmations are AI 自動, then both branches meet again at review
```

| Phase | Wraps prior stages | Entry preconditions | Exit gates / completion |
|---|---|---|---|
| `intake` | 1 | — | 需求確認 (`needs_confirmed`) |
| `content-basis` | 1.25 | 需求確認 | flag `content_basis_ready=true` (no user gate) |
| `style` | 1.5 + 2 + 2.5 + 2.75 | 需求確認 | 風格確認 (`style_locked`) then 風格拆解確認 (`style_breakdown_confirmed`) |
| `planning` | 3 | 風格確認 + 風格拆解確認 | 產生前確認 (`pre_generation_confirmed`) |
| `generation` | 4 | 產生前確認 | flag `pages_ready=true` (no user gate) |
| `review` | 5 | 產生前確認 + `pages_ready` | 審閱確認 (`review_approved`, terminal) |

User-facing confirmation gates are exactly these five:

- **需求確認** (`needs_confirmed`) — user confirms baseline judgment
- **風格確認** (`style_locked`) — user picks a style direction from generated previews
- **風格拆解確認** (`style_breakdown_confirmed`) — user confirms the three-group breakdown of style facts
- **產生前確認** (`pre_generation_confirmed`) — user approves entry to generation
- **審閱確認** (`review_approved`) — user approves the reviewed final pages

When speaking to the user, use the Chinese name (e.g., 「風格確認」). The bracketed snake_case identifier is for `stage.py pass <gate_id>` only — do not say "G2" or "gate 2" in chat replies.

Gates are append-only. The only way to undo a gate is `python3 scripts/stage.py reset --from <phase>`, which truncates downstream gates and resets flags scoped to that phase or later.

## State-First Directive

When a new conversation starts and the active session id is unknown, the agent's first action is resume discovery:

```bash
python3 scripts/stage.py resume --workspace /workspace
```

Use `python3 scripts/stage.py resume <query> --workspace /workspace` for a user-provided title slug or partial session id. Use `python3 scripts/stage.py list --workspace /workspace` to inspect unfinished sessions and `python3 scripts/stage.py list --all --workspace /workspace` to include completed sessions. If resume reports multiple candidates, use a question tool before continuing; replace the placeholder options with the candidate `session_id` values:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-session-selection",
  "title": "請選擇要接續的簡報",
  "questions": [
    {
      "id": "session_id",
      "label": "簡報工作階段",
      "type": "radio",
      "options": [
        "<session-id-1>",
        "<session-id-2>"
      ],
      "required": true
    }
  ]
}
```
```

Inside every phase with a known session id, the agent's first action is `show`, not `enter`:

```bash
python3 scripts/stage.py show --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Then, based on the output:

- If `state.json` does not exist (fresh session), run `init` first; `init` lands the session at `intake`, so DO NOT then run `enter intake`.
- If `current_phase` already equals the target phase, treat the phase as active and skip `enter` — re-entering raises `cannot re-enter`.
- If `current_phase` differs and gate / flag preconditions are met, run `enter <target-phase>`.
- Always pass `--workspace /workspace` to every `stage.py` and `build.py` command; do not rely on `WORKSPACE_DIR` or implicit cwd.

Successful mutation output from `init`, `pass`, `enter`, `set-flag`, or `reset` renders the same state fields as `show`. Treat that mutation output as the updated state view; call `show` again only for error recovery, phase starts, or uncertainty. Then load the matching `phases/<NN>-<phase>.md` (canonical names: `00-overview.md`, `10-intake.md`, `20-content-basis.md`, `30-style.md`, `40-planning.md`, `50-generation.md`, `60-review.md` — never guess `01-intake.md`).

Builder commands (`assets/canvas/build.py --phase=...`) refuse to run when state does not satisfy the phase preconditions; the failure message names the missing gate and the next stage command to run.

## state.json schema (v1)

```json
{
  "version": 1,
  "skill": "ppt-design-flow",
  "session_id": "<YYYY-MM-DD-title-slug>",
  "current_phase": "intake",
  "gates_passed": [],
  "flags": {
    "content_basis_ready": false,
    "pages_ready": false,
    "preview_mode": null,
    "candidate_mode": null,
    "fast_mode": false,
    "output_formats": []
  },
  "history": [],
  "created_at": "...",
  "updated_at": "..."
}
```

Location: `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/state.json`. Always reached through `scripts/stage.py` or `assets/stage_state.py`; never edit by hand.

## Progressive loading

| When | Load |
|---|---|
| Start of session | `SKILL.md` + this overview + `references/runtime-quickstart.md` |
| Entering any phase | `phases/<NN>-<phase>.md` |
| First style proposal of the session | `references/preview-flow.md`, `references/style-system.md` |
| Intake conversation | `references/conversation_framework.md` |
| Writing a planning file | matching `templates/<file>_reference.md` |

Do not preload every phase manual. The phase machine guarantees you cannot accidentally invoke the wrong phase's builder, so loading the active phase only is safe.

## File placement reminders

- User-facing deliverables (`.pptx`, planning files the user asked to read, exported review images) → `/workspace/` or a clearly user-named subfolder there.
- Internal workflow files (shell bundles, mapping JSON, marked images, generated candidates, `state.json`) → `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/...`.
- Never leave intermediate JSON, builder staging files, or shell bundles in the `/workspace` root.
