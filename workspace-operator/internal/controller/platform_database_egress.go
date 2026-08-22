package controller

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"strings"
)

func ParsePlatformDatabaseEgressDestination(raw string) (*TURNPolicyDestination, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}

	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.DisallowUnknownFields()
	destination := &TURNPolicyDestination{}
	if err := decoder.Decode(destination); err != nil {
		return nil, fmt.Errorf("decode platform database egress destination: %w", err)
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, fmt.Errorf("platform database egress destination contains multiple JSON values")
		}
		return nil, fmt.Errorf("decode trailing platform database egress destination data: %w", err)
	}

	switch destination.Kind {
	case TURNDestinationCIDRs, TURNDestinationFQDNs, TURNDestinationNamespacePods:
	default:
		return nil, fmt.Errorf("unsupported platform database egress destination kind %q", destination.Kind)
	}
	for _, value := range destination.Values {
		if value != strings.TrimSpace(value) {
			return nil, fmt.Errorf("platform database egress values must not contain surrounding whitespace")
		}
	}
	if destination.Namespace != strings.TrimSpace(destination.Namespace) {
		return nil, fmt.Errorf("platform database egress namespace must not contain surrounding whitespace")
	}
	for key, value := range destination.PodLabels {
		if key != strings.TrimSpace(key) || value != strings.TrimSpace(value) {
			return nil, fmt.Errorf("platform database egress podLabels must not contain surrounding whitespace")
		}
	}
	if err := validateTURNDestination(TURNPolicyBackendCilium, *destination, false); err != nil {
		return nil, fmt.Errorf("platform database egress destination: %w", err)
	}
	if destination.Kind == TURNDestinationFQDNs {
		for _, domain := range destination.Values {
			if len(domain) > 253 || net.ParseIP(domain) != nil || !firewallDomainPattern.MatchString(domain) {
				return nil, fmt.Errorf("platform database FQDN %q is not a canonical exact hostname", domain)
			}
		}
	}
	canonical := canonicalTURNDestination(*destination)
	return &canonical, nil
}
