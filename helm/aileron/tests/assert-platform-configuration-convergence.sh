#!/bin/sh
set -eu

chart_dir=${1:-helm/aileron}
rendered=$(mktemp)
optional_rendered=$(mktemp)
invalid_values=$(mktemp)
nginx_config=$(mktemp)
nginx_root=$(mktemp -d)
nginx_started=false

cleanup() {
  if [ "$nginx_started" = true ] && command -v nginx >/dev/null 2>&1; then
    nginx -s stop -c "$nginx_config" >/dev/null 2>&1 || true
  fi
  rm -f "$rendered" "$optional_rendered" "$invalid_values" "$nginx_config"
  rm -rf "$nginx_root"
}

trap cleanup EXIT

fail() {
  echo "ASSERTION FAILED: $*" >&2
  exit 1
}

assert_contains() {
  file=$1
  pattern=$2
  grep -Eq -- "$pattern" "$file" || fail "$file does not contain: $pattern"
}

assert_not_contains() {
  file=$1
  pattern=$2
  if grep -Eq -- "$pattern" "$file"; then
    fail "$file unexpectedly contains: $pattern"
  fi
}

assert_literal() {
  file=$1
  literal=$2
  grep -Fq -- "$literal" "$file" || fail "$file does not contain literal: $literal"
}

assert_not_literal() {
  file=$1
  literal=$2
  if grep -Fq -- "$literal" "$file"; then
    fail "$file unexpectedly contains literal: $literal"
  fi
}

command -v yq >/dev/null 2>&1 || fail "yq is required"
command -v nginx >/dev/null 2>&1 || fail "nginx is required"
command -v wget >/dev/null 2>&1 || fail "wget is required"

helm lint "$chart_dir" --namespace workspace-system >/dev/null
for values_file in "$chart_dir"/tests/values/*.yaml; do
  helm lint "$chart_dir" --namespace workspace-system -f "$values_file" >/dev/null
  helm template platform "$chart_dir" \
    --namespace workspace-system \
    -f "$values_file" >/dev/null
done
helm template platform "$chart_dir" \
  --namespace workspace-system \
  --set-string platformPublicOrigin=https://platform.example.com:8443 \
  --set ingress.enabled=true \
  --set ingress.tlsMode=kubernetesSecret \
  --set-string ingress.tlsSecretName=platform-tls >"$rendered"
helm template platform "$chart_dir" \
  --namespace workspace-system \
  --set turn.enabled=true \
  --set coturn.enabled=true \
  --set connectivityEvidenceGateway.hostAgent.enabled=true >"$optional_rendered"

# values/schema: one exact public origin, canonical OIDC inputs, and no override escape hatches.
assert_contains "$chart_dir/values.yaml" '^platformPublicOrigin: https://aileron\.localhost$'
assert_not_contains "$chart_dir/values.yaml" 'publicRouting:|dynamicWorkspace|^[[:space:]]+env:|extraEnv:|discoveryUrl:|scopes:|allowedAlgorithms:|maxTokenLifetimeSeconds:|requiredAcr:|jwksCacheTtl:|discoveryTimeoutSeconds:'
assert_contains "$chart_dir/values.schema.json" '"platformPublicOrigin"'
assert_contains "$chart_dir/values.schema.json" '\^https\?://'
assert_not_contains "$chart_dir/values.schema.json" '"extraEnv"|"discoveryUrl"|"scopes"|"allowedAlgorithms"|"maxTokenLifetimeSeconds"|"requiredAcr"|"jwksCacheTtl"|"discoveryTimeoutSeconds"'

for forbidden_values in \
  'unknownPlatformSetting: true' \
  'global:\n  unknownSetting: true' \
  'kubernetes:\n  unknownSetting: true' \
  'workspaceOperator:\n  unknownSetting: true' \
  'workspaceOperator:\n  image:\n    unknownSetting: true' \
  'kubernetes:\n  workspaceData:\n    unknownSetting: true' \
  'postgres:\n  unknownSetting: true' \
  'postgres:\n  persistence:\n    unknownSetting: true' \
  'redis:\n  unknownSetting: true' \
  'publicRouting:\n  scheme: https' \
  'oidc:\n  discoveryUrl: https://login.example.com/.well-known/openid-configuration' \
  'workspaceManager:\n  extraEnv: []' \
  'frontend:\n  env:\n    LEGACY_OVERRIDE: rejected'
do
  printf '%b\n' "$forbidden_values" >"$invalid_values"
  if helm template platform "$chart_dir" --namespace workspace-system -f "$invalid_values" >/dev/null 2>&1; then
    fail "forbidden values path was accepted: $forbidden_values"
  fi
done

for invalid_origin in \
  platform.example.com \
  https://platform.example.com/ \
  https://platform.example.com/path \
  https://user@platform.example.com \
  https://platform.example.com?query=yes \
  https://platform.example.com:65536
do
  printf 'platformPublicOrigin: "%s"\n' "$invalid_origin" >"$invalid_values"
  if helm template platform "$chart_dir" --namespace workspace-system -f "$invalid_values" >/dev/null 2>&1; then
    fail "invalid platformPublicOrigin was accepted: $invalid_origin"
  fi
done

# Consumers receive only canonical inputs; callbacks and browser URLs stay service-derived.
assert_contains "$rendered" 'PLATFORM_PUBLIC_ORIGIN: "https://platform\.example\.com:8443"'
assert_contains "$rendered" 'OIDC_ISSUER_URL: "https://login\.example\.com/realms/aileron"'
assert_contains "$rendered" 'OIDC_CLIENT_ID: "aileron-manager"'
assert_not_contains "$rendered" 'OIDC_DISCOVERY_URL|OIDC_REDIRECT_URI|OIDC_POST_LOGOUT_REDIRECT_URI|FRONTEND_ORIGIN|FRONTEND_PUBLIC_URL|ALLOWED_ORIGINS|PUBLIC_FRONTEND_URL|PUBLIC_ALLOWED_ORIGINS|PUBLIC_WORKSPACE_MANAGER_URL|PUBLIC_WORKSPACE_MANAGER_API_URL|VITE_API_BASE_URL|VITE_FRONTEND_PUBLIC_URL'
assert_contains "$rendered" 'name: AILERON_MANAGER_INTERNAL_URL'
assert_contains "$rendered" 'name: AILERON_PLATFORM_PUBLIC_ORIGIN'
assert_contains "$rendered" 'platform-aileron-workspace-manager\.workspace-system\.svc\.cluster\.local:3001'
assert_not_contains "$rendered" 'name: PLATFORM_MANAGER_URL|^[[:space:]]+PLATFORM_MANAGER_URL:'
assert_not_contains "$rendered" 'PUBLIC_(SCHEME|BASE_DOMAIN|FRONTEND_HOST|WORKSPACE_MANAGER_HOST|RUNTIME_HOST_PATTERN|BROWSER_HOST_PATTERN|CANVAS_HOST_PATTERN)|DYNAMIC_WORKSPACE|workspace-routing'

# A single public Ingress host reaches only the frontend.
[ "$(grep -Ec '^[[:space:]]+- host: "https?://' "$rendered" || true)" -eq 0 ] || fail "Ingress host contains a scheme"
[ "$(grep -Ec '^[[:space:]]+- host: "platform\.example\.com"' "$rendered")" -eq 1 ] || fail "Ingress must contain exactly one platform host"
assert_contains "$rendered" 'name: platform-aileron-frontend'
assert_not_contains "$rendered" 'host: "workspace-manager\.|host: "workspace-(runtime|browser|canvas)-'

# Nginx owns same-origin manager and canonical-UUID Workspace routing.
assert_contains "$rendered" 'location /api/v1'
assert_contains "$rendered" 'proxy_pass http://platform-aileron-workspace-manager\.workspace-system\.svc\.cluster\.local:3001'
assert_literal "$rendered" 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/runtime/ws/terminal(?<gateway_path>/.*)?$"'
assert_literal "$rendered" 'proxy_pass http://workspace-runtime-$workspace_id.workspace-system.svc.cluster.local:3004;'
assert_literal "$rendered" 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/runtime/.+"'
assert_literal "$rendered" 'proxy_pass http://workspace-runtime-$workspace_id.workspace-system.svc.cluster.local:3002;'
assert_literal "$rendered" 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/browser/.+"'
assert_literal "$rendered" 'rewrite ^/workspaces/[0-9a-f-]+/browser(/.*)$ $1 break;'
assert_literal "$rendered" 'proxy_pass http://workspace-browser-$workspace_id.workspace-system.svc.cluster.local:6080;'
assert_literal "$rendered" 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/canvas/.+"'
assert_literal "$rendered" 'rewrite ^/workspaces/[0-9a-f-]+/canvas(/.*)$ $1 break;'
assert_literal "$rendered" 'proxy_pass http://workspace-canvas-$workspace_id.workspace-system.svc.cluster.local:3003;'
assert_not_literal "$rendered" 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/runtime/(?<gateway_path>.*)$"'
assert_not_literal "$rendered" 'location ~ "^/workspaces/([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/(browser|canvas)(/.*)?$"'
assert_not_literal "$rendered" 'rewrite ^/workspaces/[0-9a-f-]+/(browser|canvas)(/.*)?$ $2 break;'
assert_not_literal "$rendered" 'proxy_pass http://workspace-$workspace_component-$workspace_id.workspace-system.svc.cluster.local:$workspace_service_port;'
assert_literal "$rendered" 'location = /_aileron_workspace_gateway_authorize {'
assert_literal "$rendered" 'proxy_set_header X-Aileron-Workspace-Id $workspace_id;'
assert_literal "$rendered" 'proxy_set_header Cookie "aileron_session=$cookie_aileron_workspace_gateway_session";'
assert_literal "$rendered" 'auth_request /_aileron_workspace_gateway_authorize;'
assert_contains "$rendered" 'proxy_http_version 1\.1;'
assert_contains "$rendered" 'proxy_set_header Upgrade \$http_upgrade;'
assert_contains "$rendered" 'proxy_set_header Connection \$connection_upgrade;'
assert_contains "$rendered" 'proxy_buffering off;'
assert_contains "$rendered" 'proxy_set_header Authorization \$http_authorization;'
assert_contains "$rendered" 'proxy_set_header Cookie \$http_cookie;'
assert_contains "$rendered" 'proxy_set_header X-Forwarded-Host \$http_host;'
assert_contains "$rendered" 'proxy_set_header X-Forwarded-Port \$server_port;'
assert_literal "$rendered" 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/runtime;'
assert_literal "$rendered" 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/browser;'
assert_literal "$rendered" 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/canvas;'
assert_contains "$rendered" 'proxy_set_header Sec-WebSocket-Protocol \$http_sec_websocket_protocol;'
assert_contains "$rendered" 'proxy_cache off;'
assert_contains "$rendered" 'proxy_read_timeout 3600s;'
assert_contains "$rendered" 'proxy_send_timeout 3600s;'

yq eval-all -r \
  'select(.kind == "ConfigMap" and (.metadata.name | test("-frontend-nginx$"))) | .data."nginx.conf"' \
  "$rendered" >"$nginx_config"
[ "$(grep -Fc 'location ~ "^/workspaces/' "$nginx_config")" -eq 4 ] || fail "only the four exact Workspace proxy locations may precede the SPA fallback"
[ "$(grep -Fc 'proxy_set_header Cookie $http_cookie;' "$nginx_config")" -eq 1 ] || fail "only Manager API may receive the platform Cookie"
[ "$(grep -Fc 'proxy_set_header Cookie "";' "$nginx_config")" -eq 4 ] || fail "all four Workspace upstreams must clear platform Cookies"
[ "$(grep -Fc 'auth_request /_aileron_workspace_gateway_authorize;' "$nginx_config")" -eq 4 ] || fail "all four Workspace routes must pass the Manager authorization gate"
[ "$(grep -Fc 'proxy_set_header Authorization "";' "$nginx_config")" -eq 3 ] || fail "authorization subrequest, Browser, and Canvas must clear platform Authorization"
[ "$(grep -Fc 'proxy_set_header Proxy-Authorization "";' "$nginx_config")" -eq 5 ] || fail "authorization subrequest and all four Workspace upstreams must clear proxy credentials"
[ "$(grep -Fc 'proxy_set_header X-API-Key "";' "$nginx_config")" -eq 5 ] || fail "authorization subrequest and all four Workspace upstreams must clear platform API keys"
[ "$(grep -Fc 'proxy_set_header X-CSRF-Token "";' "$nginx_config")" -eq 5 ] || fail "authorization subrequest and all four Workspace upstreams must clear Manager CSRF tokens"
# The syntax check runs outside Kubernetes, where the cluster DNS service name
# is intentionally not resolvable. Replace only the temporary rendered copy.
sed -i 's/resolver kube-dns\.kube-system\.svc\.cluster\.local/resolver 127.0.0.1/' "$nginx_config"
sed -i -E 's/[A-Za-z0-9.-]+-workspace-manager\.[A-Za-z0-9.-]+\.svc\.cluster\.local/127.0.0.1/g' "$nginx_config"
nginx_test_port=$((18000 + ($$ % 1000)))
sed -i "s/listen       8082;/listen       ${nginx_test_port};/" "$nginx_config"
sed -i "s#root   /tmp/aileron-html;#root   ${nginx_root};#g" "$nginx_config"
printf '%s\n' 'aileron-workspace-spa-root' >"$nginx_root/index.html"
chmod 755 "$nginx_root"
nginx -t -c "$nginx_config"
nginx -T -c "$nginx_config" >/dev/null
nginx -c "$nginx_config"
nginx_started=true
sleep 0.2
spa_failure=
workspace_id=11111111-1111-4111-8111-111111111111
for spa_suffix in runtime runtime/ browser browser/ canvas canvas/; do
  if spa_response=$(wget -qO- "http://127.0.0.1:${nginx_test_port}/workspaces/${workspace_id}/${spa_suffix}"); then
    if [ "$spa_response" != 'aileron-workspace-spa-root' ]; then
      spa_failure="Workspace SPA root /${spa_suffix} returned an unexpected response"
      break
    fi
  else
    spa_failure="Workspace SPA root /${spa_suffix} was intercepted by a gateway location"
    break
  fi
done
nginx -s stop -c "$nginx_config" >/dev/null
nginx_started=false
[ -z "$spa_failure" ] || fail "$spa_failure"

# The chart creates no secret material and applications consume existing Secrets as files.
assert_not_contains "$rendered" '^kind: Secret$|secretKeyRef:|stringData:'
assert_not_contains "$optional_rendered" '^kind: Secret$|secretKeyRef:|stringData:'
assert_not_contains "$chart_dir/values.yaml" '^[[:space:]]+(password|credential|internalToken|agentTokens|credentialKey):'
assert_contains "$rendered" 'name: DATABASE_URL_FILE'
assert_contains "$rendered" 'name: OIDC_CLIENT_SECRET_FILE'
assert_contains "$optional_rendered" 'name: TURN_REST_SHARED_SECRET_FILE'
assert_contains "$optional_rendered" 'name: TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE'
assert_contains "$optional_rendered" 'name: CONNECTIVITY_AGENT_TOKENS_FILE'
assert_contains "$optional_rendered" 'name: CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE'
assert_contains "$optional_rendered" 'name: CONNECTIVITY_AGENT_TOKEN_FILE'
assert_not_contains "$optional_rendered" 'name: CONNECTIVITY_AGENT_TOKENS_JSON_FILE|name: CONNECTIVITY_AGENT_TOKENS_JSON|name: CONNECTIVITY_GATEWAY_INTERNAL_TOKEN$|name: TURN_FRONTEND_PROBE_ICE_SERVERS_JSON$|name: TURN_REST_SHARED_SECRET$'
assert_contains "$rendered" 'readOnly: true'
assert_contains "$optional_rendered" 'readOnly: true'
yq eval-all -e '
  select(.kind == "Deployment" and (.metadata.name | test("-connectivity-evidence-gateway$"))) |
  .spec.template.spec.securityContext.fsGroup == 65532 and
  .spec.template.spec.securityContext.fsGroupChangePolicy == "OnRootMismatch"
' "$optional_rendered" >/dev/null || fail "Gateway Secret files must be readable by the non-root process"

echo "platform configuration convergence assertions passed"
