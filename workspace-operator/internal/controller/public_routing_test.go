package controller

import "testing"

func TestPublicRoutingConfigValidate(t *testing.T) {
	config := PublicRoutingConfig{
		Scheme:               "https",
		BaseDomain:           "example.com",
		FrontendHost:         "aileron.{baseDomain}",
		WorkspaceManagerHost: "workspace-manager.{baseDomain}",
		KeycloakHost:         "keycloak.{baseDomain}",
		RuntimeHostPattern:   "workspace-runtime-{workspaceId}.{baseDomain}",
		BrowserHostPattern:   "workspace-browser-{workspaceId}.{baseDomain}",
		CanvasHostPattern:    "workspace-canvas-{workspaceId}.{baseDomain}",
	}

	if err := config.Validate(); err != nil {
		t.Fatalf("Validate() returned error: %v", err)
	}
}

func TestPublicRoutingConfigValidateRejectsMissingWorkspaceIDPlaceholder(t *testing.T) {
	config := PublicRoutingConfig{
		Scheme:               "https",
		BaseDomain:           "example.com",
		FrontendHost:         "aileron.{baseDomain}",
		WorkspaceManagerHost: "workspace-manager.{baseDomain}",
		KeycloakHost:         "keycloak.{baseDomain}",
		RuntimeHostPattern:   "workspace-runtime.example.com",
		BrowserHostPattern:   "workspace-browser-{workspaceId}.{baseDomain}",
		CanvasHostPattern:    "workspace-canvas-{workspaceId}.{baseDomain}",
	}

	if err := config.Validate(); err == nil {
		t.Fatal("Validate() expected error for missing {workspaceId} placeholder")
	}
}

func TestPublicRoutingConfigResolveHost(t *testing.T) {
	config := PublicRoutingConfig{
		Scheme:               "https",
		BaseDomain:           "example.com",
		FrontendHost:         "aileron.{baseDomain}",
		WorkspaceManagerHost: "workspace-manager.{baseDomain}",
		KeycloakHost:         "keycloak.{baseDomain}",
		RuntimeHostPattern:   "workspace-runtime-{workspaceId}.{baseDomain}",
		BrowserHostPattern:   "workspace-browser-{workspaceId}.{baseDomain}",
		CanvasHostPattern:    "workspace-canvas-{workspaceId}.{baseDomain}",
	}

	host, err := config.ResolveHost(config.RuntimeHostPattern, "ws-123")
	if err != nil {
		t.Fatalf("ResolveHost() returned error: %v", err)
	}
	if host != "workspace-runtime-ws-123.example.com" {
		t.Fatalf("ResolveHost() = %s, want workspace-runtime-ws-123.example.com", host)
	}
}

func TestPublicRoutingConfigResolveHostRequiresWorkspaceID(t *testing.T) {
	config := PublicRoutingConfig{
		Scheme:               "https",
		BaseDomain:           "example.com",
		FrontendHost:         "aileron.{baseDomain}",
		WorkspaceManagerHost: "workspace-manager.{baseDomain}",
		KeycloakHost:         "keycloak.{baseDomain}",
		RuntimeHostPattern:   "workspace-runtime-{workspaceId}.{baseDomain}",
		BrowserHostPattern:   "workspace-browser-{workspaceId}.{baseDomain}",
		CanvasHostPattern:    "workspace-canvas-{workspaceId}.{baseDomain}",
	}

	if _, err := config.ResolveHost(config.RuntimeHostPattern, ""); err == nil {
		t.Fatal("ResolveHost() expected error when workspaceID is empty")
	}
}
