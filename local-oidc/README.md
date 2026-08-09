# 本機 OIDC profile 資產

根 `docker-compose.yml` 的 `local-oidc` profile 使用本目錄的 template 與準備程式，於啟動時把 mounted Secret 檔案轉成 Keycloak realm 與 LDAP seed。產出的檔案只存在 Compose volume，不會寫回 Repository。

OpenLDAP 直接使用 `osixia/openldap:1.5.0` 的 `LDAP_ADMIN_PASSWORD_FILE` 與
`LDAP_CONFIG_PASSWORD_FILE` 介面。該第三方 image 只在首次初始化階段讀取檔案，接著刪除
startup environment，再啟動長期 `slapd`；repository 不以 wrapper 將 Secret value 傳入
子程序環境。Keycloak 直接匯入 `aileron` realm；realm 內已有本機緊急管理員，因此不建立
master realm bootstrap administrator，也不需要 `keycloak-admin-password`。

`ldap-admin-password` 與 `ldap-config-password` 代表密碼的精確 bytes，不得包含前後空白
或結尾換行。`local-oidc-config` 會在 OpenLDAP 啟動前驗證此契約，不符合時 fail closed。

啟用方式：

```sh
docker compose --profile local-oidc up
```

Secret 檔名與唯一安裝輸入請以根 `.env.example` 及 `contracts/platform-configuration/` 為準。本目錄不保存密碼、client secret 或其他實際機密值。
