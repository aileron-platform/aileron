{{- define "aileron-site.name" -}}
aileron-site
{{- end -}}

{{- define "aileron-site.fullname" -}}
{{- printf "canvas-site-%s" (sha256sum (required "site.siteId is required" .Values.site.siteId) | trunc 12) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aileron-site.labels" -}}
app.kubernetes.io/name: {{ include "aileron-site.name" . | quote }}
app.kubernetes.io/instance: {{ include "aileron-site.fullname" . | quote }}
app.kubernetes.io/managed-by: aileron-canvas-publish
aileron.io/site-id-hash: {{ sha256sum .Values.site.siteId | trunc 12 | quote }}
aileron.io/workspace-id: {{ required "site.workspaceId is required" .Values.site.workspaceId | quote }}
{{- end -}}
