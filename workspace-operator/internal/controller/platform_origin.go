package controller

import (
	"fmt"
	"net/url"
	"strings"
)

func ParsePlatformPublicOrigin(value string) (string, error) {
	rawOrigin := value
	if rawOrigin == "" {
		return "", fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN is required")
	}
	if rawOrigin != strings.TrimSpace(rawOrigin) {
		return "", fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN must be an exact HTTP(S) origin")
	}

	parsed, err := url.Parse(rawOrigin)
	if err != nil {
		return "", fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN is invalid: %w", err)
	}
	if (parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Host == "" || parsed.Hostname() == "" || parsed.User != nil ||
		parsed.Path != "" || parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN must be an exact HTTP(S) origin")
	}
	if strings.Contains(parsed.Hostname(), "*") {
		return "", fmt.Errorf("AILERON_PLATFORM_PUBLIC_ORIGIN must not contain a wildcard host")
	}

	return parsed.Scheme + "://" + parsed.Host, nil
}
