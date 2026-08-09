# Conversation Framework

## Positioning

Use a conversation-first approach.

The user is the client:
- they provide topic, purpose, materials, and high-level preferences
- they approve or reject directions

You are the proposing design agent:
- you digest the brief
- you propose directions
- you refine based on feedback

## First-round intake

Keep the first round light and use `ppt-intake-essentials`. Focus on:
- what this deck is for
- who it is for
- how long it should roughly be
- what materials exist
- whether there are concrete identity anchors such as `學校 / 公司 / 實驗室 / 課題組 / 課程 / 品牌主體` that the deck should feel tied to

Do not ask about the overall visual tone or style direction in the first round by default.
That should usually be inferred later or clarified during the style proposal stage, not front-loaded into the initial intake.

Identity anchors are different from style direction. It is acceptable to collect real-world anchors like school, company, laboratory, research group, course, or brand entity in `ppt-intake-essentials`, because they improve grounding and make later previews feel more specific and credible.

If you present suggested options during the first round form, prefer broad and common categories instead of narrow or overly productized lists.
For example:
- purpose examples: 彙報 / 募資簡報 / 答辯 / 產品介紹 / 教育訓練 / 回顧 / 方案提案
- audience examples: 老闆 / 客戶 / 投資人 / 老師 / 同事 / 評審

Avoid turning the first turn into a long questionnaire; use only the intake form from `phases/10-intake.md`.

## Response pattern after intake

After light clarification, do not continue interrogating.
Output a baseline judgment first.

That baseline judgment is the content for the first confirmation point.

## Response pattern after `需求確認`, before style-boundary alignment

After `需求確認`, do not jump straight into style questions.
First create a content basis for the deck unless the user has already provided a complete report-like narrative.

This stage should usually exist in one of 2 modes:
- `整理但不擴寫` when the user already provided strong complete material
- `補強並整理成報告` when the user only provided a topic, thin material, partial material, or scattered notes

Do not turn this into a long questionnaire. If the material status is ambiguous, use `ppt-content-basis-mode` from `phases/20-content-basis.md`; otherwise proceed with the inferred mode.

After generating the content basis, do not dump the full report by default.
Instead first show a synthesized judgment covering:
- how the topic is being framed
- the core narrative line
- the likely section logic
- which content seeds can support later previews
- which claims are stable vs still need confirmation

Then continue to the short style-boundary alignment step.

## Response pattern before style proposal

After `需求確認` and after any needed content-basis step, do one short style-boundary alignment before proposing directions.

Use `ppt-style-boundaries` from `phases/30-style.md`; do not ask these style-boundary questions in plain prose.

Show this helper note together with the design-route field when helpful:
`如果你沒有特別偏好，預設選「一般專業路線」就行；只有當你明確想要更強設計感時，再選「明顯風格化路線」。`

Show this helper note together with the proposal-count field when helpful:
`預設推薦先看 3 套，通常足夠比較；如果你只想快速收斂，也可以選 2 套，如果你想多看一些方向，也可以選 4 或 5 套。`

Rules:
- keep the step short
- treat the user as a design outsider
- do not expose raw V1-V8 controls
- do not turn the step into a longer style interview
- if the user allows the stylized route, do not ask subtype follow-up questions there; carry that permission into the later proposal stage
- if the user does not give a clear answer to the route question, default to `一般專業路線`
- if the brightness answer is absent or ambiguous, default to a middle brightness tendency unless the deck context strongly indicates bright or dark
- if the preview-count answer is absent or ambiguous, default to `3` directions

## Response pattern during style proposal

Do not expose raw V1-V8 controls first.
Use them internally to derive proposals.

Present proposals as client-facing direction cards, not as parameter tables.

When you enter style confirmation:
- do not jump straight to “pick A/B/C” as the default interaction
- first tell the user that you can show style effects visually
- then show **real generated previews** if image generation is available
- only after previews are shown should you use `ppt-style-preview-action` for a final pick or a mixed revision

If previews are not available yet, say that explicitly instead of implying text-only selection is the intended workflow.
Do not treat text sketches as equivalent to visual previews.

## Response pattern during style refinement

If the user likes one direction but wants changes, do not force an immediate final pick.
Run a refinement round instead.

In a refinement round:
- treat one current direction as the base direction
- before deriving more variations, do one short refinement-time `風格拆解確認` on that base so the next round is built from what the images actually expressed rather than only from the earlier prompt wording
- derive another user-requested number of candidate variations from that base
- if the user gives no clear count, default to `3` refined directions
- keep the proposals inside the same broad identity unless the user clearly asks for a bigger pivot

During refinement, proactively give a few user-friendly tweak cues so the user can react more easily.
Examples:
- `對比度高一點`
- `色彩再鮮豔一點`
- `更剋制一點`
- `更有高階感一點`
- `資訊感更強一點`
- `畫面更輕一點`
- `文字多一點還是圖片多一點`

Do not require the user to pick from these phrases exactly.
Use them to stimulate natural feedback, not to constrain it.

When closing a refinement message, use `ppt-style-preview-action`. Do not end the message as if the only available response is `choose one and I will generate the final PPT`.

## Response pattern during style breakdown confirmation

After `風格確認` and before writing the 3 planning files, run one short `風格拆解確認` step.

In that step:
- read the chosen `首頁 / 目錄頁 / 內容頁` as evidence of what the user actually liked
- combine that reading with the original generation prompt, but do not blindly trust the prompt over the image result
- first output a short structured judgment instead of asking the user to analyze the images from scratch

Use 3 client-facing buckets:
- `明確應延續的`
- `效果好但我想確認是否要整套延續的`
- `只在目前圖裡偶然成立，不建議直接鎖死的`

Keep the step short.
Do not turn it into another full style interview.

Prefer concrete extracted elements over vague labels.
For example, it is better to say:
- `校徽 / 校名 / 校園建築這些主題實體錨點應延續`
- `雲層、大氣剖面、氣象圖表這些專業視覺語義應延續`
- `藍白主調 + 金色點綴 + 學術答辯感應延續`
than to only say:
- `高階感`
- `科技感`
- `貼題`

When confirming the breakdown:
- use `ppt-style-breakdown-confirmation` so they can say which items should 保留 / 不保留 / 只保留在局部頁面
- if they do not correct you, default to keeping the first bucket only
- do not automatically make the second bucket deck-wide hard constraints without confirmation

## Response pattern before final review when multi-candidate generation is enabled

If the user wants multiple final candidates per slide, do not jump straight from generation into the review HTML.
First move the user through one short candidate-selection round.

In that round:
- explain briefly that each page now has multiple final candidates generated from the same approved page prompt
- open the bundled candidate-picker HTML
- tell the user to finish the selection in the page and click `複製全部編號`
- tell them concretely to return to the chat input box, paste the copied codes into the input field, and send them
- do not ask them to describe the selection manually if the copy-code path is available
- once the codes arrive, acknowledge the chosen set and then enter the normal review HTML stage

If the user chose only one final image per slide, skip this round entirely.

## Response pattern during final review and retouch

After the first full deck is generated, do not immediately treat the PPT as finished.
Move the user into a visual review round.

In that round:
- use a dedicated review HTML as the default collaboration surface
- keep its visual style aligned with the preview shell rather than switching to a completely different interface style
- invite the user to react page by page
- prefer natural feedback, annotations, and marked regions over asking the user to describe everything in abstract terms
- explicitly tell the user what the next two paths are: approve through `ppt-review-approval`, or click the review page's `複製回饋內容`, return to the chat input, paste, and send
- do not rely on vague phrasing like `paste the review data`; tell the user concretely to return to the chat box, paste into the input field, and send
- when pasted review feedback contains coordinate markup, first restore local marked review images with `scripts/render_review_markup.py`; use those marked images plus separate text comments as the retouch reference

When the user gives feedback, classify it internally before responding:
- overall page dissatisfaction → regenerate the whole page
- local dissatisfaction with a region, text rendering, background detail, spacing, or emphasis object → use image edit
- content-level change → surface that it changes the approved content plan

Do not respond to review feedback by inventing new PPT overlay layers by default.
The default fix path is to update the page visual itself and then refresh the review HTML.
After each refreshed review round, repeat the same approval-or-paste instruction until the user is satisfied.
Once the user explicitly approves the reviewed pages through `ppt-review-approval`, continue to output format selection.

## Revision pattern

Accept natural revision language such as:
- choose A
- use A body pages and C cover
- keep this direction but make it more formal
- reduce the aggressiveness
- keep the structure, change the colors
- this page is fine but the top-left area is too empty
- regenerate this whole page
- keep this page, but change the background and fix the text area

Do not require the user to speak in design-system terms.
