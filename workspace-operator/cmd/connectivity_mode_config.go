package main

import (
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"workspace-operator/internal/controller"
)

type connectivityEvidenceGatewayConfiguration struct {
	turnProfile                 controller.TURNReachabilityProfile
	installationID              string
	credentialRevision          string
	frontendProbeICEServersJSON string
	agentTokensJSON             string
	internalToken               string
	turnRESTSharedSecret        string
}

func loadConnectivityEvidenceGatewayConfiguration() (connectivityEvidenceGatewayConfiguration, error) {
	return loadConnectivityEvidenceGatewayConfigurationFromEnvironment(os.Getenv)
}

func loadConnectivityEvidenceGatewayConfigurationFromEnvironment(
	readEnvironment environmentReader,
) (connectivityEvidenceGatewayConfiguration, error) {
	profile, err := loadTURNProfile(readEnvironment)
	if err != nil {
		return connectivityEvidenceGatewayConfiguration{}, err
	}
	if profile == nil {
		return connectivityEvidenceGatewayConfiguration{}, fmt.Errorf("TURN reachability profile is required")
	}
	installationID, err := requiredExactEnvironment(
		"AILERON_INSTALLATION_ID",
		readEnvironment("AILERON_INSTALLATION_ID"),
	)
	if err != nil {
		return connectivityEvidenceGatewayConfiguration{}, err
	}
	credentialRevision, err := requiredExactEnvironment(
		"TURN_CREDENTIAL_REVISION",
		readEnvironment("TURN_CREDENTIAL_REVISION"),
	)
	if err != nil {
		return connectivityEvidenceGatewayConfiguration{}, err
	}
	secrets, err := loadConnectivityEvidenceGatewaySecrets(
		readEnvironment,
		profile.CredentialIssuer.Kind == controller.TURNCredentialIssuerTURNREST,
	)
	if err != nil {
		return connectivityEvidenceGatewayConfiguration{}, err
	}
	return connectivityEvidenceGatewayConfiguration{
		turnProfile:                 *profile,
		installationID:              installationID,
		credentialRevision:          credentialRevision,
		frontendProbeICEServersJSON: secrets.frontendProbeICEServersJSON,
		agentTokensJSON:             secrets.agentTokensJSON,
		internalToken:               secrets.internalToken,
		turnRESTSharedSecret:        secrets.turnRESTSharedSecret,
	}, nil
}

type connectivityEvidenceGatewaySecrets struct {
	frontendProbeICEServersJSON string
	agentTokensJSON             string
	internalToken               string
	turnRESTSharedSecret        string
}

func loadConnectivityEvidenceGatewaySecrets(
	readEnvironment environmentReader,
	requireTURNRESTSharedSecret bool,
) (connectivityEvidenceGatewaySecrets, error) {
	frontendProbeICEServersJSON, err := readRequiredSecretFile(
		"TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE",
		readEnvironment("TURN_FRONTEND_PROBE_ICE_SERVERS_JSON_FILE"),
	)
	if err != nil {
		return connectivityEvidenceGatewaySecrets{}, err
	}
	agentTokensJSON, err := readRequiredSecretFile(
		"CONNECTIVITY_AGENT_TOKENS_FILE",
		readEnvironment("CONNECTIVITY_AGENT_TOKENS_FILE"),
	)
	if err != nil {
		return connectivityEvidenceGatewaySecrets{}, err
	}
	internalToken, err := readRequiredSecretFile(
		"CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE",
		readEnvironment("CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE"),
	)
	if err != nil {
		return connectivityEvidenceGatewaySecrets{}, err
	}
	turnRESTSharedSecret, err := readOptionalSecretFile(
		"TURN_REST_SHARED_SECRET_FILE",
		readEnvironment("TURN_REST_SHARED_SECRET_FILE"),
		requireTURNRESTSharedSecret,
	)
	if err != nil {
		return connectivityEvidenceGatewaySecrets{}, err
	}
	return connectivityEvidenceGatewaySecrets{
		frontendProbeICEServersJSON: frontendProbeICEServersJSON,
		agentTokensJSON:             agentTokensJSON,
		internalToken:               internalToken,
		turnRESTSharedSecret:        turnRESTSharedSecret,
	}, nil
}

type connectivityExternalAgentConfiguration struct {
	interval       time.Duration
	gatewayURL     string
	installationID string
	vantageID      string
	token          string
	caFile         string
	httpClient     *http.Client
}

func loadConnectivityExternalAgentConfiguration() (connectivityExternalAgentConfiguration, error) {
	return loadConnectivityExternalAgentConfigurationFromEnvironment(os.Getenv)
}

func loadConnectivityExternalAgentConfigurationFromEnvironment(
	readEnvironment environmentReader,
) (connectivityExternalAgentConfiguration, error) {
	intervalSeconds, err := parseRequiredPositiveInteger(
		"CONNECTIVITY_AGENT_INTERVAL_SECONDS",
		readEnvironment("CONNECTIVITY_AGENT_INTERVAL_SECONDS"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	token, err := readRequiredSecretFile(
		"CONNECTIVITY_AGENT_TOKEN_FILE",
		readEnvironment("CONNECTIVITY_AGENT_TOKEN_FILE"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	caFile, err := optionalExactEnvironment(
		"CONNECTIVITY_AGENT_CA_FILE",
		readEnvironment("CONNECTIVITY_AGENT_CA_FILE"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	httpClient, err := newExternalConnectivityAgentHTTPClient(caFile)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	gatewayURL, err := parseConnectivityEvidenceGatewayEndpoint(
		"CONNECTIVITY_EVIDENCE_GATEWAY_URL",
		readEnvironment("CONNECTIVITY_EVIDENCE_GATEWAY_URL"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	installationID, err := requiredExactEnvironment(
		"AILERON_INSTALLATION_ID",
		readEnvironment("AILERON_INSTALLATION_ID"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	vantageID, err := requiredExactEnvironment(
		"CONNECTIVITY_AGENT_VANTAGE_ID",
		readEnvironment("CONNECTIVITY_AGENT_VANTAGE_ID"),
	)
	if err != nil {
		return connectivityExternalAgentConfiguration{}, err
	}
	return connectivityExternalAgentConfiguration{
		interval:       time.Duration(intervalSeconds) * time.Second,
		gatewayURL:     gatewayURL,
		installationID: installationID,
		vantageID:      vantageID,
		token:          token,
		caFile:         caFile,
		httpClient:     httpClient,
	}, nil
}

func parseConnectivityEvidenceGatewayEndpoint(name string, rawValue string) (string, error) {
	if rawValue == "" {
		return "", fmt.Errorf("%s is required", name)
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return "", fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	parsed, err := url.Parse(rawValue)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Host == "" || parsed.User != nil || parsed.Opaque != "" ||
		parsed.Path != controller.ConnectivityEvidenceGatewayPublicPath || parsed.RawPath != "" ||
		parsed.ForceQuery || parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", fmt.Errorf(
			"%s must be an absolute HTTP endpoint with path %s and no credentials, query, or fragment",
			name,
			controller.ConnectivityEvidenceGatewayPublicPath,
		)
	}
	if port := parsed.Port(); port != "" {
		portNumber, portErr := strconv.Atoi(port)
		if portErr != nil || portNumber < 1 || portNumber > 65535 {
			return "", fmt.Errorf("%s contains an invalid port", name)
		}
	}
	return rawValue, nil
}

func parseRequiredPositiveInteger(name string, rawValue string) (int, error) {
	if rawValue == "" {
		return 0, fmt.Errorf("%s is required", name)
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return 0, fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	value, err := strconv.Atoi(rawValue)
	if err != nil || value < 1 {
		return 0, fmt.Errorf("%s must be a positive integer", name)
	}
	return value, nil
}

func loadPodNamespace(readEnvironment environmentReader) (string, error) {
	return optionalExactEnvironment("POD_NAMESPACE", readEnvironment("POD_NAMESPACE"))
}
