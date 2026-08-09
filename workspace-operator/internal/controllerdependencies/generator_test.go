package controllerdependencies

import (
	"bytes"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestGenerateArtifactsSeparatesNamespacedAndClusterPermissions(t *testing.T) {
	registry := canonicalRegistryForTest(t)
	goArtifact, helmArtifact, err := GenerateArtifacts(registry)
	if err != nil {
		t.Fatalf("generate artifacts: %v", err)
	}
	if !bytes.Contains(goArtifact, []byte("Code generated from contracts/controller-dependencies/registry.json. DO NOT EDIT.")) {
		t.Fatal("Go artifact is not marked as generated")
	}
	if !bytes.Contains(helmArtifact, []byte(`define "aileron.workspaceOperator.namespacedDependencyRules"`)) {
		t.Fatal("Helm artifact does not define namespaced dependency rules")
	}
	if !bytes.Contains(helmArtifact, []byte(`define "aileron.workspaceOperator.clusterDependencyRules"`)) {
		t.Fatal("Helm artifact does not define cluster dependency rules")
	}
	if !bytes.Contains(helmArtifact, []byte(`if .Values.cilium.enabled`)) {
		t.Fatal("Helm artifact does not preserve the Cilium enabled condition")
	}
	if !bytes.Contains(helmArtifact, []byte(`define "aileron.workspaceFirewallAttestor.namespacedDependencyRules"`)) {
		t.Fatal("Helm artifact does not define firewall attestor dependency rules")
	}
	attestorArtifact := bytes.Split(helmArtifact, []byte(`define "aileron.workspaceFirewallAttestor.namespacedDependencyRules"`))[1]
	for _, resource := range []string{`resources: ["pods"]`, `resources: ["ciliumendpoints"]`, `resources: ["ciliumnetworkpolicies"]`} {
		if !bytes.Contains(attestorArtifact, []byte(resource)) {
			t.Fatalf("firewall attestor generated RBAC is missing %s", resource)
		}
	}
	if !bytes.Contains(attestorArtifact, []byte(`if .Values.cilium.enabled`)) {
		t.Fatal("firewall attestor RBAC is not gated by Cilium")
	}
	namespacedArtifact := bytes.Split(helmArtifact, []byte(`define "aileron.workspaceOperator.clusterDependencyRules"`))[0]
	if bytes.Contains(namespacedArtifact, []byte("storageclasses")) {
		t.Fatal("cluster-scoped StorageClass permission leaked into namespaced output")
	}
}

func TestGeneratedArtifactsMatchCanonicalRegistry(t *testing.T) {
	registry := canonicalRegistryForTest(t)
	wantGo, wantHelm, err := GenerateArtifacts(registry)
	if err != nil {
		t.Fatalf("generate artifacts: %v", err)
	}
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test path")
	}
	goPath := filepath.Join(filepath.Dir(filename), "..", "controller", "controller_dependencies_generated.go")
	helmPath := "/helm/aileron/templates/_generated_workspace_operator_rbac_rules.tpl"
	gotGo, err := os.ReadFile(goPath)
	if err != nil {
		t.Fatalf("read committed Go artifact: %v", err)
	}
	gotHelm, err := os.ReadFile(helmPath)
	if err != nil {
		t.Fatalf("read committed Helm artifact: %v", err)
	}
	if !bytes.Equal(gotGo, wantGo) {
		t.Fatal("committed Go dependency registry has drifted")
	}
	if !bytes.Equal(gotHelm, wantHelm) {
		t.Fatal("committed Helm RBAC helpers have drifted")
	}
}

func canonicalRegistryForTest(t *testing.T) Registry {
	t.Helper()
	registry, err := LoadRegistry("/contracts/controller-dependencies/registry.json")
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}
	return registry
}
