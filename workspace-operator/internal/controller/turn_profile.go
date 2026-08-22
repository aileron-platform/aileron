package controller

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"sort"
	"strconv"
	"strings"
)

const (
	TURNPolicyBackendCilium     = "cilium"
	TURNPolicyBackendKubernetes = "kubernetes"
	TURNPolicyBackendUnenforced = "unenforced"

	TURNDestinationCiliumEntities = "ciliumEntities"
	TURNDestinationCIDRs          = "cidrs"
	TURNDestinationNamespacePods  = "namespacePods"
	TURNDestinationFQDNs          = "fqdns"
	TURNDestinationUnenforced     = "unenforced"

	TURNCredentialIssuerTURNREST = "turnRest"
)

type TURNPolicyDestination struct {
	Kind      string            `json:"kind"`
	Values    []string          `json:"values,omitempty"`
	Namespace string            `json:"namespace,omitempty"`
	PodLabels map[string]string `json:"podLabels,omitempty"`
}

type TURNRelayPortRange struct {
	Min int32 `json:"min"`
	Max int32 `json:"max"`
}

type TURNBackendProfile struct {
	URLs               []string              `json:"urls"`
	ControlDestination TURNPolicyDestination `json:"controlDestination"`
	RelayDestination   TURNPolicyDestination `json:"relayDestination"`
	RelayPortRange     TURNRelayPortRange    `json:"relayPortRange"`
}

type TURNFrontendProfile struct {
	URLs []string `json:"urls"`
}

type TURNCredentialIssuerProfile struct {
	Kind       string `json:"kind"`
	SecretRef  string `json:"secretRef"`
	TTLSeconds int32  `json:"ttlSeconds"`
}

type TURNEvidencePolicy struct {
	IntervalSeconds          int32    `json:"intervalSeconds"`
	TTLSeconds               int32    `json:"ttlSeconds"`
	RequiredFrontendVantages []string `json:"requiredFrontendVantages"`
}

type TURNReachabilityProfile struct {
	ContractVersion  string                      `json:"contractVersion"`
	PolicyBackend    string                      `json:"policyBackend"`
	Backend          TURNBackendProfile          `json:"backend"`
	Frontend         TURNFrontendProfile         `json:"frontend"`
	CredentialIssuer TURNCredentialIssuerProfile `json:"credentialIssuer"`
	Evidence         TURNEvidencePolicy          `json:"evidence"`
}

func ParseTURNReachabilityProfile(raw string) (*TURNReachabilityProfile, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}
	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.DisallowUnknownFields()
	profile := &TURNReachabilityProfile{}
	if err := decoder.Decode(profile); err != nil {
		return nil, fmt.Errorf("decode TURN reachability profile: %w", err)
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, fmt.Errorf("TURN reachability profile contains multiple JSON values")
		}
		return nil, fmt.Errorf("decode trailing TURN reachability profile data: %w", err)
	}
	if err := profile.Validate(); err != nil {
		return nil, err
	}
	canonical := profile.canonicalProfile()
	profile = &canonical
	return profile, nil
}

func (profile TURNReachabilityProfile) Validate() error {
	if profile.ContractVersion != BrowserConnectivityContractVersion {
		return fmt.Errorf("unsupported Browser connectivity contract version %q", profile.ContractVersion)
	}
	switch profile.PolicyBackend {
	case TURNPolicyBackendCilium, TURNPolicyBackendKubernetes, TURNPolicyBackendUnenforced:
	default:
		return fmt.Errorf("unsupported TURN policy backend %q", profile.PolicyBackend)
	}
	if len(profile.Backend.URLs) == 0 || len(profile.Frontend.URLs) == 0 {
		return fmt.Errorf("TURN backend and frontend URLs are required")
	}
	for _, endpoint := range append(append([]string{}, profile.Backend.URLs...), profile.Frontend.URLs...) {
		if _, ok := parseTURNServerAddress(strings.TrimSpace(endpoint)); !ok {
			return fmt.Errorf("invalid TURN endpoint %q", endpoint)
		}
	}
	if err := validateTURNDestination(profile.PolicyBackend, profile.Backend.ControlDestination, false); err != nil {
		return fmt.Errorf("invalid TURN control destination: %w", err)
	}
	if err := validateTURNDestination(profile.PolicyBackend, profile.Backend.RelayDestination, true); err != nil {
		return fmt.Errorf("invalid TURN relay destination: %w", err)
	}
	if profile.Backend.RelayPortRange.Min < 1024 ||
		profile.Backend.RelayPortRange.Max > 65535 ||
		profile.Backend.RelayPortRange.Min > profile.Backend.RelayPortRange.Max {
		return fmt.Errorf("TURN relay port range must be between 1024 and 65535")
	}
	if profile.CredentialIssuer.Kind != TURNCredentialIssuerTURNREST {
		return fmt.Errorf("unsupported TURN credential issuer kind %q", profile.CredentialIssuer.Kind)
	}
	if strings.TrimSpace(profile.CredentialIssuer.SecretRef) == "" ||
		profile.CredentialIssuer.TTLSeconds < 60 {
		return fmt.Errorf("TURN credential issuer kind, secretRef, and TTL of at least 60 seconds are required")
	}
	if profile.Evidence.IntervalSeconds < 1 ||
		profile.Evidence.TTLSeconds < profile.Evidence.IntervalSeconds*2 {
		return fmt.Errorf("TURN evidence TTL must be at least twice the probe interval")
	}
	if len(profile.Evidence.RequiredFrontendVantages) == 0 && profile.PolicyBackend != TURNPolicyBackendUnenforced {
		return fmt.Errorf("at least one required frontend vantage is required")
	}
	for _, vantage := range profile.Evidence.RequiredFrontendVantages {
		if strings.TrimSpace(vantage) == "" {
			return fmt.Errorf("required frontend vantages must not be empty")
		}
	}
	return nil
}

func validateTURNDestination(policyBackend string, destination TURNPolicyDestination, relay bool) error {
	for _, value := range destination.Values {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("destination values must not be empty")
		}
	}
	for key, value := range destination.PodLabels {
		if strings.TrimSpace(key) == "" || strings.TrimSpace(value) == "" {
			return fmt.Errorf("podLabels must contain non-empty entries")
		}
	}
	switch destination.Kind {
	case TURNDestinationCiliumEntities:
		if policyBackend != TURNPolicyBackendCilium || len(destination.Values) == 0 {
			return fmt.Errorf("ciliumEntities requires the Cilium policy backend and at least one value")
		}
	case TURNDestinationCIDRs:
		if len(destination.Values) == 0 {
			return fmt.Errorf("cidrs requires at least one value")
		}
		for _, value := range destination.Values {
			if _, _, err := net.ParseCIDR(strings.TrimSpace(value)); err != nil {
				return fmt.Errorf("invalid CIDR %q", value)
			}
		}
	case TURNDestinationFQDNs:
		if relay {
			return fmt.Errorf("relay destinations cannot use FQDNs")
		}
		if policyBackend != TURNPolicyBackendCilium || len(destination.Values) == 0 {
			return fmt.Errorf("fqdns requires the Cilium policy backend and at least one value")
		}
	case TURNDestinationNamespacePods:
		if strings.TrimSpace(destination.Namespace) == "" || len(destination.PodLabels) == 0 {
			return fmt.Errorf("namespacePods requires namespace and podLabels")
		}
	case TURNDestinationUnenforced:
		if policyBackend != TURNPolicyBackendUnenforced {
			return fmt.Errorf("unenforced destination requires the unenforced policy backend")
		}
	default:
		return fmt.Errorf("unsupported destination kind %q", destination.Kind)
	}
	return nil
}

func (profile TURNReachabilityProfile) Revision() string {
	canonical, err := json.Marshal(profile.canonicalProfile())
	if err != nil {
		panic(err)
	}
	digest := sha256.Sum256(canonical)
	return "sha256:" + hex.EncodeToString(digest[:])
}

func (profile TURNReachabilityProfile) canonicalProfile() TURNReachabilityProfile {
	result := profile
	result.Backend.URLs = normalizedOrderedStrings(profile.Backend.URLs)
	result.Frontend.URLs = normalizedOrderedStrings(profile.Frontend.URLs)
	result.Backend.ControlDestination = canonicalTURNDestination(profile.Backend.ControlDestination)
	result.Backend.RelayDestination = canonicalTURNDestination(profile.Backend.RelayDestination)
	result.Evidence.RequiredFrontendVantages = normalizedStringSet(profile.Evidence.RequiredFrontendVantages)
	result.CredentialIssuer.SecretRef = strings.TrimSpace(profile.CredentialIssuer.SecretRef)
	return result
}

func canonicalTURNDestination(destination TURNPolicyDestination) TURNPolicyDestination {
	result := destination
	result.Values = normalizedStringSet(destination.Values)
	result.Namespace = strings.TrimSpace(destination.Namespace)
	if destination.PodLabels != nil {
		result.PodLabels = make(map[string]string, len(destination.PodLabels))
		for key, value := range destination.PodLabels {
			result.PodLabels[strings.TrimSpace(key)] = strings.TrimSpace(value)
		}
	}
	return result
}

func normalizedOrderedStrings(values []string) []string {
	result := make([]string, len(values))
	for index, value := range values {
		result[index] = strings.TrimSpace(value)
	}
	return result
}

func normalizedStringSet(values []string) []string {
	unique := make(map[string]struct{}, len(values))
	for _, value := range values {
		unique[strings.TrimSpace(value)] = struct{}{}
	}
	result := make([]string, 0, len(unique))
	for value := range unique {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func destinationRule(destination TURNPolicyDestination) map[string]interface{} {
	switch destination.Kind {
	case TURNDestinationCiliumEntities:
		values := make([]interface{}, 0, len(destination.Values))
		for _, value := range destination.Values {
			values = append(values, value)
		}
		return map[string]interface{}{"toEntities": values}
	case TURNDestinationCIDRs:
		values := make([]interface{}, 0, len(destination.Values))
		for _, value := range destination.Values {
			values = append(values, value)
		}
		return map[string]interface{}{"toCIDR": values}
	case TURNDestinationFQDNs:
		values := make([]interface{}, 0, len(destination.Values))
		for _, value := range destination.Values {
			values = append(values, map[string]interface{}{"matchName": strings.ToLower(value)})
		}
		return map[string]interface{}{"toFQDNs": values}
	case TURNDestinationNamespacePods:
		labels := map[string]interface{}{
			"k8s:io.kubernetes.pod.namespace": destination.Namespace,
		}
		keys := make([]string, 0, len(destination.PodLabels))
		for key := range destination.PodLabels {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			labels["k8s:"+key] = destination.PodLabels[key]
		}
		return map[string]interface{}{"toEndpoints": []interface{}{map[string]interface{}{"matchLabels": labels}}}
	default:
		return nil
	}
}

func browserTURNEgressRules(profile *TURNReachabilityProfile) []interface{} {
	if profile == nil || profile.PolicyBackend == TURNPolicyBackendUnenforced {
		return nil
	}
	controlPorts := map[string]map[string]interface{}{}
	for _, endpoint := range profile.Backend.URLs {
		server, ok := parseTURNServerAddress(endpoint)
		if !ok {
			continue
		}
		for _, protocol := range server.protocols {
			key := protocol + ":" + server.port
			controlPorts[key] = map[string]interface{}{"port": server.port, "protocol": protocol}
		}
	}
	portKeys := make([]string, 0, len(controlPorts))
	for key := range controlPorts {
		portKeys = append(portKeys, key)
	}
	sort.Strings(portKeys)
	ports := make([]interface{}, 0, len(portKeys))
	for _, key := range portKeys {
		ports = append(ports, controlPorts[key])
	}
	control := destinationRule(profile.Backend.ControlDestination)
	control["toPorts"] = []interface{}{map[string]interface{}{"ports": ports}}
	relay := destinationRule(profile.Backend.RelayDestination)
	relay["toPorts"] = []interface{}{map[string]interface{}{"ports": []interface{}{map[string]interface{}{
		"port":     strconv.Itoa(int(profile.Backend.RelayPortRange.Min)),
		"endPort":  int64(profile.Backend.RelayPortRange.Max),
		"protocol": "UDP",
	}}}}
	return []interface{}{control, relay}
}
