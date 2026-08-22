package workspaceserviceidentities

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

type contractVector struct {
	WorkspaceID string                       `json:"workspaceId"`
	Namespace   string                       `json:"namespace"`
	Expected    map[string]WorkspaceIdentity `json:"expected"`
}

func TestGeneratedWorkspaceServiceIdentityArtifactsMatchCanonicalRegistry(t *testing.T) {
	registry, err := LoadRegistry("/contracts/workspace-service-identities/registry.json")
	if err != nil {
		t.Fatalf("load canonical registry: %v", err)
	}
	wantGo, wantPython, err := GenerateArtifacts(registry)
	if err != nil {
		t.Fatalf("generate workspace service identity artifacts: %v", err)
	}
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test path")
	}
	gotGo, err := os.ReadFile(filepath.Join(filepath.Dir(filename), "registry_generated.go"))
	if err != nil {
		t.Fatalf("read committed Go artifact: %v", err)
	}
	gotPython, err := os.ReadFile("/workspace-manager/app/modules/workspace/service_identities_generated.py")
	if err != nil {
		t.Fatalf("read committed Python artifact: %v", err)
	}
	if !bytes.Equal(gotGo, wantGo) {
		t.Fatal("committed Go workspace service identities have drifted")
	}
	if !bytes.Equal(gotPython, wantPython) {
		t.Fatal("committed Python workspace service identities have drifted")
	}
}

func TestWorkspaceServiceIdentityRegistryRejectsIncompleteFiniteSet(t *testing.T) {
	registry := Registry{
		ContractVersion: "1",
		Identities: []ServiceDefinition{
			{Identity: "browser", ServiceComponent: "workspace-browser", Port: 6080},
			{Identity: "canvas", ServiceComponent: "workspace-canvas", Port: 3003},
			{Identity: "runtime", ServiceComponent: "workspace-runtime", Port: 3002},
		},
	}
	if err := ValidateRegistry(registry); err == nil {
		t.Fatal("registry without Terminal identity was accepted")
	}
}

func TestWorkspaceServiceIdentityRegistryRejectsUnknownFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "registry.json")
	content := `{"contractVersion":"1","identities":[],"vectors":[],"unexpected":true}`
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write invalid registry fixture: %v", err)
	}
	if _, err := LoadRegistry(path); err == nil {
		t.Fatal("registry with unknown field was accepted")
	}
}

type identityContract struct {
	ContractVersion string           `json:"contractVersion"`
	Vectors         []contractVector `json:"vectors"`
}

func TestWorkspaceServiceIdentityMatchesCanonicalVectors(t *testing.T) {
	content, err := os.ReadFile("/contracts/workspace-service-identities/registry.json")
	if err != nil {
		t.Fatalf("read canonical workspace service identities: %v", err)
	}
	var contract identityContract
	if err := json.Unmarshal(content, &contract); err != nil {
		t.Fatalf("decode canonical workspace service identities: %v", err)
	}
	if contract.ContractVersion != "1" {
		t.Fatalf("contractVersion = %q, want 1", contract.ContractVersion)
	}
	for _, vector := range contract.Vectors {
		for identity, expected := range vector.Expected {
			actual, err := Resolve(identity, vector.WorkspaceID, vector.Namespace)
			if err != nil {
				t.Fatalf("resolve %s: %v", identity, err)
			}
			if actual != expected {
				t.Fatalf("resolve %s = %#v, want %#v", identity, actual, expected)
			}
		}
	}
}
