# Controller 依賴契約

`registry.json`是Workspace Controller所有Kubernetes API依賴的唯一權威來源，並由
`schema.json`固定正式欄位與有限集合。每個dependency必須宣告穩定identity、owner
controller、API group、resource、scope、typed object、存取模式、verbs、啟用條件，
以及watched dependency的event mapper或direct lookup的probe identity。

正式存取模式如下：

- `watched`：資源事件會觸發Workspace調和，必須宣告event mapper。
- `cached`：透過controller-runtime cache讀取，但資源事件不直接觸發Workspace調和。
- `directLookup`：只依已知identity使用APIReader直接查詢，必須宣告非破壞性probe。

Generator會產生下列不可手動修改的artifacts：

- `workspace-operator/internal/controller/controller_dependencies_generated.go`
- `helm/aileron/templates/_generated_workspace_operator_rbac_rules.tpl`

Operator container test會從canonical registry重新產生兩份內容並逐位元組比較。Helm只
render生效dependency所需的權限；mutation verbs由contract-to-RBAC tests驗證，不會以
實際create、update、patch或delete操作探測叢集。

若要在container內重新產生artifacts，可將輸出先寫入暫存目錄並與已提交內容比較：

```bash
docker compose -f workspace-operator/docker-compose.test.yml run --rm \
  workspace-operator-test go run ./cmd/generate-controller-dependencies \
  --contract /contracts/controller-dependencies/registry.json \
  --go-out /tmp/controller_dependencies_generated.go \
  --helm-out /tmp/_generated_workspace_operator_rbac_rules.tpl
```
