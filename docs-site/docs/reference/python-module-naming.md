---
title: Python 模組與檔名規則
---

# Python 模組與檔名規則

本規範適用於 `workspace-manager` 與 `workspace-runtime`。目錄先表達 domain
ownership，檔名再表達 module 內的角色或概念。

## 目錄命名

- 一律使用小寫 `snake_case`。
- domain 目錄使用產品詞彙，例如 `knowledge_base/`，不使用 `kb/` 等縮寫。
- domain module 位於 `app/modules/<domain>/`。
- 翻譯 implementation 與資源位於 `app/modules/localization/`；不建立全域
  `translations/`。
- 不建立全域 `routers/`、`services/`、`models/`、`repositories/` 或 `contracts/`
  水平 taxonomy。
- 不以 `common/`、`shared/`、`helpers/` 或 `utils/` 隱藏不明 ownership。
- 共享 module 只有在至少兩個 domain 共同擁有且通過 deletion test 時才成立。

## Module 內檔名

父目錄已表達 domain，檔名不再重複 domain 前綴：

| 用途 | 建議 | 避免 |
| --- | --- | --- |
| HTTP mapping | `router.py` | `workspace_router.py` |
| Persistence model | `models.py` | `workspace_models.py` |
| Request／response mapping | `schemas.py` | `workspace_schemas.py` |
| Repository implementation | `repository.py` | `workspace_repository_service.py` |
| 明確領域行為 | `lifecycle.py`、`authorization.py` | `service.py`、`manager.py` |
| 外部 adapter | `oidc_adapter.py`、`http_adapter.py` | `client_helper.py` |
| Module-private policy | `policy.py` 或更明確的領域概念 | `common.py`、`utils.py` |

檔名描述 ownership 內的角色，而不是堆疊技術後綴。當 `router.py`、`models.py` 或
`repository.py` 變得過大時，應按 domain concept 拆成新的 deep module，不是改成
`router_utils.py` 或 `repository_helpers.py`。

## Interface 與 adapter 命名

- interface 以能力或 port 的領域語意命名，不使用模糊的 `IService`、`BaseService`
  或 `AbstractManager`。
- adapter 檔名表達替換維度，例如 transport 或 external system。
- 只有一個 adapter 時，不為形式對稱先建立 port；兩個 adapter 才證明 seam 真實存在。
- internal seam 可供 owning module 自己的測試使用，但不得因測試方便而暴露成外部
  interface。

## Import 規則

跨 domain import 只能指向 owning module 的 interface。不得從另一個 domain 深入
引用 repository、model 或 adapter implementation。

```python
# Good: caller depends on the owning module's interface.
from app.modules.workspace.availability import check_workspace_availability

# Avoid: caller assembles another domain's implementation.
from app.modules.workspace.repository import WorkspaceRepository
from app.modules.workspace.policy import WorkspacePolicy
```

`__init__.py` 不作為大量 re-export 的 barrel。需要公開的 interface 應由 owning
module 的明確檔案提供。

## 測試檔名與位置

```text
tests/
  unit/
    modules/<domain>/test_<behavior>.py
  integration/
    modules/<domain>/test_<behavior>.py
```

- 測試目錄鏡像 domain ownership，依 domain module 組織測試。
- 測試名稱描述可觀察行為，例如 `test_start_rejects_stale_revision.py`，不以被測 class
  名稱作唯一資訊。
- unit test 驗證 in-process 領域規則；integration test 驗證 repository、adapter、
  local stand-in 與跨 seam 行為。
- interface 是 test surface。若 implementation 重排就必須修改測試，先檢查測試是否
  穿過了 interface。
- interface test 直接驗證目前 module contract；不建立重複或無必要測試。

## Log、註解與 i18n

- Python log 與程式碼註解一律使用英文。
- 使用者可見訊息必須透過既有 i18n key 與翻譯資源，不得在 router、domain
  implementation 或 adapter 寫死中文或英文。
- Localization module 擁有翻譯 implementation 與資源；其他 module 只引用 i18n key，
  不得複製相同訊息或建立全域 `translations/`。

## Review checklist

- 目錄是否直接指出產品 ownership？
- interface 是否小於其隱藏的 implementation，形成足夠 depth？
- seam 是否真的有兩個 adapter，或只是預想中的替換點？
- dependency 是否已分類為 in-process、local-substitutable、remote but owned 或
  true external？
- deletion test 是否證明 module 提供 leverage，而非 pass-through？
- 修改、缺陷、知識與測試是否具有 locality？
- 是否只保留目前 import、interface、必要 production code 與必要測試？
