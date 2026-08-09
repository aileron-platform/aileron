package controller

import "testing"

func TestParsePlatformPublicOriginAcceptsExactOrigin(t *testing.T) {
	origin, err := ParsePlatformPublicOrigin("https://aileron.example.com")
	if err != nil {
		t.Fatalf("parse Platform Public Origin: %v", err)
	}
	if origin != "https://aileron.example.com" {
		t.Fatalf("Platform Public Origin = %q, want https://aileron.example.com", origin)
	}
}

func TestParsePlatformPublicOriginRejectsNonOriginURLs(t *testing.T) {
	for name, value := range map[string]string{
		"empty":        "",
		"missing host": "https://",
		"path":         "https://aileron.example.com/workspace",
		"trailing slash": "https://aileron.example.com/",
		"surrounding whitespace": " https://aileron.example.com ",
		"query":        "https://aileron.example.com?tenant=a",
		"fragment":     "https://aileron.example.com#workspace",
		"userinfo":     "https://user@aileron.example.com",
		"wildcard":     "https://*.aileron.example.com",
		"unsupported":  "ftp://aileron.example.com",
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := ParsePlatformPublicOrigin(value); err == nil {
				t.Fatalf("ParsePlatformPublicOrigin(%q) succeeded, want error", value)
			}
		})
	}
}
