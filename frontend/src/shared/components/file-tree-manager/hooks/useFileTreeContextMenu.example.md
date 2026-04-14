# useFileTreeContextMenu Hook 使用範例

## 概述

`useFileTreeContextMenu` 是一個統一的右鍵選單項目生成 Hook，用於標準化所有檔案樹的右鍵選單行為。

## 基本用法

```typescript
import { useFileTreeContextMenu } from '@/shared/components/file-tree-manager';
import { useI18n } from '@/shared/hooks/useI18n';

const MyFileManager = () => {
  const { t } = useI18n();
  const managerState = useFileTreeState();
  
  // 生成右鍵選單項目
  const contextMenuItems = useFileTreeContextMenu({
    node: managerState.contextMenu?.node || null,
    hasClipboard: !!clipboardItem,
    t,
    callbacks: {
      onOpen: (node) => openFileInTab(node.path),
      onCreateFile: () => fileOps.openCreateFileDialog(),
      onCreateFolder: () => fileOps.openCreateFolderDialog(),
      onCopy: (node) => handleCopy(node),
      onPaste: () => handlePaste(),
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onRefresh: () => handleRefresh(),
      onClose: () => managerState.closeContextMenu(),
    },
  });

  return (
    <FileTreeContextMenu
      contextMenu={managerState.contextMenu}
      items={contextMenuItems}
      onClose={managerState.closeContextMenu}
    />
  );
};
```

## 完整範例：檔案管理

```typescript
import { useFileTreeContextMenu } from '@/shared/components/file-tree-manager';

const FileManagementView = () => {
  const { t } = useI18n();
  const managerState = useFileTreeState();
  const [clipboardItem, setClipboardItem] = useState(null);
  
  const contextMenuItems = useFileTreeContextMenu({
    // 基本配置
    node: managerState.contextMenu?.node || null,
    
    // 多選支援
    enableMultiSelect: true,
    selectedCount: managerState.selectedIds.size,
    
    // 剪貼簿狀態
    hasClipboard: !!clipboardItem,
    
    // 圖片檔案檢測
    isImageFile: managerState.contextMenu?.node 
      ? isImageFile(managerState.contextMenu.node.name) 
      : false,
    
    // 功能開關
    features: {
      open: true,
      createFile: true,
      createFolder: true,
      copy: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
      viewImage: true,
    },
    
    // 回調函數
    callbacks: {
      onOpen: (node) => openFileInTab(node.path),
      onCreateFile: () => {
        const node = managerState.contextMenu?.node;
        if (node?.type === 'directory') {
          fileOps.openCreateFileDialog(node);
        } else {
          fileOps.openCreateFileDialog();
        }
      },
      onCreateFolder: () => {
        const node = managerState.contextMenu?.node;
        if (node?.type === 'directory') {
          fileOps.openCreateFolderDialog(node);
        } else {
          fileOps.openCreateFolderDialog();
        }
      },
      onCopy: (node) => {
        setClipboardItem({ path: node.path, type: node.type });
      },
      onPaste: () => {
        if (clipboardItem) {
          handlePaste(clipboardItem);
        }
      },
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onBatchDelete: (paths) => handleBatchDelete(paths),
      onRefresh: () => handleRefresh(),
      onViewImage: (node) => setImagePreview({ node }),
      onClose: () => managerState.closeContextMenu(),
    },
    
    // 翻譯函數
    t,
  });

  return (
    <FileTreeContextMenu
      contextMenu={managerState.contextMenu}
      items={contextMenuItems}
      onClose={managerState.closeContextMenu}
    />
  );
};
```

## 唯讀模式範例：Claude Code Skills (Plugin Scope)

```typescript
const ClaudeCodeFileManager = () => {
  const { t } = useI18n();
  const managerState = useFileTreeState();
  const isReadOnly = scope === 'plugin';
  
  const contextMenuItems = useFileTreeContextMenu({
    node: managerState.contextMenu?.node || null,
    readOnly: isReadOnly,
    t,
    features: {
      view: true, // 唯讀模式只顯示查看
    },
    callbacks: {
      onView: (node) => onSelect({ path: node.path, scope }),
      onClose: () => managerState.closeContextMenu(),
    },
  });

  return (
    <FileTreeContextMenu
      contextMenu={managerState.contextMenu}
      items={contextMenuItems}
      onClose={managerState.closeContextMenu}
    />
  );
};
```

## 自定義功能範例：Template Center

```typescript
const TemplateFileManager = () => {
  const { t } = useI18n();
  const managerState = useFileTreeState();
  
  const contextMenuItems = useFileTreeContextMenu({
    node: managerState.contextMenu?.node || null,
    hasClipboard: false, // Template Center 暫不支援貼上
    t,
    features: {
      open: false,        // 不需要開啟功能
      upload: true,       // 支援上傳
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,     // 顯示複製路徑
      paste: false,       // 不支援貼上
      rename: true,
      delete: true,
      refresh: false,     // 不需要重新整理
    },
    callbacks: {
      onUpload: () => handleUpload(),
      onCreateFile: () => handleCreateFile(),
      onCreateFolder: () => handleCreateFolder(),
      onCopy: (node) => handleCopy(node),
      onCopyPath: (path) => {
        navigator.clipboard.writeText(path);
        toast({ title: '路徑已複製' });
      },
      onRename: (node) => handleRename(node),
      onDelete: (node) => handleDelete(node),
      onClose: () => managerState.closeContextMenu(),
    },
  });

  return (
    <FileTreeContextMenu
      contextMenu={managerState.contextMenu}
      items={contextMenuItems}
      onClose={managerState.closeContextMenu}
    />
  );
};
```

## 配置選項說明

### FileTreeContextMenuConfig

| 屬性 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `node` | `FileTreeNode \| null` | ✅ | 右鍵點擊的目標節點 |
| `readOnly` | `boolean` | ❌ | 是否為唯讀模式（預設：false） |
| `enableMultiSelect` | `boolean` | ❌ | 是否支援多選（預設：false） |
| `selectedCount` | `number` | ❌ | 已選擇的節點數量 |
| `hasClipboard` | `boolean` | ❌ | 剪貼簿是否有內容 |
| `isImageFile` | `boolean` | ❌ | 是否為圖片檔案 |
| `features` | `object` | ❌ | 功能開關配置 |
| `callbacks` | `object` | ✅ | 回調函數配置 |
| `t` | `function` | ✅ | 翻譯函數 |

### Features 功能開關

所有功能預設為 `true`（除了 `view` 和 `copyPath` 預設為 `false`）：

- `open`: 開啟檔案
- `view`: 查看（唯讀模式）
- `upload`: 上傳檔案
- `createFile`: 新增檔案
- `createFolder`: 新增資料夾
- `copy`: 複製
- `copyPath`: 複製路徑
- `paste`: 貼上
- `rename`: 重新命名
- `delete`: 刪除
- `refresh`: 重新整理
- `viewImage`: 查看圖片

### Callbacks 回調函數

必填回調：
- `onClose`: 關閉選單

可選回調（根據 features 配置）：
- `onOpen(node)`: 開啟檔案
- `onView(node)`: 查看（唯讀）
- `onUpload()`: 上傳檔案
- `onCreateFile()`: 新增檔案
- `onCreateFolder()`: 新增資料夾
- `onCopy(node)`: 複製
- `onCopyPath(path)`: 複製路徑
- `onPaste()`: 貼上
- `onRename(node)`: 重新命名
- `onDelete(node)`: 刪除單個項目
- `onBatchDelete(paths)`: 批次刪除
- `onRefresh()`: 重新整理
- `onViewImage(node)`: 查看圖片

## 選單結構

Hook 會根據配置自動生成以下結構的選單：

```
資料夾專屬選項：
├─ 上傳檔案 (upload)
├─ 新增資料夾 (createFolder)
└─ 新增檔案 (createFile)

─────────── (分隔線)

通用操作：
├─ 開啟 (open, 僅檔案)
├─ 查看圖片 (viewImage, 僅圖片檔案)
├─ 複製 (copy)
├─ 複製路徑 (copyPath)
└─ 貼上 (paste)

─────────── (分隔線)

檔案操作：
├─ 重新命名 (rename)
└─ 刪除 (delete)

─────────── (分隔線)

其他：
└─ 重新整理 (refresh)
```

## 優勢

1. **統一性**：所有檔案樹使用相同的選單結構
2. **靈活性**：通過 features 和 callbacks 自定義功能
3. **可維護性**：選單邏輯集中管理，易於修改
4. **類型安全**：完整的 TypeScript 類型支援
5. **國際化**：內建 i18n 支援

