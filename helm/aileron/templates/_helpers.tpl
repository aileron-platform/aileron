{{- define "aileron.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aileron.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "aileron.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.waitForJobInitContainer" -}}
- name: {{ .name }}
  image: {{ include "aileron.imageReference" (dict "name" "workspaceManager.image" "image" .root.Values.workspaceManager.image "production" .root.Values.security.requireStrongSecrets) | quote }}
  imagePullPolicy: {{ .root.Values.workspaceManager.image.pullPolicy }}
  env:
    - name: REQUIRED_JOB_NAME
      value: {{ .jobName | quote }}
  command:
    - /bin/sh
    - -ec
    - |
      exec /workspace-manager/.venv/bin/python - <<'PY'
      import json
      import os
      import ssl
      import time
      import urllib.error
      import urllib.request
      from pathlib import Path

      service_account = Path("/var/run/secrets/kubernetes.io/serviceaccount")
      namespace = (service_account / "namespace").read_text().strip()
      token = (service_account / "token").read_text().strip()
      job_name = os.environ["REQUIRED_JOB_NAME"]
      url = (
          "https://kubernetes.default.svc/apis/batch/v1/namespaces/"
          f"{namespace}/jobs/{job_name}"
      )
      context = ssl.create_default_context(cafile=str(service_account / "ca.crt"))
      while True:
          request = urllib.request.Request(
              url,
              headers={"Authorization": f"Bearer {token}"},
          )
          try:
              with urllib.request.urlopen(
                  request, context=context, timeout=10
              ) as response:
                  job = json.load(response)
          except urllib.error.HTTPError as error:
              if error.code == 404:
                  time.sleep(2)
                  continue
              raise
          conditions = {
              item.get("type"): item.get("status")
              for item in job.get("status", {}).get("conditions", [])
          }
          if conditions.get("Complete") == "True":
              break
          if conditions.get("Failed") == "True":
              raise RuntimeError(f"Required Job failed: {job_name}")
          time.sleep(2)
      PY
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities:
      drop:
        - ALL
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

{{- define "aileron.componentPodLabels" -}}
{{ include "aileron.componentLabels" . }}
app.kubernetes.io/part-of: aileron
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

{{- define "aileron.imageReference" -}}
{{- $image := .image -}}
{{- $name := .name -}}
{{- $repository := required (printf "%s.repository is required" $name) $image.repository | trim -}}
{{- $digest := $image.digest | default "" | trim -}}
{{- $tag := $image.tag | default "" | trim -}}
{{- if ne $digest "" -}}
{{- if ne $tag "" -}}
{{- fail (printf "%s.tag must be empty when %s.digest is set" $name $name) -}}
{{- end -}}
{{- if not (regexMatch `^sha256:[0-9a-f]{64}$` $digest) -}}
{{- fail (printf "%s.digest must be a lowercase sha256 digest" $name) -}}
{{- end -}}
{{- printf "%s@%s" $repository $digest -}}
{{- else -}}
{{- $resolvedTag := required (printf "%s.tag is required when digest is empty" $name) $tag -}}
{{- printf "%s:%s" $repository $resolvedTag -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateProductionImages" -}}
{{- if .Values.security.requireStrongSecrets -}}
{{- $images := list
  (dict "name" "frontend.image" "image" .Values.frontend.image)
  (dict "name" "workspaceManager.image" "image" .Values.workspaceManager.image)
  (dict "name" "workspaceOperator.image" "image" .Values.workspaceOperator.image)
  (dict "name" "workspaceOperator.runtimeImage" "image" .Values.workspaceOperator.runtimeImage)
  (dict "name" "kubernetes.browserImage" "image" .Values.kubernetes.browserImage)
  (dict "name" "kubernetes.canvasImage" "image" .Values.kubernetes.canvasImage)
  (dict "name" "postgres.image" "image" .Values.postgres.image)
}}
{{- if .Values.redis.enabled -}}
{{- $images = append $images (dict "name" "redis.image" "image" .Values.redis.image) -}}
{{- end -}}
{{- if and .Values.turn.enabled .Values.coturn.enabled -}}
{{- $images = append $images (dict "name" "coturn.image" "image" .Values.coturn.image) -}}
{{- end -}}
{{- range $entry := $images -}}
{{- $digest := $entry.image.digest | default "" | trim -}}
{{- if not (regexMatch `^sha256:[0-9a-f]{64}$` $digest) -}}
{{- fail (printf "%s.digest is required and must be a lowercase sha256 digest when security.requireStrongSecrets=true" $entry.name) -}}
{{- end -}}
{{- if ne ($entry.image.tag | default "" | trim) "" -}}
{{- fail (printf "%s.tag must be empty when security.requireStrongSecrets=true" $entry.name) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateProductionRouting" -}}
{{- if .Values.security.requireStrongSecrets -}}
{{- if ne (include "aileron.platformPublicScheme" .) "https" -}}
{{- fail "platformPublicOrigin must use https when security.requireStrongSecrets=true" -}}
{{- end -}}
{{- if not .Values.ingress.enabled -}}
{{- fail "ingress.enabled must be true when security.requireStrongSecrets=true" -}}
{{- end -}}
{{- $ingressClassName := .Values.ingress.className | default "" | trim -}}
{{- $staticIngressClassAnnotation := index (.Values.ingress.annotations | default dict) "kubernetes.io/ingress.class" | default "" | trim -}}
{{- if and
  (eq $ingressClassName "")
  (not .Values.ingress.useDefaultClass)
  (eq $staticIngressClassAnnotation "")
-}}
{{- fail "strong production routing requires ingress.className, ingress.useDefaultClass=true, or kubernetes.io/ingress.class annotation" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.storageClassName" -}}
{{- if .Values.global.storageClass }}
storageClassName: {{ .Values.global.storageClass | quote }}
{{- end }}
{{- end -}}

{{- define "aileron.workspaceRuntimeNamespace" -}}
{{- $namespace := required "kubernetes.workspaceRuntimeNamespace is required" .Values.kubernetes.workspaceRuntimeNamespace -}}
{{- if ne .Release.Namespace $namespace -}}
{{- fail (printf "Helm release namespace %q must equal kubernetes.workspaceRuntimeNamespace %q" .Release.Namespace $namespace) -}}
{{- end -}}
{{- $namespace -}}
{{- end -}}

{{- define "aileron.platformPublicOrigin" -}}
{{- $origin := required "platformPublicOrigin is required" .Values.platformPublicOrigin | trim -}}
{{- if not (regexMatch `^https?://(?:localhost|[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)(?::[1-9][0-9]{0,4})?$` $origin) -}}
{{- fail "platformPublicOrigin must be an exact http(s) scheme, host, and optional port without path or trailing slash" -}}
{{- end -}}
{{- $hostPort := regexReplaceAll `^https?://` $origin "" -}}
{{- if contains ":" $hostPort -}}
{{- $port := int (last (splitList ":" $hostPort)) -}}
{{- if gt $port 65535 -}}
{{- fail "platformPublicOrigin port must be between 1 and 65535" -}}
{{- end -}}
{{- end -}}
{{- $origin -}}
{{- end -}}

{{- define "aileron.platformPublicScheme" -}}
{{- regexFind `^https?` (include "aileron.platformPublicOrigin" .) -}}
{{- end -}}

{{- define "aileron.platformPublicHost" -}}
{{- regexReplaceAll `^https?://` (include "aileron.platformPublicOrigin" .) "" -}}
{{- end -}}

{{- define "aileron.platformPublicHostname" -}}
{{- regexReplaceAll `:[0-9]+$` (include "aileron.platformPublicHost" .) "" -}}
{{- end -}}

{{- define "aileron.validateIngressTLS" -}}
{{- $tlsMode := .Values.ingress.tlsMode -}}
{{- $tlsSecretName := .Values.ingress.tlsSecretName | default "" | trim -}}
{{- $ingressEnabled := .Values.ingress.enabled -}}
{{- if eq $tlsMode "disabled" -}}
{{- if ne $tlsSecretName "" -}}
{{- fail "ingress.tlsSecretName must be empty when ingress.tlsMode=disabled" -}}
{{- end -}}
{{- if and $ingressEnabled (eq (include "aileron.platformPublicScheme" .) "https") -}}
{{- fail "HTTPS public routing requires ingress.tlsMode=kubernetesSecret or controllerManaged" -}}
{{- end -}}
{{- else if eq $tlsMode "kubernetesSecret" -}}
{{- if ne (include "aileron.platformPublicScheme" .) "https" -}}
{{- fail "ingress.tlsMode=kubernetesSecret requires platformPublicOrigin with https" -}}
{{- end -}}
{{- if eq $tlsSecretName "" -}}
{{- fail "ingress.tlsSecretName is required when ingress.tlsMode=kubernetesSecret" -}}
{{- end -}}
{{- else if eq $tlsMode "controllerManaged" -}}
{{- if ne (include "aileron.platformPublicScheme" .) "https" -}}
{{- fail "ingress.tlsMode=controllerManaged requires platformPublicOrigin with https" -}}
{{- end -}}
{{- if ne $tlsSecretName "" -}}
{{- fail "ingress.tlsSecretName must be empty when ingress.tlsMode=controllerManaged" -}}
{{- end -}}
{{- else -}}
{{- fail "ingress.tlsMode must be disabled, kubernetesSecret, or controllerManaged" -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateIngressClassSelection" -}}
{{- $ingressClassName := .Values.ingress.className | default "" | trim -}}
{{- $staticIngressClassAnnotation := index (.Values.ingress.annotations | default dict) "kubernetes.io/ingress.class" | default "" | trim -}}
{{- if and .Values.ingress.useDefaultClass (ne $ingressClassName "") -}}
{{- fail "ingress.useDefaultClass and ingress.className are mutually exclusive" -}}
{{- end -}}
{{- if and .Values.ingress.useDefaultClass (ne $staticIngressClassAnnotation "") -}}
{{- fail "ingress.useDefaultClass and kubernetes.io/ingress.class annotations are mutually exclusive" -}}
{{- end -}}
{{- if and (ne $ingressClassName "") (ne $staticIngressClassAnnotation "") (ne $ingressClassName $staticIngressClassAnnotation) -}}
{{- fail "ingress.className and the fixed kubernetes.io/ingress.class annotation must match when both are configured" -}}
{{- end -}}
{{- end -}}

{{- define "aileron.turnSecretName" -}}
{{- required "turn.existingSecretName is required when turn.enabled=true" .Values.turn.existingSecretName -}}
{{- end -}}

{{- define "aileron.coturnFrontendHost" -}}
{{- .Values.coturn.frontendHost | lower -}}
{{- end -}}

{{- define "aileron.turnCredentialsChecksum" -}}
{{- printf "%s:%s:%s:%v:%s" (include "aileron.turnSecretName" .) .Values.turn.backendIceServersKey .Values.turn.frontendIceServersKey .Values.turn.credentialRevision (include "aileron.turnReachabilityProfileJSON" .) | sha256sum -}}
{{- end -}}

{{- define "aileron.turnReachabilityProfileJSON" -}}
{{- $profile := deepCopy .Values.turn.profile -}}
{{- $_ := set $profile.credentialIssuer "secretRef" (include "aileron.turnSecretName" .) -}}
{{- toJson $profile -}}
{{- end -}}

{{- define "aileron.validateTurnConfiguration" -}}
{{- if .Values.turn.enabled -}}
{{- $turnSecretName := include "aileron.turnSecretName" . -}}
{{- $turnBackendKey := required "turn.backendIceServersKey is required when turn.enabled=true" .Values.turn.backendIceServersKey -}}
{{- $turnFrontendKey := required "turn.frontendIceServersKey is required when turn.enabled=true" .Values.turn.frontendIceServersKey -}}
{{- if or (not (regexMatch `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` $turnSecretName)) (gt (len $turnSecretName) 253) -}}
{{- fail "turn.existingSecretName must be a valid Kubernetes Secret name" -}}
{{- end -}}
{{- range $name, $key := dict "turn.backendIceServersKey" $turnBackendKey "turn.frontendIceServersKey" $turnFrontendKey -}}
{{- if or (gt (len $key) 253) (not (regexMatch `^[-._a-zA-Z0-9]+$` $key)) -}}
{{- fail (printf "%s must be a valid Secret data key" $name) -}}
{{- end -}}
{{- end -}}
{{- $requiredVantages := .Values.turn.profile.evidence.requiredFrontendVantages -}}
{{- if and (gt (len $requiredVantages) 0) (not .Values.connectivityEvidenceGateway.enabled) -}}
{{- fail "connectivityEvidenceGateway.enabled must be true when required frontend vantages are configured" -}}
{{- end -}}
{{- if .Values.connectivityEvidenceGateway.enabled -}}
{{- $installationID := required "connectivityEvidenceGateway.installationId is required" .Values.connectivityEvidenceGateway.installationId -}}
{{- if eq ($installationID | trim) "" -}}
{{- fail "connectivityEvidenceGateway.installationId must not be empty" -}}
{{- end -}}
{{- range $vantage := $requiredVantages -}}
{{- if not (regexMatch `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` $vantage) -}}
{{- fail "TURN required frontend vantage IDs must be valid DNS labels" -}}
{{- end -}}
{{- end -}}
{{- if and .Values.connectivityEvidenceGateway.hostAgent.enabled (not (has .Values.connectivityEvidenceGateway.hostAgent.vantageId $requiredVantages)) -}}
{{- fail "connectivityEvidenceGateway.hostAgent.vantageId must be a required frontend vantage" -}}
{{- end -}}
{{- $agentCASecretName := .Values.connectivityEvidenceGateway.hostAgent.tls.caSecretName | default "" | trim -}}
{{- if and (ne $agentCASecretName "") (or (gt (len $agentCASecretName) 253) (not (regexMatch `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` $agentCASecretName))) -}}
{{- fail "connectivityEvidenceGateway.hostAgent.tls.caSecretName must be a valid Kubernetes Secret name" -}}
{{- end -}}
{{- $agentCASecretKey := .Values.connectivityEvidenceGateway.hostAgent.tls.caSecretKey | default "" | trim -}}
{{- if and (ne $agentCASecretName "") (or (eq $agentCASecretKey "") (gt (len $agentCASecretKey) 253) (not (regexMatch `^[-._a-zA-Z0-9]+$` $agentCASecretKey))) -}}
{{- fail "connectivityEvidenceGateway.hostAgent.tls.caSecretKey must be a valid Secret data key when caSecretName is configured" -}}
{{- end -}}
{{- end -}}
{{- $relayMinPort := int .Values.turn.profile.backend.relayPortRange.min -}}
{{- $relayMaxPort := int .Values.turn.profile.backend.relayPortRange.max -}}
{{- if gt $relayMinPort $relayMaxPort -}}
{{- fail "turn.profile.backend.relayPortRange.min must not exceed max" -}}
{{- end -}}
{{- if and .Values.coturn.enabled (and (ge (int .Values.coturn.listenerPort) $relayMinPort) (le (int .Values.coturn.listenerPort) $relayMaxPort)) -}}
{{- fail "coturn.listenerPort must be outside the TURN relay port range" -}}
{{- end -}}
{{- if .Values.coturn.enabled -}}
{{- if ne .Values.turn.profile.credentialIssuer.kind "turnRest" -}}
{{- fail "coturn.enabled requires turn.profile.credentialIssuer.kind=turnRest" -}}
{{- end -}}
{{- $coturnNamespace := required "coturn.namespace is required when coturn.enabled=true" .Values.coturn.namespace -}}
{{- $coturnHost := include "aileron.coturnFrontendHost" . -}}
{{- if not (regexMatch `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$` $coturnHost) -}}
{{- fail "coturn.frontendHost must resolve to a valid DNS hostname" -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateProductionStorage" -}}
{{- if .Values.security.requireStrongSecrets -}}
{{- if ne (.Values.global.storageClass | default "" | trim) "" -}}
{{- fail "global.storageClass must be empty when security.requireStrongSecrets=true" -}}
{{- end -}}
{{- range $name, $value := dict
  "kubernetes.workspaceData.storageClassName" .Values.kubernetes.workspaceData.storageClassName
  "kubernetes.runtimeHome.storageClassName" .Values.kubernetes.runtimeHome.storageClassName
  "kubernetes.knowledgeBases.storageClassName" .Values.kubernetes.knowledgeBases.storageClassName
  "kubernetes.managerState.storageClassName" .Values.kubernetes.managerState.storageClassName
}}
{{- if eq ($value | default "" | trim) "" -}}
{{- fail (printf "%s is required when security.requireStrongSecrets=true" $name) -}}
{{- end -}}
{{- end -}}
{{- if and .Values.postgres.enabled .Values.postgres.persistence.enabled (eq (.Values.postgres.persistence.storageClassName | default "" | trim) "") -}}
{{- fail "postgres.persistence.storageClassName is required when security.requireStrongSecrets=true" -}}
{{- end -}}
{{- if and .Values.redis.enabled .Values.redis.persistence.enabled (eq (.Values.redis.persistence.storageClassName | default "" | trim) "") -}}
{{- fail "redis.persistence.storageClassName is required when security.requireStrongSecrets=true" -}}
{{- end -}}
{{- if and (has "ReadWriteOnce" .Values.kubernetes.managerState.accessModes) (ne (int .Values.workspaceManager.replicaCount) 1) -}}
{{- fail "workspaceManager.replicaCount must be 1 when manager state uses ReadWriteOnce" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateAdminBootstrap" -}}
{{- if .Values.bootstrap.admin.enabled -}}
{{- if not .Values.workspaceManager.enabled -}}
{{- fail "workspaceManager.enabled must be true when administrator bootstrap is enabled" -}}
{{- end -}}
{{- $subject := trim (required "bootstrap.admin.subject is required when administrator bootstrap is enabled" .Values.bootstrap.admin.subject) -}}
{{- $username := trim (required "bootstrap.admin.username is required when administrator bootstrap is enabled" .Values.bootstrap.admin.username) -}}
{{- $email := trim (required "bootstrap.admin.email is required when administrator bootstrap is enabled" .Values.bootstrap.admin.email) -}}
{{- if or (eq $subject "") (gt (len $subject) 255) -}}
{{- fail "bootstrap.admin.subject must contain between 1 and 255 non-whitespace characters" -}}
{{- end -}}
{{- if or (eq $username "") (gt (len $username) 255) -}}
{{- fail "bootstrap.admin.username must contain between 1 and 255 non-whitespace characters" -}}
{{- end -}}
{{- if or (eq $email "") (gt (len $email) 255) (not (contains "@" $email)) -}}
{{- fail "bootstrap.admin.email must be a valid email address with at most 255 characters" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aileron.validateOIDCCA" -}}
{{- $clientSecretName := required "oidc.clientSecretName is required" .Values.oidc.clientSecretName | trim -}}
{{- $clientSecretKey := required "oidc.clientSecretKey is required" .Values.oidc.clientSecretKey | trim -}}
{{- if not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$" $clientSecretName) -}}
{{- fail "oidc.clientSecretName must be a valid existing Secret name" -}}
{{- end -}}

{{- if not (regexMatch "^[A-Za-z0-9][A-Za-z0-9._-]*$" $clientSecretKey) -}}
{{- fail "oidc.clientSecretKey must be a valid Secret data key" -}}
{{- end -}}
{{- $secretName := .Values.oidc.caSecretName | default "" | trim -}}
{{- $secretKey := .Values.oidc.caSecretKey | default "ca.crt" | trim -}}
{{- if and (ne $secretName "") (not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$" $secretName)) -}}
{{- fail "oidc.caSecretName must be a valid Kubernetes Secret name" -}}
{{- end -}}
{{- if not (regexMatch "^[A-Za-z0-9][A-Za-z0-9._-]*$" $secretKey) -}}
{{- fail "oidc.caSecretKey must be a valid Secret data key" -}}
{{- end -}}
{{- end -}}
