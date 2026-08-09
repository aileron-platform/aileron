---
title: ProductShell 與語意產品區域
---

# ProductShell 與語意產品區域

本頁定義 Workspace、Knowledge Base 與 Marketplace 共用的產品工作區 Shell。`ProductShell` 是唯一的共用 Shell interface；產品路由、授權、作用中功能與內容由各產品 Adapter 解析後交給它。Shell 只理解語意區域、幾何、互動狀態與版面偏好，不理解產品名稱或功能規則。

## Interface

`frontend/src/shared/components/shell/ProductShell.tsx` 的 `ProductShell` 接受下列 props：

| Interface 欄位 | 責任 |
|---|---|
| `topBar` | 全域導覽內容；可省略 |
| `header` | 產品頁面標頭；可省略 |
| `body` | `regions` 或 `state` 其中一種 Shell body |
| `preferences` | 版面偏好 Adapter；提供 identity、load 與 save |
| `display` | 主內容展開或 Companion 全螢幕的 display state；可省略 |

`body.kind = 'regions'` 必須提供 `main`，並可提供 `navigation`、`navigator` 與 `companion`。`body.kind = 'state'` 提供一個完整內容狀態，適用於產品的 loading、denied 或 error 畫面。狀態畫面仍由 `ProductShell` 承載，不由產品 Adapter early return 繞過 Shell。

## 語意區域

| 區域 | Interface 責任 | 可省略 | 內容 owner |
|---|---|---:|---|
| `navigation` | 產品層級導覽與主要功能選擇 | 是 | 產品 Adapter |
| `navigator` | 目前功能的檔案樹、清單、設定類別或操作入口 | 是 | 產品 Adapter |
| `main` | 主要內容、詳情、編輯器或工作台 | 否 | 產品 Adapter |
| `companion` | Chat、Terminal 或其他輔助工作區 | 是 | 產品 Adapter |

每個 column region 提供 `content`、`behavior` 與 `presentation`：

- `content` 接收 collapsed state，負責產生區域內容。
- `behavior` 宣告 `collapsible`、`resizable`、`defaultWidth`、`minWidth` 與 `maxWidth`。
- `presentation` 提供 accessible label、chrome variant、responsive policy 與 header slots。

Companion 另外宣告 `side` 與 `bottom` 兩組尺寸政策、`side | bottom` placement、collapsed content、收合／展開／Resize 文案與 reveal request id。產品只提供內容和能力；placement、尺寸、收合、Resize 與主內容空間由 Shell 執行。

## Shell implementation

`ProductShell` 的 implementation 擁有所有跨產品幾何與互動：

- 依 `topBar`、可選 `header`、`navigation`、`navigator`、`main`、`companion` 的實際存在組合 body。
- 以 region behavior clamp 寬度與高度，並保留主內容的最小可用寬度與高度。
- 管理 column 與 Companion 的 Resize、收合、responsive 隱藏、overflow、scroll、focus cursor 與 fullscreen。
- 以 `data-shell-region`、`data-shell-body` 與 `data-shell-state` 提供穩定的測試 surface。
- `main-expanded` 只呈現主內容；`companion-fullscreen` 只呈現 Companion，Escape 由 display adapter 處理。
- `main` 與各內容容器使用 `min-w-0`、`min-h-0` 與自身 overflow 邊界，避免內容把水平捲動推到 document 層。

Shell 不接受產品名稱、route、capability、resource role、API response 或 feature-specific condition。任何需要這些資訊的決策都必須在產品 Adapter 或產品 surface model 完成。

## 欄位尺寸與空間退讓

Workspace、Knowledge Base 與應用市集（Marketplace）的正式 Shell preset 遵循相同的展開欄位尺寸基準：

| 語意區域 | 展開最小寬度 | 展開預設寬度 |
|---|---:|---:|
| `navigation` | 240px | 240px |
| `navigator` | 270px | 270px |

`navigation` 與 `navigator` 收合後都使用獨立的 64px collapsed rail；collapsed rail 不屬於展開欄位的最小寬度。各 preset 的最大寬度、收合、Resize 與 responsive policy 仍由其既有 behavior contract 宣告。

Workspace 的側邊 Companion 最小寬度為 408px，`main` 最小可用寬度為 320px。當側邊 Companion 與 `navigation`、`navigator` 及 `main` 的最低支援幾何無法同時容納時，`ProductShell` 暫時將側邊 Companion 呈現為 48px compact rail。可用水平空間恢復後，Shell 自動還原 Companion 在退讓前的展開狀態；這個 responsive 收合不寫入版面偏好。底部 Companion 不受此空間退讓規則影響。最低支援 viewport 維持 1024×768；低於此支援邊界不新增 navigation 或 navigator 的自動收合規則。

## 版面偏好

`ProductShellPreferencesAdapter` 是 Shell 的外部 seam：

```ts
interface ProductShellPreferencesAdapter {
  identity: string;
  load(): ProductShellPreferences | null;
  save(preferences: ProductShellPreferences): void;
}
```

Shell 以 `identity` 識別目前作用域，load 初始值，並在 layout state 變更後以 debounce save。`ProductShellPreferences` 保存 `navigation`、`navigator` 與 `companion` 的 collapsed、width、height 與 placement；所有載入值都依 region behavior clamp。

Workspace 載入版面偏好時，已儲存且符合目前 region behavior 範圍的 `navigation` 與 `navigator` 寬度予以保留；低於正式最小寬度的載入值，分別由 Shell clamp 至 240px 與 270px。

產品 Adapter 決定 identity 與 persistence policy：

- Workspace 使用 Workspace runtime identity 與 Workspace layout storage。
- Knowledge Base 與 Marketplace 不掛載 preferences adapter，因此使用 Shell 預設值且不持久化版面狀態。

## 產品 Adapter

### Workspace

`frontend/src/features/workspace/layout/WorkspaceShellAdapter.tsx` 由 `resolveWorkspaceShellSurface()` 先解析產品狀態，再建立 `ProductShellBody`：

- `navigation` 是 Workspace sidebar。
- `navigator` 依目前 feature、subView、Reader capability、Terminal 頁面與 main expanded 狀態決定是否存在。
- `main` 是 Workspace feature content。
- `companion` 在 Runtime 存在且 Chat 或 Terminal capability 可用時掛載；Terminal 可選 side 或 bottom placement，Chat 可進入 fullscreen。
- Workspace Provider、Version Control Provider、Realtime Provider 與 File Workbench orchestration 留在 Workspace Adapter 或其產品 owner，不進入 Shell。

Workspace 的 `WorkspaceShellSurfaceModel` 是純決策 interface，包含 active agent tool、navigator 是否存在、main expanded、Companion active tab、Companion placement 與 fullscreen 等結果。它不渲染 DOM，也不執行 API mutation。

### Knowledge Base

`frontend/src/features/knowledge-base/components/KnowledgeBaseShellAdapter.tsx` 將 Knowledge Base surface 映射為 `ProductShellBody`：

- list 與 detail 內容可提供 `navigation`、`navigator` 與 `main`。
- loading、permission denied 與 error 使用 `body.kind = 'state'`，仍保留產品提供的 header。
- Knowledge Base 不提供 Companion，因此 Shell 不建立空的 Companion 區域。
- Knowledge Base Files、Version Control、sharing、workspace attachment 與 settings 的 route、query、permission 與 API mapping 留在 Knowledge Base owner。

### Marketplace

`frontend/src/features/marketplace/components/MarketplaceShellAdapter.tsx` 將 catalog、detail、editor 與 settings surface 映射為相同的 `ProductShellBody` interface。Marketplace 不提供 Companion。

Marketplace Settings 的現行區域契約如下：

| 區域 | 內容 |
|---|---|
| `navigation` | 設定類別；Version Control 作用中時展開 `changes` 與 `history` 子選單 |
| `navigator` | 一般設定、SSH key、活動紀錄的完整內容，或 Version Control 的 branch、sync、file changes／history list |
| `main` | Version Control 的 Diff 或 Commit 詳情；其他設定不建立空白第三區域 |

Version Control 子選單以 `section=versionControl&submenu=changes|history` 表達；缺少 `submenu` 時使用 `changes`。Route parser、query、selection 與 authorization 由 Marketplace owner 處理，Shell 只承載結果。

## 內容與狀態契約

產品 Adapter 必須先完成 route、resource role、platform operation 與 runtime availability 判定，再決定要提供 regions 或 state：

- 未解析完成的資料不能交給 Shell 推導。
- `state` 內容必須填滿 `main` 區域可用空間，並在自身邊界管理 scroll。
- 不存在的區域不建立 placeholder、空欄或空間保留。
- Read-only control 是否顯示與 disabled 由產品 capability model 決定；Shell 不做授權判斷。
- i18n label、aria label、error message 與操作文案由產品或 shared locale contract 提供，不寫死在 Shell。

## Module ownership 與禁止依賴

| Module | 可以依賴 | 不可以擁有 |
|---|---|---|
| `shared/components/shell` | neutral region types、layout preferences、UI primitives、i18n accessor | 產品 route、功能名稱、resource role、API query、產品 capability |
| Workspace Adapter | Workspace Provider、surface model、Workspace content、Workspace preferences | 第二套 column geometry、產品自有 Resize handle |
| Knowledge Base Adapter | Knowledge Base route／permission／content contract | Companion 或另一個 Shell implementation |
| Marketplace Adapter | Marketplace surface、settings route／query／content contract | 巢狀 Shell、第二組 mode rail、產品自有欄寬計算 |

產品間的跨模組引用仍只經各自 root `public.ts`；Shell 不成為跨 feature domain data 的交換站。只有真正 neutral 的 Shell types、preferences 與 presentation contract 位於 shared。

## 程式索引

| 責任 | 目前 owner |
|---|---|
| Shared Shell interface 與 implementation | `frontend/src/shared/components/shell/ProductShell.tsx`、`productShellTypes.ts` |
| Shared preference normalization | `frontend/src/shared/components/shell/productShellPreferences.ts` |
| Workspace surface decision | `frontend/src/features/workspace/layout/workspaceShellSurfaceModel.ts` |
| Workspace Adapter | `frontend/src/features/workspace/layout/WorkspaceShellAdapter.tsx` |
| Knowledge Base Adapter | `frontend/src/features/knowledge-base/components/KnowledgeBaseShellAdapter.tsx` |
| Marketplace Adapter | `frontend/src/features/marketplace/components/MarketplaceShellAdapter.tsx` |
| Cross-product visual／interaction fixture | `frontend/e2e/fixtures/product-shell.tsx`、`frontend/e2e/product-shell.spec.ts` |
| Architecture boundary test | `frontend/src/architecture/frontendArchitecture.test.ts` |

## 驗證契約

Shell 的 test surface 必須同時驗證 interface 行為與產品 Adapter：

- Shared unit tests 驗證 region behavior、clamp、preferences、Resize、collapse、placement 與 fullscreen。
- Workspace、Knowledge Base、Marketplace tests 驗證 surface model、state body、region presence 與 capability mapping。
- Product Shell E2E fixture 驗證欄位 owner、viewport 邊界、document overflow、dialog／menu 邊界與三產品共同互動。
- 前端 architecture test 驗證 shared 不依賴 feature、feature 只使用公開入口，以及 `ProductShell` 是跨產品的 Shell seam。
- 前端所有正式測試、typecheck、lint、build 與 E2E 驗證都在 project test container 內執行。
