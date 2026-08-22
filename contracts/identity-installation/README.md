# Identity installation contract

`profile.schema.json` 是 installation layer 選擇 Identity adapter 的唯一資料契約。
`bundledKeycloak` 與 `externalOidc` 必須且只能擇一；兩者都只向 Aileron 投影標準
OIDC issuer、client ID、client Secret reference 與 CA Secret reference。

Bundled adapter 固定使用獨立的 `helm/aileron-identity` release。External adapter 不建立
Identity Plane，conformance vectors 刻意使用非 Keycloak provider，避免核心契約綁定產品實作。

Identity adapter 選擇與 Identity database 來源是兩個不同契約。只有 `bundledKeycloak` 會部署 Identity
chart；該 chart 再只以自身的 `postgres.enabled` 選擇內建或外部 PostgreSQL。這裡不新增 database mode
欄位，也不把 database 來源投影成平行 adapter flag。
