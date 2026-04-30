# ToolWidget 元件

仿照終端風格的工具展示元件，適合用於展示命令執行過程、工具輸出、API 請求等場景。

## 特色

- 🎨 **終端風格設計** - 採用深色主題，模擬終端外觀
- 🔴 **狀態指示器** - 支援綠色/黃色/紅色狀態指示
- 📦 **模組化設計** - 提供 Command、Output、Section 等子元件
- ⚡ **靈活使用** - 可自由組合子元件或直接使用自訂內容
- 🎯 **TypeScript 支援** - 完整的型別定義

## 基本使用

```tsx
import ToolWidget from '@/features/agent-tools/components/ToolWidget';

function Example() {
  return (
    <ToolWidget title="Terminal" showStatus statusColor="green">
      <ToolWidget.Command>
        npm run build
      </ToolWidget.Command>
      <ToolWidget.Output>
        ✓ Build completed successfully!
      </ToolWidget.Output>
    </ToolWidget>
  );
}
```

## Props

### ToolWidget

| Prop | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `title` | `string` | `"Terminal"` | 工具名稱（顯示在標題欄） |
| `showStatus` | `boolean` | `true` | 是否顯示狀態指示器 |
| `statusColor` | `"green"` \| `"yellow"` \| `"red"` | `"green"` | 狀態指示器顏色 |
| `dark` | `boolean` | `true` | 是否為深色模式 |
| `className` | `string` | - | 自訂樣式類名 |
| `children` | `ReactNode` | - | 子元件 |

### 子元件

#### ToolWidget.Command

顯示命令區域。

```tsx
<ToolWidget.Command>
  cat workspace-runtime/file.json | jq '.items[]'
</ToolWidget.Command>
```

#### ToolWidget.Output

顯示輸出區域。

```tsx
<ToolWidget.Output>
  Process completed successfully!
</ToolWidget.Output>
```

#### ToolWidget.Section

自訂區塊，可指定標題。

```tsx
<ToolWidget.Section title="Response">
  {"{ \"status\": \"ok\" }"}
</ToolWidget.Section>
```

## 使用範例

### 範例 1: Git 命令

```tsx
<ToolWidget title="Git Status" showStatus statusColor="green">
  <ToolWidget.Command>git status</ToolWidget.Command>
  <ToolWidget.Output>
    On branch main{'\n'}
    nothing to commit, working tree clean
  </ToolWidget.Output>
</ToolWidget>
```

### 範例 2: API 請求

```tsx
<ToolWidget title="API Request" showStatus statusColor="green">
  <ToolWidget.Section title="Request">
    POST /api/v1/workspaces
  </ToolWidget.Section>
  <ToolWidget.Section title="Response" className="mt-4">
    {JSON.stringify({ id: "ws_123", status: "active" }, null, 2)}
  </ToolWidget.Section>
</ToolWidget>
```

### 範例 3: 建置過程

```tsx
<ToolWidget title="Build Process" showStatus statusColor="yellow">
  <ToolWidget.Command>npm run build</ToolWidget.Command>
  <ToolWidget.Output>
{`> building...
✓ 1234 modules transformed.
dist/index.html     0.45 kB
dist/index.js     123.45 kB
✓ built in 3.21s`}
  </ToolWidget.Output>
</ToolWidget>
```

### 範例 4: 錯誤狀態

```tsx
<ToolWidget title="Error" showStatus statusColor="red">
  <ToolWidget.Output>
    ✗ Error: Command failed with exit code 1
  </ToolWidget.Output>
</ToolWidget>
```

### 範例 5: 程式碼片段

```tsx
<ToolWidget title="Code Snippet" showStatus={false}>
  <ToolWidget.Section title="TypeScript">
{`interface User {
  id: string;
  name: string;
  email: string;
}`}
  </ToolWidget.Section>
</ToolWidget>
```

## 線上示範

訪問示範頁面查看更多範例：

```
http://localhost:5173/demo/tool-widget
```

## 設計靈感

此元件的設計靈感來自終端模擬器和開發者工具的界面，使用深色主題和等寬字體，提供熟悉的開發者體驗。

## 自訂樣式

你可以透過 `className` prop 自訂樣式：

```tsx
<ToolWidget
  title="Custom"
  className="text-xs" // 縮小字體
>
  {/* ... */}
</ToolWidget>
```

## 相容性

- ✅ React 18+
- ✅ TypeScript 5+
- ✅ Tailwind CSS 3+
