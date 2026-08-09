# Phase 10 — Intake

| | |
|---|---|
| **Preconditions** | (none) |
| **Entry action** | `python3 scripts/stage.py init --session-id <YYYY-MM-DD-title-slug> --workspace /workspace` for a fresh session (auto-lands at `intake`). Do NOT run `enter intake` afterwards. |
| **Exit gates** | 需求確認 (`needs_confirmed`) |

## Goal

Understand what the deck is for without over-questioning, then output a baseline judgment for the user to confirm.

## Opening flow disclosure (REQUIRED on first reply)

The very first chat reply of the session MUST briefly explain the whole flow so the user knows what to expect. Place it at the top of the reply, before any intake questions. The disclosure MUST include an ASCII flow diagram covering all five user-facing confirmations in their order, rendered inside a fenced code block so the monospace alignment survives. Use language equivalent to (paraphrasing OK; do not omit any step, do not drop the ASCII diagram):

> 我會用一條分階段的流程帶你做這份 PPT，總共有 5 道確認點，你都有機會調整、回頭或結束：
>
> ```text
>  [1] 需求確認
>   |    聽你說 → 我給判斷 → 你確認方向，並選 詳細 flow / 快速 flow
>   |    ↻ 不滿意 → 我修正判斷後再給一次
>   |
>   |-- 詳細 flow --------------------------------------------------------.
>   v                                                                  |
>  [2] 風格確認                                                        |
>   |    先選預覽工具：SVG 快速預覽（便宜、快、適合比較方向）           |
>   |                  或 imagegen 高擬真預覽（慢，更接近最終視覺）     |
>   |    我出幾套視覺方向（首頁／目錄頁／內容頁） → 你選一條             |
>   |    ↻ 要調整某方向 → 我問你「重出 / 先記下 / 取消」                 |
>   v                                                                  |
>  [3] 風格拆解確認                                                    |
>   |    我從你選的圖裡拆出穩定特徵 → 你確認哪些延續、哪些不鎖死         |
>   v                                                                  |
>  [4] 產生前確認                                                      |
>   |    我寫成 整體設計 / 每頁規劃 / 生成限制 三份文件                  |
>   |    ↻ 要改規劃 → 我改完再給你看，再點頭才動手生圖                   |
>   |                                                                  |
>   '-- 快速 flow： [2] AI 自動 → [3] AI 自動 → [4] AI 自動 ------------'
>   v
>  [5] 審閱確認
>        最終頁面一律由 imagegen 產出（不論前面預覽選什麼）
>        第一版頁面 → 審閱介面逐頁標記要改的地方
>        ↻ 標記了就改 → 我修完重新進審閱 → 反覆到你滿意
>        滿意 → 選擇匯出 PPTX / HTML 簡報 / 兩者都要
>
>  任何一步都可以叫我「回到上一步」「重來這一步」或「換個方向」，
>  我會用 reset 把流程退回對應位置。
> ```

Diagram conventions:

- `[N]` — phase milestone, bracketed step number so the user can refer back by number.
- `|` and `v` — vertical flow between steps.
- `→` — left-to-right action inside one step.
- `↻` — same-step loop / can-retry path; describe the loop in one line so the user sees what triggers the redo.
- Trailing note — cross-phase reset reminder for "回到上一步" / "重來這一步".

Render the diagram with pure ASCII connectors (`[N]`, `|`, `v`) plus the single-width arrow glyphs `→` and `↻`; do NOT switch to box-drawing characters (`┌─┐│└─┘`) — they mis-align with double-width Chinese characters in many chat surfaces.

After the disclosure, immediately continue into the intake question tool described below. Do not put the disclosure into a separate turn that waits for the user to acknowledge — they should see disclosure + first question tool in one reply.

## Inputs to elicit (lightweight)

Collect only the essentials:

- what the PPT is for
- who the audience is
- rough length or duration
- what materials already exist
- whether there are concrete identity anchors such as school, company, laboratory, research group, course, product line, or brand entity that should ground the deck

When giving example choices in the first intake round, use broad common examples. Recommended examples:

- purpose: 彙報 / 募資簡報 / 答辯 / 產品介紹 / 教育訓練 / 回顧 / 方案提案
- audience: 老闆 / 客戶 / 投資人 / 老師 / 同事 / 評審

Do not require the user to specify the desired overall tone in the first intake round. If they volunteer it, you can use it. If they do not, surface style direction later in `phases/30-style.md`.

Use the root `Structured question tool rule` for intake essentials. This is the only normal case where required disclosure prose appears before a form:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-intake-essentials",
  "title": "請補充簡報基本資訊",
  "questions": [
    {
      "id": "purpose",
      "label": "簡報用途",
      "type": "text",
      "placeholder": "例如：彙報、募資簡報、答辯、產品介紹",
      "required": true
    },
    {
      "id": "audience",
      "label": "主要聽眾",
      "type": "text",
      "placeholder": "例如：老闆、客戶、投資人、老師、同事、評審",
      "required": true
    },
    {
      "id": "length",
      "label": "頁數或時間",
      "type": "text",
      "placeholder": "例如：10 頁、15 分鐘、未定"
    },
    {
      "id": "materials",
      "label": "現有材料",
      "type": "textarea",
      "placeholder": "貼上已有大綱、資料狀態、檔案摘要，或寫「只有主題」"
    },
    {
      "id": "identity_anchors",
      "label": "識別錨點",
      "type": "textarea",
      "placeholder": "學校、公司、實驗室、課程、產品線、品牌等；沒有可填「無」"
    }
  ]
}
```
```

## Baseline judgment output

After the intake exchange, output a short baseline judgment covering:

- deck goal
- target audience
- recommended deck type
- recommended page range
- narrative spine
- usable identity anchors
- missing critical information

## Flow choice (REQUIRED before `needs_confirmed`)

After intake data is gathered and the baseline judgment is ready, use `ppt-needs-confirmation` so the user can confirm/correct the baseline judgment and choose one flow before passing `needs_confirmed`:

- `詳細 flow` — keeps every style and planning confirmation, best when the user wants to compare visual directions and tune the deck deliberately.
- `快速 flow` — AI selects style and planning from the confirmed anchors, best when the user wants a usable first deck quickly and will review the full result at the end.

Do not pick this on the user's behalf. Do not infer fast mode from urgency, sparse input, or your own confidence; the user must explicitly choose.

Use the root `Structured question tool rule` for this confirmation and flow choice when the user has not already chosen:

Call `mcp__aileron__ask_user_question` with:

```json
{
  "id": "ppt-needs-confirmation",
  "title": "請確認需求方向與流程",
  "questions": [
    {
      "id": "needs_status",
      "label": "需求判斷",
      "type": "radio",
      "options": [
        "方向正確，繼續",
        "需要修正"
      ],
      "required": true
    },
    {
      "id": "corrections",
      "label": "修正內容",
      "type": "textarea",
      "placeholder": "如果選「需要修正」，請寫要改的地方；否則可留空"
    },
    {
      "id": "flow",
      "label": "流程模式",
      "type": "radio",
      "options": [
        "詳細 flow",
        "快速 flow"
      ],
      "required": true
    }
  ]
}
```
```

Action mapping:

- If the user chooses `快速 flow`, run `python3 scripts/stage.py set-flag fast_mode true --session-id <YYYY-MM-DD-title-slug> --workspace /workspace`, then run `pass needs_confirmed`.
- If the user chooses `詳細 flow`, leave `fast_mode` at the default `false` (or run `set-flag fast_mode false` if it was previously enabled during intake), then run `pass needs_confirmed`.
- `set-flag fast_mode ...` must happen before `pass needs_confirmed`; after intake, enabling fast mode is rejected by the state machine.

## Confirmation gate — 需求確認 (`needs_confirmed`)

Stop and use `ppt-needs-confirmation` to let the user confirm or correct the baseline judgment and choose `詳細 flow` or `快速 flow`. Once the user agrees and the flow choice has been recorded, run:

```bash
python3 scripts/stage.py pass needs_confirmed --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

Then transition to `content-basis` (or skip straight to `style` only if the user already supplied complete report-like narrative content — see `phases/20-content-basis.md` for the skip rule):

```bash
python3 scripts/stage.py enter content-basis --session-id <YYYY-MM-DD-title-slug> --workspace /workspace
```

## Reference

- `references/conversation_framework.md` — conversation-first intake patterns; load only if the initial exchange needs more structure.
