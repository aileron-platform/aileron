package main

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	corev1 "k8s.io/api/core/v1"

	"workspace-operator/internal/controller"
)

func TestLoadOperatorConfigurationValidatesAndTypesEnvironment(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["PLATFORM_STORAGE_GID"] = "1000"
	environment["WORKSPACE_STORAGE_CLASS_NAME"] = "workspace-data"
	environment["RUNTIME_HOME_STORAGE_CLASS_NAME"] = "runtime-home"
	environment["WORKSPACE_IMAGE_PULL_SECRET_NAMES"] = "first,second,first"
	environment["PLATFORM_DATABASE_CILIUM_EGRESS_JSON"] = `{"kind":"namespacePods","namespace":"platform-data","podLabels":{"app.kubernetes.io/name":"postgres"}}`

	configuration, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err != nil {
		t.Fatalf("load operator configuration: %v", err)
	}
	if configuration.platformPublicOrigin != "https://platform.example.com" {
		t.Fatalf("platform origin = %q", configuration.platformPublicOrigin)
	}
	if configuration.managerURL != "http://workspace-manager.platform.svc.cluster.local:3001" {
		t.Fatalf("manager URL = %q", configuration.managerURL)
	}
	if configuration.platformStorageGID == nil || *configuration.platformStorageGID != 1000 {
		t.Fatalf("platform storage GID = %#v", configuration.platformStorageGID)
	}
	if configuration.runtimeHomeAccessMode != corev1.ReadWriteOnce {
		t.Fatalf("Runtime HOME access mode = %q", configuration.runtimeHomeAccessMode)
	}
	if !configuration.ciliumEnabled {
		t.Fatal("Cilium should be enabled")
	}
	if configuration.platformDatabaseEgressDestination == nil ||
		configuration.platformDatabaseEgressDestination.Namespace != "platform-data" {
		t.Fatalf("platform database egress destination = %#v", configuration.platformDatabaseEgressDestination)
	}
	if !reflect.DeepEqual(configuration.workloadImagePullSecrets, []string{"first", "second"}) {
		t.Fatalf("image pull secrets = %#v", configuration.workloadImagePullSecrets)
	}
	if configuration.browserCredentialKeyring == nil {
		t.Fatal("browser credential keyring was not loaded")
	}
}

func TestLoadOperatorConfigurationRejectsInvalidPlatformDatabaseEgressDestination(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["PLATFORM_DATABASE_CILIUM_EGRESS_JSON"] = `{"kind":"namespacePods","namespace":"platform-data"}`

	_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "namespacePods requires namespace and podLabels") {
		t.Fatalf("error = %v, want platform database egress validation failure", err)
	}
}

func TestLoadOperatorConfigurationRejectsInvalidRequiredSettings(t *testing.T) {
	testCases := []struct {
		name        string
		environment string
		value       string
		wantError   string
	}{
		{name: "missing manager URL", environment: "AILERON_MANAGER_INTERNAL_URL", value: "", wantError: "AILERON_MANAGER_INTERNAL_URL is required"},
		{name: "manager URL path", environment: "AILERON_MANAGER_INTERNAL_URL", value: "http://manager:3001/api", wantError: "without path"},
		{name: "manager URL whitespace", environment: "AILERON_MANAGER_INTERNAL_URL", value: " http://manager:3001", wantError: "surrounding whitespace"},
		{name: "missing knowledge base PVC", environment: "KNOWLEDGE_BASES_PVC_NAME", value: "", wantError: "KNOWLEDGE_BASES_PVC_NAME is required"},
		{name: "knowledge base PVC whitespace", environment: "KNOWLEDGE_BASES_PVC_NAME", value: " knowledge-bases ", wantError: "surrounding whitespace"},
		{name: "ambiguous Cilium boolean", environment: "CILIUM_ENABLED", value: "1", wantError: "exactly true or false"},
		{name: "whitespace Cilium boolean", environment: "CILIUM_ENABLED", value: " true ", wantError: "exactly true or false"},
		{name: "invalid storage GID", environment: "PLATFORM_STORAGE_GID", value: "0", wantError: "positive integer"},
		{name: "storage GID whitespace", environment: "PLATFORM_STORAGE_GID", value: " 1000", wantError: "surrounding whitespace"},
		{name: "Workspace storage class whitespace", environment: "WORKSPACE_STORAGE_CLASS_NAME", value: " shared-rwx ", wantError: "surrounding whitespace"},
		{name: "Runtime HOME storage class whitespace", environment: "RUNTIME_HOME_STORAGE_CLASS_NAME", value: " runtime-rwx ", wantError: "surrounding whitespace"},
		{name: "image pull Secret item whitespace", environment: "WORKSPACE_IMAGE_PULL_SECRET_NAMES", value: "first, second", wantError: "item must not contain surrounding whitespace"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			environment := validOperatorEnvironment(t)
			environment[testCase.environment] = testCase.value
			_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
			if err == nil || !strings.Contains(err.Error(), testCase.wantError) {
				t.Fatalf("error = %v, want containing %q", err, testCase.wantError)
			}
		})
	}
}

func TestParseOptionalServiceURLRejectsInvalidPortsAndWhitespace(t *testing.T) {
	testCases := []struct {
		name  string
		value string
	}{
		{name: "port above range", value: "http://gateway.example.com:65536"},
		{name: "zero port", value: "http://gateway.example.com:0"},
		{name: "non-numeric port", value: "http://gateway.example.com:not-a-port"},
		{name: "leading whitespace", value: " http://gateway.example.com:8083"},
		{name: "trailing whitespace", value: "http://gateway.example.com:8083 "},
		{name: "whitespace-only optional value", value: " "},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if _, err := parseOptionalServiceURL("CONNECTIVITY_EVIDENCE_GATEWAY_URL", testCase.value); err == nil {
				t.Fatalf("expected %q to be rejected", testCase.value)
			}
		})
	}
}

func TestLoadOperatorConfigurationFailsWhenBrowserKeyringIsUnavailable(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["BROWSER_CREDENTIAL_KEYRING_FILE"] = filepath.Join(t.TempDir(), "missing.json")

	_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "BROWSER_CREDENTIAL_KEYRING_FILE") {
		t.Fatalf("error = %v, want browser keyring failure", err)
	}
}

func TestLoadOperatorConfigurationRejectsPartialTURNConfiguration(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["TURN_CREDENTIAL_REVISION"] = "1"

	_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "must be configured together") {
		t.Fatalf("error = %v, want partial TURN configuration failure", err)
	}
}

func TestLoadOperatorConfigurationRejectsWhitespaceInRequiredTURNString(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["TURN_REACHABILITY_PROFILE_JSON"] = validTURNProfile(t)
	environment["TURN_ICE_SERVERS_SECRET_NAME"] = " turn-ice "
	environment["TURN_BACKEND_ICE_SERVERS_SECRET_KEY"] = "backend.json"
	environment["TURN_FRONTEND_ICE_SERVERS_SECRET_KEY"] = "frontend.json"
	environment["TURN_CREDENTIAL_REVISION"] = "1"

	_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "TURN_ICE_SERVERS_SECRET_NAME must not contain surrounding whitespace") {
		t.Fatalf("error = %v, want exact TURN string failure", err)
	}
}

func TestLoadOperatorConfigurationLoadsConditionalGatewaySecretFile(t *testing.T) {
	environment := validOperatorEnvironment(t)
	profile := validTURNProfile(t)
	environment["TURN_REACHABILITY_PROFILE_JSON"] = profile
	environment["TURN_ICE_SERVERS_SECRET_NAME"] = "turn-ice"
	environment["TURN_BACKEND_ICE_SERVERS_SECRET_KEY"] = "backend.json"
	environment["TURN_FRONTEND_ICE_SERVERS_SECRET_KEY"] = "frontend.json"
	environment["TURN_CREDENTIAL_REVISION"] = "1"
	environment["BROWSER_CONNECTIVITY_PROBE_IMAGE"] = "operator:test"
	environment["AILERON_INSTALLATION_ID"] = "installation-1"
	environment["CONNECTIVITY_EVIDENCE_GATEWAY_URL"] = "http://connectivity-gateway.platform.svc.cluster.local:8083"
	tokenPath := filepath.Join(t.TempDir(), "internal-token")
	if err := os.WriteFile(tokenPath, []byte(" gateway-token\n"), 0o440); err != nil {
		t.Fatalf("write gateway token: %v", err)
	}
	environment["CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE"] = tokenPath

	configuration, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err != nil {
		t.Fatalf("load TURN operator configuration: %v", err)
	}
	if configuration.turnProfile == nil || configuration.connectivityGatewayToken != "gateway-token" {
		t.Fatalf("TURN gateway configuration was not loaded: %#v", configuration)
	}
}

func TestLoadOperatorConfigurationRejectsPlaintextGatewayTokenFallback(t *testing.T) {
	environment := validOperatorEnvironment(t)
	environment["TURN_REACHABILITY_PROFILE_JSON"] = validTURNProfile(t)
	environment["TURN_ICE_SERVERS_SECRET_NAME"] = "turn-ice"
	environment["TURN_BACKEND_ICE_SERVERS_SECRET_KEY"] = "backend.json"
	environment["TURN_FRONTEND_ICE_SERVERS_SECRET_KEY"] = "frontend.json"
	environment["TURN_CREDENTIAL_REVISION"] = "1"
	environment["BROWSER_CONNECTIVITY_PROBE_IMAGE"] = "operator:test"
	environment["AILERON_INSTALLATION_ID"] = "installation-1"
	environment["CONNECTIVITY_EVIDENCE_GATEWAY_URL"] = "http://connectivity-gateway.platform.svc.cluster.local:8083"
	environment["CONNECTIVITY_GATEWAY_INTERNAL_TOKEN"] = "plaintext-must-not-be-used"

	_, err := loadOperatorConfigurationFromEnvironment(mapEnvironment(environment))
	if err == nil || !strings.Contains(err.Error(), "CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE") {
		t.Fatalf("error = %v, want missing Secret file failure", err)
	}
}

func validOperatorEnvironment(t *testing.T) map[string]string {
	t.Helper()
	keyringPath := filepath.Join(t.TempDir(), "keyring.json")
	keyringPayload := map[string]any{
		"algorithm":   "hkdf-sha256-v1",
		"activeKeyId": "browser-key-1",
		"keys": map[string]string{
			"browser-key-1": base64.RawURLEncoding.EncodeToString(
				[]byte("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
			),
		},
	}
	rawKeyring, err := json.Marshal(keyringPayload)
	if err != nil {
		t.Fatalf("marshal keyring: %v", err)
	}
	if err := os.WriteFile(keyringPath, rawKeyring, 0o440); err != nil {
		t.Fatalf("write keyring: %v", err)
	}
	return map[string]string{
		"AILERON_PLATFORM_PUBLIC_ORIGIN":   "https://platform.example.com",
		"AILERON_MANAGER_INTERNAL_URL":     "http://workspace-manager.platform.svc.cluster.local:3001",
		"KNOWLEDGE_BASES_PVC_NAME":         "knowledge-bases",
		"RUNTIME_HOME_STORAGE_ACCESS_MODE": "ReadWriteOnce",
		"CILIUM_ENABLED":                   "true",
		"BROWSER_CREDENTIAL_KEYRING_FILE":  keyringPath,
	}
}

func validTURNProfile(t *testing.T) string {
	t.Helper()
	profile := controller.TURNReachabilityProfile{
		ContractVersion: controller.BrowserConnectivityContractVersion,
		PolicyBackend:   controller.TURNPolicyBackendCilium,
		Backend: controller.TURNBackendProfile{
			URLs:               []string{"turn:turn.example.com:3478"},
			ControlDestination: controller.TURNPolicyDestination{Kind: controller.TURNDestinationCiliumEntities, Values: []string{"host"}},
			RelayDestination:   controller.TURNPolicyDestination{Kind: controller.TURNDestinationCIDRs, Values: []string{"192.0.2.0/24"}},
			RelayPortRange:     controller.TURNRelayPortRange{Min: 49160, Max: 49259},
		},
		Frontend:         controller.TURNFrontendProfile{URLs: []string{"turn:turn.example.com:3478"}},
		CredentialIssuer: controller.TURNCredentialIssuerProfile{Kind: "turnRest", SecretRef: "turn-rest", TTLSeconds: 300},
		Evidence:         controller.TURNEvidencePolicy{IntervalSeconds: 30, TTLSeconds: 90, RequiredFrontendVantages: []string{"external"}},
	}
	raw, err := json.Marshal(profile)
	if err != nil {
		t.Fatalf("marshal TURN profile: %v", err)
	}
	return string(raw)
}

func mapEnvironment(values map[string]string) environmentReader {
	return func(name string) string {
		return values[name]
	}
}
