package controller

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestTURNProbeServerStartsWithRevisionFencedPendingEvidence(t *testing.T) {
	t.Parallel()
	profile := turnProfileForTest("turn:turn.internal.example:3478")
	probe, err := NewTURNProbeServer(
		*profile,
		"7",
		`[{"urls":["turn:turn.internal.example:3478"],"username":"user","credential":"secret"}]`,
		"shared-secret",
		"backend:workspace-1",
		"installation-1",
	)
	if err != nil {
		t.Fatalf("NewTURNProbeServer() error = %v", err)
	}

	request := httptest.NewRequest(http.MethodGet, "/v1/evidence", nil)
	response := httptest.NewRecorder()
	probe.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	var snapshot TURNPathEvidenceSnapshot
	if err := json.Unmarshal(response.Body.Bytes(), &snapshot); err != nil {
		t.Fatalf("decode evidence: %v", err)
	}
	if snapshot.LatestAttempt.Outcome != TURNProbeOutcomeFailure ||
		snapshot.LatestAttempt.ErrorCode != "TURN_PROBE_PENDING" ||
		snapshot.LatestAttempt.ProfileRevision != profile.Revision() ||
		snapshot.LatestAttempt.CredentialRevision != "7" ||
		snapshot.LatestAttempt.Producer.InstallationID != "installation-1" {
		t.Fatalf("unexpected evidence snapshot: %#v", snapshot)
	}
}

func TestDecodeTURNURLsAcceptsWebRTCStringAndArrayForms(t *testing.T) {
	t.Parallel()
	for _, raw := range []string{
		`"turn:turn.example.com:3478"`,
		`["turn:turn.example.com:3478","turn:turn.example.com:3478?transport=tcp"]`,
	} {
		urls, err := decodeTURNURLs(json.RawMessage(raw))
		if err != nil || len(urls) == 0 {
			t.Fatalf("decodeTURNURLs(%s) = %#v, %v", raw, urls, err)
		}
	}
}
