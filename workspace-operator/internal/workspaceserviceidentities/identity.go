package workspaceserviceidentities

import "fmt"

type WorkspaceIdentity struct {
	ServiceName string `json:"serviceName"`
	FQDN        string `json:"fqdn"`
	Port        int    `json:"port"`
	URL         string `json:"url"`
}

func Resolve(identity string, workspaceID string, namespace string) (WorkspaceIdentity, error) {
	definition, ok := canonicalWorkspaceServiceDefinitions[identity]
	if !ok {
		return WorkspaceIdentity{}, fmt.Errorf("unknown workspace service identity %q", identity)
	}
	if workspaceID == "" || namespace == "" {
		return WorkspaceIdentity{}, fmt.Errorf("workspace ID and namespace are required")
	}
	serviceName := fmt.Sprintf("%s-%s", definition.ServiceComponent, workspaceID)
	fqdn := fmt.Sprintf("%s.%s.svc.cluster.local", serviceName, namespace)
	return WorkspaceIdentity{ServiceName: serviceName, FQDN: fqdn, Port: definition.Port, URL: fmt.Sprintf("http://%s:%d", fqdn, definition.Port)}, nil
}

func MustResolve(identity string, workspaceID string, namespace string) WorkspaceIdentity {
	resolved, err := Resolve(identity, workspaceID, namespace)
	if err != nil {
		panic(err)
	}
	return resolved
}
