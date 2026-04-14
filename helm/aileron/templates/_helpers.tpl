{{- define "aileron.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aileron.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "aileron.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "aileron.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "aileron.labels" -}}
helm.sh/chart: {{ include "aileron.chart" . }}
app.kubernetes.io/name: {{ include "aileron.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: aileron
{{- end -}}

{{- define "aileron.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aileron.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "aileron.componentLabels" -}}
{{ include "aileron.selectorLabels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "aileron.serviceAccountName" -}}
{{- if .serviceAccount.create -}}
{{- default (printf "%s-%s" (include "aileron.fullname" .root) .nameSuffix) .serviceAccount.name -}}
{{- else -}}
{{- default "default" .serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "aileron.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "aileron.storageClassName" -}}
{{- if .Values.global.storageClass }}
storageClassName: {{ .Values.global.storageClass | quote }}
{{- end }}
{{- end -}}

{{- define "aileron.resolveHostTemplate" -}}
{{- $template := .template -}}
{{- $baseDomain := .baseDomain -}}
{{- $workspaceID := default "" .workspaceID -}}
{{- $resolved := $template | replace "{baseDomain}" $baseDomain -}}
{{- if ne $workspaceID "" -}}
{{- $resolved = $resolved | replace "{workspaceId}" $workspaceID -}}
{{- end -}}
{{- $resolved -}}
{{- end -}}

{{- define "aileron.publicHost" -}}
{{- include "aileron.resolveHostTemplate" (dict "template" .template "baseDomain" .Values.publicRouting.baseDomain "workspaceID" .workspaceID) -}}
{{- end -}}

{{- define "aileron.publicURL" -}}
{{- printf "%s://%s" .Values.publicRouting.scheme (include "aileron.publicHost" (dict "template" .template "workspaceID" .workspaceID "Values" .Values)) -}}
{{- end -}}

{{- define "aileron.publicWildcardHost" -}}
{{- include "aileron.resolveHostTemplate" (dict "template" (.template | replace "{workspaceId}" "*") "baseDomain" .Values.publicRouting.baseDomain) -}}
{{- end -}}

{{- define "aileron.coturnHost" -}}
{{- if not .Values.coturn.enabled -}}
{{- "" -}}
{{- else -}}
{{- required "coturn.host is required when coturn.enabled=true" .Values.coturn.host -}}
{{- end -}}
{{- end -}}

{{- define "aileron.coturnFrontendHost" -}}
{{- if not .Values.coturn.enabled -}}
{{- "" -}}
{{- else -}}
{{- required "coturn.frontendHost is required when coturn.enabled=true" .Values.coturn.frontendHost -}}
{{- end -}}
{{- end -}}

{{- define "aileron.coturnExternalIp" -}}
{{- if not .Values.coturn.enabled -}}
{{- "" -}}
{{- else -}}
{{- required "coturn.externalIp is required when coturn.enabled=true" .Values.coturn.externalIp -}}
{{- end -}}
{{- end -}}
