package main

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"

	corev1 "k8s.io/api/core/v1"

	"workspace-operator/internal/controller"
)

type operatorConfiguration struct {
	platformPublicOrigin           string
	managerURL                     string
	knowledgeBasesPVCName          string
	platformStorageGID             *int64
	workspaceStorageClass          string
	runtimeHomeStorageClass        string
	runtimeHomeAccessMode          corev1.PersistentVolumeAccessMode
	workloadImagePullSecrets       []string
	ciliumEnabled                  bool
	turnProfile                    *controller.TURNReachabilityProfile
	turnICEServersSecretName       string
	turnBackendSecretKey           string
	turnFrontendSecretKey          string
	turnCredentialRevision         string
	browserConnectivityProbeImage  string
	connectivityEvidenceGatewayURL string
	connectivityInstallationID     string
	connectivityGatewayToken       string
	browserCredentialKeyring       *controller.BrowserCredentialKeyring
}

type environmentReader func(string) string

func loadOperatorConfiguration() (operatorConfiguration, error) {
	return loadOperatorConfigurationFromEnvironment(os.Getenv)
}

func loadOperatorConfigurationFromEnvironment(
	readEnvironment environmentReader,
) (operatorConfiguration, error) {
	platformPublicOrigin, err := controller.ParsePlatformPublicOrigin(
		readEnvironment("AILERON_PLATFORM_PUBLIC_ORIGIN"),
	)
	if err != nil {
		return operatorConfiguration{}, fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN: %w", err)
	}
	managerURL, err := parseRequiredServiceURL(
		"AILERON_MANAGER_INTERNAL_URL",
		readEnvironment("AILERON_MANAGER_INTERNAL_URL"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	knowledgeBasesPVCName, err := requiredExactEnvironment(
		"KNOWLEDGE_BASES_PVC_NAME",
		readEnvironment("KNOWLEDGE_BASES_PVC_NAME"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	platformStorageGID, err := parseOptionalPositiveInt64(
		"PLATFORM_STORAGE_GID",
		readEnvironment("PLATFORM_STORAGE_GID"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	workspaceStorageClass, err := optionalExactEnvironment(
		"WORKSPACE_STORAGE_CLASS_NAME",
		readEnvironment("WORKSPACE_STORAGE_CLASS_NAME"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	runtimeHomeStorageClass, err := optionalExactEnvironment(
		"RUNTIME_HOME_STORAGE_CLASS_NAME",
		readEnvironment("RUNTIME_HOME_STORAGE_CLASS_NAME"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	workloadImagePullSecrets, err := commaSeparatedExactValues(
		"WORKSPACE_IMAGE_PULL_SECRET_NAMES",
		readEnvironment("WORKSPACE_IMAGE_PULL_SECRET_NAMES"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	runtimeHomeAccessModeValue := readEnvironment("RUNTIME_HOME_STORAGE_ACCESS_MODE")
	if runtimeHomeAccessModeValue != strings.TrimSpace(runtimeHomeAccessModeValue) {
		return operatorConfiguration{}, fmt.Errorf(
			"RUNTIME_HOME_STORAGE_ACCESS_MODE must not contain surrounding whitespace",
		)
	}
	runtimeHomeAccessMode, err := controller.ParseRuntimeHomeStorageAccessMode(runtimeHomeAccessModeValue)
	if err != nil {
		return operatorConfiguration{}, fmt.Errorf("RUNTIME_HOME_STORAGE_ACCESS_MODE: %w", err)
	}
	ciliumEnabled, err := parseRequiredBoolean(
		"CILIUM_ENABLED",
		readEnvironment("CILIUM_ENABLED"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	turnProfile, err := loadOperatorTURNConfiguration(readEnvironment)
	if err != nil {
		return operatorConfiguration{}, err
	}

	browserConnectivityProbeImage := readEnvironment("BROWSER_CONNECTIVITY_PROBE_IMAGE")
	connectivityInstallationID := readEnvironment("AILERON_INSTALLATION_ID")
	if turnProfile != nil {
		browserConnectivityProbeImage, err = requiredExactEnvironment(
			"BROWSER_CONNECTIVITY_PROBE_IMAGE",
			browserConnectivityProbeImage,
		)
		if err != nil {
			return operatorConfiguration{}, fmt.Errorf("TURN configuration: %w", err)
		}
		connectivityInstallationID, err = requiredExactEnvironment(
			"AILERON_INSTALLATION_ID",
			connectivityInstallationID,
		)
		if err != nil {
			return operatorConfiguration{}, fmt.Errorf("TURN configuration: %w", err)
		}
	} else {
		browserConnectivityProbeImage = strings.TrimSpace(browserConnectivityProbeImage)
		connectivityInstallationID = strings.TrimSpace(connectivityInstallationID)
	}

	connectivityEvidenceGatewayURL, err := parseOptionalServiceURL(
		"CONNECTIVITY_EVIDENCE_GATEWAY_URL",
		readEnvironment("CONNECTIVITY_EVIDENCE_GATEWAY_URL"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	connectivityGatewayToken := ""
	if connectivityEvidenceGatewayURL != "" {
		if turnProfile == nil {
			return operatorConfiguration{}, fmt.Errorf(
				"CONNECTIVITY_EVIDENCE_GATEWAY_URL requires TURN configuration",
			)
		}
		connectivityGatewayToken, err = readRequiredSecretFile(
			"CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE",
			readEnvironment("CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE"),
		)
		if err != nil {
			return operatorConfiguration{}, err
		}
	}

	browserCredentialKeyringPath, err := requiredExactEnvironment(
		"BROWSER_CREDENTIAL_KEYRING_FILE",
		readEnvironment("BROWSER_CREDENTIAL_KEYRING_FILE"),
	)
	if err != nil {
		return operatorConfiguration{}, err
	}
	browserCredentialKeyring, err := controller.LoadBrowserCredentialKeyring(browserCredentialKeyringPath)
	if err != nil {
		return operatorConfiguration{}, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_FILE: %w", err)
	}

	return operatorConfiguration{
		platformPublicOrigin:           platformPublicOrigin,
		managerURL:                     managerURL,
		knowledgeBasesPVCName:          knowledgeBasesPVCName,
		platformStorageGID:             platformStorageGID,
		workspaceStorageClass:          workspaceStorageClass,
		runtimeHomeStorageClass:        runtimeHomeStorageClass,
		runtimeHomeAccessMode:          runtimeHomeAccessMode,
		workloadImagePullSecrets:       workloadImagePullSecrets,
		ciliumEnabled:                  ciliumEnabled,
		turnProfile:                    turnProfile,
		turnICEServersSecretName:       readEnvironment("TURN_ICE_SERVERS_SECRET_NAME"),
		turnBackendSecretKey:           readEnvironment("TURN_BACKEND_ICE_SERVERS_SECRET_KEY"),
		turnFrontendSecretKey:          readEnvironment("TURN_FRONTEND_ICE_SERVERS_SECRET_KEY"),
		turnCredentialRevision:         readEnvironment("TURN_CREDENTIAL_REVISION"),
		browserConnectivityProbeImage:  browserConnectivityProbeImage,
		connectivityEvidenceGatewayURL: connectivityEvidenceGatewayURL,
		connectivityInstallationID:     connectivityInstallationID,
		connectivityGatewayToken:       connectivityGatewayToken,
		browserCredentialKeyring:       browserCredentialKeyring,
	}, nil
}

func loadOperatorTURNConfiguration(
	readEnvironment environmentReader,
) (*controller.TURNReachabilityProfile, error) {
	profileValue := readEnvironment("TURN_REACHABILITY_PROFILE_JSON")
	if profileValue != strings.TrimSpace(profileValue) {
		return nil, fmt.Errorf(
			"TURN_REACHABILITY_PROFILE_JSON must not contain surrounding whitespace",
		)
	}
	profile, err := controller.ParseTURNReachabilityProfile(
		profileValue,
	)
	if err != nil {
		return nil, fmt.Errorf("TURN_REACHABILITY_PROFILE_JSON: %w", err)
	}
	requiredNames := []string{
		"TURN_ICE_SERVERS_SECRET_NAME",
		"TURN_BACKEND_ICE_SERVERS_SECRET_KEY",
		"TURN_FRONTEND_ICE_SERVERS_SECRET_KEY",
		"TURN_CREDENTIAL_REVISION",
	}
	configured := 0
	for _, name := range requiredNames {
		value := readEnvironment(name)
		if value != "" {
			configured++
			if _, err := requiredExactEnvironment(name, value); err != nil {
				return nil, fmt.Errorf("TURN configuration: %w", err)
			}
		}
	}
	if profile == nil && configured == 0 {
		return nil, nil
	}
	if profile == nil || configured != len(requiredNames) {
		return nil, fmt.Errorf(
			"TURN_REACHABILITY_PROFILE_JSON and TURN Secret settings must be configured together",
		)
	}
	return profile, nil
}

func parseRequiredServiceURL(name string, rawValue string) (string, error) {
	value, err := parseOptionalServiceURL(name, rawValue)
	if err != nil {
		return "", err
	}
	if value == "" {
		return "", fmt.Errorf("%s is required", name)
	}
	return value, nil
}

func parseOptionalServiceURL(name string, rawValue string) (string, error) {
	if rawValue == "" {
		return "", nil
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return "", fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	value := rawValue
	parsed, err := url.Parse(value)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Host == "" || parsed.User != nil || parsed.Path != "" ||
		parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", fmt.Errorf("%s must be an absolute HTTP origin without path, query, or fragment", name)
	}
	if port := parsed.Port(); port != "" {
		portNumber, portErr := strconv.Atoi(port)
		if portErr != nil || portNumber < 1 || portNumber > 65535 {
			return "", fmt.Errorf("%s contains an invalid port", name)
		}
	}
	return value, nil
}

func requiredExactEnvironment(name string, rawValue string) (string, error) {
	if rawValue == "" {
		return "", fmt.Errorf("%s is required", name)
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return "", fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	return rawValue, nil
}

func optionalExactEnvironment(name string, rawValue string) (string, error) {
	if rawValue == "" {
		return "", nil
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return "", fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	return rawValue, nil
}

func parseOptionalPositiveInt64(name string, rawValue string) (*int64, error) {
	if rawValue == "" {
		return nil, nil
	}
	if rawValue != strings.TrimSpace(rawValue) {
		return nil, fmt.Errorf("%s must not contain surrounding whitespace", name)
	}
	parsed, err := strconv.ParseInt(rawValue, 10, 64)
	if err != nil || parsed <= 0 {
		return nil, fmt.Errorf("%s must be a positive integer", name)
	}
	return &parsed, nil
}

func parseRequiredBoolean(name string, rawValue string) (bool, error) {
	switch rawValue {
	case "true":
		return true, nil
	case "false":
		return false, nil
	default:
		return false, fmt.Errorf("%s must be exactly true or false", name)
	}
}

func commaSeparatedExactValues(name string, rawValue string) ([]string, error) {
	if rawValue == "" {
		return []string{}, nil
	}
	values := make([]string, 0)
	seen := map[string]struct{}{}
	for _, value := range strings.Split(rawValue, ",") {
		if value == "" {
			return nil, fmt.Errorf("%s must contain non-empty items", name)
		}
		if value != strings.TrimSpace(value) {
			return nil, fmt.Errorf("%s item must not contain surrounding whitespace", name)
		}
		if _, exists := seen[value]; exists {
			continue
		}
		seen[value] = struct{}{}
		values = append(values, value)
	}
	return values, nil
}
