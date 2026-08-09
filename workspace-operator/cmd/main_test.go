package main

import (
	"encoding/pem"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"k8s.io/apimachinery/pkg/runtime"
)

func TestExternalConnectivityAgentHTTPClientTrustsConfiguredCA(t *testing.T) {
	server := httptest.NewTLSServer(nil)
	defer server.Close()
	caPath := filepath.Join(t.TempDir(), "ca.crt")
	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: server.Certificate().Raw})
	if err := os.WriteFile(caPath, caPEM, 0o600); err != nil {
		t.Fatalf("write CA: %v", err)
	}

	client, err := newExternalConnectivityAgentHTTPClient(caPath)
	if err != nil {
		t.Fatalf("build client: %v", err)
	}
	response, err := client.Get(server.URL)
	if err != nil {
		t.Fatalf("request trusted endpoint: %v", err)
	}
	response.Body.Close()
}

func TestExternalConnectivityAgentHTTPClientRejectsInvalidCA(t *testing.T) {
	caPath := filepath.Join(t.TempDir(), "ca.crt")
	if err := os.WriteFile(caPath, []byte("not a certificate"), 0o600); err != nil {
		t.Fatalf("write invalid CA: %v", err)
	}
	if _, err := newExternalConnectivityAgentHTTPClient(caPath); err == nil {
		t.Fatal("expected invalid CA to be rejected")
	}
}

func TestLoadRequiredSecretFile(t *testing.T) {
	secretPath := filepath.Join(t.TempDir(), "token")
	if err := os.WriteFile(secretPath, []byte("  probe-token\n"), 0o600); err != nil {
		t.Fatalf("write token: %v", err)
	}
	token, err := readRequiredSecretFile("CONNECTIVITY_AGENT_TOKEN_FILE", secretPath)
	if err != nil {
		t.Fatalf("load token: %v", err)
	}
	if token != "probe-token" {
		t.Fatalf("token = %q, want probe-token", token)
	}
}

func TestLoadRequiredSecretFileRejectsMissingAndEmptyFiles(t *testing.T) {
	if _, err := readRequiredSecretFile("CONNECTIVITY_AGENT_TOKEN_FILE", ""); err == nil {
		t.Fatal("expected an unset secret file to be rejected")
	}

	emptyPath := filepath.Join(t.TempDir(), "empty-token")
	if err := os.WriteFile(emptyPath, []byte(" \n"), 0o600); err != nil {
		t.Fatalf("write empty token: %v", err)
	}
	if _, err := readRequiredSecretFile("CONNECTIVITY_AGENT_TOKEN_FILE", emptyPath); err == nil {
		t.Fatal("expected an empty secret file to be rejected")
	}

	if _, err := readRequiredSecretFile(
		"CONNECTIVITY_AGENT_TOKEN_FILE",
		filepath.Join(t.TempDir(), "missing-token"),
	); err == nil {
		t.Fatal("expected an unreadable secret file to be rejected")
	}

	if _, err := readRequiredSecretFile("CONNECTIVITY_AGENT_TOKEN_FILE", " "+emptyPath); err == nil {
		t.Fatal("expected surrounding whitespace in a secret path to be rejected")
	}
}

func TestLoadConnectivityEvidenceGatewaySecretsFromFiles(t *testing.T) {
	want := map[string]string{
		"TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE": `[{"urls":["turns:turn.example.com:5349"]}]`,
		"CONNECTIVITY_AGENT_TOKENS_FILE":            `{"external":"agent-token"}`,
		"CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE":  "internal-token",
		"TURN_REST_SHARED_SECRET_FILE":              "turn-rest-secret",
	}
	for environmentName, value := range want {
		writeSecretEnvironment(t, environmentName, value)
	}

	secrets, err := loadConnectivityEvidenceGatewaySecrets(os.Getenv, true)
	if err != nil {
		t.Fatalf("load gateway secrets: %v", err)
	}
	if secrets.frontendProbeICEServersJSON != want["TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE"] {
		t.Fatalf("frontend probe ICE servers = %q", secrets.frontendProbeICEServersJSON)
	}
	if secrets.agentTokensJSON != want["CONNECTIVITY_AGENT_TOKENS_FILE"] {
		t.Fatalf("agent tokens = %q", secrets.agentTokensJSON)
	}
	if secrets.internalToken != want["CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE"] {
		t.Fatalf("internal token = %q", secrets.internalToken)
	}
	if secrets.turnRESTSharedSecret != want["TURN_REST_SHARED_SECRET_FILE"] {
		t.Fatalf("TURN REST shared secret = %q", secrets.turnRESTSharedSecret)
	}
}

func TestLoadConnectivityEvidenceGatewaySecretsRejectsPlaintextFallbacks(t *testing.T) {
	testCases := []struct {
		name                  string
		fileEnvironmentName   string
		legacyEnvironmentName string
	}{
		{
			name:                  "frontend probe ICE servers",
			fileEnvironmentName:   "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE",
			legacyEnvironmentName: "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON",
		},
		{
			name:                  "agent tokens",
			fileEnvironmentName:   "CONNECTIVITY_AGENT_TOKENS_FILE",
			legacyEnvironmentName: "CONNECTIVITY_AGENT_TOKENS_JSON",
		},
		{
			name:                  "internal token",
			fileEnvironmentName:   "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE",
			legacyEnvironmentName: "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN",
		},
		{
			name:                  "TURN REST shared secret",
			fileEnvironmentName:   "TURN_REST_SHARED_SECRET_FILE",
			legacyEnvironmentName: "TURN_REST_SHARED_SECRET",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			writeSecretEnvironment(t, "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE", `[{"urls":["turns:turn.example.com:5349"]}]`)
			writeSecretEnvironment(t, "CONNECTIVITY_AGENT_TOKENS_FILE", `{"external":"agent-token"}`)
			writeSecretEnvironment(t, "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE", "internal-token")
			writeSecretEnvironment(t, "TURN_REST_SHARED_SECRET_FILE", "turn-rest-secret")
			t.Setenv(testCase.fileEnvironmentName, "")
			t.Setenv(testCase.legacyEnvironmentName, "plaintext-must-not-be-used")

			if _, err := loadConnectivityEvidenceGatewaySecrets(os.Getenv, true); err == nil {
				t.Fatalf("expected missing %s file to be rejected", testCase.fileEnvironmentName)
			}
		})
	}
}

func TestLoadConnectivityEvidenceGatewaySecretsAllowsMissingOptionalTURNRESTFile(t *testing.T) {
	writeSecretEnvironment(t, "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE", `[{"urls":["turns:turn.example.com:5349"]}]`)
	writeSecretEnvironment(t, "CONNECTIVITY_AGENT_TOKENS_FILE", `{"external":"agent-token"}`)
	writeSecretEnvironment(t, "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE", "internal-token")
	t.Setenv("TURN_REST_SHARED_SECRET_FILE", "")

	secrets, err := loadConnectivityEvidenceGatewaySecrets(os.Getenv, false)
	if err != nil {
		t.Fatalf("load gateway secrets without TURN REST issuer: %v", err)
	}
	if secrets.turnRESTSharedSecret != "" {
		t.Fatalf("TURN REST shared secret = %q, want empty", secrets.turnRESTSharedSecret)
	}
}

func writeSecretEnvironment(t *testing.T, environmentName string, value string) {
	t.Helper()
	secretPath := filepath.Join(t.TempDir(), environmentName)
	if err := os.WriteFile(secretPath, []byte(value), 0o600); err != nil {
		t.Fatalf("write %s: %v", environmentName, err)
	}
	t.Setenv(environmentName, secretPath)
}

func TestLoadBrowserConnectivityProbeConfigurationReadsBackendICEFromSecretFile(t *testing.T) {
	environment := map[string]string{
		"TURN_REACHABILITY_PROFILE_JSON": validTURNProfile(t),
		"TURN_CREDENTIAL_REVISION":       "revision-7",
		"TURN_PROBE_IDENTITY":            "backend:workspace-123",
		"AILERON_INSTALLATION_ID":        "installation-1",
	}
	environment["TURN_BACKEND_ICE_SERVERS_JSON_FILE"] = writeSecretFile(
		t,
		"backend-ice-servers.json",
		`[{"urls":["turns:turn.example.com:5349"],"username":"probe","credential":"secret"}]`,
	)
	environment["TURN_REST_SHARED_SECRET_FILE"] = writeSecretFile(
		t,
		"turn-rest-shared-secret",
		"turn-rest-secret",
	)

	configuration, err := loadBrowserConnectivityProbeConfigurationFromEnvironment(
		mapEnvironment(environment),
	)
	if err != nil {
		t.Fatalf("load Browser connectivity probe configuration: %v", err)
	}
	if configuration.backendICEServersJSON != `[{"urls":["turns:turn.example.com:5349"],"username":"probe","credential":"secret"}]` {
		t.Fatalf("backend ICE servers = %q", configuration.backendICEServersJSON)
	}
	if configuration.turnRESTSharedSecret != "turn-rest-secret" {
		t.Fatalf("TURN REST shared secret = %q", configuration.turnRESTSharedSecret)
	}
}

func TestLoadBrowserConnectivityProbeConfigurationRejectsPlaintextBackendICEFallback(t *testing.T) {
	environment := map[string]string{
		"TURN_REACHABILITY_PROFILE_JSON":     validTURNProfile(t),
		"TURN_CREDENTIAL_REVISION":           "revision-7",
		"TURN_BACKEND_ICE_SERVERS_JSON":      `[{"urls":["turn:turn.example.com:3478"]}]`,
		"TURN_REST_SHARED_SECRET_FILE":       writeSecretFile(t, "turn-rest-shared-secret", "turn-rest-secret"),
		"TURN_PROBE_IDENTITY":                "backend:workspace-123",
		"AILERON_INSTALLATION_ID":            "installation-1",
		"TURN_BACKEND_ICE_SERVERS_JSON_FILE": "",
	}

	_, err := loadBrowserConnectivityProbeConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "TURN_BACKEND_ICE_SERVERS_JSON_FILE") {
		t.Fatalf("error = %v, want missing backend ICE Secret file failure", err)
	}
}

func writeSecretFile(t *testing.T, name string, value string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(value), 0o440); err != nil {
		t.Fatalf("write %s: %v", name, err)
	}
	return path
}

func TestBuildManagerOptionsLimitsCacheToPodNamespace(t *testing.T) {
	options, err := buildManagerOptions(
		runtime.NewScheme(),
		":9090",
		":8081",
		true,
		" workspace-system ",
	)
	if err != nil {
		t.Fatalf("build manager options: %v", err)
	}

	if len(options.Cache.DefaultNamespaces) != 1 {
		t.Fatalf("expected one watched namespace, got %d", len(options.Cache.DefaultNamespaces))
	}
	if _, ok := options.Cache.DefaultNamespaces["workspace-system"]; !ok {
		t.Fatalf("expected cache to watch workspace-system only")
	}
	if options.Metrics.BindAddress != ":9090" {
		t.Fatalf("expected metrics bind address :9090, got %q", options.Metrics.BindAddress)
	}
}

func TestBuildManagerOptionsRejectsMissingPodNamespace(t *testing.T) {
	_, err := buildManagerOptions(runtime.NewScheme(), "0", ":8081", false, " ")
	if err == nil {
		t.Fatal("expected missing POD_NAMESPACE to be rejected")
	}
}
