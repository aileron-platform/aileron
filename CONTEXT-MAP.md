# Context Map

## Contexts

- [Aileron 資料服務](./CONTEXT.md) — 定義 Aileron 使用的資料服務、資料所有權與部署生命週期邊界
- [Aileron Marketplace](./packages/aileron-marketplace-core/CONTEXT.md) — 定義 Marketplace source、Plugin catalog、安裝與內部衍生版本的身分及生命週期邊界

## Relationships

- **Marketplace → Workspace Runtime**：Marketplace 指定 Plugin 來源與發布版本；Workspace Runtime 執行目標 Workspace 的安裝與移除操作。
- **Marketplace → Version Control**：Private Marketplace Source 與 Aileron Managed Registry 以 Git 保存可稽核且不可變的發布內容。
