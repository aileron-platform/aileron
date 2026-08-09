#!/bin/sh

# shellcheck disable=SC2016
set -eu

chart_dir="helm/aileron"
runtime_namespace="workspace-system"
turn_test_secret="external-turn-ice"
work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM

fail() {
  echo "Helm platform assertion failed: $*" >&2
  exit 1
}

assert_contains() {
  file="$1"
  pattern="$2"
  description="$3"
  grep -Fq -- "${pattern}" "${file}" || fail "${description}"
}

assert_absent() {
  file="$1"
  pattern="$2"
  description="$3"
  if grep -Fq -- "${pattern}" "${file}"; then
    fail "${description}"
  fi
}

assert_minimum_count() {
  file="$1"
  pattern="$2"
  minimum="$3"
  description="$4"
  count="$(grep -Fc -- "${pattern}" "${file}" || true)"
  [ "${count}" -ge "${minimum}" ] || fail "${description}: found ${count}, expected at least ${minimum}"
}

assert_render_fails() {
  expected_messages="$1"
  description="$2"
  shift 2
  output_file="${work_dir}/negative-$(date +%s)-$$.log"
  if helm template aileron "${chart_dir}" \
    --namespace "${runtime_namespace}" "$@" > "${output_file}" 2>&1; then
    fail "${description}: render unexpectedly succeeded"
  fi
  previous_ifs="${IFS}"
  IFS='|'
  for expected_message in ${expected_messages}; do
    assert_contains \
      "${output_file}" \
      "${expected_message}" \
      "${description}: wrong failure reason"
  done
  IFS="${previous_ifs}"
}

assert_yaml() {
  file="$1"
  expression="$2"
  description="$3"
  if ! yq eval-all -e "${expression}" "${file}" >/dev/null; then
    fail "${description}"
  fi
}

assert_document_count() {
  file="$1"
  kind="$2"
  name_suffix="$3"
  expected_count="$4"
  description="$5"
  assert_yaml \
    "${file}" \
    "[select(.kind == \"${kind}\" and (.metadata.name | test(\"${name_suffix}$\")))] | length == ${expected_count}" \
    "${description}"
}

assert_role_rule() {
  file="$1"
  role_suffix="$2"
  api_groups="$3"
  resources="$4"
  verbs="$5"
  description="$6"
  assert_yaml \
    "${file}" \
    "[select(.kind == \"Role\" and (.metadata.name | test(\"${role_suffix}$\")))] | .[0].rules as \$rules | [\$rules[] | select([((.apiGroups | sort | join(\",\")) == (${api_groups} | sort | join(\",\"))), ((.resources | sort | join(\",\")) == (${resources} | sort | join(\",\"))), ((.verbs | sort | join(\",\")) == (${verbs} | sort | join(\",\")))] | all)] | length == 1" \
    "${description}"
}

assert_identity_provisioning_contract() {
  file="$1"
  oidc_client_secret_name="${2:-aileron-oidc-client}"

  assert_document_count "${file}" Job -admin-bootstrap 1 "identity: administrator bootstrap Job count is invalid"
  assert_document_count "${file}" Secret -secrets 0 "identity: chart-managed platform Secret must be absent"
  assert_yaml \
    "${file}" \
    '[select(((.metadata.name // "") | downcase) | contains("keycloak"))] | length == 0' \
    "identity: bundled Keycloak resources must be absent"
  assert_yaml \
    "${file}" \
    "[select(.kind == \"Deployment\" and (.metadata.name | test(\"-workspace-manager$\")))] | .[0] as \$manager | (\$manager.spec.template.spec.containers[0]) as \$container | (\$container.env | map(select(.name == \"OIDC_CLIENT_SECRET_FILE\"))) as \$entries | (\$manager.spec.template.spec.volumes | map(select(.name == \"manager-private-secrets\")) | .[0].projected.sources | map(select(.secret.name == \"${oidc_client_secret_name}\"))) as \$sources | [(\$entries | length == 1), (\$entries[0].value == \"/run/secrets/aileron/oidc-client-secret\"), (\$sources | length == 1), (\$sources[0].secret.items[0].key == \"client-secret\"), (\$sources[0].secret.items[0].path == \"oidc-client-secret\")] | all" \
    "identity: Manager must mount the existing OIDC client Secret as a file"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0].spec.template.spec.containers[0].env | map(select(.name | test("OIDC"))) | length == 0' \
    "identity: Workspace Operator must not receive external OIDC configuration"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Job" and (.metadata.name | test("-admin-bootstrap$")))] | .[0] as $job | [($job.metadata.namespace == "workspace-system"), ($job.metadata.annotations."helm.sh/hook" == "post-install,post-upgrade"), ($job.metadata.annotations."helm.sh/hook-weight" == "10"), ($job.metadata.annotations."helm.sh/hook-delete-policy" == "before-hook-creation,hook-succeeded"), ($job.spec.template.spec.restartPolicy == "OnFailure"), ($job.spec.template.spec.automountServiceAccountToken == false), ($job.spec.template.spec.securityContext.runAsNonRoot == true)] | all' \
    "identity: administrator bootstrap Job metadata contract is invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Job" and (.metadata.name | test("-admin-bootstrap$")))] | .[0] as $job | ($job.spec.template.spec.containers) as $containers | ($containers[0].env | map(select(.name == "DATABASE_URL_FILE"))) as $database | ($containers[0].env | map(select(.name == "OIDC_ISSUER_URL"))) as $issuer | ($containers[0].env | map(select(.name == "BOOTSTRAP_ADMIN_SUBJECT"))) as $subject | ($containers[0].env | map(select(.name == "BOOTSTRAP_ADMIN_USERNAME"))) as $username | ($containers[0].env | map(select(.name == "BOOTSTRAP_ADMIN_EMAIL"))) as $email | ($job.spec.template.spec.volumes | map(select(.name == "platform-secrets"))) as $volumes | [ (($containers | length) == 1), ($containers[0].name == "bootstrap-administrator"), ($containers[0].command[2] | contains("/workspace-manager/scripts/bootstrap_admin_user.py")), (($containers[0].command | join(" ") | contains("--subject"))), (($containers[0].command | join(" ") | contains("--password-file")) | not), (($database | length) == 1), ($database[0].value == "/run/secrets/aileron/database-url"), (($issuer | length) == 1), ($issuer[0].valueFrom.configMapKeyRef.key == "OIDC_ISSUER_URL"), ($subject[0].value == "00000000-0000-4000-8000-000000000001"), ($username[0].value == "admin"), ($email[0].value == "admin@aileron.com"), (($containers[0].volumeMounts | map(select(.name == "platform-secrets" and .mountPath == "/run/secrets/aileron" and .readOnly == true)) | length) == 1), (($volumes | length) == 1), ($volumes[0].secret.secretName == "aileron-platform-secrets"), ($volumes[0].secret.items[0].path == "database-url") ] | all' \
    "identity: administrator bootstrap container contract is invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Job" and (.metadata.name | test("-admin-bootstrap$")))] | .[0].spec.template.spec.containers[0].resources as $resources | [($resources.requests.cpu == "25m"), ($resources.requests.memory == "64Mi"), ($resources.limits.cpu == "250m"), ($resources.limits.memory == "256Mi")] | all' \
    "identity: administrator bootstrap Job resources are invalid"

  echo "identity: external OIDC and administrator bootstrap Helm contracts passed"
}

assert_platform_service_contract() {
  platform_contract_file="$1"
  platform="$2"
  nginx_config="${work_dir}/${platform}-frontend-nginx.conf"

  yq eval-all -r \
    'select(.kind == "ConfigMap" and (.metadata.name | test("-frontend-nginx$"))) | .data."nginx.conf"' \
    "${platform_contract_file}" > "${nginx_config}"

  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "Deployment" or .kind == "StatefulSet" or .kind == "DaemonSet" or .kind == "Job")] | ((length > 0) and (map(.spec.template.metadata.labels."app.kubernetes.io/part-of" == "aileron") | all))' \
    "${platform}: workload Pod ownership labels are invalid"
  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "ConfigMap" and (.metadata.name | test("-frontend-nginx$")))] | .[0].data."nginx.conf" as $config | [ ($config | contains("pid /tmp/nginx.pid;")), ($config | contains("root   /tmp/aileron-html;")), ($config | contains("client_body_temp_path /tmp/client_temp;")), ($config | contains("/usr/share/nginx/html") | not) ] | all' \
    "${platform}: Frontend Nginx arbitrary-UID paths are invalid"
  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "ConfigMap" and (.metadata.name | test("-frontend-nginx$")))] | .[0].data."nginx.conf" as $config | [($config | contains("/runtime/ws/terminal")), ($config | contains("proxy_pass http://workspace-runtime-$workspace_id.workspace-system.svc.cluster.local:3004;")), ($config | contains("proxy_pass http://workspace-$workspace_component-$workspace_id.workspace-system.svc.cluster.local:$workspace_service_port;"))] | all' \
    "${platform}: Frontend Nginx terminal route must target the Runtime terminal port"
  for directive in \
    'proxy_set_header Host $http_host;' \
    'proxy_set_header X-Forwarded-Host $http_host;' \
    'proxy_set_header X-Forwarded-Port $server_port;' \
    'proxy_set_header Sec-WebSocket-Protocol $http_sec_websocket_protocol;' \
    'proxy_buffering off;' \
    'proxy_request_buffering off;' \
    'proxy_cache off;' \
    'proxy_read_timeout 3600s;' \
    'proxy_send_timeout 3600s;'; do
    assert_minimum_count "${nginx_config}" "${directive}" 4 "${platform}: Frontend Nginx same-origin streaming directive is incomplete"
  done
  assert_minimum_count "${nginx_config}" 'auth_request /_aileron_workspace_gateway_authorize;' 3 "${platform}: Workspace routes must enforce the Manager authorization gate"
  assert_minimum_count "${nginx_config}" 'proxy_set_header Authorization $http_authorization;' 3 "${platform}: Manager and Runtime routes must preserve bearer authorization"
  assert_minimum_count "${nginx_config}" 'proxy_set_header Cookie $http_cookie;' 1 "${platform}: Manager API route must preserve its session cookie"
  assert_minimum_count "${nginx_config}" 'proxy_set_header Cookie "";' 3 "${platform}: Workspace upstreams must not receive browser cookies"
  assert_minimum_count "${nginx_config}" 'proxy_set_header Authorization "";' 2 "${platform}: Authorization subrequest and browser workloads must clear bearer credentials"
  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "Deployment" and ((.metadata.name // "") | test("-frontend$")))] | .[0] as $workload | ($workload.spec.template.spec.containers | map(select(.name == "frontend"))) as $containers | [($workload.spec.template.spec.automountServiceAccountToken == false), ($workload.spec.template.spec.securityContext.runAsNonRoot == true), ($workload.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($workload.spec.template.spec.securityContext | has("runAsUser") | not), ($workload.spec.template.spec.securityContext | has("runAsGroup") | not), (($workload.spec.template.metadata.annotations."checksum/nginx-config" // "") | test("^[0-9a-f]{64}$")), (($containers | length) == 1), ($containers[0].securityContext.allowPrivilegeEscalation == false), ($containers[0].securityContext.readOnlyRootFilesystem == true), (($containers[0].securityContext.capabilities.drop | join(",")) == "ALL"), (($containers[0].volumeMounts | map(select(.name == "nginx-config" and .readOnly == true)) | length) == 1), (($containers[0].volumeMounts | map(select(.name == "tmp" and .mountPath == "/tmp")) | length) == 1), (($workload.spec.template.spec.volumes | map(select(.name == "tmp" and has("emptyDir"))) | length) == 1)] | all' \
    "${platform}: Frontend restricted-runtime contract is invalid"
  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "StatefulSet" and (.metadata.name | test("-redis$")))] | .[0] as $workload | ($workload.spec.template.spec.containers | map(select(.name == "redis"))) as $containers | [ ($workload.spec.template.spec.automountServiceAccountToken == false), ($workload.spec.template.spec.securityContext.runAsNonRoot == true), ($workload.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($workload.spec.template.spec.securityContext | has("runAsUser") | not), ($workload.spec.template.spec.securityContext | has("runAsGroup") | not), (($containers | length) == 1), ($containers[0].image == "ailerondocker/platform-redis:latest"), (($containers[0].args | join(",")) == "--appendonly,yes,--maxmemory,256mb,--maxmemory-policy,allkeys-lru"), ($containers[0].securityContext.allowPrivilegeEscalation == false), ($containers[0].securityContext.readOnlyRootFilesystem == true), (($containers[0].securityContext.capabilities.drop | join(",")) == "ALL"), ($containers[0].securityContext | has("runAsUser") | not), (($containers[0].volumeMounts | map(select(.name == "data" and .mountPath == "/data")) | length) == 1), (($containers[0].volumeMounts | map(select(.name == "tmp" and .mountPath == "/tmp")) | length) == 1), (($workload.spec.volumeClaimTemplates | map(select(.metadata.name == "data")) | length) == 1) ] | all' \
    "${platform}: Redis restricted-runtime contract is invalid"
  assert_yaml \
    "${platform_contract_file}" \
    '[select(.kind == "StatefulSet" and (.metadata.name | test("-postgres$")))] | .[0] as $workload | ($workload.spec.template.spec.containers | map(select(.name == "postgres"))) as $containers | [ ($workload.spec.template.spec.automountServiceAccountToken == false), ($workload.spec.template.spec.securityContext.runAsNonRoot == true), ($workload.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($workload.spec.template.spec.securityContext | has("runAsUser") | not), ($workload.spec.template.spec.securityContext | has("runAsGroup") | not), (($containers | length) == 1), ($containers[0].image == "ailerondocker/platform-postgres:latest"), (($containers[0].env | map(select(.name == "POSTGRES_HOST_AUTH_METHOD" or .name == "KEYCLOAK_DATABASE")) | length) == 0), (($containers[0].env | map(select(.name == "POSTGRES_INITDB_ARGS" and .value == "--auth-host=scram-sha-256")) | length) == 1), (($containers[0].env | map(select(.name == "PGDATA" and .value == "/var/lib/postgresql/data/pgdata")) | length) == 1), ($containers[0].securityContext.allowPrivilegeEscalation == false), ($containers[0].securityContext.readOnlyRootFilesystem == true), (($containers[0].securityContext.capabilities.drop | join(",")) == "ALL"), ($containers[0].securityContext | has("runAsUser") | not), (($containers[0].volumeMounts | map(select(.name == "data" and .mountPath == "/var/lib/postgresql/data")) | length) == 1), (($containers[0].volumeMounts | map(select(.name == "init-sql" and .mountPath == "/docker-entrypoint-initdb.d" and .readOnly == true)) | length) == 1), (($containers[0].volumeMounts | map(select(.name == "postgres-run" and .mountPath == "/var/run/postgresql")) | length) == 1), (($containers[0].volumeMounts | map(select(.name == "tmp" and .mountPath == "/tmp")) | length) == 1), (($workload.spec.volumeClaimTemplates | map(select(.metadata.name == "data")) | length) == 1) ] | all' \
    "${platform}: Postgres restricted-runtime contract is invalid"
  assert_absent "${platform_contract_file}" ')\\gexec' "${platform}: PostgreSQL bootstrap SQL must keep psql meta-commands on their own line"
  if [ "${platform}" = "ocp" ]; then
    assert_yaml \
      "${platform_contract_file}" \
      '[select(.kind == "StatefulSet" and (.metadata.name | test("-(redis|postgres)$")))] | map(.spec.template.spec.securityContext | has("fsGroup") | not) | all' \
      "ocp: platform services must leave fsGroup to the Project SCC"
  else
    assert_yaml \
      "${platform_contract_file}" \
      '[select(.kind == "StatefulSet" and (.metadata.name | test("-(redis|postgres)$")))] | map(.spec.template.spec.securityContext.fsGroup == 2000) | all' \
      "${platform}: platform services must use the platform storage group"
  fi

  echo "${platform}: Frontend, Redis, and Postgres Helm contracts passed"
}

assert_workspace_platform_contract() {
  file="$1"
  platform="$2"
  cilium_enabled="${3:-false}"

  assert_yaml \
    "${file}" \
    '[select(.kind == "ClusterRole" or .kind == "ClusterRoleBinding")] | length == 2' \
    "${platform}: only the Workspace Operator StorageClass RBAC may be cluster-wide"
  assert_yaml \
    "${file}" \
    '[select(.kind == "ClusterRole" and (.metadata.name | test("-workspace-operator-storageclasses$")))] | .[0] as $role | [($role.rules | length == 1), (($role.rules[0].apiGroups | join(",")) == "storage.k8s.io"), (($role.rules[0].resources | join(",")) == "storageclasses"), (($role.rules[0].verbs | join(",")) == "get")] | all' \
    "${platform}: Workspace Operator StorageClass ClusterRole is not least privilege"
  assert_yaml \
    "${file}" \
    '[select(.kind == "ClusterRoleBinding" and (.metadata.name | test("-workspace-operator-storageclasses$")))] | .[0] as $binding | [($binding.roleRef.apiGroup == "rbac.authorization.k8s.io"), ($binding.roleRef.kind == "ClusterRole"), ($binding.roleRef.name | test("-workspace-operator-storageclasses$")), ($binding.subjects | length == 1), ($binding.subjects[0].kind == "ServiceAccount"), ($binding.subjects[0].name | test("-workspace-operator$"))] | all' \
    "${platform}: Workspace Operator StorageClass ClusterRoleBinding is invalid"
  assert_document_count "${file}" Deployment -workspace-manager 1 "${platform}: Workspace Manager Deployment count is invalid"
  assert_document_count "${file}" Deployment -workspace-operator 1 "${platform}: Workspace Operator Deployment count is invalid"
  if [ "${cilium_enabled}" = "true" ]; then
    assert_document_count "${file}" DaemonSet -workspace-firewall-attestor 1 "${platform}: firewall attestor DaemonSet count is invalid"
    assert_document_count "${file}" Role -workspace-firewall-attestor 1 "${platform}: firewall attestor Role count is invalid"
    assert_document_count "${file}" RoleBinding -workspace-firewall-attestor 1 "${platform}: firewall attestor RoleBinding count is invalid"
    assert_document_count "${file}" ServiceAccount -workspace-firewall-attestor 1 "${platform}: firewall attestor ServiceAccount count is invalid"
  else
    assert_document_count "${file}" DaemonSet -workspace-firewall-attestor 0 "${platform}: firewall attestor must not render without Cilium"
    assert_document_count "${file}" Role -workspace-firewall-attestor 0 "${platform}: firewall attestor Role must not render without Cilium"
    assert_document_count "${file}" RoleBinding -workspace-firewall-attestor 0 "${platform}: firewall attestor RoleBinding must not render without Cilium"
    assert_document_count "${file}" ServiceAccount -workspace-firewall-attestor 0 "${platform}: firewall attestor ServiceAccount must not render without Cilium"
  fi
  assert_document_count "${file}" ConfigMap -manager-bootstrap 1 "${platform}: Manager bootstrap ConfigMap count is invalid"
  assert_document_count "${file}" ConfigMap -firewall-defaults 0 "${platform}: legacy firewall defaults ConfigMap must not render"
  assert_document_count "${file}" Role -workspace-manager 1 "${platform}: Workspace Manager Role count is invalid"
  assert_document_count "${file}" Role -workspace-operator 1 "${platform}: Workspace Operator Role count is invalid"
  assert_document_count "${file}" Secret -secrets 0 "${platform}: chart-managed platform Secret must be absent"
  assert_document_count "${file}" PersistentVolumeClaim knowledge-bases-pvc 1 "${platform}: Knowledge Base PVC count is invalid"
  assert_document_count "${file}" PersistentVolumeClaim workspace-manager-state 1 "${platform}: Manager state PVC count is invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$")))] | .[0].spec.strategy.type == "Recreate"' \
    "${platform}: Workspace Manager must use Recreate for its singleton state PVC"
  assert_yaml \
    "${file}" \
    'select(.kind == "ConfigMap" and (.metadata.name | test("-platform-config$"))) as $config | select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$"))) as $manager | select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | ($manager.spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0].env) as $manager_env | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env) as $operator_env | ($manager_env | map(select(.name == "WORKSPACE_STORAGE_SIZE"))) as $workspace_size | ($manager_env | map(select(.name == "RUNTIME_HOME_STORAGE_SIZE"))) as $home_size | [($config.data.WORKSPACE_STORAGE_SIZE == "20Gi"), ($config.data.RUNTIME_HOME_STORAGE_SIZE == "2Gi"), (($workspace_size | length) == 1), ($workspace_size[0].valueFrom.configMapKeyRef.name == $config.metadata.name), ($workspace_size[0].valueFrom.configMapKeyRef.key == "WORKSPACE_STORAGE_SIZE"), (($home_size | length) == 1), ($home_size[0].valueFrom.configMapKeyRef.name == $config.metadata.name), ($home_size[0].valueFrom.configMapKeyRef.key == "RUNTIME_HOME_STORAGE_SIZE"), (($operator_env | map(select(.name == "WORKSPACE_STORAGE_SIZE" or .name == "RUNTIME_HOME_STORAGE_SIZE")) | length) == 0)] | all' \
    "${platform}: storage capacity defaults must feed Manager, not Operator"
  assert_yaml \
    "${file}" \
    '[select((.kind == "Deployment" and ((.metadata.name | test("-(workspace-manager|workspace-operator)$")))) or (.kind == "DaemonSet" and (.metadata.name | test("-workspace-firewall-attestor$"))) or (.kind == "Role" and ((.metadata.name | test("-(workspace-manager|workspace-operator|workspace-firewall-attestor)$")))) or (.kind == "ServiceAccount" and ((.metadata.name | test("-(workspace-manager|workspace-operator|workspace-firewall-attestor)$")))) or (.kind == "PersistentVolumeClaim" and (.metadata.name == "knowledge-bases-pvc" or .metadata.name == "workspace-manager-state")))] | [ .[] | .metadata.namespace == "workspace-system" ] | all' \
    "${platform}: core Workspace resources must share the canonical namespace"
  assert_yaml \
    "${file}" \
    'select(.kind == "ConfigMap" and (.metadata.name | test("-manager-bootstrap$"))) as $bootstrap | select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$"))) as $manager | ($bootstrap.data."firewall-seed.json" | from_json) as $seed | ($manager.spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0]) as $container | [($bootstrap.metadata.namespace == "workspace-system"), ($seed.workspace.egressMode == "unrestricted"), (($seed.workspace.allowedDomains | length) == 0), ($seed.browser.egressMode == "unrestricted"), (($seed.browser.allowedDomains | length) == 0), (($container.env | map(select(.name == "FIREWALL_SEED_FILE" and .value == "/etc/aileron/bootstrap/firewall-seed.json")) | length) == 1), (($container.volumeMounts | map(select(.name == "manager-bootstrap" and .mountPath == "/etc/aileron/bootstrap" and .readOnly == true)) | length) == 1), (($manager.spec.template.spec.volumes | map(select(.name == "manager-bootstrap" and .configMap.name == $bootstrap.metadata.name)) | length) == 1), ($manager.spec.template.metadata.annotations."checksum/manager-bootstrap" | test("^[0-9a-f]{64}$"))] | all' \
    "${platform}: Manager-only firewall seed contract is invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0] as $operator | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0]) as $container | [(($container.env | map(select(.name | test("^FIREWALL_(DEFAULTS|SEED)"))) | length) == 0), (($container.volumeMounts // [] | map(select(.name == "manager-bootstrap")) | length) == 0), (($operator.spec.template.spec.volumes // [] | map(select(.name == "manager-bootstrap")) | length) == 0)] | all' \
    "${platform}: Operator must not receive the Manager firewall seed"

  for probe in livenessProbe readinessProbe startupProbe; do
    assert_yaml \
      "${file}" \
      "[select(.kind == \"Deployment\" and (.metadata.name | test(\"-workspace-manager$\")))] | .[0].spec.template.spec.containers | [ .[] | select(.name == \"workspace-manager\") ] | ((length == 1) and ((.[0].${probe}.exec.command | length) >= 1) and (.[0].${probe}.exec.command[0] == \"/workspace-manager/scripts/kubernetes_healthcheck.sh\") and ((.[0].${probe}.exec.command[1:] | map(select(. != \"--ready\")) | length) == 0) and (.[0].${probe}.timeoutSeconds == 20))" \
      "${platform}: Manager ${probe} must verify the API and local Celery worker"
  done
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0].spec.template.spec.containers | [ .[] | select(.name == "workspace-operator") ] | length == 1' \
    "${platform}: Workspace Operator container count is invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0].spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env as $env | ($env | map(select(.name == "POD_NAMESPACE"))) as $pod_namespace | [ (($pod_namespace | length) == 1), ($pod_namespace[0].valueFrom.fieldRef.fieldPath == "metadata.namespace"), (($env | map(select(.name == "WATCH_NAMESPACE" or .name == "RUNTIME_K8S_NAMESPACE")) | length) == 0) ] | all' \
    "${platform}: Operator namespace must come only from Pod metadata"
  assert_yaml \
    "${file}" \
    'select(.kind == "ConfigMap" and (.metadata.name | test("-platform-config$"))) as $config | select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env) as $env | ($env | map(select(.name == "AILERON_MANAGER_INTERNAL_URL"))) as $manager | ($env | map(select(.name == "AILERON_PLATFORM_PUBLIC_ORIGIN"))) as $origin | [(($manager | length) == 1), ($manager[0].value | contains("-workspace-manager.workspace-system.svc.cluster.local:3001")), (($origin | length) == 1), ($origin[0].value == $config.data.PLATFORM_PUBLIC_ORIGIN), (($env | map(select(.name == "PLATFORM_MANAGER_URL")) | length) == 0), (($config.data | has("PLATFORM_MANAGER_URL")) | not)] | all' \
    "${platform}: Operator canonical Manager URL and public origin environment contract is invalid"

  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$")))] | .[0].spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0].env | map(select(.name == "INTERNAL_API_TOKEN")) | length == 0' \
    "${platform}: legacy shared internal API token must be absent"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$")))] | .[0].spec.template.spec.containers | [ .[] | select(.name == "workspace-manager") ] | .[0].env | [ .[] | select(.name == "WORKSPACE_RUNTIME_URL") ] | length == 0' \
    "${platform}: static Workspace Runtime URL must be absent"
  assert_yaml \
    "${file}" \
    'select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$"))) as $manager | ($manager.spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0]) as $container | ($container.env | map(select(.name == "DATABASE_URL_FILE"))) as $database_env | ($container.env | map(select(.name == "RUNTIME_DATABASE_CREDENTIAL_KEY_FILE"))) as $key_env | ($container.volumeMounts | map(select(.name == "manager-private-secrets"))) as $mounts | ($manager.spec.template.spec.volumes | map(select(.name == "manager-private-secrets"))) as $volumes | ($volumes[0].projected.sources | map(select(.secret.name == "aileron-platform-secrets"))) as $secret_sources | [ (($database_env | length) == 1), ($database_env[0].value == "/run/secrets/aileron/database-url"), (($key_env | length) == 1), ($key_env[0].value == "/run/secrets/aileron/runtime-database-credential.key"), (($mounts | length) == 1), ($mounts[0].mountPath == "/run/secrets/aileron"), ($mounts[0].readOnly == true), (($volumes | length) == 1), ($volumes[0].projected.defaultMode == "0440"), (($secret_sources | length) == 1), (($secret_sources[0].secret.items | length) == 2), (($secret_sources[0].secret.items | map(select(.key == "database-url" and .path == "database-url")) | length) == 1), (($secret_sources[0].secret.items | map(select(.key == "runtime-database-credential-key" and .path == "runtime-database-credential.key")) | length) == 1) ] | all' \
    "${platform}: Manager existing platform Secret file mounts are invalid"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" or .kind == "Job") | .spec.template.spec.containers[] | .env[]? | select(.name == "DATABASE_URL" or .name == "PLATFORM_DATABASE_URL" or .name == "OIDC_CLIENT_SECRET" or .name == "PLATFORM_OIDC_CLIENT_SECRET" or .name == "TURN_SERVER_USERNAME" or .name == "TURN_SERVER_CREDENTIAL") | select(has("value"))] | length == 0' \
    "${platform}: workload specs contain a managed secret literal"
  assert_yaml \
    "${file}" \
    '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0].spec.template.spec.containers | [ .[] | select(.name == "workspace-operator") ] | .[0].env | [ .[] | select(.name == "PLATFORM_DATABASE_URL" or .name == "PLATFORM_REDIS_URL" or .name == "PLATFORM_OIDC_CLIENT_SECRET") ] | length == 0' \
    "${platform}: Operator must not receive platform database, Redis, or client-secret configuration"

  assert_yaml "${file}" '[select(.kind == "Role" and (.metadata.name | test("-workspace-manager$")))] | .[0].rules | length == 4' "${platform}: Manager RBAC rule count is invalid"
  assert_role_rule "${file}" -workspace-manager '["platform.aileron.io"]' '["workspaces"]' '["get", "create", "patch", "delete"]' "${platform}: Manager Workspace RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-manager '[""]' '["pods"]' '["list"]' "${platform}: Manager Pod RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-manager '[""]' '["persistentvolumeclaims"]' '["get"]' "${platform}: Manager knowledge-base PVC preflight RBAC rule is invalid"
  assert_yaml "${file}" '[select(.kind == "Role" and (.metadata.name | test("-workspace-manager$")))] | .[0].rules | [ .[] | select((.resources | join(",")) == "persistentvolumeclaims") ] as $rules | [ (($rules | length) == 1), (($rules[0].resourceNames | join(",")) == "knowledge-bases-pvc") ] | all' "${platform}: Manager knowledge-base PVC preflight RBAC resourceNames are invalid"
  assert_role_rule "${file}" -workspace-manager '[""]' '["secrets"]' '["create", "patch", "delete"]' "${platform}: Manager Runtime Secret RBAC rule is invalid"

  expected_operator_rules=9
  if [ "${cilium_enabled}" = "true" ]; then
    expected_operator_rules=11
  fi
  assert_yaml "${file}" "[select(.kind == \"Role\" and (.metadata.name | test(\"-workspace-operator$\")))] | .[0].rules | length == ${expected_operator_rules}" "${platform}: Operator RBAC rule count is invalid"
  assert_role_rule "${file}" -workspace-operator '[""]' '["pods"]' '["get", "list", "watch"]' "${platform}: Operator read RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-operator '[""]' '["secrets"]' '["create", "get", "list", "watch"]' "${platform}: Operator browser credential Secret RBAC rule is invalid"
  for resource in persistentvolumeclaims serviceaccounts services; do
    assert_role_rule "${file}" -workspace-operator '[""]' "[\"${resource}\"]" '["create", "delete", "get", "list", "update", "watch"]' "${platform}: Operator ${resource} RBAC rule is invalid"
  done
  assert_role_rule "${file}" -workspace-operator '["apps"]' '["deployments"]' '["create", "delete", "get", "list", "update", "watch"]' "${platform}: Operator Deployment RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-operator '["platform.aileron.io"]' '["workspaces"]' '["get", "list", "update", "watch"]' "${platform}: Operator Workspace RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-operator '["platform.aileron.io"]' '["workspaces/status"]' '["update"]' "${platform}: Operator Workspace status RBAC rule is invalid"
  assert_role_rule "${file}" -workspace-operator '["platform.aileron.io"]' '["workspaces/finalizers"]' '["update"]' "${platform}: Operator Workspace finalizer RBAC rule is invalid"
  if [ "${cilium_enabled}" = "true" ]; then
    assert_role_rule "${file}" -workspace-operator '["cilium.io"]' '["ciliumnetworkpolicies"]' '["create", "delete", "get", "list", "update", "watch"]' "${platform}: Operator Cilium RBAC rule is invalid"
    assert_role_rule "${file}" -workspace-operator '["cilium.io"]' '["ciliumendpoints"]' '["get", "list", "watch"]' "${platform}: Operator CiliumEndpoint RBAC rule is invalid"
    assert_yaml "${file}" '[select(.kind == "Role" and (.metadata.name | test("-workspace-firewall-attestor$")))] | .[0].rules | length == 3' "${platform}: firewall attestor RBAC rule count is invalid"
    assert_role_rule "${file}" -workspace-firewall-attestor '[""]' '["pods"]' '["get", "list"]' "${platform}: firewall attestor Pod RBAC rule is invalid"
    assert_role_rule "${file}" -workspace-firewall-attestor '["cilium.io"]' '["ciliumendpoints"]' '["get", "list"]' "${platform}: firewall attestor CiliumEndpoint RBAC rule is invalid"
    assert_role_rule "${file}" -workspace-firewall-attestor '["cilium.io"]' '["ciliumnetworkpolicies"]' '["get", "list", "patch"]' "${platform}: firewall attestor CiliumNetworkPolicy RBAC rule is invalid"
    assert_yaml \
      "${file}" \
      '[select(.kind == "RoleBinding" and (.metadata.name | test("-workspace-firewall-attestor$")))] | .[0] as $binding | [($binding.roleRef.kind == "Role"), ($binding.roleRef.name | test("-workspace-firewall-attestor$")), ($binding.subjects | length == 1), ($binding.subjects[0].kind == "ServiceAccount"), ($binding.subjects[0].namespace == "workspace-system"), ($binding.subjects[0].name | test("-workspace-firewall-attestor$"))] | all' \
      "${platform}: firewall attestor RoleBinding is invalid"
    assert_yaml \
      "${file}" \
      '[select(.kind == "DaemonSet" and (.metadata.name | test("-workspace-firewall-attestor$")))] | .[0] as $daemon | ($daemon.spec.template.spec.containers | map(select(.name == "firewall-attestor")) | .[0]) as $container | [($daemon.spec.template.spec.hostNetwork != true), ($daemon.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($daemon.spec.template.spec.serviceAccountName | test("-workspace-firewall-attestor$")), ($container.securityContext.runAsUser == 0), ($container.securityContext.allowPrivilegeEscalation == false), ($container.securityContext.readOnlyRootFilesystem == true), (($container.securityContext.capabilities.drop | join(",")) == "ALL"), (($container.args | map(select(. == "--mode=firewall-attestor")) | length) == 1), (($container.args | map(select(. == "--cilium-socket-path=/var/run/cilium/cilium.sock")) | length) == 1), (($container.args | map(select(. == "--firewall-attestor-poll-interval=5s")) | length) == 1), (($container.args | map(select(. == "--firewall-attestation-max-age=30s")) | length) == 1), (($container.volumeMounts | map(select(.name == "cilium-run" and .mountPath == "/var/run/cilium/cilium.sock" and .readOnly == true)) | length) == 1), (($daemon.spec.template.spec.volumes | map(select(.name == "cilium-run" and .hostPath.path == "/var/run/cilium/cilium.sock" and .hostPath.type == "Socket")) | length) == 1), ($container.resources.requests.cpu == "10m"), ($container.resources.requests.memory == "32Mi"), ($container.resources.limits.cpu == "100m"), ($container.resources.limits.memory == "64Mi")] | all' \
      "${platform}: firewall attestor socket, identity, resource, and hardening contracts are invalid"
  fi

  echo "${platform}: Kubernetes platform Helm contracts passed"
}

command -v yq >/dev/null 2>&1 || fail "yq is required for structured YAML assertions"
./scripts/test/helm/assert-workspace-storage-crd.sh

assert_yaml \
  "${chart_dir}/values.schema.json" \
  '(.properties.kubernetes.required | contains(["workspaceDefaults"])) and (.definitions.workspaceExecutionPlaneResources.required | contains(["runtime", "browser", "canvas"])) and (.definitions.workspaceResourceProfile.required | contains(["resources"])) and (.definitions.workspaceResourceProfile.properties.resources.required | contains(["requests", "limits"])) and (.definitions.workspaceResourceValues.required | contains(["cpu", "memory"])) and (.properties.workspaceOperator.required | contains(["firewallAttestor"])) and (.properties.workspaceOperator.properties.firewallAttestor.required | contains(["socketPath", "pollInterval", "maxAge", "serviceAccount", "nodeSelector", "tolerations", "resources"])) and (.definitions.containerResources.required | contains(["requests", "limits"]))' \
  "Workspace execution-plane and firewall attestor resource values must be required by the Helm schema"
assert_yaml \
  "${chart_dir}/crds/platform.aileron.io_workspaces.yaml" \
  '.spec as $crd | ($crd.versions | map(select(.name == "v1alpha1")) | .[0].schema.openAPIV3Schema) as $schema | ($schema.properties.status.properties.components.properties) as $components | [($crd.scope == "Namespaced"), ($schema.properties.spec.properties.targetNamespace.type == "string"), ($schema.properties.spec.properties.targetNamespace.description | contains("metadata.namespace")), ($schema.properties.status.properties.targetNamespace.type == "string"), ($schema.properties.status.properties.targetNamespace.description | contains("metadata.namespace")), ([$components.runtime, $components.browser, $components.canvas] | map([((.properties | has("internalUrl")) | not), ((.properties | has("externalUrl")) | not)] | all) | all)] | all' \
  "Workspace CRD does not expose the deployment-derived namespace assertion"
assert_absent \
  "${chart_dir}/crds/platform.aileron.io_workspaces.yaml" \
  'self.metadata.namespace' \
  "Workspace CRD must not depend on unsupported metadata.namespace CEL access"
assert_absent \
  "contracts/controller-dependencies/registry.json" \
  'networking.ingresses' \
  "Workspace controller dependency registry must not include dynamic Ingresses"
assert_absent \
  "${chart_dir}/templates/_generated_workspace_operator_rbac_rules.tpl" \
  'resources: ["ingresses"]' \
  "Workspace Operator generated RBAC must not include dynamic Ingresses"

assert_render_fails \
  'Additional property env is not allowed|Additional property extraEnv is not allowed|workspaceOperator.env: Must not validate the schema (not)' \
  'unknown environment surfaces were accepted' \
  --set-string workspaceManager.env.ARBITRARY_UNSUPPORTED_ENV=rejected \
  --set-string 'workspaceManager.extraEnv[0].name=ARBITRARY_UNSUPPORTED_ENV' \
  --set-string 'workspaceManager.extraEnv[0].value=rejected' \
  --set-string workspaceOperator.env.ARBITRARY_UNSUPPORTED_ENV=rejected
assert_render_fails \
  'kubernetes.storageVerification.workspaceStorageClassName is required when storage verification is enabled' \
  'storage verification without a disposable Workspace StorageClass was accepted' \
  --set kubernetes.storageVerification.enabled=true
assert_render_fails \
  'kubernetes.storageVerification.managerStateStorageClassName is required when storage verification is enabled' \
  'storage verification without a disposable Manager state StorageClass was accepted' \
  --set kubernetes.storageVerification.enabled=true \
  --set-string kubernetes.storageVerification.workspaceStorageClassName=workspace-verification
assert_render_fails \
  'storageVerification|size|not allowed' \
  'legacy shared storage verification size was accepted' \
  --set-string kubernetes.storageVerification.size=2Gi
assert_render_fails \
  'workspaceSize' \
  'invalid Workspace verification Kubernetes quantity was accepted' \
  --set-string kubernetes.storageVerification.workspaceSize=invalid
assert_render_fails \
  'managerStateSize' \
  'invalid Manager state verification Kubernetes quantity was accepted' \
  --set-string kubernetes.storageVerification.managerStateSize=invalid
assert_render_fails \
  'bootstrap.admin.username|String length must be greater than or equal to 1' \
  'administrator bootstrap without a username was accepted' \
  --set-string bootstrap.admin.username=
assert_render_fails \
  'bootstrap.admin.username must contain between 1 and 255 non-whitespace characters' \
  'administrator bootstrap accepted a whitespace-only username' \
  --set-string 'bootstrap.admin.username=   '
assert_render_fails \
  'bootstrap.admin.email|email' \
  'administrator bootstrap accepted an invalid email address' \
  --set-string bootstrap.admin.email=invalid-email
assert_render_fails \
  'workspaceManager.enabled must be true when administrator bootstrap is enabled' \
  'administrator bootstrap silently disappeared when Manager was disabled' \
  --set workspaceManager.enabled=false
assert_render_fails \
  'turn|existingSecretName' \
  'TURN accepted a missing existing Secret' \
  --set turn.enabled=true \
  --set-string turn.existingSecretName=
assert_render_fails \
  'turn|backendIceServersKey' \
  'TURN accepted an empty backend ICE server Secret key' \
  --set turn.enabled=true \
  --set-string turn.backendIceServersKey=
assert_render_fails \
  'turn|credentialRevision' \
  'TURN accepted an empty credential revision' \
  --set turn.enabled=true \
  --set-string turn.credentialRevision=
assert_render_fails \
  'Additional property provider is not allowed' \
  'removed TURN provider inference field was accepted' \
  --set turn.provider=external
assert_render_fails \
  'connectivityEvidenceGateway.enabled must be true when required frontend vantages are configured' \
  'TURN accepted required frontend evidence without an evidence Gateway' \
  --set turn.enabled=true \
  --set connectivityEvidenceGateway.enabled=false
assert_render_fails \
  'connectivityEvidenceGateway.hostAgent.vantageId must be a required frontend vantage' \
  'host connectivity agent accepted an undeclared vantage identity' \
  --set turn.enabled=true \
  --set connectivityEvidenceGateway.hostAgent.enabled=true \
  --set-string connectivityEvidenceGateway.hostAgent.vantageId=undeclared
assert_render_fails \
  'coturn.enabled requires turn.profile.credentialIssuer.kind=staticSecret' \
  'bundled static TURN accepted the TURN REST issuer contract' \
  --set turn.enabled=true \
  --set coturn.enabled=true \
  --set-string turn.profile.credentialIssuer.kind=turnRest

for platform in eks gke aks ocp rke2 native-kubernetes; do
  values_file="${chart_dir}/tests/values/platform-${platform}.yaml"
  rendered_file="${work_dir}/${platform}.yaml"

  helm lint "${chart_dir}" \
    --namespace "${runtime_namespace}" \
    --values "${values_file}"
  helm template aileron "${chart_dir}" \
    --namespace "${runtime_namespace}" \
    --values "${values_file}" > "${rendered_file}"

  assert_workspace_platform_contract "${rendered_file}" "${platform}"

  workspace_verification_storage_class="$(yq eval '.kubernetes.storageVerification.workspaceStorageClassName' "${values_file}")"
  manager_verification_storage_class="$(yq eval '.kubernetes.storageVerification.managerStateStorageClassName' "${values_file}")"
  workspace_verification_size="$(yq eval '.kubernetes.storageVerification.workspaceSize' "${values_file}")"
  manager_verification_size="$(yq eval '.kubernetes.storageVerification.managerStateSize' "${values_file}")"
  workspace_storage_class="$(yq eval '.kubernetes.workspaceData.storageClassName' "${values_file}")"
  runtime_home_storage_class="$(yq eval '.kubernetes.runtimeHome.storageClassName' "${values_file}")"
  runtime_home_access_mode="$(yq eval '.kubernetes.runtimeHome.accessMode' "${values_file}")"
  knowledge_base_storage_class="$(yq eval '.kubernetes.knowledgeBases.storageClassName' "${values_file}")"
  knowledge_base_access_modes="$(yq eval '.kubernetes.knowledgeBases.accessModes | join(",")' "${values_file}")"
  manager_storage_class="$(yq eval '.kubernetes.managerState.storageClassName' "${values_file}")"
  manager_access_modes="$(yq eval '.kubernetes.managerState.accessModes | join(",")' "${values_file}")"
  if [ -z "${workspace_verification_storage_class}" ] || [ "${workspace_verification_storage_class}" = "null" ]; then
    fail "${platform}: Workspace storage verification StorageClass is missing"
  fi
  if [ -z "${manager_verification_storage_class}" ] || [ "${manager_verification_storage_class}" = "null" ]; then
    fail "${platform}: Manager state storage verification StorageClass is missing"
  fi
  if [ -z "${runtime_home_storage_class}" ] || [ "${runtime_home_storage_class}" = "null" ]; then
    fail "${platform}: Runtime HOME StorageClass is missing"
  fi
  [ "${workspace_verification_storage_class}" != "${workspace_storage_class}" ] || \
    fail "${platform}: Workspace verification must not reuse the production StorageClass"
  [ "${manager_verification_storage_class}" != "${manager_storage_class}" ] || \
    fail "${platform}: Manager state verification must not reuse the production StorageClass"
  case "${workspace_verification_storage_class}" in
    *-delete) ;;
    *) fail "${platform}: Workspace verification StorageClass name must identify Delete reclaim policy" ;;
  esac
  case "${manager_verification_storage_class}" in
    *-delete) ;;
    *) fail "${platform}: Manager state verification StorageClass name must identify Delete reclaim policy" ;;
  esac
  case "${platform}" in
    gke)
      [ "${workspace_storage_class}" = "enterprise-multishare-rwx" ] || \
        fail "gke: Workspace must use the GKE Filestore multishare RWX class"
      [ "${knowledge_base_storage_class}" = "enterprise-multishare-rwx" ] || \
        fail "gke: Knowledge Base must use the GKE Filestore multishare RWX class"
      ;;
    aks)
      [ "${workspace_storage_class}" = "azurefile-nfs-premiumv2-custom" ] || \
        fail "aks: Workspace must use the custom Azure Files NFS class"
      [ "${knowledge_base_storage_class}" = "azurefile-nfs-premiumv2-custom" ] || \
        fail "aks: Knowledge Base must use the custom Azure Files NFS class"
      ;;
    native-kubernetes)
      [ "${runtime_home_storage_class}" = "csi-rwo" ] || \
        fail "native-kubernetes: Runtime HOME must use an RWO CSI class"
      [ "${manager_storage_class}" = "csi-rwo" ] || \
        fail "native-kubernetes: Manager state must use an RWO CSI class"
      ;;
  esac
  assert_yaml \
    "${rendered_file}" \
    "[select(.kind == \"Job\" and (.metadata.name | test(\"-storage-verification$\")))] | .[0].spec.template.spec.volumes as \$volumes | (\$volumes | map(select(.name == \"workspace-data\")) | .[0].ephemeral.volumeClaimTemplate.spec) as \$workspace | (\$volumes | map(select(.name == \"manager-state\")) | .[0].ephemeral.volumeClaimTemplate.spec) as \$manager | [((\$volumes | map(select(has(\"ephemeral\"))) | length) == 2), (\$workspace.storageClassName == \"${workspace_verification_storage_class}\"), ((\$workspace.accessModes | join(\",\")) == \"ReadWriteMany\"), (\$workspace.resources.requests.storage == \"${workspace_verification_size}\"), (\$manager.storageClassName == \"${manager_verification_storage_class}\"), ((\$manager.accessModes | join(\",\")) == \"${manager_access_modes}\"), (\$manager.resources.requests.storage == \"${manager_verification_size}\")] | all" \
    "${platform}: Workspace and Manager state verification claims are invalid"
  assert_yaml \
    "${rendered_file}" \
    "select(.kind == \"PersistentVolumeClaim\" and .metadata.name == \"knowledge-bases-pvc\") as \$knowledge | select(.kind == \"PersistentVolumeClaim\" and .metadata.name == \"workspace-manager-state\") as \$manager | [(\$knowledge.spec.storageClassName == \"${knowledge_base_storage_class}\"), ((\$knowledge.spec.accessModes | join(\",\")) == \"${knowledge_base_access_modes}\"), (\$manager.spec.storageClassName == \"${manager_storage_class}\"), ((\$manager.spec.accessModes | join(\",\")) == \"${manager_access_modes}\")] | all" \
    "${platform}: production Knowledge Base and Manager state PVC contracts are invalid"
  assert_yaml \
    "${rendered_file}" \
    "select(.kind == \"ConfigMap\" and (.metadata.name | test(\"-platform-config$\"))) as \$config | [(\$config.data.RUNTIME_HOME_STORAGE_CLASS_NAME == \"${runtime_home_storage_class}\"), (\$config.data.RUNTIME_HOME_STORAGE_ACCESS_MODE == \"${runtime_home_access_mode}\")] | all" \
    "${platform}: Runtime HOME storage contract did not reach the Operator configuration"
  assert_yaml \
    "${rendered_file}" \
    '[select(.kind == "Job" and (.metadata.name | test("-storage-verification$")))] | .[0].spec.template.spec as $pod | [($pod.automountServiceAccountToken == false), ($pod | has("serviceAccountName") | not)] | all' \
    "${platform}: storage verification must not receive Kubernetes API credentials"
  assert_contains "${rendered_file}" 'RUNTIME_K8S_NAMESPACE: "workspace-system"' "${platform}: Manager runtime namespace is not canonical"
  assert_absent "${rendered_file}" 'TARGET_NAMESPACE_SOURCE' "${platform}: legacy target namespace routing source is not allowed"
  assert_absent "${rendered_file}" 'WATCH_NAMESPACE' "${platform}: legacy Operator watch namespace configuration is not allowed"
  assert_absent "${rendered_file}" 'RUNTIME_K8S_CR_NAMESPACE' "${platform}: a separate Workspace CR namespace is not allowed"
  assert_absent "${rendered_file}" 'RUNTIME_K8S_ALLOWED_NAMESPACES' "${platform}: a user-selectable Workspace namespace allow-list is not allowed"
  assert_absent "${rendered_file}" 'VITE_WORKSPACE_K8S_ALLOWED_NAMESPACES' "${platform}: the frontend namespace allow-list is not allowed"
  assert_absent "${rendered_file}" 'VITE_WORKSPACE_K8S_DEFAULT_NAMESPACE' "${platform}: the frontend namespace default is not allowed"
  assert_contains "${rendered_file}" 'app.kubernetes.io/component: knowledge-bases' "${platform}: Knowledge Base PVC is missing"
  assert_contains "${rendered_file}" 'app.kubernetes.io/component: workspace-manager-state' "${platform}: Manager state PVC is missing"
  assert_contains "${rendered_file}" 'claimName: knowledge-bases-pvc' "${platform}: Manager does not mount the canonical Knowledge Base claim"
  assert_contains "${rendered_file}" 'claimName: workspace-manager-state' "${platform}: Manager does not mount its state claim"
  assert_contains "${rendered_file}" 'mountPath: /state' "${platform}: Manager writable state root is missing"
  assert_contains "${rendered_file}" 'mountPath: /tmp' "${platform}: writable tmp root is missing"
  assert_contains "${rendered_file}" '- name: MARKETPLACE_STORAGE_PATH' "${platform}: Marketplace state path is not configured"
  assert_contains "${rendered_file}" 'value: /state/marketplace' "${platform}: Marketplace state is outside the Manager state claim"
  assert_contains "${rendered_file}" '- name: CODEX_MANAGER_STATE_DIR' "${platform}: Codex login state path is not configured"
  assert_contains "${rendered_file}" 'value: /state/codex' "${platform}: Codex login state is outside the Manager state claim"
  assert_contains "${rendered_file}" 'ephemeral:' "${platform}: Workspace and Manager state profile probes are missing"
  assert_contains "${rendered_file}" 'post-install,post-upgrade' "${platform}: storage verification is not an install failure gate"
  assert_contains "${rendered_file}" 'verify_root /workspace-data workspace-data' "${platform}: Workspace RWX backend is not verified"
  assert_contains "${rendered_file}" 'verify_root /manager-state manager-state' "${platform}: Manager state backend is not verified"
  assert_contains "${rendered_file}" 'verify_root /knowledge-bases knowledge-bases' "${platform}: Knowledge Base backend is not verified"
  assert_contains "${rendered_file}" 'root must not be writable by other users' "${platform}: storage verification accepts an other-writable root"
  assert_contains "${rendered_file}" '- name: RUNTIME_ASSERTION_PRIVATE_KEY_FILE' "${platform}: Manager signer private key file is not configured"
  assert_contains "${rendered_file}" '- name: RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE' "${platform}: Manager signer JWKS file is not configured"
  assert_contains "${rendered_file}" 'name: runtime-assertion-signer' "${platform}: Manager signer Secret is not projected"
  assert_contains "${rendered_file}" 'secretName: runtime-assertion-public-jwks' "${platform}: verifier JWKS Secret is not shared with Manager and Runtime"
  assert_contains "${rendered_file}" 'mountPath: /etc/aileron/runtime-assertions' "${platform}: verifier JWKS file mount is missing"
  assert_contains "${rendered_file}" 'latest-kubernetes-amd64' "${platform}: Kubernetes image target is not selected"
  assert_absent "${rendered_file}" 'hostPath:' "${platform}: hostPath is not allowed"
  assert_absent "${rendered_file}" 'privileged: true' "${platform}: privileged containers are not allowed"
  assert_absent "${rendered_file}" 'runAsUser:' "${platform}: fixed runAsUser is not allowed"
  assert_absent "${rendered_file}" 'anyuid' "${platform}: OpenShift anyuid SCC is not allowed"
  assert_absent "${rendered_file}" 'type: Unconfined' "${platform}: unconfined seccomp is not allowed"

  assert_minimum_count "${rendered_file}" 'runAsNonRoot: true' 4 "${platform}: restricted Pod security context is incomplete"
  assert_minimum_count "${rendered_file}" 'readOnlyRootFilesystem: true' 5 "${platform}: production container root filesystem is writable"
  assert_minimum_count "${rendered_file}" 'type: RuntimeDefault' 4 "${platform}: RuntimeDefault seccomp is incomplete"
  assert_minimum_count "${rendered_file}" '- ALL' 5 "${platform}: Linux capabilities are not dropped"
  if [ "${platform}" = "ocp" ]; then
    assert_absent "${rendered_file}" 'fsGroup:' "ocp: fsGroup must be injected by the Project SCC"
    assert_absent "${rendered_file}" 'kind: SecurityContextConstraints' "ocp: an additional SCC must not be installed"
  else
    assert_minimum_count "${rendered_file}" 'fsGroup: 2000' 2 "${platform}: storage fsGroup contract is incomplete"
  fi

  echo "${platform}: chart-compatible render assertions passed"
done

identity_rendered_file="${work_dir}/identity-provisioning.yaml"
helm lint "${chart_dir}" --namespace "${runtime_namespace}"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" > "${identity_rendered_file}"
assert_identity_provisioning_contract "${identity_rendered_file}"
assert_platform_service_contract "${identity_rendered_file}" default
assert_document_count "${identity_rendered_file}" Job -storage-verification 0 "default: storage verification must be disabled"
assert_document_count "${identity_rendered_file}" Ingress -aileron 0 "default: public Ingress must require deployment opt-in"
assert_document_count "${identity_rendered_file}" ClusterRole -workspace-operator-storageclasses 0 "default: disabled StorageClass dependency must not leave ClusterRole permissions"
assert_document_count "${identity_rendered_file}" ClusterRoleBinding -workspace-operator-storageclasses 0 "default: disabled StorageClass dependency must not leave a ClusterRoleBinding"

oidc_ca_rendered_file="${work_dir}/oidc-ca.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set-string oidc.caSecretName=private-platform-ca \
  --set-string oidc.caSecretKey=ca.pem > "${oidc_ca_rendered_file}"
assert_yaml \
  "${oidc_ca_rendered_file}" \
  'select(.kind == "ConfigMap" and (.metadata.name | test("-platform-config$"))) as $config | select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$"))) as $manager | select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | ($manager.spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0]) as $manager_container | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0]) as $operator_container | [(($config.data | has("OIDC_CA_SECRET_NAME")) | not), (($config.data | has("OIDC_CA_SECRET_KEY")) | not), (($manager_container.env | map(select(.name == "OIDC_CA_CERT_FILE" and .value == "/etc/aileron/oidc-ca/ca.crt")) | length) == 1), (($manager_container.volumeMounts | map(select(.name == "oidc-ca" and .mountPath == "/etc/aileron/oidc-ca" and .readOnly == true)) | length) == 1), (($manager.spec.template.spec.volumes | map(select(.name == "oidc-ca" and .secret.secretName == "private-platform-ca" and .secret.items[0].key == "ca.pem" and .secret.items[0].path == "ca.crt")) | length) == 1), (($operator_container.env | map(select(.name | test("OIDC"))) | length) == 0)] | all' \
  "OIDC custom CA trust must terminate at Manager"

admin_bootstrap_disabled_file="${work_dir}/admin-bootstrap-disabled.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set bootstrap.admin.enabled=false > "${admin_bootstrap_disabled_file}"
assert_document_count "${admin_bootstrap_disabled_file}" Job -admin-bootstrap 0 "identity: disabled administrator bootstrap Job must be absent"
assert_document_count "${admin_bootstrap_disabled_file}" Secret -secrets 0 "identity: disabled administrator bootstrap must not render a platform Secret"

assert_render_fails \
  'workspaceDefaults|runtime|requests|memory|1Gi' \
  'Workspace Runtime accepted a resource value outside the Helm contract' \
  --set-string kubernetes.workspaceDefaults.runtime.resources.requests.memory=2Gi

assert_render_fails \
  'workspaceDefaults|canvas|requests|cpu|100m' \
  'Workspace Canvas accepted a resource value outside the Helm contract' \
  --set-string kubernetes.workspaceDefaults.canvas.resources.requests.cpu=500m

postgres_run_as_user_rendered_file="${work_dir}/postgres-run-as-user.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set postgres.runAsUser=1024 > "${postgres_run_as_user_rendered_file}"
assert_yaml \
  "${postgres_run_as_user_rendered_file}" \
  '[select(.spec.template.spec.securityContext.runAsUser != null)] as $workloads | [ (($workloads | length) == 1), ($workloads[0].kind == "StatefulSet"), ($workloads[0].metadata.name | test("-postgres$")), ($workloads[0].spec.template.spec.securityContext.runAsUser == 1024), ($workloads[0].spec.template.spec.securityContext.fsGroup == 2000) ] | all' \
  "explicit Postgres runAsUser must apply only to the PostgreSQL StatefulSet and retain fsGroup"

ocp_platform_services_rendered_file="${work_dir}/ocp-platform-services.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/platform-ocp.yaml" \
  --set frontend.enabled=true \
  --set postgres.enabled=true \
  --set redis.enabled=true \
  --set bootstrap.admin.enabled=true \
  > "${ocp_platform_services_rendered_file}"
assert_platform_service_contract "${ocp_platform_services_rendered_file}" ocp
assert_identity_provisioning_contract "${ocp_platform_services_rendered_file}" external-oidc-client
assert_absent "${ocp_platform_services_rendered_file}" 'runAsUser:' "ocp: administrator bootstrap must not use a fixed UID"
assert_absent "${ocp_platform_services_rendered_file}" 'runAsGroup:' "ocp: administrator bootstrap must not use a fixed GID"
assert_absent "${ocp_platform_services_rendered_file}" 'fsGroup:' "ocp: administrator bootstrap must leave fsGroup to the Project SCC"

external_turn_rendered_file="${work_dir}/external-turn.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/platform-ocp.yaml" \
  --set turn.enabled=true \
  --set ingress.tlsMode=controllerManaged \
  --set-string 'turn.profile.backend.urls[0]=turn:turn.internal.example:3478' \
  --set-string 'turn.profile.frontend.urls[0]=turns:turn.example.com:5349' \
  --set-string turn.existingSecretName="${turn_test_secret}" \
  --set-string turn.profile.credentialIssuer.kind=turnRest \
  --set-string turn.credentialRevision=credential-v7 > "${external_turn_rendered_file}"
assert_document_count "${external_turn_rendered_file}" DaemonSet -coturn 0 "external TURN: built-in DaemonSet must be absent"
assert_document_count "${external_turn_rendered_file}" Service -coturn 0 "external TURN: built-in Service must be absent"
assert_document_count "${external_turn_rendered_file}" ServiceAccount -coturn 0 "external TURN: built-in ServiceAccount must be absent"
assert_document_count "${external_turn_rendered_file}" Secret -coturn-credentials 0 "external TURN: built-in credentials Secret must be absent"
assert_document_count "${external_turn_rendered_file}" Namespace aileron-turn-system 0 "external TURN: built-in target Namespace must be absent"
assert_document_count "${external_turn_rendered_file}" Deployment -connectivity-evidence-gateway 1 "external TURN: evidence Gateway Deployment count is invalid"
assert_document_count "${external_turn_rendered_file}" Service -connectivity-evidence-gateway 1 "external TURN: evidence Gateway Service count is invalid"
assert_document_count "${external_turn_rendered_file}" Secret -connectivity-evidence 0 "external TURN: evidence credentials must be supplied as an existing Secret"
assert_yaml \
  "${external_turn_rendered_file}" \
  'select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env) as $env | ($env | map(select(.name == "TURN_REACHABILITY_PROFILE_JSON"))) as $profile | ($env | map(select(.name == "TURN_ICE_SERVERS_SECRET_NAME"))) as $secret_name | ($env | map(select(.name == "TURN_BACKEND_ICE_SERVERS_SECRET_KEY"))) as $backend_key | ($env | map(select(.name == "TURN_FRONTEND_ICE_SERVERS_SECRET_KEY"))) as $frontend_key | ($env | map(select(.name == "TURN_CREDENTIAL_REVISION"))) as $revision | [($operator.spec.template.metadata.annotations."checksum/turn-credential-contract" | test("^[0-9a-f]{64}$")), (($profile | length) == 1), (($profile[0].value | from_json | .contractVersion) == "browser-connectivity/v1"), (($profile[0].value | from_json | .backend.urls[0]) == "turn:turn.internal.example:3478"), (($profile[0].value | from_json | .frontend.urls[0]) == "turns:turn.example.com:5349"), (($secret_name | length) == 1), ($secret_name[0].value == "external-turn-ice"), (($backend_key | length) == 1), ($backend_key[0].value == "backend-ice-servers-json"), (($frontend_key | length) == 1), ($frontend_key[0].value == "frontend-ice-servers-json"), (($revision | length) == 1), ($revision[0].value == "credential-v7"), (($env | map(select(.name == "TURN_SERVER_URL" or .name == "TURN_PROVIDER" or .name == "TURN_RELAY_MIN_PORT" or .name == "TURN_RELAY_MAX_PORT")) | length) == 0)] | all' \
  "external TURN: Operator must reference pre-rendered ICE server JSON without receiving plaintext credentials"
assert_yaml \
  "${external_turn_rendered_file}" \
  'select(.kind == "Deployment" and (.metadata.name | test("-connectivity-evidence-gateway$"))) as $gateway | select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | select(.kind == "Deployment" and (.metadata.name | test("-workspace-manager$"))) as $manager | ($gateway.spec.template.spec.containers | map(select(.name == "gateway")) | .[0]) as $gateway_container | ($gateway.spec.template.spec.volumes | map(select(.name == "connectivity-auth")) | .[0]) as $gateway_auth | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0]) as $operator_container | ($manager.spec.template.spec.containers | map(select(.name == "workspace-manager")) | .[0]) as $manager_container | ($manager.spec.template.spec.volumes | map(select(.name == "manager-private-secrets")) | .[0]) as $manager_secrets | [($gateway.spec.replicas == 1), ($gateway.spec.template.spec.automountServiceAccountToken == false), ($gateway.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($gateway_container.securityContext.readOnlyRootFilesystem == true), (($gateway_container.env | map(select(.name == "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE" and .value == "/run/secrets/aileron-connectivity/probe-ice-servers.json")) | length) == 1), (($gateway_container.env | map(select(.name == "CONNECTIVITY_AGENT_TOKENS_FILE" and .value == "/run/secrets/aileron-connectivity/agent-tokens.json")) | length) == 1), (($gateway_container.env | map(select(.name == "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE" and .value == "/run/secrets/aileron-connectivity/internal-token")) | length) == 1), (($gateway_container.env | map(select(.name == "TURN_REST_SHARED_SECRET_FILE" and .value == "/run/secrets/aileron-connectivity/turn-rest-shared-secret")) | length) == 1), (($gateway_container.env | map(select(.name == "CONNECTIVITY_AGENT_TOKENS_JSON_FILE" or .name == "CONNECTIVITY_AGENT_TOKENS_JSON" or .name == "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN" or .name == "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON" or .name == "TURN_REST_SHARED_SECRET")) | length) == 0), (($gateway_container.volumeMounts | map(select(.name == "connectivity-auth" and .readOnly == true)) | length) == 1), (($gateway_auth.projected.sources | map(select(.secret.name == "external-turn-ice" and .secret.items[0].path == "turn-rest-shared-secret")) | length) == 1), (($operator_container.env | map(select(.name == "CONNECTIVITY_EVIDENCE_GATEWAY_URL" and (.value | contains(".svc.cluster.local:8083")))) | length) == 1), (($operator_container.env | map(select(.name == "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE" and .value == "/run/secrets/aileron-connectivity/internal-token")) | length) == 1), (($operator_container.env | map(select(.name == "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN")) | length) == 0), (($operator_container.volumeMounts | map(select(.name == "connectivity-auth" and .readOnly == true)) | length) == 1), (($manager_container.env | map(select(.name == "TURN_BROWSER_CREDENTIAL_ISSUER_KIND" and .value == "turnRest")) | length) == 1), (($manager_container.env | map(select(.name == "TURN_FRONTEND_ICE_SERVERS_JSON_FILE" and .value == "/run/secrets/aileron/turn-frontend-ice-servers.json")) | length) == 1), (($manager_container.env | map(select(.name == "TURN_REST_SHARED_SECRET_FILE" and .value == "/run/secrets/aileron/turn-rest-shared-secret")) | length) == 1), (($manager_secrets.projected.sources | map(select(.secret.name == "external-turn-ice" and (.secret.items | length) == 2)) | length) == 1)] | all' \
  "external TURN: evidence Gateway and Operator trust boundary is invalid"

builtin_turn_rendered_file="${work_dir}/builtin-turn.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set turn.enabled=true \
  --set coturn.enabled=true \
  --set ingress.tlsMode=controllerManaged \
  --set-string platformPublicOrigin=https://aileron.apps.example.com \
  > "${builtin_turn_rendered_file}"
assert_document_count "${builtin_turn_rendered_file}" DaemonSet -coturn 1 "built-in TURN: DaemonSet count is invalid"
assert_document_count "${builtin_turn_rendered_file}" Service -coturn 1 "built-in TURN: Service count is invalid"
assert_document_count "${builtin_turn_rendered_file}" ServiceAccount -coturn 1 "built-in TURN: ServiceAccount count is invalid"
assert_document_count "${builtin_turn_rendered_file}" Secret -turn-ice 0 "built-in TURN: ICE credentials must use an existing Secret"
assert_document_count "${builtin_turn_rendered_file}" Secret -coturn-auth 0 "built-in TURN: Coturn credentials must use an existing Secret"
assert_document_count "${builtin_turn_rendered_file}" Namespace aileron-turn-system 1 "built-in TURN: Namespace count is invalid"
assert_document_count "${builtin_turn_rendered_file}" Deployment -connectivity-evidence-gateway 1 "built-in TURN: evidence Gateway Deployment count is invalid"
assert_document_count "${builtin_turn_rendered_file}" Service -connectivity-evidence-gateway 1 "built-in TURN: evidence Gateway Service count is invalid"
assert_document_count "${builtin_turn_rendered_file}" Secret -connectivity-evidence 0 "built-in TURN: evidence credentials must use an existing Secret"
assert_yaml \
  "${builtin_turn_rendered_file}" \
  '[.] as $docs | ($docs | map(select(.kind == "Namespace" and .metadata.name == "aileron-turn-system")) | .[0]) as $namespace | ($docs | map(select(.kind == "DaemonSet" and (.metadata.name | test("-coturn$")))) | .[0]) as $coturn | ($docs | map(select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))) | .[0]) as $operator | ($coturn.spec.template.spec.containers | map(select(.name == "coturn")) | .[0]) as $container | ($coturn.spec.template.spec.volumes | map(select(.name == "coturn-auth")) | .[0]) as $auth | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env) as $operator_env | [($namespace.metadata.labels."pod-security.kubernetes.io/enforce" == "privileged"), ($coturn.metadata.namespace == "aileron-turn-system"), ($coturn.spec.template.spec.hostNetwork == true), ($coturn.spec.template.spec.dnsPolicy == "ClusterFirstWithHostNet"), ($coturn.spec.template.spec.securityContext.runAsUser == 65534), ($coturn.spec.template.spec.securityContext.runAsGroup == 65534), (($container.args | join(",")) | contains("min-port=49160")), (($container.args | join(",")) | contains("max-port=49259")), (($container.args | join(",")) | contains("external-ip=$NODE_IP")), (($container.env | map(select(.name == "TURN_USERNAME_FILE" and .value == "/run/secrets/aileron-coturn/username")) | length) == 1), (($container.env | map(select(.name == "TURN_CREDENTIAL_FILE" and .value == "/run/secrets/aileron-coturn/credential")) | length) == 1), (($container.volumeMounts | map(select(.name == "coturn-auth" and .readOnly == true)) | length) == 1), ($auth.secret.secretName == "aileron-coturn-auth"), (($operator_env | map(select(.name == "TURN_REACHABILITY_PROFILE_JSON") | .value | from_json | .backend.relayPortRange.min == 49160) | length) == 1), (($operator_env | map(select(.name == "TURN_ICE_SERVERS_SECRET_NAME" and .value == "aileron-turn-ice")) | length) == 1), (($operator_env | map(select(.name == "TURN_SERVER_URL" or .name == "TURN_RELAY_MIN_PORT" or .name == "TURN_RELAY_MAX_PORT")) | length) == 0)] | all' \
  "built-in TURN: DaemonSet, Secret, and Operator contracts are invalid"
assert_yaml \
  "${builtin_turn_rendered_file}" \
  '[select((.kind == "DaemonSet" or .kind == "Deployment" or .kind == "StatefulSet" or .kind == "Job") and .spec.template.spec.hostNetwork == true)] | [length == 1, (.[0].kind == "DaemonSet"), (.[0].metadata.name | test("-coturn$"))] | all' \
  "built-in TURN: Coturn must be the only hostNetwork workload"

host_agent_rendered_file="${work_dir}/host-connectivity-agent.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set turn.enabled=true \
  --set coturn.enabled=true \
  --set connectivityEvidenceGateway.hostAgent.enabled=true \
  --set-string connectivityEvidenceGateway.hostAgent.tls.caSecretName=private-platform-ca \
  --set-string connectivityEvidenceGateway.hostAgent.tls.caSecretKey=ca.pem \
  --set-string platformPublicOrigin=https://aileron.apps.example.com \
  --set-string ingress.tlsMode=controllerManaged \
  > "${host_agent_rendered_file}"
assert_document_count "${host_agent_rendered_file}" DaemonSet -connectivity-host-agent 1 "host connectivity agent: DaemonSet count is invalid"
assert_yaml \
  "${host_agent_rendered_file}" \
  'select(.kind == "DaemonSet" and (.metadata.name | test("-connectivity-host-agent$"))) as $agent | ($agent.spec.template.spec.containers | map(select(.name == "agent")) | .[0]) as $container | ($agent.spec.template.spec.volumes | map(select(.name == "agent-token")) | .[0]) as $token_volume | ($agent.spec.template.spec.volumes | map(select(.name == "agent-ca")) | .[0]) as $ca_volume | [($agent.spec.template.spec.hostNetwork == true), ($agent.spec.template.spec.dnsPolicy == "ClusterFirstWithHostNet"), ($agent.spec.template.spec.automountServiceAccountToken == false), ($agent.spec.template.spec.securityContext.seccompProfile.type == "RuntimeDefault"), ($agent.spec.template.spec.securityContext.fsGroup == 65532), ($container.securityContext.readOnlyRootFilesystem == true), (($container.securityContext.capabilities.drop | join(",")) == "ALL"), (($container.env | map(select(.name == "CONNECTIVITY_EVIDENCE_GATEWAY_URL" and .value == "https://aileron.apps.example.com/api/v1/connectivity-evidence")) | length) == 1), (($container.env | map(select(.name == "CONNECTIVITY_AGENT_TOKEN_FILE" and .value == "/var/run/aileron-connectivity-agent/token")) | length) == 1), (($container.env | map(select(.name == "CONNECTIVITY_AGENT_CA_FILE" and .value == "/var/run/aileron-connectivity-agent-ca/ca.crt")) | length) == 1), (($container.env | map(select(.name == "CONNECTIVITY_AGENT_TOKEN")) | length) == 0), (($container.volumeMounts | map(select(.name == "agent-token" and .readOnly == true)) | length) == 1), (($container.volumeMounts | map(select(.name == "agent-ca" and .readOnly == true)) | length) == 1), ($token_volume.secret.defaultMode == 288), ($token_volume.secret.items[0].key == "agent-host-token"), ($ca_volume.secret.secretName == "private-platform-ca"), ($ca_volume.secret.items[0].key == "ca.pem")] | all' \
  "host connectivity agent: external vantage and credential contract is invalid"

ephemeral_platform_services_rendered_file="${work_dir}/ephemeral-platform-services.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set postgres.persistence.enabled=false \
  --set redis.persistence.enabled=false > "${ephemeral_platform_services_rendered_file}"
assert_yaml \
  "${ephemeral_platform_services_rendered_file}" \
  '[select(.kind == "StatefulSet" and (.metadata.name | test("-(redis|postgres)$")))] | [ .[] | [(.spec | has("volumeClaimTemplates") | not), ((.spec.template.spec.volumes | map(select(.name == "data" and has("emptyDir"))) | length) == 1)] | all ] | all' \
  "ephemeral platform services must replace data claims with explicit emptyDir volumes"

assert_render_fails \
  'ingress.tlsMode=kubernetesSecret requires platformPublicOrigin with https' \
  'Kubernetes Secret TLS mode was accepted for HTTP public routing' \
  --set-string platformPublicOrigin=http://aileron.localhost \
  --set-string ingress.tlsMode=kubernetesSecret \
  --set-string ingress.tlsSecretName=workspace-public-tls

tls_rendered_file="${work_dir}/tls-enabled.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set-string platformPublicOrigin=https://aileron.localhost \
  --set ingress.enabled=true \
  --set-string ingress.className=nginx \
  --set-string ingress.tlsMode=kubernetesSecret \
  --set-string ingress.tlsSecretName=workspace-public-tls > "${tls_rendered_file}"
assert_yaml \
  "${tls_rendered_file}" \
  '[select(.kind == "Ingress" and (.metadata.name | test("-aileron$")))] | .[0] as $ingress | [($ingress.spec.tls | length == 1), ($ingress.spec.tls[0].secretName == "workspace-public-tls"), (($ingress.spec.tls[0].hosts | join(",")) == "aileron.localhost")] | all' \
  "platform Ingress TLS contract is invalid"
assert_yaml \
  "${tls_rendered_file}" \
  'select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$"))) as $operator | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env) as $env | (($env | map(select(.name == "PUBLIC_INGRESS_TLS_MODE" or .name == "PUBLIC_INGRESS_TLS_SECRET_NAME")) | length) == 0)' \
  "fixed platform Ingress TLS configuration is invalid"

gke_controller_managed_routing_file="${work_dir}/gke-controller-managed-routing.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/platform-gke.yaml" \
  --values "${chart_dir}/tests/values/immutable-images.yaml" \
  --values "${chart_dir}/tests/values/production-routing-gke.yaml" \
  --set security.requireStrongSecrets=true \
  > "${gke_controller_managed_routing_file}"
assert_yaml \
  "${gke_controller_managed_routing_file}" \
  'select(.kind == "Ingress" and (.metadata.name | test("-aileron$"))) as $ingress | [($ingress.spec | has("ingressClassName") | not), ($ingress.spec | has("tls") | not), ($ingress.metadata.annotations."kubernetes.io/ingress.class" == "gce"), ($ingress.metadata.annotations."ingress.gcp.kubernetes.io/pre-shared-cert" == "aileron-public")] | all' \
  "GKE controller-managed routing contract is invalid"

nginx_upload_routing_file="${work_dir}/nginx-upload-routing.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/production-routing.yaml" \
  > "${nginx_upload_routing_file}"
assert_yaml \
  "${nginx_upload_routing_file}" \
  'select(.kind == "Ingress" and (.metadata.name | test("-aileron$"))) as $ingress | [(($ingress.metadata.annotations."nginx.ingress.kubernetes.io/proxy-body-size") == "1100m"), (($ingress.metadata.annotations."nginx.ingress.kubernetes.io/proxy-request-buffering") == "off"), (($ingress.metadata.annotations."nginx.ingress.kubernetes.io/proxy-read-timeout") == "3600"), (($ingress.metadata.annotations."nginx.ingress.kubernetes.io/proxy-send-timeout") == "3600")] | all' \
  "NGINX upload and streaming annotations must cover the fixed platform Ingress"

image_pull_secrets_rendered_file="${work_dir}/image-pull-secrets.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --set-string 'global.imagePullSecrets[0].name=harbor-primary' \
  --set-string 'global.imagePullSecrets[1].name=harbor-secondary' > "${image_pull_secrets_rendered_file}"
assert_yaml \
  "${image_pull_secrets_rendered_file}" \
  '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0] as $operator | ($operator.spec.template.spec.imagePullSecrets // []) as $pod_secrets | ($operator.spec.template.spec.containers | map(select(.name == "workspace-operator")) | .[0].env | map(select(.name == "WORKSPACE_IMAGE_PULL_SECRET_NAMES"))) as $entries | [ (($pod_secrets | length) == 2), ($pod_secrets[0].name == "harbor-primary"), ($pod_secrets[1].name == "harbor-secondary"), (($entries | length) == 1), ($entries[0].value == "harbor-primary,harbor-secondary") ] | all' \
  "global image pull Secrets were not propagated to the Operator and Workspace workloads"

managed_registry_rendered_file="${work_dir}/managed-registry-auth.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/platform-eks.yaml" \
  --values "${chart_dir}/tests/values/immutable-images.yaml" \
  --values "${chart_dir}/tests/values/production-routing.yaml" \
  --values "${chart_dir}/tests/values/managed-registry-auth.yaml" \
  --set security.requireStrongSecrets=true \
  > "${managed_registry_rendered_file}"
assert_yaml \
  "${managed_registry_rendered_file}" \
  '[select(.kind == "Deployment" and (.metadata.name | test("-workspace-operator$")))] | .[0].spec.template.spec as $pod | ($pod.containers | map(select(.name == "workspace-operator")) | .[0].env | map(select(.name == "WORKSPACE_IMAGE_PULL_SECRET_NAMES"))) as $entries | [(($pod.imagePullSecrets // []) | length == 0), ($entries | length == 0)] | all' \
  "production rendering must support kubelet-managed registry authentication"

cilium_rendered_file="${work_dir}/cilium-enabled.yaml"
helm template aileron "${chart_dir}" \
  --namespace "${runtime_namespace}" \
  --values "${chart_dir}/tests/values/platform-eks.yaml" \
  --set cilium.enabled=true > "${cilium_rendered_file}"
assert_workspace_platform_contract \
  "${cilium_rendered_file}" \
  cilium-enabled \
  true
