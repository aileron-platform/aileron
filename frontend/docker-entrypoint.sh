#!/bin/sh
set -e

# Runtime env injection: replace __PLACEHOLDER__ in built JS/HTML with actual env vars
# This allows changing URLs without rebuilding the image
ENV_VARS="VITE_API_BASE_URL VITE_FRONTEND_PUBLIC_URL VITE_KEYCLOAK_SERVER_URL VITE_KEYCLOAK_REALM VITE_KEYCLOAK_CLIENT_ID VITE_RUNTIME_PROVISIONER VITE_WORKSPACE_K8S_ALLOWED_NAMESPACES VITE_WORKSPACE_K8S_DEFAULT_NAMESPACE VITE_CILIUM_ENABLED"

for var in $ENV_VARS; do
  placeholder="__${var}__"
  value=$(eval echo "\$$var")
  if [ -n "$value" ]; then
    echo "Injecting $var = $value"
    find /usr/share/nginx/html -type f \( -name "*.js" -o -name "*.html" \) -exec sed -i "s|${placeholder}|${value}|g" {} +
  fi
done

exec "$@"
