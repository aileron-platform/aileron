package workspaceserviceidentities

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/format"
	"io"
	"os"
	"sort"
	"strconv"
)

type Registry struct {
	ContractVersion string              `json:"contractVersion"`
	Identities      []ServiceDefinition `json:"identities"`
	Vectors         []ContractVector    `json:"vectors"`
}

type ContractVector struct {
	WorkspaceID string                       `json:"workspaceId"`
	Namespace   string                       `json:"namespace"`
	Expected    map[string]WorkspaceIdentity `json:"expected"`
}

type ServiceDefinition struct {
	Identity         string `json:"identity"`
	ServiceComponent string `json:"serviceComponent"`
	Port             int    `json:"port"`
}

func LoadRegistry(path string) (Registry, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return Registry{}, fmt.Errorf("read workspace service identity registry: %w", err)
	}
	var registry Registry
	decoder := json.NewDecoder(bytes.NewReader(content))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&registry); err != nil {
		return Registry{}, fmt.Errorf("decode workspace service identity registry: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return Registry{}, fmt.Errorf("decode workspace service identity registry: trailing JSON document")
	}
	if err := ValidateRegistry(registry); err != nil {
		return Registry{}, err
	}
	return registry, nil
}

func ValidateRegistry(registry Registry) error {
	if registry.ContractVersion != "1" || len(registry.Identities) == 0 {
		return fmt.Errorf("workspace service identity registry must use contractVersion 1 and contain identities")
	}
	seen := make(map[string]struct{}, len(registry.Identities))
	for index, definition := range registry.Identities {
		if definition.Identity == "" || definition.ServiceComponent == "" || definition.Port < 1 || definition.Port > 65535 {
			return fmt.Errorf("workspace service identity %d is invalid", index)
		}
		if _, duplicate := seen[definition.Identity]; duplicate {
			return fmt.Errorf("duplicate workspace service identity %q", definition.Identity)
		}
		seen[definition.Identity] = struct{}{}
	}
	if !sort.SliceIsSorted(registry.Identities, func(i, j int) bool {
		return registry.Identities[i].Identity < registry.Identities[j].Identity
	}) {
		return fmt.Errorf("workspace service identities must be sorted")
	}
	for _, required := range []string{"browser", "canvas", "runtime", "terminal"} {
		if _, present := seen[required]; !present {
			return fmt.Errorf("workspace service identity %q is required", required)
		}
	}
	if len(seen) != 4 {
		return fmt.Errorf("workspace service identity registry contains unknown identities")
	}
	if len(registry.Vectors) == 0 {
		return fmt.Errorf("workspace service identity registry must contain contract vectors")
	}
	definitions := make(map[string]ServiceDefinition, len(registry.Identities))
	for _, definition := range registry.Identities {
		definitions[definition.Identity] = definition
	}
	for index, vector := range registry.Vectors {
		if vector.WorkspaceID == "" || vector.Namespace == "" || len(vector.Expected) != len(definitions) {
			return fmt.Errorf("workspace service identity vector %d is incomplete", index)
		}
		for identity, definition := range definitions {
			expected, present := vector.Expected[identity]
			if !present {
				return fmt.Errorf("workspace service identity vector %d is missing %q", index, identity)
			}
			serviceName := fmt.Sprintf("%s-%s", definition.ServiceComponent, vector.WorkspaceID)
			fqdn := fmt.Sprintf("%s.%s.svc.cluster.local", serviceName, vector.Namespace)
			canonical := WorkspaceIdentity{
				ServiceName: serviceName,
				FQDN:        fqdn,
				Port:        definition.Port,
				URL:         fmt.Sprintf("http://%s:%d", fqdn, definition.Port),
			}
			if expected != canonical {
				return fmt.Errorf("workspace service identity vector %d has invalid %q projection", index, identity)
			}
		}
	}
	return nil
}

func GenerateArtifacts(registry Registry) ([]byte, []byte, error) {
	if err := ValidateRegistry(registry); err != nil {
		return nil, nil, err
	}
	var goOutput bytes.Buffer
	goOutput.WriteString("// Code generated from contracts/workspace-service-identities/registry.json. DO NOT EDIT.\n\n")
	goOutput.WriteString("package workspaceserviceidentities\n\n")
	goOutput.WriteString("type serviceDefinition struct {\nServiceComponent string\nPort int\n}\n\n")
	goOutput.WriteString("var canonicalWorkspaceServiceDefinitions = map[string]serviceDefinition{\n")
	for _, definition := range registry.Identities {
		fmt.Fprintf(&goOutput, "%s: {ServiceComponent: %s, Port: %d},\n", strconv.Quote(definition.Identity), strconv.Quote(definition.ServiceComponent), definition.Port)
	}
	goOutput.WriteString("}\n")
	formattedGo, err := format.Source(goOutput.Bytes())
	if err != nil {
		return nil, nil, fmt.Errorf("format Go workspace service identities: %w", err)
	}

	var pythonOutput bytes.Buffer
	pythonOutput.WriteString("\"\"\"Generated from contracts/workspace-service-identities/registry.json.\"\"\"\n\n")
	pythonOutput.WriteString("CANONICAL_WORKSPACE_SERVICE_DEFINITIONS: dict[str, tuple[str, int]] = {\n")
	for _, definition := range registry.Identities {
		fmt.Fprintf(&pythonOutput, "    %s: (%s, %d),\n", strconv.Quote(definition.Identity), strconv.Quote(definition.ServiceComponent), definition.Port)
	}
	pythonOutput.WriteString("}\n")
	return formattedGo, pythonOutput.Bytes(), nil
}
