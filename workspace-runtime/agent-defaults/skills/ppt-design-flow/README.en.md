# ppt-design-flow

[中文](./README.md) | **English**

A **phase-driven, preview-first** PPT design-flow skill. It turns a vague PPT request into a content basis, visual style previews, locked planning files, generated page visuals, and a reviewed final deck. The stage gates are program-enforced: `scripts/stage.py` owns the state machine, and `assets/canvas/build.py` refuses to run when phase preconditions are unmet — agents cannot skip the confirmation gates.

Fast flow is available when the user explicitly chooses it during intake: the agent records `fast_mode=true`, uses documented style defaults, silently completes style/planning gates, and returns to the user at review with recovery commands. After review approval, the user can export `.pptx`, standalone browser-ready HTML, or both.

> **Output is image-first.** The preview stage offers SVG quick preview or `imagegen` high-fidelity preview at user choice; the final generation stage defaults to `imagegen` for full-page visuals which are then packaged into a PPTX. Pages are close to high-fidelity visual layouts suited for presentation, briefing, and image-level retouch — they are not native PPT objects you can edit element by element.

## What it does

It fits requests like:

- "Make me a PPT."
- "Turn this report into slides."
- "Help me build a defense deck."
- "Build a product-intro deck."
- "Show me a few style directions before we pick one."
- "I only have a topic and scattered material — please structure it into a presentable basis first."

It is not template stitching, nor a long-form parameter questionnaire. It runs a phase-driven, proposal-style flow:

1. Lightweight intake → baseline judgment
2. Gate "Needs confirmation" (`needs_confirmed`)
3. Content basis (`content_report.md`)
4. Style boundary alignment + multi-direction style previews + refinement (optional)
5. Gates "Style confirmation" (`style_locked`) and "Style breakdown confirmation" (`style_breakdown_confirmed`)
6. Planning files: Overall Design (`design_spec.md`) / Per-Slide Plan (`slide_blueprint.md`) / Generation Constraints (`spec_lock.md`)
7. Gate "Pre-generation confirmation" (`pre_generation_confirmed`)
8. Generation (single-image or multi-candidate path)
9. Review shell loop with retouch rounds
10. Gate "Review approval" (`review_approved`), then export the final PPT

Detailed per-phase procedure: [`phases/00-overview.md`](./phases/00-overview.md).

## Why this skill

Generic PPT flows tend to fail in two directions:

- **Too template-y**: tidy but generic, weak fit to the actual topic.
- **Too shallow**: visually like a PPT, but lacks narrative depth to support a real presentation.

`ppt-design-flow` aims to avoid both:

- Frontstage dialog stays light; no long forms.
- When material is thin, build content basis before discussing style.
- Style is confirmed by *visual previews*, not text descriptions.
- Final page visuals follow an image-first path; no patch-overlay rescue.
- Skip-gate behavior is blocked at the program level — the agent cannot bypass confirmation gates.

## Core characteristics

### Conversation-first
The user is the commissioning party; the agent acts as the proposing design side. First questions are light; no long form.

### Preview-first
Final style confirmation depends on generated `cover / TOC / body` previews. Preview mode is the user's choice: SVG quick preview or `imagegen` high-fidelity preview.

### Phase-driven + program-enforced gates
Six phases (`intake → content-basis → style → planning → generation → review`) and five user-facing confirmations (needs → style → style breakdown → pre-generation → review), enforced via `state.json` + builder pre-flight. If the agent tries to skip, the builder exits 2 with an explicit error.

### Content basis before style
After needs confirmation, if the user did not provide complete report-like material, a `content_report.md` is built as the upstream content basis. All later previews and planning files inherit from it.

### Review is part of the main flow
After the first full set of page visuals, the review shell loop is mandatory. The final deck is exported only after the review approval gate.

## Planning artifacts

- `content_report.md` — upstream content basis (before style).
- **Overall Design** (`design_spec.md`) — global deck rationale, direction, continuity constraints.
- **Per-Slide Plan** (`slide_blueprint.md`) — per-page intent, content payload, visual strategy.
- **Generation Constraints** (`spec_lock.md`) — execution constraints and final generation guardrails.

## Directory layout

```text
ppt-design-flow/
├─ SKILL.md
├─ README.md / README.en.md
├─ phases/
│  ├─ 00-overview.md
│  ├─ 10-intake.md
│  ├─ 20-content-basis.md
│  ├─ 30-style.md
│  ├─ 40-planning.md
│  ├─ 50-generation.md
│  └─ 60-review.md
├─ references/
│  ├─ conversation_framework.md
│  ├─ style-system.md
│  └─ preview-flow.md
├─ templates/
│  ├─ content_report_reference.md
│  ├─ design_spec_reference.md
│  ├─ slide_blueprint_reference.md
│  └─ spec_lock_reference.md
├─ assets/
│  ├─ canvas_protocol.py
│  ├─ stage_state.py
│  └─ canvas/
│     ├─ build.py
│     ├─ preview_shell/index.html
│     ├─ candidate_picker_shell/index.html
│     └─ review_shell/index.html
├─ scripts/
│  ├─ stage.py
│  └─ render_review_markup.py
└─ tests/
   ├─ test_canvas_builders.py
   ├─ test_stage_state.py
   └─ test_gate_enforcement.py
```

## Suitable scenarios

Defense decks, research briefings, project reports, product introductions, fundraising decks, training materials, proposal decks, internal retros / briefings.

Especially when: the user only has a topic or scattered material; content must be strengthened before style; visual previews are needed before locking direction; the final result must inherit the confirmed preview visual logic.

## Notes

- Default ratio is `16:9` unless the user explicitly requests otherwise.
- Previews must be content-bearing — not empty scaffolds or placeholder imagery.
- Multiple confirmation gates are intentional; they are program-enforced by `scripts/stage.py` + `assets/canvas/build.py`.
- Sample images and demo PPT will be published with a later release.

## Acknowledgements

Thanks to the [Linux.do community](https://linux.do/) for advancing open sharing.
