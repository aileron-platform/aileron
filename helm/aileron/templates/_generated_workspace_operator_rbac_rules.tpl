{{/* Code generated from contracts/controller-dependencies/registry.json. DO NOT EDIT. */}}
{{- define "aileron.workspaceOperator.namespacedDependencyRules" -}}
{{- if .Values.cilium.enabled }}
- apiGroups: ["cilium.io"]
  resources: ["ciliumendpoints"]
  verbs: ["get", "list", "watch"]
{{- end }}
{{- if .Values.cilium.enabled }}
- apiGroups: ["cilium.io"]
  resources: ["ciliumnetworkpolicies"]
  verbs: ["create", "delete", "get", "list", "update", "watch"]
{{- end }}
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["create", "delete", "get", "list", "update", "watch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["create", "get", "list", "watch"]
- apiGroups: [""]
  resources: ["serviceaccounts"]
  verbs: ["create", "delete", "get", "list", "update", "watch"]
- apiGroups: [""]
  resources: ["services"]
  verbs: ["create", "delete", "get", "list", "update", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create", "delete", "get", "list", "update", "watch"]
- apiGroups: ["platform.aileron.io"]
  resources: ["workspaces/finalizers"]
  verbs: ["update"]
- apiGroups: ["platform.aileron.io"]
  resources: ["workspaces"]
  verbs: ["get", "list", "update", "watch"]
- apiGroups: ["platform.aileron.io"]
  resources: ["workspaces/status"]
  verbs: ["update"]
{{- end }}
{{- define "aileron.workspaceOperator.clusterDependencyRules" -}}
{{- if or (ne (trim .Values.kubernetes.workspaceData.storageClassName) "") (ne (trim .Values.kubernetes.runtimeHome.storageClassName) "") }}
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get"]
{{- end }}
{{- end }}
{{- define "aileron.workspaceFirewallAttestor.namespacedDependencyRules" -}}
{{- if .Values.cilium.enabled }}
- apiGroups: ["cilium.io"]
  resources: ["ciliumendpoints"]
  verbs: ["get", "list"]
{{- end }}
{{- if .Values.cilium.enabled }}
- apiGroups: ["cilium.io"]
  resources: ["ciliumnetworkpolicies"]
  verbs: ["get", "list", "patch"]
{{- end }}
{{- if .Values.cilium.enabled }}
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
{{- end }}
{{- end }}
{{- define "aileron.workspaceOperator.clusterDependenciesEnabled" -}}
{{- if or (ne (trim .Values.kubernetes.workspaceData.storageClassName) "") (ne (trim .Values.kubernetes.runtimeHome.storageClassName) "") -}}true{{- else -}}false{{- end -}}
{{- end }}
