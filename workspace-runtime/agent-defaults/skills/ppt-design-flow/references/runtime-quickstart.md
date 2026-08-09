# Runtime Quickstart

Use this as the compact runtime map for routine `ppt-design-flow` execution. Load detailed phase files only when entering that phase or when a branch needs the full contract.

## State Commands

Always pass `--workspace /workspace`.

Use the same `<YYYY-MM-DD-title-slug>` value as the session id throughout the run.

When the session id is unknown in a new conversation, resume the latest unfinished session first:

```bash
python3 scripts/stage.py resume --workspace /workspace
```

Resume a specific session with a title slug or partial session id:

```bash
python3 scripts/stage.py resume <query> --workspace /workspace
```

List available sessions when resume is ambiguous:

```bash
python3 scripts/stage.py list --workspace /workspace
python3 scripts/stage.py list --all --workspace /workspace
```

Start a phase with a known session id by inspecting state:

```bash
python3 scripts/stage.py show --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

If no state exists, initialize:

```bash
python3 scripts/stage.py init --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Mutation commands (`init`, `pass`, `enter`, `set-flag`, `reset`) print the same rendered state shape as `show` when they succeed. Treat that mutation output as the updated state view. Run `show` again only when starting a phase, recovering from an error, or when state is uncertain.

## Phase Loading

- Start: load `SKILL.md`, `phases/00-overview.md`, and this quickstart.
- Active phase only: load `phases/<NN>-<phase>.md`.
- Style proposal or refinement: load `references/preview-flow.md` and `references/style-system.md`.
- Intake wording help: load `references/conversation_framework.md` only when needed.
- Planning files: load the matching `templates/<file>_reference.md`.

## Imagegen Adoption

Adopt file-backed `imagegen` output before any workflow file references it:

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

Use `style-preview` for style candidates, `final-page` for selected final pages, `final-candidate` for multi-candidate generation, and `review-export` for user-requested review exports.
`final-page` adoption updates `generation/final-pages.json`, the current image mapping used by review and final exports. When regenerating one slide, pass `--slide-id <slide-id>` so the mapping replaces that slide's current image.
Normal adoption moves the generated file into the active workspace session tree. Use `--copy` only when the user explicitly needs the original generated-image source preserved.

## Canvas Publishing

Use the bundled canvas builder:

```bash
python3 assets/canvas/build.py --phase=<preview|candidate-picker|review> \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact \
  --asset-mode reference \
  --image <adopted-image>...
```

For review after final-page generation, prefer the current mapping instead of expanding every path manually:

```bash
python3 assets/canvas/build.py --phase=review \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact \
  --asset-mode reference \
  --image-list /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json
```

Use `--asset-mode reference` for images already adopted under `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/...`. Omit it for arbitrary external images; default `copy` mode copies those images into the bundle.

## Completed Deck Revision

Use `$ppt-revision-flow` when the user wants to modify an already completed deck. It uses the same shared runtime and session state.

Enter revision mode:

```bash
python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

When target pages are known:

```bash
python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace --pages '["S03", "S07"]'
```

Build the revision review surface from the current final page mapping:

```bash
python3 assets/canvas/build.py --phase=revision \
  --workspace /workspace --session-id <YYYY-MM-DD-title-slug> \
  --revision-id <revision-id> --print-artifact \
  --asset-mode reference \
  --image-list /workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/generation/final-pages.json
```

Complete revision mode after the user approves the revised pages:

```bash
python3 scripts/stage.py complete-revision --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Revision mode only covers existing-slide visual changes. It does not add, delete, reorder, or re-plan slides.

## Output Placement

- User-facing outputs live under `/workspace/<YYYY-MM-DD-title-slug>/`.
- Final `.pptx`, `.html`, HTML asset folders, planning files, and review exports belong in that run output folder.
- Default HTML export writes `<deck>.html` plus `assets/slides/` inside the run output folder.
- Pass `--inline-assets` to `scripts/build_html_deck.py` only when the user needs a single portable HTML file.
- Internal shells, generated candidates, adopted imagegen assets, review markup, state, mapping JSON, and `imagegen-assets.json` stay under `/workspace/.aileron/canvases/ppt-design-flow/<YYYY-MM-DD-title-slug>/`.
