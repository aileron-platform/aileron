{{- define "aileron-identity.name" -}}
aileron-identity
{{- end }}

{{- define "aileron-identity.labels" -}}
app.kubernetes.io/part-of: aileron-identity
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end }}

{{- define "aileron-identity.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{ toYaml . | indent 2 }}
{{- end }}
{{- end }}

{{- define "aileron-identity.databaseJdbcUrl" -}}
{{- $url := printf "jdbc:postgresql://aileron-identity-postgres:5432/%s" .Values.postgres.database -}}
{{- if not .Values.postgres.enabled -}}
{{- $url = .Values.postgres.jdbcUrl -}}
{{- if .Values.postgres.caSecretName -}}
{{- $separator := "?" -}}
{{- if contains "?" $url -}}
{{- $separator = "&" -}}
{{- end -}}
{{- $url = printf "%s%ssslrootcert=/etc/aileron/data-service-ca/identity-database/ca.crt" $url $separator -}}
{{- end -}}
{{- end -}}
{{- $url -}}
{{- end }}

{{- define "aileron-identity.databaseLibpqUrl" -}}
{{- include "aileron-identity.databaseJdbcUrl" . | trimPrefix "jdbc:" -}}
{{- end }}
