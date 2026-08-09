---
title: 前端架構
---

# 前端架構

本文件說明 Aileron 前端的模組邊界、Workspace canonical route、Shared Components 分類，以及命名與複用規則。共用產品 Shell 的 interface 與三個產品 Adapter 詳見[ProductShell 與語意產品區域](/architecture/frontend/product-shell)；跨產品版本控制與 Repository Setup 詳見[共用版本控制與 Repository Setup](/architecture/overview/version-control)。

## 架構總覽

前端採用 feature-oriented 架構，讓產品領域擁有自己的 route、畫面、狀態與 API mapping，同時將真正跨領域的能力留在 `shared`。

目前的架構涵蓋 Workspace、Workspace Automation、Shared Components、AI Chat、Knowledge Base、Marketplace 與 User Management：

- Workspace route gate、ProductShell Adapter、Provider、Reducer 與 file-tree orchestration 依單一責任拆分，不集中於巨型檔案。
- `workspace-automation` 是唯一的 Automation 前端模組。
- Workspace 不依賴 `app` 內部實作，跨 feature 依賴不形成循環。
- 需要 Workspace runtime identity 的功能使用 workspace ID-scoped canonical route；建立前流程、全域 selector、全域 Automation 與外部 deep link adapter 是明列例外。
- `workspace/features/*` 有明確的私有子功能 ownership，不以形式化扁平化取代領域邊界。
- Shared Components 依穩定責任分類，透過明確 package entry 對外，feature-specific ownership 不滲入 shared。
- AI Chat 的 route page、API、model、storage、realtime 及 attachment contract 各有明確 owner，跨模組整合只經根 `public.ts`。
- Knowledge Base 的 lifecycle、檔案、版本控制、sharing、workspace attachment 及 settings 維持單一 feature owner，非 React adapter／model／API snapshot 不混入 `components`。
- Marketplace 的 center、detail、editor 及 settings 是同一模組的私有子領域；route page、storage、model、detail／editor 專屬元件與檔案 workbench adapter 各自歸入明確 owner。

### Same-origin 網路契約

Frontend 不擁有 API base URL、public URL、Runtime host 或動態 port 設定。API、OAuth、Runtime、Browser、Canvas 與 WebSocket builder 只組合目前 Origin 下的 `/api/v1/...` 與 `/workspaces/{uuid}/runtime|browser|canvas/...` 相對路徑。Nginx／Vite gateway 只接受 canonical Workspace UUID 與固定 target；每個 Workspace gateway request 先透過 Manager 的 resource operation gate 驗證讀取權限，再將所有瀏覽器 Cookie、Authorization、proxy authorization、API key 與 CSRF header 從執行平面 upstream 移除。Manager API session cookie 僅限 `/api/v1`，另以限縮於 `/workspaces` 的 HttpOnly gateway session cookie 支援授權子請求。Gateway 保留必要的 `X-Forwarded-*`、streaming、WebSocket Upgrade 與 subprotocol。唯一保留的 Vite build capability flag 是 `VITE_BROWSER_EXTENSION_ID`。

## 依賴方向

正式依賴方向為：

```text
app → features → shared
app → shared
```

各層責任如下：

- `app`：application composition、頂層 router、global navigation 與 provider 組合。
- `features`：產品領域、route-visible page、domain state 與 API adapter。
- `shared`：不含產品 ownership 的 UI primitive、layout primitive、workflow、i18n、API infrastructure 與 utility。

禁止下列依賴：

```text
shared ✕→ app
shared ✕→ features
feature ✕→ app internals
feature ✕→ sibling feature internals
```

頂層大模組之間的引用只能經由對方根目錄的 `public.ts`，不得深入引用對方的 `components`、`hooks`、`model`、`providers` 或 `api`。`workspace/features/*` 與 `marketplace/features/*` 都是所屬大模組內的私有子功能；各子功能可直接引用自身內部與大模組根層契約，但不得引用 sibling 子功能，也不得建立 nested `public.ts` 或 `index.ts` barrel。兩個以上私有子功能共同需要的 domain 能力，提升到大模組根層的語意資料夾，而不是從其中一個子功能對外輸出。

`frontend/src/architecture/frontendArchitecture.test.ts` 以 TypeScript AST 解析靜態 import、import type、export、dynamic import 與 `require`，持續守護上述邊界：禁止所有 feature 依賴 App、Shared 反向依賴 App／Features、任何外部 consumer 深入引用 feature internals，以及任一 `<top-feature>/features` 下的 nested feature 互相引用。Filesystem 規則另外要求每個頂層 feature 只有根層 `public.ts`，並禁止 feature 內出現 nested `public.ts(x)` 或 `index.ts(x)` barrel。

### Feature 公開入口與延遲載入

`app` 與兄弟大模組不得知道 feature 內部的 page、context、hook 或 module 檔案路徑。每個需要被外部使用的 feature 都以根目錄 `public.ts` 定義最小公開契約：

- `auth/public.ts` 輸出 `RequireAuth`、`PublicRoute`、`AuthProvider`、`useAuth`、`OidcUserProfile`，以及 `loadLoginPage`、`loadRegisterPage`、`loadCallbackPage`。App Shell、App Provider、Global Navigation 與其他大模組只從此處使用認證契約。
- `knowledge-base/public.ts`、`marketplace/public.ts`、`user-management/public.ts` 與 `workspace-automation/public.ts` 分別提供 `loadKnowledgeBaseModule`、`loadMarketplaceModule`、`loadUserManagementModule` 與 `loadAutomationModule`。loader 在 feature 邊界內將 named module component 轉成 `React.lazy` 需要的 `{ default: Component }`，不為此恢復 component default export。
- `ai-chat/public.ts` 提供 `loadAiChatPage`、Companion、timeline、settings、query key 及 integration context 等實際跨模組契約。Workspace 只透過該 loader 組合 `AiChatPage`；Workspace Automation 只透過同一公開入口取得 thread query 與 timeline 契約。
- AppRouter 只從各 feature `public.ts` 取得 route component 或 lazy loader；延遲載入時機、route boundary、Suspense fallback、route JSX 與 URL 契約由此維持一致。feature 內部可依實際 ownership 使用相對路徑，不從自己的 public entry 回繞。

這個規則是單向邊界，不是 giant barrel。`public.ts` 不轉匯所有內部 symbol，也不為資料夾對稱而建立空入口。

## 主要產品領域模組 ownership

| 模組 | Ownership | 不負責 |
|---|---|---|
| `workspace` | Workspace identity、Shell、runtime composition、檔案管理、版本控制、Workspace Settings、Container、Canvas 與 Agent Settings | 全域導覽實作、Automation domain、通用 UI primitive |
| `workspace-automation` | `/automation` Dashboard、workspace-scoped Automation page、job、execution、排程表單及 Automation API | Workspace Provider、Workspace layout、Workspace 內部 route parser |
| `workspace-wizard` | Workspace 建立前的四步表單、branch lookup、建立與 setup polling | 已存在 Workspace 的 runtime route 與 Provider state |
| `ai-chat` | Thread、Turn、timeline、Agent event normalization、attachments 與 Chat UI | Workspace route／runtime ownership、Automation job lifecycle |
| `auth` | 登入、callback、session bootstrap 與 authenticated principal | Workspace／Knowledge Base 資源授權決策 |
| `marketplace` | Marketplace center、package detail、canonical editor、settings、Registry lifecycle 與 user-copy management | Knowledge Base editor、通用 editor framework、Workspace runtime ownership |
| `knowledge-base` | Knowledge Base lifecycle、檔案、版本控制、sharing、workspace attachment 與 settings | Marketplace Registry package lifecycle、Workspace runtime ownership |
| `user-management` | Users、groups、role issue 與成員管理流程 | Knowledge Base 專屬群組語意、全域 navigation state |

`knowledge-base` 是正式資料夾名稱；文件或程式碼不混用 `knowledge`、`knowledgeBase` 資料夾或 `KB` 檔名縮寫。

## 授權資料邊界

`auth` 保存 `/api/v1/oauth2/session` 回傳的 `admin | member` 平台角色與後端產生的 platform `allowedOperations`。平台級 route、query 與 mutation 直接依 operation gate；Workspace 與 Knowledge Base feature 則正規化後端提供的 `accessRole`、`accessSource`、完整 `accessSources` 與 resource `allowedOperations`。未知 operation、缺少欄位或格式錯誤一律 fail closed。前端只保留已知 `OperationId` 型別，不維護角色 requirement map，也不從角色 rank 推導 mutation。

全域入口與建立按鈕對所有有效 Member 開放；User Management、Platform Resources、Marketplace canonical publish／Registry 與 Canvas publish 使用 Admin platform operation。已存在資源的 route、query、WebSocket、Provider、dialog 與 mutation 一律依後端 `allowedOperations`。收到結構化授權錯誤或視窗重新取得焦點／可見性時，只刷新目前作用中的授權資料。降級但仍可讀時保留記憶體草稿並禁止提交；完全撤權時卸載內容、連線與草稿。Reader 的主要 control 保留但停用，不顯示 tooltip 或唯讀 Banner，也不能先建立 request、dialog 或 session。

## 資料夾結構

```text
frontend/src/
  app/
    components/
      navigation/
    routes/
    providers/

  features/
    workspace/
      WorkspaceModule.tsx
      public.ts
      api/
      availability/
      config/
      deep-link/
      hooks/
      integrations/
      routes/
      layout/
        WorkspaceShell.tsx
        WorkspaceShellAdapter.tsx
        WorkspaceFeatureContent.tsx
        WorkspaceSidebar.tsx
        WorkspaceCompanionColumn.tsx
        hooks/
      model/
      providers/
      query/
      realtime/
      selection/
      services/
      storage/
      features/
        agent-settings/
        browser/
        canvas/
        container-management/
        file-management/
        version-control/
        workspace-settings/

    workspace-automation/
      AutomationModule.tsx
      public.ts
      routes/
      pages/
      components/
      hooks/
      api/
      model/
      providers/

    workspace-wizard/
      WorkspaceWizardPage.tsx
      public.ts
      components/
      hooks/
      model/
      services/

    ai-chat/
    auth/
    marketplace/
    knowledge-base/
    user-management/

  # 本節相關 shared 路徑節錄
  shared/
    components/
      ui/
      layout/
      shell/
      markdown/
      monaco/
      split-pane/
      file-workbench/
      document-workflow/
      document-resource/
      hook-workflow/
      mcp-workflow/
      settings-workflow/
      resource-workflow/
      slash-command-picker/
      version-control/
    api/
    hooks/
    locales/
    services/
    utils/
    …
```

Workspace 子領域依 ownership 放在 `features/`；此架構不建立新的 layout engine、全域 state framework、Universal Editor 或 Universal Workspace Controller。

`workspace/features/*` 表示 Workspace 大模組內的私有子功能，不是第二套頂層 feature。Agent Settings、Canvas、Container Management、File Management、Version Control 與 Workspace Settings 都依賴 Workspace route、runtime 或 Provider composition，因此保留在此層。只有同時擁有獨立頂層入口與跨大模組使用者的 Workspace Automation 提升為 `features/workspace-automation`。

### Workspace 根層 ownership

Workspace 根層依責任使用語意資料夾，不以單一模糊的 `types` 或 `utils` 收納不同性質的程式：

- `WorkspaceModule.tsx`：Workspace route composition；`public.ts`：唯一跨大模組入口，只輸出已證實的外部契約。
- `api/`：Workspace lifecycle 與 runtime HTTP mapping；`storage/`：ProductShell layout 與 tab persistence。
- `availability/`：進入Workspace前的fail-closed guard與不可用狀態頁；`config/`：browser extension部署設定。
- `layout/`：Workspace runtime gate、`WorkspaceShellAdapter`、ProductShell semantic regions、欄位 content presentation 與純 layout model。
- `hooks/`：跨 Workspace 子功能的 orchestration，例如 runtime、route sync、delete fallback 與 Git context query adapter。
- `model/`：Workspace domain type與Git context；`services/`只擁有browser extension pairing transport，不作為通用catch-all。
- `query/`：Workspace-wide query cache orchestration；不放 feature-specific UI 或 HTTP mapping。
- `providers/`、`selection/` 與 `realtime/`：分別負責 Workspace state composition、selected-workspace contract 與即時事件生命週期。
- `routes/`、`deep-link/` 與 `integrations/`：分別負責 URL adapter、外部檔案連結解析，以及對其他大模組 public contract 的薄整合層。
- `features/`：Workspace-private domain implementation。每個 nested feature 只能直接引用自身內部、Workspace 根層契約、全域 `shared`，或其他頂層大模組的 `public.ts`。

`features/workspace/features` 不建立第二層公開 API。若兩個 nested feature 需要同一個 Workspace-specific query 或 orchestration，將最小契約提升到根層 `hooks/`、`query/`、`providers/` 等對應資料夾；不以 sibling deep import 或 nested barrel 解決。

Provider state 只保存 UI、layout、navigation、file-management 與 context contract；HTTP response DTO 放在 `api/workspaceApiTypes.ts`，不混入 Provider state type。一般 `useWorkspace` consumer 由 `providers/WorkspaceProvider` façade 取得；只有由 Provider 本身組合、若經 façade 會形成循環的 AI Chat integration 與 file chooser 直接引用同一個 `WorkspaceContext` owner，不建立第二個 Context instance。檔案分頁目前只有一種 file-management scope，因此 action、Context、cache key 與 persistence 不保留單一值 scope abstraction；Git context ID 仍負責隔離 primary／worktree 分頁，`workspace_tabs_file-management_<workspaceId>_ctx_<contextId>` 是現行 key。

Workspace root `realtime/` 擁有 Workspace WebSocket manager、terminal policy、xterm instance registry 與 terminal store；container-management 的 React components 只消費這些 domain contract。`realtime/` 不反向深入引用 `workspace/features/*`，components 也不各自重複 dispose 同一 terminal instance。

### Workspace layout ownership

Workspace core presentation 一律放在 `features/workspace/layout`，不混放於 generic `components/`：

- `WorkspaceShell.tsx`：runtime full-page gate、重試／刪除動作，以及 `WorkspaceShellAdapter` 的 mount boundary。
- `WorkspaceShellAdapter.tsx`：解析 Workspace surface、組合 `ProductShellBody`、ProductShell preferences、Version Control Provider 與 Realtime Provider。
- `WorkspaceFeatureContent.tsx`：second／main feature lazy mapping、Suspense fallback 與 feature-specific content props，不擁有 route 或 Provider state。
- `WorkspaceSidebar.tsx`、`WorkspaceCompanionColumn.tsx`：Workspace 專屬欄位 content presentation；欄位幾何、resize、collapse 與 fullscreen 由 ProductShell 提供。
- `layout/hooks/useWorkspaceDocumentSelection.ts`：document dirty／blocked selection；`storage/workspaceShellLayoutStorage.ts`：Workspace layout preferences 的 identity、payload 與 persistence。
- `workspaceShellSurfaceModel.ts`、`workspaceSidebarModel.ts`、`agentToolNavigationModel.ts`：純 layout／navigation decision，不存 feature state。

`features/workspace/features/*` 維持 Workspace-private 子領域；只有真正的 core layout 可進入 `layout/`，domain panel 不因被 Shell 使用就搬入此資料夾。

### Workspace Wizard 邊界

Workspace Wizard 是建立前流程，因尚未有 `workspaceId`，合法入口固定為 `/workspaces/workspace-wizard`。它不依賴 `app` internals：`app` 只從 `workspace-wizard/public.ts` lazy-load page，並注入 global navigation slot 與 authenticated user ID。Wizard 內部以 `model/` 保存表單 contract，step 直接引用實際 owner，不建立 `index.ts` barrel 或未使用的 Module wrapper。

建立 API 成功後，`createdWorkspaceId` 是唯一建立結果；readiness retry 只重新查詢該 ID，不再次 POST 建立另一個 Workspace，不改四步流程的 DOM、class、i18n key 與正常導向。

## Workspace canonical route

Workspace runtime identity 一律來自 URL 的 `workspaceId`。正式路由如下：

```text
/workspaces/:workspaceId/home
/workspaces/:workspaceId/files
/workspaces/:workspaceId/version-control/:subView?
/workspaces/:workspaceId/workspace-settings/:subView?
/workspaces/:workspaceId/container-management/:subView?
/workspaces/:workspaceId/workspace-automation
/workspaces/:workspaceId/canvas
/workspaces/:workspaceId/browser
/workspaces/:workspaceId/:agentTool/:subView?
```

路由規則：

1. `/workspaces` 依目前選取的 workspace 導向其 canonical home；沒有 workspace 時才進入 wizard。
2. 任一 scoped route mount 時，以 URL `workspaceId` 同步 selected workspace。
3. workspace selector 切換後導向新 workspace 的 canonical home。
4. route builder 必須明確接收 `workspaceId`，不從全域狀態隱式推測。
5. query、hash 語意維持不變；只有明確含 `:subView?` 的功能路由支援子畫面。
6. `/workspace/*` 是外部檔案連結 resolver，不屬於 `/workspaces/...` 應用路由家族。它是唯一明定保留的入口，僅負責解析檔案路徑並立即導向 `/workspaces/:workspaceId/files?open=...`，不參與其他應用路由邏輯。

不含 workspace ID 的合法入口只有下列四類：

| 路徑 | Owner | 不含 ID 的原因 |
|---|---|---|
| `/workspaces` | Workspace selection | 先解析目前選取項，再導向 canonical home 或 Wizard |
| `/workspaces/workspace-wizard` | Workspace Wizard | 建立前尚不存在 workspace ID |
| `/automation` | Workspace Automation | 跨 Workspace 的全域 dashboard |
| `/workspace/*` | External deep link adapter | 解析檔案路徑後立即導向 scoped files route |

除上表四類入口外，Workspace 功能路由都必須帶有 `workspaceId`，並使用上方列出的 canonical route pattern；route builder 不建立其他無 ID 的 Workspace 子路徑。

全域 `/automation` 由頂層 `workspace-automation` 大模組擁有，刻意不含 `workspaceId`；只有 `/workspaces/:workspaceId/workspace-automation` 使用 Workspace runtime identity。兩者是各自獨立的入口，互不轉發。

## Workspace 與 Workspace Automation 邊界

`workspace/public.ts` 只輸出外部 consumer 真正需要的穩定契約：

- `loadWorkspaceModule`，供 app router 合法 lazy-load，避免 selection context 讓整個 Workspace chunk 提前載入。
- `WorkspaceSelectionProvider`、selection hook 與只讀 `readSelectedWorkspaceId` contract，供 app composition、Global Navigation 與 Marketplace reader 使用；storage implementation 保持私有。
- `WorkspaceFileDeepLinkRoute`，供 AppRouter eager 處理外部 `/workspace/*` 檔案連結，不連帶載入完整 Workspace chunk。
- `fetchWorkspaceList`，供 Knowledge Base attachment candidate 等外部 consumer 讀取最小 Workspace 清單；recent-workspace preference 不是 Workspace domain API，統一由 `shared/api/recentWorkspaceApi.ts` 供 Auth callback 與 Workspace Provider 使用。

AI Chat integration adapter 由 Workspace 內部組合；AI Chat 不為了取得 runtime、file chooser 或 Canvas action 而 import Workspace public surface。它不輸出完整 Provider state、reducer action、layout model 或任意 component barrel。

`workspace-automation/public.ts` 只輸出：

- `loadAutomationModule`，供 AppRouter 維持 Automation 的延遲載入邊界。
- `WorkspaceAutomationPage`，供 Workspace 的薄 route adapter 組合 workspace-scoped 畫面。

Workspace 只能透過這個 public surface 渲染 Automation。Workspace Automation 不反向引用 Workspace internals；`workspaceId`、`runtimeBaseUrl` 與必要 capability 由 route adapter 以 props 傳入。

全域 `/automation` 與 workspace-scoped Automation 共用 feature-local `AutomationJobTable`、pagination 與 execution controller；scope adapter 只表達 workspace 欄位、copy 與不同的 cell DOM。dialog chrome、page layout 與不同 lifecycle 維持分開，不以 universal form 或大量 boolean variant 強迫共用。

目前 Workspace Automation 的邊界為：

- `features/workspace-automation` 是唯一大模組。
- AppRouter 只從根 `public.ts` 取得 `loadAutomationModule`；Workspace 只透過薄 `WorkspaceAutomationRoute` 渲染 workspace-scoped page，route owner 唯一。
- route adapter 僅傳入 workspace/runtime/locale contract；Workspace Automation 不 import Workspace 或 App internals，AI Chat contract 只經 `ai-chat/public.ts`。
- neutral runtime URL resolver 位於 `shared/utils/runtimeUrl.ts`；全域與 workspace page 共用 feature-local job table 與 pagination，但資料取得、close lifecycle、dialog 與 page orchestration 仍由各頁擁有。

## AI Chat 架構

AI Chat 是 Workspace home route 與 companion column 共用的獨立大模組。它不 import Workspace internals；Workspace 注入 runtime、file chooser 與 Canvas 整合，Workspace Automation 只經 `ai-chat/public.ts` 使用必要契約。模組分類如下：

```text
features/ai-chat/
├── AiChatPage.tsx
├── api/
│   ├── threadApi.ts
│   ├── threadApiHttp.ts
│   └── threadQueryKeys.ts
├── attachments/
│   ├── attachmentConstraints.ts
│   ├── attachmentModel.ts
│   └── uploadChatAttachment.ts
├── components/
├── contexts/
├── events/
├── hooks/
├── model/
│   ├── questionFormModel.ts
│   ├── threadCapabilitiesModel.ts
│   ├── threadErrorNoticeModel.ts
│   ├── threadListModel.ts
│   ├── threadModel.ts
│   ├── threadSelectionModel.ts
│   ├── threadSettingsModel.ts
│   ├── threadStatusModel.ts
│   ├── threadTimelineModel.ts
│   └── threadTitleModel.ts
├── realtime/threadEvents.ts
├── storage/aiChatStorage.ts
└── public.ts
```

分類規則：

- Workspace `home/*` 顯示的 route-visible component 固定命名為 `AiChatPage`；公開 lazy loader 為 `loadAiChatPage`。
- API request type 使用 `Payload`／`Query`，HTTP mapping 與 query key 放在 `api/`；attachment kind、upload response 與 operation 由 `attachments/attachmentModel.ts` 擁有。
- thread 本體、capability、timeline 與各純規則依 domain owner 拆入 `model/`。根層不重新建立無語意 `types.ts`、`utils.ts` 或 `constants.ts`，大模組內也不新增 nested barrel。
- `AgentMode` 是前端 TypeScript 型別名稱；serialized 欄位 `claudeMode` 及 `execute`／`plan` 值是目前 contract。五組 `aichat.*` storage key、payload、讀取順序與最終值依同一 contract 解析。
- Home 與 Companion 共用 `threadSelectionModel` 的純 precedence；caller 先提供已排序／已過濾 threads，query、saved ID、第一筆的次序不變。Page／Companion 各自擁有 selection state、last-thread storage 與 removal fallback。
- 純資料解析、格式化或錯誤 notice 決策放在 `model/*Model.ts`；`components/` 只保留 render、interaction 及 Context／registry 等 presentation owner。不把純 model 放回 component 資料夾。

Shared adoption：

- AI Chat 使用 Shared Markdown、form／dialog primitive、collapsed sidebar controls、Shell 寬度 token 及 File Workbench drag payload，不在 feature 內重做這些 contract。
- Home thread column 是 AI Chat feature-local content，維持 320–560px、collapsed 64px、mount-local 且沒有 separator ARIA；它不宣告 ProductShell region，避免把 AI Chat 的獨立 selection lifecycle 混入共用 Shell。
- `WorkspaceFileChooserDialog` 維持 quick filter 與立即單選，不由含 toolbar／search／multi-select／drag 的完整 File Tree workflow 取代。AI Chat git diff 與 shared version-control diff 的 parser、grid、loading／empty DOM 不同，也不強制合併。
- Companion 外層由 Workspace 的 ProductShell `companion` region 持有；AI Chat 只提供 content、tab 與 capability mapping，不建立第二個 Shell。Message／Tool／Question Form 維持 AI Chat feature-local owner。

Query key 的唯一 owner 為 `api/threadQueryKeys.ts`，跨 feature 需要的 key 只由根 `public.ts` 公開。`useThreads.patchDraft` 成功後與 create、detail 及 realtime 相同，以 `aiChatThreadQueryKey(workspaceId, thread.id)` 寫入 canonical workspace-scoped cache。

## Knowledge Base 架構

Knowledge Base 是 `/knowledge-bases` 大模組，擁有知識庫 lifecycle、檔案、Git、sharing、workspace attachment 及 settings；外部只經根 `public.ts` 取得 lazy module loader 或三個確實跨模組的 type。

```text
features/knowledge-base/
├── KnowledgeBaseModule.tsx
├── public.ts
├── adapters/
│   └── file-workbench/
│       ├── knowledgeBaseFileTreeDataAdapter.ts
│       └── knowledgeBaseFileWorkbenchAdapter.ts
├── api/
│   ├── knowledgeBaseApi.ts
│   └── knowledgeBaseVersionControlSnapshot.ts
├── components/
│   ├── KnowledgeBaseFilesTab.tsx
│   ├── KnowledgeBaseVersionControlTab.tsx
│   ├── KnowledgeBaseSharingTab.tsx
│   ├── KnowledgeBaseWorkspacesTab.tsx
│   ├── KnowledgeBaseSettingsTab.tsx
│   ├── KnowledgeBaseSidebar.tsx
│   ├── KnowledgeBaseCreateDialog.tsx
│   └── knowledgeBaseNavigation.ts
├── model/
│   ├── formatKnowledgeBaseFileSize.ts
│   ├── knowledgeBaseFileModel.ts
│   ├── knowledgeBaseShellModel.ts
│   └── knowledgeBaseTypes.ts
├── providers/KnowledgeBaseProvider.tsx
└── routes/
    ├── KnowledgeBaseListRoute.tsx
    ├── KnowledgeBaseCreateRoute.tsx
    └── KnowledgeBaseDetailRoute.tsx
```

分類與命名規則：

- `KnowledgeBaseModule` 只組合 Provider、top-level shell 及 nested routes；`KnowledgeBase*Route` 是 URL adapter，detail 內可見 pane 固定使用 `KnowledgeBase*Tab`。React owner 使用 PascalCase，adapter／API／model／view metadata 使用語意化 camelCase，資料夾使用 kebab-case。
- `components` 只保存 React presentation 及直接供 sidebar 使用的 Lucide icon／label metadata。Shared File Workbench adapter 位於 `adapters/file-workbench`，route／navigation 決策位於 `model/knowledgeBaseShellModel.ts`，repository status／branches／commits 的 snapshot 組合位於 `api/knowledgeBaseVersionControlSnapshot.ts`；檔案路徑（root、join、parent、name）與檔案 API 錯誤／衝突邏輯位於 `model/knowledgeBaseFileModel.ts`——root `/` 語意與 shared tree model 的 `null` parent 契約不同，因此維持 feature owner。
- 不建立 root giant barrel、nested `public.ts`、空資料夾或 compatibility re-export。App 與 Workspace consumer 只進入 `knowledge-base/public.ts`；Knowledge Base 若需 Workspace contract，只引用 `workspace/public.ts`。
- Module、route、tab、provider 一律使用 named export。Detail route 的 Version Control lazy import 在 feature 內把 named component 映射成 React.lazy 所需 default shape，不恢復 component default export。

Shared adoption：

- Top level 與 detail 由 `KnowledgeBaseShellAdapter` 映射到 ProductShell；Knowledge Base sidebar 是 `navigation` content，Files 與 Version Control 依 surface 提供 `navigator` content，main content 由 detail route 擁有。
- Files 完整使用 `FileManagementShell`、`FileManagementSidebarWorkflow`、`FileTreePanel`、shared context menu／dialogs／archive overlays 及 `FileViewerWorkbench`。Markdown、圖片、Mermaid、Drawio 與 code 由 shared viewer 分派；Knowledge Base 只保留 API、revision、permission、archive polling、clipboard 及 feature error contract。file operation response 的 revision 解析統一由 shared `file-workbench` 的 `adapters/fileResponseAdapter.ts`（`getFileOperationResponseRevision`）提供，供 Knowledge Base Files 與 Shared `useFileTreeManager` 共用。
- Knowledge Base 與 Workspace 的 dialog state 都由 `toFileManagementDialogState` 產生，該 function 由 Shared File Workbench workflow owner 輸出；兩個 consumer 傳給 `FileManagementDialogs` 的 state 逐欄一致。
- Version Control 的 data query／type 來自 `@/shared/version-control`，React presentation 來自 `@/shared/components/version-control`；不在 feature 重做 query factory、changes sidebar、diff viewer 或 remote workflow。
- Knowledge Base 不提供 ProductShell `companion` region；任意檔案樹、多 tabs、archive、raw blob 及多格式 viewer 由 Knowledge Base 與 File Workbench contract 組合，不引入 AI Chat quick chooser 或固定 document workflow 的額外 mode。

Route source-of-truth 為 `ROUTES.knowledgeBase`；UI 的 workspace attachment pane 固定使用 `workspaces(id)` 並輸出 `/knowledge-bases/:id/workspaces`。Knowledge Base attachment HTTP endpoints 為 `/knowledge-bases/:id/attachments`；API、payload 與畫面 route 不混用。

## Marketplace 架構

Marketplace 是 `/marketplace` 大模組，擁有 package center、detail、canonical editor、settings、registry storage、Registry package CRUD／version-control lifecycle，以及目前使用者的 user-copy preflight／一次性 apply 流程。成功後檔案由使用者自行管理，module 不維護 enable／disable／update／reinstall／uninstall lifecycle。App 只經根 `public.ts` lazy-load module；Marketplace 需要 Workspace selection 或 list contract 時只引用 `workspace/public.ts`。`features/marketplace-*` 是同一大模組內的 private 子領域，不是第二組頂層 feature，也不為形式對稱扁平化。

```text
features/marketplace/
├── MarketplaceModule.tsx
├── public.ts
├── adapters/
│   ├── marketplaceFileTreeAdapter.ts
│   └── marketplaceFileWorkbenchAdapter.ts
├── api/marketplaceApi.ts
├── components/MarketplaceInstallOutput.tsx
├── model/
│   ├── marketplaceFeatureCounts.ts
│   ├── marketplaceFeatureLabels.ts
│   ├── marketplacePackageActionModel.ts
│   ├── marketplacePermissions.ts
│   └── marketplaceTypes.ts
├── storage/marketplaceStorage.ts
├── utils/downloadBlob.ts
└── features/
    ├── marketplace-center/
    │   └── MarketplaceCenterPage.tsx
    ├── marketplace-detail/
    │   ├── MarketplaceDetailPage.tsx
    │   ├── adapters/marketplaceReadonlyViewerAdapter.ts
    │   ├── components/
    │   └── model/
    │       ├── marketplaceDetailHookModel.ts
    │       └── marketplaceDetailNavigationModel.ts
    ├── marketplace-editor/
    │   ├── MarketplaceEditorPage.tsx
    │   ├── components/MarketplaceEditorHeader.tsx
    │   ├── dialogs/
    │   ├── resources/
    │   ├── marketplaceFileResourceModel.ts
    │   └── marketplaceHookModel.ts
    └── marketplace-settings/
        └── MarketplaceSettingsPage.tsx
```

分類與命名規則：

- React Router 直接 render 的四個 owner 固定使用 `*Page`；可重用的 React presentation 使用 PascalCase `*Section`／`*Dialog`／`*Header`，純規則使用語意化 camelCase `*Model.ts`，storage contract 位於 `storage/`。
- 正式協定縮寫在 TypeScript identifier 與檔名一律使用 `MCP`，包含 `MarketplaceMCPPage`、`MarketplaceEditorMCPSection` 及 `marketplaceMCPServerDialogSchema.ts`；serialized feature key `mcp`、JSON 欄位 `mcpServers`、API payload／URL 與 i18n key 使用小寫 contract。
- `MarketplaceCenterPage`、`MarketplaceDetailPage`、`MarketplaceEditorPage` 與 `MarketplaceSettingsPage` 只引用自身 private 子領域或 Marketplace root 契約；四個 nested feature 之間禁止 sibling import，也不建立 nested `public.ts`／`index.ts`。
- Detail-only component、readonly adapter、hook projection 及 navigation model 歸入 `marketplace-detail`；Editor-only header、file resource model 與 Marketplace Hook parser／serializer／projection model 歸入 `marketplace-editor`。只有 Center 與 Detail 共同使用的 `MarketplaceInstallOutput` 及兩個逐字相同 pure action helper 留在 Marketplace root。
- Root 依責任分為 `api`、`adapters`、`components`、`model`、`storage` 與 `utils`；不建立模糊 `constants.ts`、`types.ts` 或 giant barrel。`'local-user'`、`'current-workspace'`、三個 Marketplace storage key 及 current → remembered → first option → sentinel 解析順序是不可變 contract。
- Marketplace 不依賴 `app` internals。authenticated user ID 由已持有 App state 的 `AppRouter` 以必填 `string | null` prop 經 Module 傳給 Settings Page，不在 feature 內反向讀 App context。

Shared adoption：

- Center／detail／editor／settings 由 `MarketplaceShellAdapter` 映射到 ProductShell；global navigation、responsive filter、detail tabs 與 editor content 依 surface 交給對應 semantic region。
- Detail 唯讀檔案區與 Editor Files 使用 Shared File Workbench 的 tree、sidebar workflow、viewer tabs、code／markdown／image viewer、context menu、dialog 及 resize mechanics。Marketplace 只保留 package API、revision、managed-root permission、path mapping 與 resource mutation。
- Detail tabs、Center responsive filters 與 File Resource workflow 各自保留 product-owned contract；Marketplace 不提供 ProductShell `companion` region，也不在 feature 內建立第二套欄位幾何。
- Detail 與 Center 的 install／export／delete dialogs 維持不同 owner 與 DOM。只有逐字相同的 command label 及 error mapping 提升為 Marketplace root pure model；不建立含大量 boolean variant 的 Universal Marketplace Dialog。
- Marketplace Hook model 包含 resource item、Marketplace i18n 與 native package JSON 投影，不提升為 provider-neutral Shared Hook contract；Detail tabs、Settings Version Control 與 Action Dialog 也沒有等價 Shared DOM／state contract，因此不強制替換。

## 複用規則

程式只有同時符合下列條件才提升到全域 `shared`：

1. 至少兩個獨立 production consumer 使用；測試引用不計入。含 domain 語意的 workflow 原則上必須跨兩個大模組；無 domain 的 foundational primitive 可由不同 production ownership 的 shared package／feature 共同證明複用。
2. 行為與契約相同，不只是外觀相似。
3. 可透過 neutral props 或 adapter 隔離 domain。
4. 抽出後不需要大量 boolean props 或 feature-specific branch。

只在同一大模組內重複的能力先放 module-local `components`、`hooks` 或 `model`。shared file-workbench、ProductShell、document-resource 與 version-control workflow 不在 feature 層重做。

### Shared root 分類與依賴邊界

`src/shared` 只承載不依賴 App、Pages 或任一 Feature 的中立能力。Shared 不設 giant root barrel；consumer 依能力引用 direct module 或該 package 的公開入口。根層分類如下：

| 分類 | Ownership | 不應放入的內容 |
|---|---|---|
| `api` | 跨大模組且 domain-neutral 的 HTTP client／adapter，例如基礎 API client、container image 與 slash command API | Workspace、Settings、Marketplace 等 feature endpoint、query 或 mutation |
| `components` | 跨 production ownership 證實可複用的 primitive、layout、content platform 與 neutral workflow | route、permission、runtime identity 或 feature-specific orchestration |
| `constants` | 全產品共用且穩定的常數，例如 canonical route contract | 單一 feature 的尺寸、狀態、filter 或 query key |
| `contexts`、`hooks` | 全產品 runtime context 與薄 accessor，例如 I18n、resolved theme 與 container images | feature store、controller、mutation 或只包一層的 convenience hook |
| `design-system` | global token、theme 與確實有 production consumer 的全域 selector | 未引用的 selector、feature-specific CSS 或顯示文字 |
| `locales` | `en`／`zh-TW` 等值 key tree、共用字詞與依 module 語意分類的翻譯來源 | 已無 production resolver 的 key、只由測試使用的翻譯副本 |
| `realtime` | 中立 WebSocket connection lifecycle 與 registry mechanics | feature event schema、subscription policy 或 domain reconnect orchestration |
| `services/logger` | 唯一跨模組 service：具 module prefix 的安全 logging contract | global mutable singleton、runtime level setter、token、auth code、verifier 或完整 authorization URL |
| `types` | 確實跨兩個以上大模組的 agentic tool、container image、I18n、slash command 與 user contract | Marketplace、Knowledge Base、Workspace、Settings 或 Git owner type |
| `utils` | 小型、無狀態、domain-neutral 的 `cn`、OAuth PKCE、runtime URL 與 type guard | file、version-control 或 feature-specific formatter／policy |
| `version-control` | VC data contract、fetcher、query factory、query key、optimistic cache 與 error mapping | React presentation、feature scope UI 或 owner-specific Git context |

Version Control 刻意保留兩個 sibling entry，而不是重複實作：`@/shared/version-control` 是無 UI 的 data package；`@/shared/components/version-control` 是 React presentation package。依賴只能由 presentation 指向 data，data 不反向依賴 component。需要 query、cache 或 type 的 consumer 不必載入 UI dependency；需要畫面的 consumer 才使用 component entry。兩者不合成 giant barrel，也不因名稱相近而做純路徑搬移。

依賴與公開入口規則：

1. `shared` 只能依賴 `shared`、第三方 package 與平台 API，不 import `app`、`pages` 或 `features`。
2. 有 package boundary 的能力使用 named export：Logger 由 `@/shared/services/logger`、VC data 由 `@/shared/version-control`、Shared Components 由各 package root 輸出。package 內一律使用 relative import。
3. `api/*`、`constants/*`、`contexts/*`、`hooks/*`、`types/*` 與小型 `utils/*` 維持語意化 direct entry，不為統一形式建立 root barrel。
4. Version Control 的 data entry 與 `shared/components/version-control` presentation entry 分離；UI barrel 不轉匯 query、optimistic update、error 或 domain type。
5. File type、icon、size 與 language 判斷由 File Workbench／viewer owner 管理；Knowledge Base 保留自己的顯示 formatter。不同顯示契約不為了「共用」而合併。
6. feature contract 一旦只有單一 owner，就搬回該 feature 的 `api/`、`model/` 或 `storage/`。
7. Locale source 檔依 module 語意命名，例如 `workspaceAutomation.ts`；runtime translation key 依 UI contract 使用 `automation`。動態 prefix 必須由 resolver test 明列合法集合。
8. Design System 只保留 live token 與 selector；刪除 CSS 前需同時確認 JSX／TSX、class composition、Markdown renderer 與動態 class builder 都無 consumer。

Shared root 的檔名遵循同一責任原則：單一 React owner 使用 PascalCase，多 symbol mechanics、API、model、adapter、storage 與 utility 使用語意化 camelCase，hook 使用 `useXxx`。不新增 `common/`、`lib/`、`misc/`、籠統 `types.ts`／`utils.ts`，也不為對稱建立空資料夾。

### Shared Components 分類與公開入口

`shared/components` 依穩定責任分類，不依目前使用它的 feature 命名：

| 分類 | 資料夾 | Ownership |
|---|---|---|
| Design-system primitives | `ui` | shadcn／Radix primitive 與跨產品一致的基礎互動 |
| Presentation 與 layout primitives | `layout`、`shell`、`split-pane` | 無 domain 的 header／collapsed presentation、多欄 slot／resize state 與通用 split pane |
| Content platform | `markdown`、`monaco` | Markdown render／edit 與 Monaco integration；不擁有 feature query、route 或 mutation |
| File workflow | `file-workbench` | file tree、adapter、archive、dialogs、sidebar workflow、viewer workbench 與 split view |
| Document workflow | `document-workflow`、`document-resource` | 純 document editing mechanics，以及 source-backed document query／selection orchestration |
| Neutral domain workflow | `hook-workflow`、`mcp-workflow`、`settings-workflow`、`resource-workflow`、`slash-command-picker`、`version-control` | 跨兩個以上 production consumer 且 contract 相同的互動流程或 presentation |

資料夾與檔案規則：

1. 一個第一層資料夾只代表一個穩定責任；不以 `common`、`misc` 或目前 feature 名稱建立 shared 分類。
2. 小 package 維持扁平；只有大型 package 在責任明確時使用 `model/`、`adapters/`、`hooks/`、`primitives/`、`tree/`、`viewer/`、`workflows/` 或 `archive/`。不為追求對稱建立空資料夾。
3. 自有且以單一 React component 為主的檔案使用 PascalCase；`ui` 內 vendor／shadcn primitive 使用 kebab-case；包含多個 symbol 的 integration／mechanics module 使用語意化 camelCase。hook 使用 `useXxx`，純 model、adapter 與 storage 也使用語意化 camelCase；`shared/components` 內不加冗餘 `Shared` 前綴。
4. shared package 可以用根 `index.ts` 定義明確 public surface；package 內部一律使用 relative import，不從自己的 barrel 回繞，也不將 internal module 為方便而加入 barrel。
5. 大模組仍只透過根 `public.ts` 跨模組；shared package 的 `index.ts` 不代表可以 deep import feature internals。
6. `ui/*`、`layout/*`、`markdown/*` 與 `monaco/*` 是 direct-entry primitive／platform integration，不建立 giant barrel；其他有 package entry 的 shared package 才受 root entry 規則約束。

`file-workbench` 刻意提供兩個入口：

- `@/shared/components/file-workbench` 是輕量主入口，提供 tree、adapter、archive、dialogs 與 management workflow。
- `@/shared/components/file-workbench/viewer-entry` 是 viewer 次入口，提供 `FileViewerWorkbench`、split view、viewer tab hooks、對應 type contract 與 `CodeTextEditor`；viewer context／toolbar 維持 package internal。
- 主入口不轉匯 viewer implementation 或 viewer type；需要 viewer runtime 或 contract 的 consumer 必須明確引用次入口。兩個入口以外不引用 `viewer/*`、`tree/*`、`workflows/*` 等 internal path。

採用 shared component 前必須同時確認：

1. 至少兩個 production 大模組需要同一 contract，且不是只有測試或未來假設。
2. DOM、class、ARIA、interaction、loading/error、keyboard、resize、persistence 與資料轉換語意相同。
3. feature 差異能留在 neutral prop、slot 或 adapter 邊界；若需要 feature 名稱判斷、大量 boolean variant 或 route/runtime knowledge，就留在 feature。
4. 現有 shared contract 能滿足時直接採用；只有兩個以上 production consumer 同時需要的 neutral 缺口，才擴充最小 API。

下列責任明確不抽象進 shared：

- feature route、runtime identity、API client、permission、domain mutation 與 feature-specific query identity；adapter-driven generic query orchestration 可以由 shared workbench 擁有。
- Workspace 專屬三／四欄 DOM、64px collapsed、300ms transition、fullscreen、bottom terminal 與 feature hide 規則。
- Automation fixed filter、Marketplace responsive filter、File Chooser modal lazy tree。
- User Management detail／filter／pagination、Create User／Package／Knowledge Base dialogs、feature-specific PluginCard／Empty State，以及 Workspace／Knowledge Base local-history UI。
- 只有單一 production consumer 的 feature wrapper、dialog chrome、toolbar、empty state 或 presenter。
- 需要 Universal Editor、Universal Workspace Controller、新 layout engine 或 schema-driven variant framework 才能整併的相似畫面。

### 檔案管理與三／四欄共用契約

這兩組大型共用能力採「先複用、再新增」：

- `shared/components/file-workbench` 的穩定主幹是 file-tree manager／adapter、`FileManagementSidebarWorkflow`、`FileManagementShell`、dialogs、`FileViewerWorkbench` 與 split view。Workspace、Knowledge Base、Marketplace 與 Agent Settings 保留各自的 API adapter、permission、domain mutation，以及必要的 runtime gate、clipboard／drag-drop 等 feature-specific orchestration。
- `shared/components/shell` 的公開主幹是 `ProductShell`、ProductShell region types、preferences adapter 與 shared presentation primitives。ProductShell 擁有 semantic region 的 layout state、resize、collapse、responsive、overflow 與 fullscreen；產品 Adapter 只提供 content、behavior、presentation 與 product state mapping。

採用規則：

1. DOM、class、ARIA、collapsed width、transition、resize、persistence、keyboard、drag/drop、loading/error 與 adapter contract 都相同時，直接採用 shared component。
2. 只有兩個以上 production 大模組共同需要的 neutral 缺口，才補最小 shared prop／slot。
3. Workspace 欄位具有 64px collapsed、300ms transition、feature hide、fullscreen、bottom terminal 與 Version Control scope 等專屬契約；Workspace Adapter 將這些限制轉成 ProductShell region behavior，由 ProductShell 統一執行幾何與互動。
4. Marketplace 檔案側欄的 resize mechanics 採用 `useResizableSidebar`，展開寬度為 320、collapsed 寬度為 44；從 collapsed 按住 separator 時先顯示 320，拖曳以 240 起算並 clamp 於 240／520，DOM、class 與 ARIA 維持同一 contract。shared hook 可接受 drag start width，但不因此改變當下 visible width。
5. `FileManagementSidebarWorkflow` 與 feature runtime gate 只有一個 `loadTree()` owner；controlled manager 不由兩個 effect 重複載入。
6. Automation fixed filter、Marketplace responsive filter 與 File Chooser modal tree 僅外觀相似，不套用 file-management workflow 或宣告式 column framework。
7. 零 production caller 且與 live workflow 重疊的 layout、toolbar、resolver 與 barrel 直接刪除，不為未來假設保留。

目前 production 採用與責任如下：

| Consumer | 共用契約 | Feature-local 責任 | 載入 owner／不採用理由 |
|---|---|---|---|
| Workspace Files | sidebar workflow、manager、tree panel、viewer workbench、split view | runtime identity、clipboard、drag/drop、file mutations、version-control refresh | `loadEnabled=false`；runtime-ready effect 唯一呼叫 `loadTree()` |
| Agent Settings | managed sidebar workflow、viewer workbench | runtime readiness 與設定頁 API | workflow 接收 refresh signal；manager `autoLoad=false` |
| Knowledge Base Files | page shell、second column、sidebar workflow、viewer workbench | Knowledge Base API、permission、rename／delete contract | `loadEnabled=true`；workflow 唯一載入，manager `autoLoad=false` |
| Marketplace files | second column／sidebar workflow／viewer workbench 或 read-only workbench | Marketplace provider API、唯讀或 editor mutation | controlled manager 直接符合 constrained generic；dialog-state generic narrowing 留在 render body 邊界 |
| Workspace File Chooser | file-tree primitives | modal preset filter、lazy expand、單檔立即選取 | 互動契約不同，不套完整 sidebar workflow |

ProductShell 依實際提供的 `navigation`、`navigator`、`main` 與 `companion` regions 組合三／四欄 DOM；Workspace、Knowledge Base 與 Marketplace 都由各自 Adapter 提供 product mapping，不建立第二套 Shell implementation。Workspace local `FileEditor` 只保留 runtime、mutation 與 split-view adapter orchestration，未重複實作 workbench。

Workspace-private file-tree orchestration 固定放在 `features/workspace/features/file-management/hooks`：主 adapter 組合 manager、runtime identity 與 hidden-file visibility；`workspaceFileTreeModel` 只做純 mapping；interaction hook 負責 selection、expand、collapse 與 drag/drop；mutation hook 負責 create、delete、copy、move、upload、download、read、save 與 version-control refresh。這些責任不提升到 `shared`，因為它們依賴 Workspace runtime 與 version-control domain；shared manager 的能力也不在此重做。

Workspace reducer 依 action ownership 拆為 layout、navigation、version control、feature settings 與 file management 純 reducer。root reducer 僅使用 exhaustive action map 分派，維持同一 `WorkspaceState`／`WorkspaceAction`；slice 不互相呼叫，也不新增第二個 store 或 mirror state。

## 命名規則

| 類型 | 規則 |
|---|---|
| 大模組／資料夾 | kebab-case |
| 自有單一 React component／檔名 | PascalCase |
| Vendor／shadcn UI primitive | 使用 vendor 定義的 kebab-case |
| 多 symbol integration／mechanics module | 語意化 camelCase |
| Hook | `useXxx` |
| 頂層入口 | `XxxModule` |
| URL／params adapter | `XxxRoute` |
| route-visible 畫面 | `XxxPage` |
| 完整互動工作區 | `XxxWorkbench` |
| 單一格式／內容呈現 | `XxxViewer` |
| slot／欄位／結構，不直接持有 API mutation | `XxxShell` |
| 無狀態 CSS／尺寸排列 | `XxxLayout` |
| 可複用有狀態流程 | `XxxWorkflow` |
| modal boundary | `XxxDialog` |
| React context owner | `XxxProvider` |
| state orchestration | `useXxxController` |
| persistence／imperative lifecycle owner | `XxxManager` |
| 純 state／transform | `xxxModel` |
| HTTP mapping | `xxxApi` |
| 契約轉換 | `xxxAdapter` |
| persistence | `xxxStorage` |
| 縮寫 | 已建立品牌／協定縮寫維持正式拼法（例如 `MCP`）；一般單字內縮寫使用 `Id`、`Url`、`Ssh` |

大模組不新增無語意的 root `types.ts`、`utils.ts`、`constants.ts`。API type 使用 `Payload`、`Response`、`Query`，表單資料使用 `FormValues`。component 與檔名同步使用 PascalCase，test 與正式 subject 同名。大模組內層不新增 `index.ts` barrel，跨大模組公開入口統一為根目錄 `public.ts`；shared package 只在第一層 package 根使用明確 `index.ts`，必要的次入口必須像 `file-workbench/viewer-entry.ts` 一樣有清楚的載入邊界。

## 測試與驗證

前端測試與靜態驗證統一在 container 執行：

```bash
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run test:run
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run typecheck
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run typecheck:shared
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run lint
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run build
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test \
  npm exec --yes madge -- --extensions ts,tsx --ts-config tsconfig.json --circular src/shared
```

- 模組依賴方向由 `src/architecture/frontendArchitecture.test.ts` 以 TypeScript AST 解析 import、import type、export、dynamic import 與 `require` 持續守護。
- i18n 一致性由 `src/shared/locales/i18nIntegrity.test.ts` 驗證。
- 文件站分別以 `--locale zh-Hant` 與 `--locale en` build，且不提交 `.docusaurus` 或 `build` 產物。

## 平台資源資料邊界

Platform Resources 將「資源管理」與「統計分析」設為獨立 route。管理 route 只載入 inventory、篩選與 mutation；分析 route 才載入摘要、分布、資源趨勢與容量趨勢，各區塊都有自己的 loading／error／retry。管理查詢與分析期間分別保存在 URL；圖表 wrapper 留在 feature 內，並提供可由鍵盤與螢幕閱讀器讀取的文字表格。Runtime telemetry、Manager ingestion、capacity policy 與 data session 的跨層 ownership 詳見[平台資源與 Runtime Telemetry 架構](/architecture/overview/platform-resource-observability)。
