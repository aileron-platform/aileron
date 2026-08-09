# Preview Flow

## Purpose

The preview stage lets the user judge a style direction visually before planning the full deck.

## Fixed preview set

Each style direction must generate exactly 3 preview pages using the user-confirmed preview execution mode: `SVG quick preview` or `imagegen visual preview`.
Unless the user explicitly asks for another presentation format, those previews must be generated in a `16:9` slide ratio rather than a generic illustration ratio such as `3:2`.
These 3 pages must also preserve strong intra-direction continuity so the user can judge one coherent style system rather than 3 loosely related outputs:

1. `首頁`
   - checks first impression
   - checks main visual and composition
   - checks tone and metaphor

2. `目錄頁`
   - checks structure and hierarchy
   - checks whether the style can support a system page
   - checks the transition from cover into content

3. `內容頁`
   - checks whether the style can actually carry information
   - checks readability and emphasis
   - checks whether the visual grammar survives real content

A valid preview page must contain plausible filled content rather than placeholder-only structure.
That means:
- do not generate placeholder text such as “在此輸入…”, “title here”, “lorem ipsum”, or empty label boxes intended to be filled later
- do not generate large empty containers, blank dashboard shells, or decorative modules with no real information inside
- do not silently switch to textless image generation just to avoid text rendering problems when the preview page is supposed to demonstrate content structure
- the TOC page should show believable section titles or navigational items
- the content page should show believable headings, bullets, labels, cards, numbers, or relationships with enough content to judge usability
- the cover may stay lighter in information density, but it still should not contain obvious placeholder copy

Text sketches, ASCII boxes, pseudo-layouts, and purely verbal examples do **not** count as previews in this workflow.
SVG previews count only when the user chose `SVG quick preview`; they must be complete visual slide previews, not wireframes or placeholder shells.

If `content_report.md` or another approved content-basis summary exists, preview content must draw from it.
That means:
- the cover should reflect the content thesis or core framing rather than only a decorative topic shell
- the TOC page should reflect the narrative chain or section candidates rather than a generic chapter list
- the content page should use page-content candidates, visualizable content, or report-derived arguments rather than generic filler structure
- do not create a second unrelated topic outline during preview generation when a content basis already exists
- if part of the preview content is inferred rather than user-provided, keep it general and avoid unsupported precise claims

## Comparison principle

The number of style directions may vary by user preference, but all proposed directions should use the same 3 preview page types so the user can compare them fairly.


## Aileron Web Canvas UI fit

The preview shells are content-owned surfaces embedded inside Web Canvas. Keep them visually integrated without depending on Aileron frontend internals:

- Do not recreate platform chrome such as navigation, sidebars, sync status, route tabs, or system errors.
- Use a restrained workbench style: neutral background, low-shadow panels, modest radii, stable 16:9 media frames, and compact controls.
- Avoid landing-page composition, oversized hero treatment, decorative gradient blobs, and brand-like platform labels.
- Keep generated slide images primary. Controls and notes should support inspection, comparison, selection, and review without dominating the canvas.
- Treat labels in the shell as skill-owned preview content. Platform-owned UI text remains outside the shell and uses project i18n keys.

## Presentation principle

Use the bundled preview shell at `assets/preview_shell/index.html` by default.
Treat it as the required workflow UI shell, not as optional inspiration.
For each style direction, show:
- the lightweight proposal card text
- the 3 preview pages beside or under it

Do not create a replacement preview shell, a lookalike HTML page, or a fresh preview interface from scratch just because it feels easier.
Only depart from the bundled shell if that asset is genuinely unavailable or the user explicitly asks for a different interface, and if that happens, say so clearly.

After the HTML shell is filled, publish it through the Aileron Canvas manifest when a workspace is available:

1. Choose a safe session id matching `^[a-zA-Z0-9_-]{1,64}$`.
2. Run the phase builder with `--workspace /workspace --session-id <YYYY-MM-DD-title-slug> --print-artifact`.
3. The builder writes the static shell under `/workspace/.aileron/canvases/<skill-name>/<YYYY-MM-DD-title-slug>/<phase>/`.
4. The builder atomically rewrites `/workspace/.aileron/canvas.json` so that phase becomes the single active canvas.
5. Call `mcp__aileron__show_canvas_artifact` with the builder-printed JSON arguments in the final chat reply.

Do not bypass the manifest path by opening generated files directly during Aileron workflows.

Use `<skill-name>` as the skill namespace for internal Aileron canvas files. For this skill, that namespace resolves to `ppt-design-flow`; it is not a platform-wide fixed path for other skills.

Only user-facing review or delivery files should be placed directly under `/workspace` or a clear user-facing subfolder. Internal assets, copied preview images, candidate images, review markup outputs, mapping JSON, session state, and shell bundles should stay under `/workspace/.aileron/canvases/<skill-name>/<YYYY-MM-DD-title-slug>/...`.


Builder commands should use the canvas manifest path when a workspace is available:

```bash
python3 assets/preview_shell/build_preview_html.py --workspace /workspace --session-id 2026-05-19-deck-title --title "PPT style preview" --image /workspace/path/to/cover.png --print-artifact
python3 assets/candidate_picker_shell/build_candidate_picker_html.py --workspace /workspace --session-id 2026-05-19-deck-title --title "PPT candidate picker" --print-artifact
python3 assets/review_shell/build_review_html.py --workspace /workspace --session-id 2026-05-19-deck-title --title "PPT review" --print-artifact
```

## Canvas artifact tool arguments

Use the single canvas artifact tool arguments when handing shell output to Web Canvas:

```json
{
  "title": "<canvas title>",
  "route": "/"
}
```

This is an internal platform signal. When it appears in a reply, use the root `User-facing language guardrail`: describe only the user-visible result, next action, or decision.

## Candidate-picker and review-shell continuity

If the workflow later enters optional multi-candidate final selection, use the bundled candidate-picker shell at `assets/candidate_picker_shell/index.html` by default.
Do not switch to a visually unrelated candidate-selection page, and do not create a visually similar but separate candidate-picker shell from scratch.
The intended continuity is achieved by reusing the bundled candidate-picker shell itself, not by inventing another page that merely resembles the preview shell.

When the workflow later enters final review and retouch, use the bundled review shell at `assets/review_shell/index.html` by default.
Do not switch to a visually unrelated review page, and do not create a visually similar but separate review shell from scratch.
The intended continuity is achieved by reusing the bundled review shell itself, not by inventing another page that merely resembles the preview shell.

The review HTML should:
- preserve the same overall design family, spacing rhythm, panel language, and image presentation logic
- replace style-comparison emphasis with page-by-page review emphasis
- make it easy to inspect one page, leave feedback, and then compare refreshed results after edits
- keep image review primary rather than burying the visuals under large control panels

## Hard rule

Style selection should default to preview-first.
That means:
- do not jump directly from proposal text to asking the user to choose a final direction
- first show the previews using the user-confirmed preview execution mode
- do not assume `imagegen` is required for the preview stage when the user chose `SVG quick preview`
- if the requested preview mode is not available, explicitly tell the user that preview display is part of the workflow and say what is blocking it right now

The user must never be left with the impression that style choice is text-only by default.

## Generation expectation

Before producing style previews, use `ppt-style-boundaries` from `phases/30-style.md`; it includes the choice between `SVG quick preview` and `imagegen visual preview`.
Default to `SVG quick preview` when the user gives no clear preference because `imagegen` can be slow.
When the user chooses `SVG quick preview`, create content-bearing SVG previews for the preview and refinement stages only. Label them as quick previews and keep them directionally faithful enough for style comparison.
When the user chooses `imagegen visual preview`, use `imagegen` for preview images if the tool is available; otherwise use whatever image-generation path is available and clearly state the fallback.
Image-generation prompts should inherit both the style direction and the current content basis, rather than only the visual style request.
Do not downgrade to text mockups silently.
Do not use SVG, data-URI SVG, HTML screenshots, canvas, PPT-native shapes, or hand-coded renderings as substitutes when the user chose `imagegen visual preview`.
SVG or data-URI SVG images inside bundled shells are placeholders/demo assets only unless they have been intentionally replaced by content-bearing SVG quick previews for the current deck.
Only fall back to text-only examples when:
- the user explicitly asks for rough mockups only, or
- the requested preview mode is unavailable right now and you have clearly told the user so.

## Speed and QA rule

The preview stage is a directional comparison step, not a polishing pass.
That means:
- generate the planned preview set directly instead of repeatedly testing one image at a time unless the generation path itself is unverified
- at most one minimal chain check is enough when the local generation path has not yet been confirmed in the current turn
- after the chain is confirmed, generate the remaining previews in batch without repeated intermediate spot-check loops
- do not regenerate pages just to slightly improve one candidate unless the result is clearly broken, unreadable, or off-direction
- do not run multiple rounds of manual re-checking before showing the user the preview set
- once each direction has a usable `首頁 / 目錄頁 / 內容頁`, assemble the preview page and show it
- apply the same speed rule during style refinement rounds; refinement is another comparison loop, not a polishing detour

Favor speed, comparability, and directionality over internal perfectionism at this stage.
