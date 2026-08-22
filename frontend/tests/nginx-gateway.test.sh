#!/bin/sh
set -eu

workspace_id='11111111-1111-4111-8111-111111111111'

stop_nginx() {
  nginx -s stop -c /workspace/nginx.conf >/dev/null 2>&1 || true
}

trap stop_nginx EXIT HUP INT TERM

rendered="$(nginx -T -c /workspace/nginx.conf 2>&1)"

require_line() {
  pattern="$1"
  printf '%s\n' "${rendered}" | grep -F "${pattern}" >/dev/null
}

require_count() {
  expected="$1"
  pattern="$2"
  actual="$(printf '%s\n' "${rendered}" | grep -F -c "${pattern}" || true)"
  [ "${actual}" -eq "${expected}" ] || {
    echo "Expected ${expected} occurrences of ${pattern}, found ${actual}" >&2
    exit 1
  }
}

require_line 'resolver 127.0.0.11'
require_line 'workspace-runtime-$workspace_id:3002'
require_line 'workspace-runtime-$workspace_id:3004'
require_line 'workspace-browser-$workspace_id:6080'
require_line 'workspace-canvas-$workspace_id:3003'
require_line 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/runtime/.+"'
require_line 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/browser/.+"'
require_line 'location ~ "^/workspaces/(?<workspace_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/canvas/.*"'
require_line 'location ^~ /api/v1/connectivity-evidence'
require_line 'proxy_pass http://connectivity-evidence-gateway:8083;'
require_line 'location = /_aileron_workspace_gateway_authorize'
require_line 'proxy_pass http://workspace-manager:3001/api/v1/workspaces/gateway/authorize;'
require_line 'proxy_set_header X-Aileron-Workspace-Id $workspace_id;'
require_line 'proxy_set_header Cookie "aileron_session=$cookie_aileron_workspace_gateway_session";'
require_count 4 'auth_request /_aileron_workspace_gateway_authorize;'
require_count 4 'proxy_set_header Authorization $http_authorization;'
require_count 3 'proxy_set_header Authorization "";'
require_count 1 'proxy_set_header Cookie $http_cookie;'
require_count 5 'proxy_set_header Cookie "";'
require_count 5 'proxy_set_header Proxy-Authorization "";'
require_count 5 'proxy_set_header X-API-Key "";'
require_count 5 'proxy_set_header X-CSRF-Token "";'
require_line 'proxy_set_header X-Forwarded-Proto $scheme;'
require_line 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/runtime;'
require_line 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/browser;'
require_line 'proxy_set_header X-Forwarded-Prefix /workspaces/$workspace_id/canvas;'
require_line 'proxy_set_header Upgrade $http_upgrade;'
require_line 'proxy_set_header Sec-WebSocket-Protocol $http_sec_websocket_protocol;'
require_line 'proxy_buffering off;'
require_line 'proxy_request_buffering off;'

if printf '%s\n' "${rendered}" | grep -F 'proxy_pass $http_' >/dev/null; then
  echo 'Request-supplied upstream is forbidden' >&2
  exit 1
fi

nginx -c /workspace/nginx.conf
sleep 0.2

if wget -qO /dev/null \
  "http://127.0.0.1:8082/workspaces/${workspace_id}/canvas/headers"; then
  echo 'Workspace route accepted a request without a gateway session' >&2
  exit 1
fi

response="$(wget -qO- \
  --header='Cookie: aileron_workspace_gateway_session=opaque-session; aileron_session=manager-session-must-not-leak' \
  --header='Authorization: Bearer browser-credential-must-not-leak' \
  --header='Proxy-Authorization: Basic proxy-credential-must-not-leak' \
  --header='X-API-Key: api-key-must-not-leak' \
  --header='X-CSRF-Token: csrf-must-not-leak' \
  "http://127.0.0.1:8082/workspaces/${workspace_id}/canvas/headers")"

[ "${response}" = "|||||/workspaces/${workspace_id}/canvas" ] || {
  echo "Workspace upstream credential stripping failed: ${response}" >&2
  exit 1
}

root_response="$(wget -qO- \
  --header='Cookie: aileron_workspace_gateway_session=opaque-session' \
  "http://127.0.0.1:8082/workspaces/${workspace_id}/canvas/?lang=zh-TW")"

[ "${root_response}" = "|||||/workspaces/${workspace_id}/canvas" ] || {
  echo "Canvas root gateway routing failed: ${root_response}" >&2
  exit 1
}

connectivity_response="$(wget -qO- \
  --header='Authorization: Bearer host-agent-token' \
  --header='Cookie: manager-session-must-not-leak' \
  "http://127.0.0.1:8082/api/v1/connectivity-evidence")"
[ "${connectivity_response}" = "/api/v1/connectivity-evidence|Bearer host-agent-token|" ] || {
  echo "Connectivity evidence gateway routing failed: ${connectivity_response}" >&2
  exit 1
}
