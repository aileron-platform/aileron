---
title: Registry 與治理
---

# Registry 與治理

Platform admin 在應用中心管理 Managed Plugins，並在 Marketplace Settings 管理 Managed Registry、Git identity、SSH 金鑰、版本控制與活動紀錄。

Managed Registry 是可變的 working tree。Aileron 不建立不可變 release tag、不自動 commit 或 push，也不追蹤外部 Marketplace Source。Git 操作由使用者自行決定；系統不提供內容 rollback。

Import 只在操作期間讀取 Git 或 ZIP 來源，並把選取內容與來源證明複製進 Registry。來源不是持續存在的產品物件，沒有 refresh、removal impact、sync 或 update 狀態。

Activity 是 append-only terminal audit，action 為 `import`、`install`、`copy` 或 `delete`，不是 authoritative installation lifecycle。CLI 命令結果依既有 audit 保存期限保留。
