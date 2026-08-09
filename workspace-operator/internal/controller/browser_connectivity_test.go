package controller

import (
	"encoding/json"
	"errors"
	"os"
	"strings"
	"testing"
	"time"
)

type evaluatorFixture struct {
	CredentialRevision string `json:"credentialRevision"`
	Now                string `json:"now"`
	Cases              []struct {
		Name         string                               `json:"name"`
		Backend      *TURNPathEvidenceSnapshot            `json:"backend"`
		BackendRef   string                               `json:"backendRef"`
		BackendError string                               `json:"backendError"`
		Frontend     map[string]*TURNPathEvidenceSnapshot `json:"frontend"`
		Expected     struct {
			State         string  `json:"state"`
			Admission     string  `json:"admission"`
			BackendState  string  `json:"backendState"`
			FrontendState string  `json:"frontendState"`
			Reason        string  `json:"reason"`
			ErrorCode     *string `json:"errorCode"`
		} `json:"expected"`
	} `json:"cases"`
}

func TestEvaluateBrowserConnectivityMatchesSharedFixtures(t *testing.T) {
	profileRaw, err := os.ReadFile("/contracts/browser-connectivity/turn-reachability-profile.json")
	if err != nil {
		t.Fatalf("read profile: %v", err)
	}
	profile, err := ParseTURNReachabilityProfile(string(profileRaw))
	if err != nil {
		t.Fatalf("parse profile: %v", err)
	}
	fixtureRaw, err := os.ReadFile("/contracts/browser-connectivity/evaluator-cases.json")
	if err != nil {
		t.Fatalf("read evaluator fixtures: %v", err)
	}
	var fixture evaluatorFixture
	if err := json.Unmarshal(fixtureRaw, &fixture); err != nil {
		t.Fatalf("decode evaluator fixtures: %v", err)
	}
	now, err := time.Parse(time.RFC3339, fixture.Now)
	if err != nil {
		t.Fatalf("parse fixture authority time: %v", err)
	}
	backends := map[string]*TURNPathEvidenceSnapshot{}
	for index := range fixture.Cases {
		item := &fixture.Cases[index]
		if item.Backend != nil {
			backends[item.Name] = item.Backend
		}
	}
	for index := range fixture.Cases {
		item := &fixture.Cases[index]
		t.Run(item.Name, func(t *testing.T) {
			backend := item.Backend
			if item.BackendRef != "" {
				backend = backends[item.BackendRef]
			}
			var backendErr error
			if item.BackendError != "" {
				backendErr = errors.New(item.BackendError)
			}
			status := projectBrowserConnectivity(
				profile, fixture.CredentialRevision, backend, backendErr,
				item.Frontend, map[string]error{}, now,
			)
			if status.State != item.Expected.State ||
				status.Admission != item.Expected.Admission ||
				status.BackendState != item.Expected.BackendState ||
				status.FrontendState != item.Expected.FrontendState {
				t.Fatalf("projection = %#v, expected = %#v", status, item.Expected)
			}
			expectedError := ""
			if item.Expected.ErrorCode != nil {
				expectedError = *item.Expected.ErrorCode
			}
			if status.ErrorCode != expectedError {
				t.Fatalf("errorCode = %q, want %q", status.ErrorCode, expectedError)
			}
			if status.Reason != item.Expected.Reason {
				t.Fatalf("reason = %q, want %q", status.Reason, item.Expected.Reason)
			}
		})
	}
}

func TestEvidenceFreshnessRejectsEitherRevisionMismatch(t *testing.T) {
	now := time.Now().UTC()
	evidence := TURNPathEvidence{
		TURNProbeAttempt: TURNProbeAttempt{
			ContractVersion:    BrowserConnectivityContractVersion,
			ProfileRevision:    "sha256:" + strings.Repeat("a", 64),
			CredentialRevision: "credential-1",
			Outcome:            TURNProbeOutcomeSuccess,
		},
		AcceptedAt: now.Add(-time.Second),
		ExpiresAt:  now.Add(time.Minute),
	}
	if evidenceIsFresh(evidence, "different-profile", "credential-1", now) ||
		evidenceIsFresh(evidence, evidence.ProfileRevision, "different-credential", now) {
		t.Fatal("revision-mismatched evidence was accepted")
	}
}

func TestEvidenceSnapshotRejectsCrossProducerLastSuccess(t *testing.T) {
	now := time.Now().UTC()
	latest := TURNPathEvidence{
		TURNProbeAttempt: TURNProbeAttempt{
			ContractVersion: BrowserConnectivityContractVersion,
			Producer:        TURNPathEvidenceProducer{InstallationID: "install-1", VantageID: "host"},
			ProfileRevision: "sha256:" + strings.Repeat("a", 64), CredentialRevision: "credential-1",
			Outcome: TURNProbeOutcomeFailure,
		},
		AcceptedAt: now, ExpiresAt: now.Add(time.Minute),
	}
	lastSuccess := latest
	lastSuccess.Outcome = TURNProbeOutcomeSuccess
	lastSuccess.Producer.VantageID = "other"

	if evidenceSnapshotIsValid(TURNPathEvidenceSnapshot{
		ContractVersion: BrowserConnectivityContractVersion,
		LatestAttempt:   latest,
		LastSuccess:     &lastSuccess,
	}, "host") {
		t.Fatal("cross-producer last success was accepted")
	}
}
