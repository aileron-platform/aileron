package controller

import (
	"strings"
	"testing"
)

func TestParsePlatformDatabaseEgressDestinationAcceptsSupportedTargets(t *testing.T) {
	testCases := []string{
		`{"kind":"namespacePods","namespace":"platform-data","podLabels":{"app.kubernetes.io/name":"postgres"}}`,
		`{"kind":"cidrs","values":["10.24.0.0/16"]}`,
		`{"kind":"fqdns","values":["database.example.com"]}`,
	}
	for _, raw := range testCases {
		destination, err := ParsePlatformDatabaseEgressDestination(raw)
		if err != nil {
			t.Fatalf("parse %s: %v", raw, err)
		}
		if destination == nil {
			t.Fatalf("parse %s returned no destination", raw)
		}
	}
}

func TestParsePlatformDatabaseEgressDestinationRejectsAmbiguousTargets(t *testing.T) {
	testCases := []struct {
		raw       string
		wantError string
	}{
		{raw: `{"kind":"namespacePods","namespace":"platform-data"}`, wantError: "namespace and podLabels"},
		{raw: `{"kind":"cidrs","values":["not-a-cidr"]}`, wantError: "invalid CIDR"},
		{raw: `{"kind":"fqdns","values":["*.example.com"]}`, wantError: "canonical exact hostname"},
		{raw: `{"kind":"namespacePods","namespace":"platform-data","podLabels":{"app":" postgres "}}`, wantError: "surrounding whitespace"},
		{raw: `{"kind":"ciliumEntities","values":["world"]}`, wantError: "unsupported"},
		{raw: `{"kind":"fqdns","values":["database.example.com"],"unknown":true}`, wantError: "unknown field"},
		{raw: `{"kind":"fqdns","values":["database.example.com"]}{}`, wantError: "multiple JSON values"},
	}
	for _, testCase := range testCases {
		_, err := ParsePlatformDatabaseEgressDestination(testCase.raw)
		if err == nil || !strings.Contains(err.Error(), testCase.wantError) {
			t.Fatalf("parse %s error = %v, want containing %q", testCase.raw, err, testCase.wantError)
		}
	}
}
