package controllerdependencies

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

type Scope string

const (
	ScopeNamespaced Scope = "namespaced"
	ScopeCluster    Scope = "cluster"
)

type AccessMode string

const (
	AccessModeWatched      AccessMode = "watched"
	AccessModeCached       AccessMode = "cached"
	AccessModeDirectLookup AccessMode = "directLookup"
)

type EnabledCondition string

const (
	ConditionAlways                   EnabledCondition = "always"
	ConditionCiliumEnabled            EnabledCondition = "ciliumEnabled"
	ConditionStorageClassesConfigured EnabledCondition = "storageClassesConfigured"
)

type Registry struct {
	ContractVersion string       `json:"contractVersion"`
	Dependencies    []Dependency `json:"dependencies"`
}

type Dependency struct {
	Identity            string           `json:"identity"`
	OwnerController     string           `json:"ownerController"`
	APIGroup            string           `json:"apiGroup"`
	Resource            string           `json:"resource"`
	Scope               Scope            `json:"scope"`
	TypedObject         string           `json:"typedObject"`
	AccessMode          AccessMode       `json:"accessMode"`
	Verbs               []string         `json:"verbs"`
	EnabledCondition    EnabledCondition `json:"enabledCondition"`
	EventMapperIdentity string           `json:"eventMapperIdentity,omitempty"`
	ProbeIdentity       string           `json:"probeIdentity,omitempty"`
}

func LoadRegistry(path string) (Registry, error) {
	file, err := os.Open(path)
	if err != nil {
		return Registry{}, fmt.Errorf("open controller dependency registry: %w", err)
	}
	defer file.Close()

	decoder := json.NewDecoder(file)
	decoder.DisallowUnknownFields()
	var registry Registry
	if err := decoder.Decode(&registry); err != nil {
		return Registry{}, fmt.Errorf("decode controller dependency registry: %w", err)
	}
	if err := ValidateRegistry(registry); err != nil {
		return Registry{}, err
	}
	return registry, nil
}

func ValidateRegistry(registry Registry) error {
	if registry.ContractVersion != "1" {
		return fmt.Errorf("unsupported controller dependency contractVersion %q", registry.ContractVersion)
	}
	if len(registry.Dependencies) == 0 {
		return fmt.Errorf("controller dependency registry must not be empty")
	}
	seen := make(map[string]struct{}, len(registry.Dependencies))
	previousIdentity := ""
	for index, dependency := range registry.Dependencies {
		if err := validateDependency(dependency); err != nil {
			return fmt.Errorf("dependency %d: %w", index, err)
		}
		if _, exists := seen[dependency.Identity]; exists {
			return fmt.Errorf("duplicate dependency identity %q", dependency.Identity)
		}
		seen[dependency.Identity] = struct{}{}
		if previousIdentity != "" && dependency.Identity <= previousIdentity {
			return fmt.Errorf("dependencies must be sorted by identity")
		}
		previousIdentity = dependency.Identity
	}
	return nil
}

func validateDependency(dependency Dependency) error {
	if strings.TrimSpace(dependency.Identity) == "" || strings.TrimSpace(dependency.OwnerController) == "" ||
		strings.TrimSpace(dependency.Resource) == "" || strings.TrimSpace(dependency.TypedObject) == "" {
		return fmt.Errorf("identity, ownerController, resource, and typedObject are required")
	}
	if dependency.Scope != ScopeNamespaced && dependency.Scope != ScopeCluster {
		return fmt.Errorf("dependency %q has invalid scope %q", dependency.Identity, dependency.Scope)
	}
	if dependency.AccessMode != AccessModeWatched && dependency.AccessMode != AccessModeCached &&
		dependency.AccessMode != AccessModeDirectLookup {
		return fmt.Errorf("dependency %q has invalid accessMode %q", dependency.Identity, dependency.AccessMode)
	}
	if dependency.EnabledCondition != ConditionAlways && dependency.EnabledCondition != ConditionCiliumEnabled &&
		dependency.EnabledCondition != ConditionStorageClassesConfigured {
		return fmt.Errorf("dependency %q has invalid enabledCondition %q", dependency.Identity, dependency.EnabledCondition)
	}
	if len(dependency.Verbs) == 0 || !sort.StringsAreSorted(dependency.Verbs) {
		return fmt.Errorf("dependency %q verbs must be nonempty and sorted", dependency.Identity)
	}
	if dependency.AccessMode == AccessModeWatched && strings.TrimSpace(dependency.EventMapperIdentity) == "" {
		return fmt.Errorf("watched dependency %q requires eventMapperIdentity", dependency.Identity)
	}
	if dependency.AccessMode == AccessModeDirectLookup && strings.TrimSpace(dependency.ProbeIdentity) == "" {
		return fmt.Errorf("direct lookup dependency %q requires probeIdentity", dependency.Identity)
	}
	if dependency.AccessMode != AccessModeWatched && dependency.EventMapperIdentity != "" {
		return fmt.Errorf("dependency %q must not declare eventMapperIdentity", dependency.Identity)
	}
	if dependency.AccessMode != AccessModeDirectLookup && dependency.ProbeIdentity != "" {
		return fmt.Errorf("dependency %q must not declare probeIdentity", dependency.Identity)
	}
	return nil
}
