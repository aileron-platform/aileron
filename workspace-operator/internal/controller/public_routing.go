package controller

import (
	"fmt"
	"os"
	"strings"
)

type PublicRoutingConfig struct {
	Scheme               string
	BaseDomain           string
	IngressClassName     string
	FrontendHost         string
	WorkspaceManagerHost string
	KeycloakHost         string
	RuntimeHostPattern   string
	BrowserHostPattern   string
	CanvasHostPattern    string
}

func LoadPublicRoutingConfigFromEnv() (PublicRoutingConfig, error) {
	config := PublicRoutingConfig{
		Scheme:               strings.TrimSpace(os.Getenv("PUBLIC_SCHEME")),
		BaseDomain:           strings.TrimSpace(os.Getenv("PUBLIC_BASE_DOMAIN")),
		IngressClassName:     strings.TrimSpace(os.Getenv("PUBLIC_INGRESS_CLASS_NAME")),
		FrontendHost:         strings.TrimSpace(os.Getenv("PUBLIC_FRONTEND_HOST")),
		WorkspaceManagerHost: strings.TrimSpace(os.Getenv("PUBLIC_WORKSPACE_MANAGER_HOST")),
		KeycloakHost:         strings.TrimSpace(os.Getenv("PUBLIC_KEYCLOAK_HOST")),
		RuntimeHostPattern:   strings.TrimSpace(os.Getenv("PUBLIC_RUNTIME_HOST_PATTERN")),
		BrowserHostPattern:   strings.TrimSpace(os.Getenv("PUBLIC_BROWSER_HOST_PATTERN")),
		CanvasHostPattern:    strings.TrimSpace(os.Getenv("PUBLIC_CANVAS_HOST_PATTERN")),
	}

	if config.Scheme == "" {
		config.Scheme = "http"
	}
	if config.BaseDomain == "" {
		config.BaseDomain = "aileron.localhost"
	}
	if config.FrontendHost == "" {
		config.FrontendHost = "aileron.{baseDomain}"
	}
	if config.WorkspaceManagerHost == "" {
		config.WorkspaceManagerHost = "workspace-manager.{baseDomain}"
	}
	if config.KeycloakHost == "" {
		config.KeycloakHost = "keycloak.{baseDomain}"
	}
	if config.RuntimeHostPattern == "" {
		config.RuntimeHostPattern = "workspace-runtime-{workspaceId}.{baseDomain}"
	}
	if config.BrowserHostPattern == "" {
		config.BrowserHostPattern = "workspace-browser-{workspaceId}.{baseDomain}"
	}
	if config.CanvasHostPattern == "" {
		config.CanvasHostPattern = "workspace-canvas-{workspaceId}.{baseDomain}"
	}

	if err := config.Validate(); err != nil {
		return PublicRoutingConfig{}, err
	}
	return config, nil
}

func (c PublicRoutingConfig) Validate() error {
	if c.Scheme != "http" && c.Scheme != "https" {
		return fmt.Errorf("PUBLIC_SCHEME must be either 'http' or 'https'")
	}
	if strings.TrimSpace(c.BaseDomain) == "" {
		return fmt.Errorf("PUBLIC_BASE_DOMAIN must not be empty")
	}

	for _, template := range []string{c.RuntimeHostPattern, c.BrowserHostPattern, c.CanvasHostPattern} {
		if !strings.Contains(template, "{workspaceId}") {
			return fmt.Errorf("workspace host pattern must include '{workspaceId}'")
		}
	}

	if _, err := c.ResolveHost(c.FrontendHost, ""); err != nil {
		return err
	}
	if _, err := c.ResolveHost(c.WorkspaceManagerHost, ""); err != nil {
		return err
	}
	if _, err := c.ResolveHost(c.KeycloakHost, ""); err != nil {
		return err
	}
	if _, err := c.ResolveHost(c.RuntimeHostPattern, "sample"); err != nil {
		return err
	}
	if _, err := c.ResolveHost(c.BrowserHostPattern, "sample"); err != nil {
		return err
	}
	if _, err := c.ResolveHost(c.CanvasHostPattern, "sample"); err != nil {
		return err
	}

	return nil
}

func (c PublicRoutingConfig) ResolveHost(template string, workspaceID string) (string, error) {
	host := strings.ReplaceAll(template, "{baseDomain}", c.BaseDomain)
	if strings.Contains(host, "{workspaceId}") {
		if strings.TrimSpace(workspaceID) == "" {
			return "", fmt.Errorf("workspaceID is required to resolve workspace host pattern")
		}
		host = strings.ReplaceAll(host, "{workspaceId}", workspaceID)
	}
	if strings.Contains(host, "{") || strings.Contains(host, "}") {
		return "", fmt.Errorf("unresolved public host template: %s", template)
	}
	if strings.TrimSpace(host) == "" {
		return "", fmt.Errorf("resolved public host must not be empty")
	}
	return host, nil
}

func (c PublicRoutingConfig) BuildURL(template string, workspaceID string) (string, error) {
	host, err := c.ResolveHost(template, workspaceID)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s://%s", c.Scheme, host), nil
}
