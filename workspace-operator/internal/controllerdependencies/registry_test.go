package controllerdependencies

import (
	"path/filepath"
	"runtime"
	"testing"
)

func TestLoadRegistryAcceptsCanonicalControllerDependencies(t *testing.T) {
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test path")
	}
	contractPath := filepath.Clean(filepath.Join(
		filepath.Dir(filename),
		"..", "..", "..", "contracts", "controller-dependencies", "registry.json",
	))

	registry, err := LoadRegistry(contractPath)
	if err != nil {
		t.Fatalf("load canonical registry: %v", err)
	}
	if registry.ContractVersion != "1" {
		t.Fatalf("contractVersion = %q, want 1", registry.ContractVersion)
	}
	if len(registry.Dependencies) != 15 {
		t.Fatalf("dependency count = %d, want 15", len(registry.Dependencies))
	}
	if registry.Dependencies[0].Identity != "cilium.endpoints" {
		t.Fatalf("first dependency = %q, want cilium.endpoints", registry.Dependencies[0].Identity)
	}
	attestorDependencies := 0
	for _, dependency := range registry.Dependencies {
		if dependency.OwnerController == "workspace-firewall-attestor" {
			attestorDependencies++
			if dependency.EnabledCondition != ConditionCiliumEnabled {
				t.Fatalf("attestor dependency %q is not gated by Cilium", dependency.Identity)
			}
		}
	}
	if attestorDependencies != 3 {
		t.Fatalf("firewall attestor dependency count = %d, want 3", attestorDependencies)
	}
}

func TestValidateRegistryRejectsModeWithoutMapperOrProbe(t *testing.T) {
	registry := Registry{
		ContractVersion: "1",
		Dependencies: []Dependency{{
			Identity:         "pods.managed",
			OwnerController:  "workspace-controller",
			APIGroup:         "",
			Resource:         "pods",
			Scope:            ScopeNamespaced,
			TypedObject:      "corev1.Pod",
			AccessMode:       AccessModeWatched,
			Verbs:            []string{"get", "list", "watch"},
			EnabledCondition: ConditionAlways,
		}},
	}

	if err := ValidateRegistry(registry); err == nil {
		t.Fatal("watched dependency without event mapper was accepted")
	}
	registry.Dependencies[0].AccessMode = AccessModeDirectLookup
	if err := ValidateRegistry(registry); err == nil {
		t.Fatal("direct lookup dependency without probe identity was accepted")
	}
}
