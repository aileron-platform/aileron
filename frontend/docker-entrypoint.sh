#!/bin/sh
set -e

# Inject runtime environment values into an ephemeral copy of the static assets.
ENV_VARS="VITE_BROWSER_EXTENSION_ID"
HTML_ROOT=/tmp/aileron-html

if [ -d "${HTML_ROOT}" ]; then
  chmod -R u+w "${HTML_ROOT}"
fi
rm -rf "${HTML_ROOT}"
mkdir -p "${HTML_ROOT}"
cp -R /opt/aileron/html/. "${HTML_ROOT}/"
chmod -R u+w "${HTML_ROOT}"

for var in $ENV_VARS; do
  placeholder="__${var}__"
  value=$(printenv "${var}" || true)
  if [ -n "$value" ]; then
    escaped_value=$(printf '%s' "${value}" | sed 's/[\\&|]/\\&/g')
    echo "Injecting runtime value for ${var}"
    find "${HTML_ROOT}" -type f \( -name "*.js" -o -name "*.html" \) \
      -exec sed -i "s|${placeholder}|${escaped_value}|g" {} +
  fi
done

find "${HTML_ROOT}" -type d -exec chmod u-w {} +
find "${HTML_ROOT}" -type f -exec chmod u-w {} +

exec "$@"
