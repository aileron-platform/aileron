// Code generated from contracts/workspace-service-identities/registry.json. DO NOT EDIT.

package workspaceserviceidentities

type serviceDefinition struct {
	ServiceComponent string
	Port             int
}

var canonicalWorkspaceServiceDefinitions = map[string]serviceDefinition{
	"browser":  {ServiceComponent: "workspace-browser", Port: 6080},
	"canvas":   {ServiceComponent: "workspace-canvas", Port: 3003},
	"runtime":  {ServiceComponent: "workspace-runtime", Port: 3002},
	"terminal": {ServiceComponent: "workspace-runtime", Port: 3004},
}
