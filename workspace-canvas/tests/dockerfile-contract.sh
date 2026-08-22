#!/usr/bin/env bash
set -euo pipefail

dockerfile="${1:-workspace-canvas/Dockerfile}"

grep -Fq \
  'find /opt/canvas-nextjs-template /opt/canvas-default-source /canvas-management /scripts \' \
  "${dockerfile}"
grep -Fq '      -type d -exec chmod a+rx {} +' "${dockerfile}"
grep -Fq '      -type f -exec chmod a+r {} +' "${dockerfile}"
grep -Fq '    && chmod 0755 /scripts/*.sh' "${dockerfile}"

readability_line="$(grep -n -m1 -F 'find /opt/canvas-nextjs-template /opt/canvas-default-source /canvas-management /scripts \' "${dockerfile}" | cut -d: -f1)"
scripts_copy_line="$(grep -n -m1 -F 'COPY scripts/ /scripts/' "${dockerfile}" | cut -d: -f1)"
scripts_chmod_line="$(grep -n -m1 -F '&& chmod 0755 /scripts/*.sh' "${dockerfile}" | cut -d: -f1)"

(( scripts_copy_line < readability_line ))
(( readability_line < scripts_chmod_line ))

printf 'Canvas Dockerfile readability contract passed\n'
