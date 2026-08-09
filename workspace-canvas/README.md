# Workspace Canvas 路徑前綴契約

Workspace Canvas 的 render server 對外由同源 path gateway 提供服務。Gateway 會先移除公開路徑前綴，再把原始 Canvas request path 傳入 render server，並以 `X-Forwarded-Prefix` 宣告公開前綴。

## 接受的前綴

`X-Forwarded-Prefix` 只接受下列完整格式：

```text
/workspaces/{canonical-uuid}/canvas
```

其中 UUID 必須是小寫、連字號分隔、RFC 4122 variant，版本限 1 至 5。Header 不得包含尾端斜線、額外 path、逗號串接值或其他 alias。非契約值的 HTTP request 回傳 `400` 與 `CANVAS_FORWARDED_PREFIX_INVALID`；WebSocket upgrade 回傳 `400 Bad Request`。

若 request 未帶 `X-Forwarded-Prefix`，render server 維持容器內直接存取模式，所有 URL 均使用根路徑。這是唯一不套用公開前綴的情況。

## Proxy 行為

- 傳給 Next.js 的 HTTP 與 WebSocket request path 保持 gateway strip 後的值，不把公開前綴送入 upstream path。
- `X-Forwarded-Prefix` 原樣傳給 Next.js，包括 WebSocket upgrade。
- HTML 中的 root-relative URL、Next.js `/_next/*` reference，以及 `/__aileron/bridge.js` 會改寫到該 request 的公開前綴下。
- JavaScript 中的 Next.js internal asset reference與 CSS `url(...)` 的 root-relative asset reference會改寫到公開前綴下。
- Root-relative `Location` response header會改寫到公開前綴下；absolute URL 保持原值。
- Static Canvas 的 HTML、JavaScript 與 CSS 使用相同的 request-scoped 改寫規則。

前綴只存在於單一 HTTP request 或 WebSocket upgrade 的處理範圍，不儲存在 process global state。因此同一個 Canvas process 可安全地並行處理不同 Workspace 的公開前綴。
