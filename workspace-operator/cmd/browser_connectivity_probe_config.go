package main

import (
	"fmt"
	"os"
	"strings"

	"workspace-operator/internal/controller"
)

type browserConnectivityProbeConfiguration struct {
	turnProfile           controller.TURNReachabilityProfile
	credentialRevision    string
	backendICEServersJSON string
	turnRESTSharedSecret  string
	probeIdentity         string
	installationID        string
}

func loadBrowserConnectivityProbeConfiguration() (browserConnectivityProbeConfiguration, error) {
	return loadBrowserConnectivityProbeConfigurationFromEnvironment(os.Getenv)
}

func loadBrowserConnectivityProbeConfigurationFromEnvironment(
	readEnvironment environmentReader,
) (browserConnectivityProbeConfiguration, error) {
	profile, err := loadTURNProfile(readEnvironment)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	if profile == nil {
		return browserConnectivityProbeConfiguration{}, fmt.Errorf("TURN reachability profile is required")
	}
	credentialRevision, err := requiredExactEnvironment(
		"TURN_CREDENTIAL_REVISION",
		readEnvironment("TURN_CREDENTIAL_REVISION"),
	)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	backendICEServersJSON, err := readRequiredSecretFile(
		"TURN_BACKEND_ICE_SERVERS_JSON_FILE",
		readEnvironment("TURN_BACKEND_ICE_SERVERS_JSON_FILE"),
	)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	turnRESTSharedSecret, err := readOptionalSecretFile(
		"TURN_REST_SHARED_SECRET_FILE",
		readEnvironment("TURN_REST_SHARED_SECRET_FILE"),
		profile.CredentialIssuer.Kind == controller.TURNCredentialIssuerTURNREST,
	)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	probeIdentity, err := requiredExactEnvironment(
		"TURN_PROBE_IDENTITY",
		readEnvironment("TURN_PROBE_IDENTITY"),
	)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	installationID, err := requiredExactEnvironment(
		"AILERON_INSTALLATION_ID",
		readEnvironment("AILERON_INSTALLATION_ID"),
	)
	if err != nil {
		return browserConnectivityProbeConfiguration{}, err
	}
	return browserConnectivityProbeConfiguration{
		turnProfile:           *profile,
		credentialRevision:    credentialRevision,
		backendICEServersJSON: backendICEServersJSON,
		turnRESTSharedSecret:  turnRESTSharedSecret,
		probeIdentity:         probeIdentity,
		installationID:        installationID,
	}, nil
}

func loadTURNProfile(readEnvironment environmentReader) (*controller.TURNReachabilityProfile, error) {
	profilePath, err := optionalExactEnvironment(
		"TURN_REACHABILITY_PROFILE_FILE",
		readEnvironment("TURN_REACHABILITY_PROFILE_FILE"),
	)
	if err != nil {
		return nil, err
	}
	profileJSON := readEnvironment("TURN_REACHABILITY_PROFILE_JSON")
	if profilePath != "" {
		raw, readErr := os.ReadFile(profilePath)
		if readErr != nil {
			return nil, fmt.Errorf("read TURN reachability profile: %w", readErr)
		}
		return controller.ParseTURNReachabilityProfile(string(raw))
	}
	if profileJSON != "" && profileJSON != strings.TrimSpace(profileJSON) {
		return nil, fmt.Errorf("TURN_REACHABILITY_PROFILE_JSON must not contain surrounding whitespace")
	}
	return controller.ParseTURNReachabilityProfile(profileJSON)
}

func readOptionalSecretFile(name string, rawPath string, required bool) (string, error) {
	if !required && rawPath == "" {
		return "", nil
	}
	return readRequiredSecretFile(name, rawPath)
}
