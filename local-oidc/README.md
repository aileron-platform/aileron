# 本機 OIDC profile 資產

根 `docker-compose.yml` 的 `local-oidc` profile 使用本目錄的 template 與準備程式，於啟動時把 mounted Secret 檔案轉成 Keycloak realm。產出的檔案只存在 Compose volume，不會寫回 Repository。

此 profile 只啟動 Keycloak。`keycloak-bootstrap-admin-password` 只建立獨立的 Keycloak
Admin Console 管理員。`aileron` realm 的 Aileron 平台管理員直接使用
`BOOTSTRAP_ADMIN_SUBJECT`、`BOOTSTRAP_ADMIN_USERNAME`、`BOOTSTRAP_ADMIN_EMAIL` 與
`local-oidc-platform-admin-password`，因此 OIDC subject 與 Manager bootstrap snapshot
完全一致。隔離的本機環境預設使用 `admin`／`admin123`，應用授權仍由 canonical
`(issuer, subject)` 平台授權流程管理。

realm 預設關閉 self-registration，一般原生使用者由 Admin Console 管理。未來若整合 LDAP，
只能在 Keycloak 內以 User Federation 擴充，不得改變本 profile 的 Aileron OIDC 契約。

啟用方式：

```sh
docker compose --profile local-oidc up
```

Secret 檔名與唯一安裝輸入請以根 `.env.example` 及 `contracts/platform-configuration/` 為準。本目錄不保存密碼、client secret 或其他實際機密值。
