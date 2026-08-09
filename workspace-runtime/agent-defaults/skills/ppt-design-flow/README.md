# ppt-design-flow

**中文** | [English](./README.en.md)

一個 **phase-driven、preview-first** 的 PPT design flow skill：把一個模糊的 PPT 需求，分階段推進成內容基底、視覺風格預覽、規劃定稿、生成與審閱。整套流程由程式端強制階段門檻 — `scripts/stage.py` 負責 state machine，`assets/canvas/build.py` 在前置條件未滿足時直接拒絕執行，避免 agent 跳過確認。

使用者在 intake 明確選擇時可啟用快速 flow：agent 會記錄 `fast_mode=true`，依文件化的風格預設自動完成風格與規劃 gate，並在審閱階段提供回復到詳細 flow 的指令。審閱通過後可選擇匯出 `.pptx`、單檔 HTML 簡報，或兩者都要。

> **輸出方式是 image-first。** 預覽階段由使用者選擇 SVG 快速預覽或 imagegen 高擬真預覽；最終生成階段預設使用 **imagegen** 生成整頁視覺圖，再封裝進 PPTX。成品接近高完成度視覺稿式演示頁，適合展示、彙報、繼續做影像級 retouch；頁面內的文字、圖形、裝飾元素通常不會像原生 PPT 元素一樣逐項可編輯。

## 它做什麼

適合處理這類請求：

- 「幫我做一個 PPT」
- 「把這份報告整理成演示稿」
- 「幫我做答辯 PPT」
- 「做一個產品介紹 deck」
- 「先給我幾套視覺方向看看，再決定風格」
- 「我現在只有主題和一些散材料，你先幫我把它整理成能做 PPT 的東西」

它不是模板拼貼，也不是長表單問卷。它走一條 phase-driven 的提案式工作流：

1. 輕量 intake → 輸出 baseline judgment
2. 需求確認 (`needs_confirmed`)
3. 補內容基底（`content_report.md`）
4. 風格邊界對齊 + 多套風格方向預覽 + 必要時 refinement
5. 風格確認 (`style_locked`) 與 風格拆解確認 (`style_breakdown_confirmed`)
6. 寫 整體設計 (`design_spec.md`) / 每頁規劃 (`slide_blueprint.md`) / 生成限制 (`spec_lock.md`)
7. 產生前確認 (`pre_generation_confirmed`)
8. 生成（單張或多候選）
9. 審閱 review shell，反覆 retouch
10. 審閱確認 (`review_approved`) 後匯出最終 PPT

詳細逐 phase 操作見 [`phases/00-overview.md`](./phases/00-overview.md)。

## 為什麼要做這個 skill

一般 PPT 工作流容易在兩個方向上出問題：

- **太模板化**：看起來工整，但與主題貼合度不夠，容易泛。
- **太淺**：視覺上像 PPT，但內容沒有形成真正能支撐彙報的敘事與深度。

`ppt-design-flow` 的目標：

- 前臺對話儘量輕，不把使用者拖進長問卷
- 材料偏薄時，先補內容基底，再談風格
- 風格確認靠**視覺化預覽**，不是文字描述
- 最終頁面視覺走 **image-first** 路徑，不靠後期大量補 overlay 修修補補
- 跳關由程式端擋下，agent 不能繞過確認門

## 核心特點

### Conversation-first
使用者被當成委託方，agent 被當成提案、設計、推進的設計側。首輪問題輕量、不做長表單。

### Preview-first
最終風格確認靠生成的 `首頁 / 目錄頁 / 內容頁` 預覽。預覽模式可以是 SVG 快速預覽或 imagegen 高擬真預覽，由使用者選。

### Phase-driven + 程式擋跳關
6 個 phase（`intake → content-basis → style → planning → generation → review`）+ 5 道使用者確認（需求確認 → 風格確認 → 風格拆解確認 → 產生前確認 → 審閱確認），由 `state.json` 與 builder pre-flight 強制。agent 跳關 builder 直接 exit 2 並印明確錯誤。

### 先補內容，再做風格
需求確認後若使用者沒提供完整報告材料，先寫 `content_report.md` 作為上游內容基底，後續預覽和規劃都從此延伸。

### Review 是主流程的一部分
第一版完整結果出來後不視為結束，必走 review shell loop，審閱確認通過才匯出。

## 規劃產物

- `content_report.md` — 風格前內容基底
- **整體設計** (`design_spec.md`) — 整套 deck 的全域理由、方向、連續性約束
- **每頁規劃** (`slide_blueprint.md`) — 逐頁定義頁面意圖、內容 payload、視覺策略
- **生成限制** (`spec_lock.md`) — 執行約束檔案

## 目錄結構

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

## 適用場景

答辯稿、研究彙報、專案彙報、產品介紹、募資簡報、教育訓練教材、提案 deck、內部回顧 / 彙報簡報。

特別適合：使用者只有主題或零散材料、需在風格前先把內容補紮實、需先看視覺化預覽再決定方向、最終成品必須繼承已確認預覽的視覺邏輯。

## 說明

- 預設比例是 `16:9`，除非使用者明確要求其他比例。
- 預覽頁應當是 content-bearing 的，而不是空架構或 placeholder image。
- 多個確認 gate 是刻意設計，由 `scripts/stage.py` + `assets/canvas/build.py` 程式擋住。
- 範例圖與 demo PPT 將隨後續 release 補上。

## 致謝

本專案感謝 [Linux.do 社群](https://linux.do/) 對開源分享與傳播的推動。
