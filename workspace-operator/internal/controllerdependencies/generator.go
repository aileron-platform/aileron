package controllerdependencies

import (
	"bytes"
	"fmt"
	"go/format"
	"strconv"
)

func GenerateArtifacts(registry Registry) ([]byte, []byte, error) {
	if err := ValidateRegistry(registry); err != nil {
		return nil, nil, err
	}
	goArtifact, err := generateGoArtifact(registry)
	if err != nil {
		return nil, nil, err
	}
	return goArtifact, generateHelmArtifact(registry), nil
}

func generateGoArtifact(registry Registry) ([]byte, error) {
	var output bytes.Buffer
	output.WriteString("// Code generated from contracts/controller-dependencies/registry.json. DO NOT EDIT.\n\n")
	output.WriteString("package controller\n\n")
	output.WriteString("import controllerdependencies \"workspace-operator/internal/controllerdependencies\"\n\n")
	output.WriteString("var canonicalControllerDependencies = []controllerdependencies.Dependency{\n")
	for _, dependency := range registry.Dependencies {
		if dependency.OwnerController != "workspace-controller" {
			continue
		}
		fmt.Fprintf(&output, "{Identity: %s, OwnerController: %s, APIGroup: %s, Resource: %s, Scope: controllerdependencies.Scope(%s), TypedObject: %s, AccessMode: controllerdependencies.AccessMode(%s), Verbs: []string{%s}, EnabledCondition: controllerdependencies.EnabledCondition(%s)",
			strconv.Quote(dependency.Identity), strconv.Quote(dependency.OwnerController), strconv.Quote(dependency.APIGroup),
			strconv.Quote(dependency.Resource), strconv.Quote(string(dependency.Scope)), strconv.Quote(dependency.TypedObject),
			strconv.Quote(string(dependency.AccessMode)), quotedStrings(dependency.Verbs), strconv.Quote(string(dependency.EnabledCondition)))
		if dependency.EventMapperIdentity != "" {
			fmt.Fprintf(&output, ", EventMapperIdentity: %s", strconv.Quote(dependency.EventMapperIdentity))
		}
		if dependency.ProbeIdentity != "" {
			fmt.Fprintf(&output, ", ProbeIdentity: %s", strconv.Quote(dependency.ProbeIdentity))
		}
		output.WriteString("},\n")
	}
	output.WriteString("}\n")
	formatted, err := format.Source(output.Bytes())
	if err != nil {
		return nil, fmt.Errorf("format generated Go dependency registry: %w", err)
	}
	return formatted, nil
}

func quotedStrings(values []string) string {
	var output bytes.Buffer
	for index, value := range values {
		if index > 0 {
			output.WriteString(", ")
		}
		output.WriteString(strconv.Quote(value))
	}
	return output.String()
}

func generateHelmArtifact(registry Registry) []byte {
	var output bytes.Buffer
	output.WriteString("{{/* Code generated from contracts/controller-dependencies/registry.json. DO NOT EDIT. */}}\n")
	writeHelmRules(&output, "aileron.workspaceOperator.namespacedDependencyRules", registry.Dependencies, "workspace-controller", ScopeNamespaced)
	writeHelmRules(&output, "aileron.workspaceOperator.clusterDependencyRules", registry.Dependencies, "workspace-controller", ScopeCluster)
	writeHelmRules(&output, "aileron.workspaceFirewallAttestor.namespacedDependencyRules", registry.Dependencies, "workspace-firewall-attestor", ScopeNamespaced)
	output.WriteString("{{- define \"aileron.workspaceOperator.clusterDependenciesEnabled\" -}}\n")
	output.WriteString("{{- if or (ne (trim .Values.kubernetes.workspaceData.storageClassName) \"\") (ne (trim .Values.kubernetes.runtimeHome.storageClassName) \"\") -}}true{{- else -}}false{{- end -}}\n")
	output.WriteString("{{- end }}\n")
	return output.Bytes()
}

func writeHelmRules(output *bytes.Buffer, name string, dependencies []Dependency, ownerController string, scope Scope) {
	fmt.Fprintf(output, "{{- define %q -}}\n", name)
	for _, dependency := range dependencies {
		if dependency.Scope != scope || dependency.OwnerController != ownerController {
			continue
		}
		condition := helmCondition(dependency.EnabledCondition)
		if condition != "" {
			fmt.Fprintf(output, "{{- if %s }}\n", condition)
		}
		fmt.Fprintf(output, "- apiGroups: [%s]\n", strconv.Quote(dependency.APIGroup))
		fmt.Fprintf(output, "  resources: [%s]\n", strconv.Quote(dependency.Resource))
		fmt.Fprintf(output, "  verbs: [%s]\n", quotedStrings(dependency.Verbs))
		if condition != "" {
			output.WriteString("{{- end }}\n")
		}
	}
	output.WriteString("{{- end }}\n")
}

func helmCondition(condition EnabledCondition) string {
	switch condition {
	case ConditionAlways:
		return ""
	case ConditionCiliumEnabled:
		return ".Values.cilium.enabled"
	case ConditionStorageClassesConfigured:
		return `or (ne (trim .Values.kubernetes.workspaceData.storageClassName) "") (ne (trim .Values.kubernetes.runtimeHome.storageClassName) "")`
	default:
		return "false"
	}
}
