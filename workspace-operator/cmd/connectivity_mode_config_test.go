package main

import (
	"encoding/pem"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestLoadConnectivityEvidenceGatewayConfigurationTypesAllInputs(t *testing.T) {
	environment := validConnectivityEvidenceGatewayEnvironment(t)

	configuration, err := loadConnectivityEvidenceGatewayConfigurationFromEnvironment(
		mapEnvironment(environment),
	)
	if err != nil {
		t.Fatalf("load connectivity evidence gateway configuration: %v", err)
	}
	if configuration.installationID != "installation-1" ||
		configuration.credentialRevision != "revision-7" ||
		configuration.frontendProbeICEServersJSON == "" ||
		configuration.agentTokensJSON == "" ||
		configuration.internalToken != "internal-token" ||
		configuration.turnRESTSharedSecret != "turn-rest-secret" {
		t.Fatalf("gateway configuration = %#v", configuration)
	}
}

func TestLoadConnectivityEvidenceGatewayConfigurationRejectsInexactInputs(t *testing.T) {
	testCases := []struct {
		name        string
		environment string
		value       string
		wantError   string
	}{
		{name: "installation ID", environment: "AILERON_INSTALLATION_ID", value: " installation-1", wantError: "surrounding whitespace"},
		{name: "credential revision", environment: "TURN_CREDENTIAL_REVISION", value: "revision-7 ", wantError: "surrounding whitespace"},
		{name: "TURN profile", environment: "TURN_REACHABILITY_PROFILE_JSON", value: " " + validTURNProfile(t), wantError: "surrounding whitespace"},
		{name: "frontend ICE file", environment: "TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE", value: " /run/secrets/frontend.json", wantError: "surrounding whitespace"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			environment := validConnectivityEvidenceGatewayEnvironment(t)
			environment[testCase.environment] = testCase.value
			_, err := loadConnectivityEvidenceGatewayConfigurationFromEnvironment(mapEnvironment(environment))
			if err == nil || !strings.Contains(err.Error(), testCase.wantError) {
				t.Fatalf("error = %v, want containing %q", err, testCase.wantError)
			}
		})
	}
}

func TestLoadConnectivityExternalAgentConfigurationTypesAllInputs(t *testing.T) {
	environment := validConnectivityExternalAgentEnvironment(t)

	configuration, err := loadConnectivityExternalAgentConfigurationFromEnvironment(
		mapEnvironment(environment),
	)
	if err != nil {
		t.Fatalf("load external connectivity agent configuration: %v", err)
	}
	if configuration.interval != 30*time.Second ||
		configuration.gatewayURL != "https://platform.example.com/api/v1/connectivity-evidence" ||
		configuration.installationID != "installation-1" ||
		configuration.vantageID != "external" ||
		configuration.token != "agent-token" ||
		configuration.caFile == "" {
		t.Fatalf("external agent configuration = %#v", configuration)
	}
}

func TestLoadConnectivityExternalAgentConfigurationRejectsInexactInputs(t *testing.T) {
	testCases := []struct {
		name        string
		environment string
		value       string
		wantError   string
	}{
		{name: "interval", environment: "CONNECTIVITY_AGENT_INTERVAL_SECONDS", value: " 30", wantError: "surrounding whitespace"},
		{name: "gateway URL", environment: "CONNECTIVITY_EVIDENCE_GATEWAY_URL", value: "https://platform.example.com/api/v1/connectivity-evidence ", wantError: "surrounding whitespace"},
		{name: "installation ID", environment: "AILERON_INSTALLATION_ID", value: " installation-1", wantError: "surrounding whitespace"},
		{name: "vantage ID", environment: "CONNECTIVITY_AGENT_VANTAGE_ID", value: "external ", wantError: "surrounding whitespace"},
		{name: "CA file", environment: "CONNECTIVITY_AGENT_CA_FILE", value: " /run/secrets/ca.crt", wantError: "surrounding whitespace"},
		{name: "token file", environment: "CONNECTIVITY_AGENT_TOKEN_FILE", value: " /run/secrets/token", wantError: "surrounding whitespace"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			environment := validConnectivityExternalAgentEnvironment(t)
			environment[testCase.environment] = testCase.value
			_, err := loadConnectivityExternalAgentConfigurationFromEnvironment(mapEnvironment(environment))
			if err == nil || !strings.Contains(err.Error(), testCase.wantError) {
				t.Fatalf("error = %v, want containing %q", err, testCase.wantError)
			}
		})
	}
}

func TestParseConnectivityEvidenceGatewayEndpointRequiresCanonicalPath(t *testing.T) {
	valid := []string{
		"https://platform.example.com/api/v1/connectivity-evidence",
		"http://127.0.0.1:18083/api/v1/connectivity-evidence",
	}
	for _, value := range valid {
		parsed, err := parseConnectivityEvidenceGatewayEndpoint(
			"CONNECTIVITY_EVIDENCE_GATEWAY_URL",
			value,
		)
		if err != nil || parsed != value {
			t.Fatalf("parse %q = %q, %v", value, parsed, err)
		}
	}

	invalid := []string{
		"https://platform.example.com",
		"https://platform.example.com/api/v1/connectivity-evidence/",
		"https://platform.example.com/api/v1/other",
		"https://user:password@platform.example.com/api/v1/connectivity-evidence",
		"https://platform.example.com:0/api/v1/connectivity-evidence",
		"https://platform.example.com:65536/api/v1/connectivity-evidence",
		"https://platform.example.com/api/v1/connectivity-evidence?debug=true",
		"https://platform.example.com/api/v1/connectivity-evidence#fragment",
	}
	for _, value := range invalid {
		if _, err := parseConnectivityEvidenceGatewayEndpoint(
			"CONNECTIVITY_EVIDENCE_GATEWAY_URL",
			value,
		); err == nil {
			t.Fatalf("expected %q to be rejected", value)
		}
	}
}

func TestLoadPodNamespaceRejectsSurroundingWhitespace(t *testing.T) {
	_, err := loadPodNamespace(mapEnvironment(map[string]string{"POD_NAMESPACE": " operator-system "}))
	if err == nil || !strings.Contains(err.Error(), "surrounding whitespace") {
		t.Fatalf("error = %v, want exact POD_NAMESPACE failure", err)
	}
}

func validConnectivityEvidenceGatewayEnvironment(t *testing.T) map[string]string {
	t.Helper()
	return map[string]string{
		"TURN_REACHABILITY_PROFILE_JSON":            validTURNProfile(t),
		"AILERON_INSTALLATION_ID":                   "installation-1",
		"TURN_CREDENTIAL_REVISION":                  "revision-7",
		"TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE": writeSecretFile(t, "frontend-ice-servers.json", `[{"urls":["turns:turn.example.com:5349"]}]`),
		"CONNECTIVITY_AGENT_TOKENS_FILE":            writeSecretFile(t, "agent-tokens.json", `{"external":"agent-token"}`),
		"CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE":  writeSecretFile(t, "internal-token", "internal-token"),
		"TURN_REST_SHARED_SECRET_FILE":              writeSecretFile(t, "turn-rest-shared-secret", "turn-rest-secret"),
	}
}

func validConnectivityExternalAgentEnvironment(t *testing.T) map[string]string {
	t.Helper()
	return map[string]string{
		"CONNECTIVITY_AGENT_INTERVAL_SECONDS": "30",
		"CONNECTIVITY_AGENT_TOKEN_FILE":       writeSecretFile(t, "agent-token", "agent-token"),
		"CONNECTIVITY_AGENT_CA_FILE":          writeTestCAFile(t),
		"CONNECTIVITY_EVIDENCE_GATEWAY_URL":   "https://platform.example.com/api/v1/connectivity-evidence",
		"AILERON_INSTALLATION_ID":             "installation-1",
		"CONNECTIVITY_AGENT_VANTAGE_ID":       "external",
	}
}

func writeTestCAFile(t *testing.T) string {
	t.Helper()
	server := httptest.NewTLSServer(nil)
	defer server.Close()
	return writeSecretFile(t, "ca.crt", string(pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: server.Certificate().Raw,
	})))
}
