package controller

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func newGatewayForTest(t *testing.T) (*ConnectivityEvidenceGateway, time.Time) {
	t.Helper()
	profile := validTURNProfile()
	profile.Evidence.RequiredFrontendVantages = []string{"host"}
	profile.Evidence.TTLSeconds = 90
	profile.CredentialIssuer.TTLSeconds = 300
	iceServers := `[{
		"urls":["turns:turn.example.com:5349"],
		"username":"probe-user",
		"credential":"probe-credential"
	}]`
	gateway, err := NewConnectivityEvidenceGateway(
		profile,
		"installation-1",
		"credential-7",
		iceServers,
		`{"host":"agent-token"}`,
		"internal-token",
		"turn-rest-shared-secret",
	)
	if err != nil {
		t.Fatalf("NewConnectivityEvidenceGateway() error = %v", err)
	}
	now := time.Date(2026, 8, 5, 1, 2, 3, 0, time.UTC)
	gateway.now = func() time.Time { return now }
	return gateway, now
}

func gatewayJSONRequest(t *testing.T, handler http.Handler, method string, path string, token string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var payload []byte
	if body != nil {
		var err error
		payload, err = json.Marshal(body)
		if err != nil {
			t.Fatal(err)
		}
	}
	request := httptest.NewRequest(method, path, bytes.NewReader(payload))
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	return recorder
}

func issueGatewayChallenge(t *testing.T, gateway *ConnectivityEvidenceGateway) ExternalProbeChallenge {
	t.Helper()
	recorder := gatewayJSONRequest(
		t,
		gateway.Handler(),
		http.MethodPost,
		ConnectivityEvidenceGatewayPublicPath+"/v1/challenges",
		"agent-token",
		ExternalProbeChallengeRequest{InstallationID: "installation-1", VantageID: "host"},
	)
	if recorder.Code != http.StatusCreated {
		t.Fatalf("challenge status = %d, body = %s", recorder.Code, recorder.Body.String())
	}
	var challenge ExternalProbeChallenge
	if err := json.Unmarshal(recorder.Body.Bytes(), &challenge); err != nil {
		t.Fatal(err)
	}
	return challenge
}

func TestConnectivityEvidenceGatewayRejectsLegacyPublicRootPaths(t *testing.T) {
	gateway, _ := newGatewayForTest(t)
	for _, path := range []string{"/v1/challenges", "/v1/evidence"} {
		recorder := gatewayJSONRequest(t, gateway.Handler(), http.MethodPost, path, "agent-token", map[string]string{})
		if recorder.Code != http.StatusNotFound {
			t.Fatalf("legacy path %s status = %d, want %d", path, recorder.Code, http.StatusNotFound)
		}
	}
}

func TestConnectivityEvidenceGatewayAcceptsFreshOneTimeEvidence(t *testing.T) {
	gateway, now := newGatewayForTest(t)
	challenge := issueGatewayChallenge(t, gateway)
	measuredAt := now.Add(24 * time.Hour)
	attempt := TURNProbeAttempt{
		ContractVersion: BrowserConnectivityContractVersion,
		Producer: TURNPathEvidenceProducer{
			InstallationID: "installation-1",
			VantageID:      "host",
		},
		ProfileRevision:    challenge.ProfileRevision,
		CredentialRevision: challenge.CredentialRevision,
		Outcome:            TURNProbeOutcomeSuccess,
		MeasuredAt:         &measuredAt,
		RelayAddress:       "203.0.113.20:49160",
	}
	submission := ExternalProbeSubmission{
		ChallengeID:    challenge.ChallengeID,
		Nonce:          challenge.Nonce,
		InstallationID: "installation-1",
		VantageID:      "host",
		Attempt:        attempt,
	}
	recorder := gatewayJSONRequest(t, gateway.Handler(), http.MethodPost, ConnectivityEvidenceGatewayPublicPath+"/v1/evidence", "agent-token", submission)
	if recorder.Code != http.StatusNoContent {
		t.Fatalf("submission status = %d, body = %s", recorder.Code, recorder.Body.String())
	}

	replay := gatewayJSONRequest(t, gateway.Handler(), http.MethodPost, ConnectivityEvidenceGatewayPublicPath+"/v1/evidence", "agent-token", submission)
	if replay.Code != http.StatusConflict {
		t.Fatalf("replay status = %d, want %d", replay.Code, http.StatusConflict)
	}

	readPath := "/v1/evidence/" + challenge.ProfileRevision + "/host"
	unauthorized := gatewayJSONRequest(t, gateway.Handler(), http.MethodGet, readPath, "agent-token", nil)
	if unauthorized.Code != http.StatusUnauthorized {
		t.Fatalf("external read status = %d, want %d", unauthorized.Code, http.StatusUnauthorized)
	}
	read := gatewayJSONRequest(t, gateway.Handler(), http.MethodGet, readPath, "internal-token", nil)
	if read.Code != http.StatusOK {
		t.Fatalf("internal read status = %d, body = %s", read.Code, read.Body.String())
	}
	var snapshot TURNPathEvidenceSnapshot
	if err := json.Unmarshal(read.Body.Bytes(), &snapshot); err != nil {
		t.Fatal(err)
	}
	if !snapshot.LatestAttempt.AcceptedAt.Equal(now) ||
		!snapshot.LatestAttempt.ExpiresAt.Equal(now.Add(90*time.Second)) ||
		snapshot.LastSuccess == nil {
		t.Fatalf("authority did not stamp evidence: %#v", snapshot)
	}
}

func TestConnectivityEvidenceGatewayRejectsIdentityAndRevisionMismatch(t *testing.T) {
	gateway, _ := newGatewayForTest(t)
	unauthorized := gatewayJSONRequest(
		t,
		gateway.Handler(),
		http.MethodPost,
		ConnectivityEvidenceGatewayPublicPath+"/v1/challenges",
		"wrong-token",
		ExternalProbeChallengeRequest{InstallationID: "installation-1", VantageID: "host"},
	)
	if unauthorized.Code != http.StatusUnauthorized {
		t.Fatalf("challenge status = %d, want %d", unauthorized.Code, http.StatusUnauthorized)
	}

	challenge := issueGatewayChallenge(t, gateway)
	recorder := gatewayJSONRequest(t, gateway.Handler(), http.MethodPost, ConnectivityEvidenceGatewayPublicPath+"/v1/evidence", "agent-token", ExternalProbeSubmission{
		ChallengeID:    challenge.ChallengeID,
		Nonce:          challenge.Nonce,
		InstallationID: "installation-1",
		VantageID:      "host",
		Attempt: TURNProbeAttempt{
			ContractVersion:    BrowserConnectivityContractVersion,
			Producer:           TURNPathEvidenceProducer{InstallationID: "installation-1", VantageID: "host"},
			ProfileRevision:    "stale-profile",
			CredentialRevision: challenge.CredentialRevision,
			Outcome:            TURNProbeOutcomeSuccess,
			RelayAddress:       "203.0.113.20:49160",
		},
	})
	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("submission status = %d, want %d", recorder.Code, http.StatusUnprocessableEntity)
	}
}

func TestConnectivityEvidenceGatewayRetainsSameRevisionLastSuccess(t *testing.T) {
	gateway, now := newGatewayForTest(t)
	submit := func(outcome string, relayAddress string, errorCode string) {
		challenge := issueGatewayChallenge(t, gateway)
		recorder := gatewayJSONRequest(t, gateway.Handler(), http.MethodPost, ConnectivityEvidenceGatewayPublicPath+"/v1/evidence", "agent-token", ExternalProbeSubmission{
			ChallengeID:    challenge.ChallengeID,
			Nonce:          challenge.Nonce,
			InstallationID: "installation-1",
			VantageID:      "host",
			Attempt: TURNProbeAttempt{
				ContractVersion:    BrowserConnectivityContractVersion,
				Producer:           TURNPathEvidenceProducer{InstallationID: "installation-1", VantageID: "host"},
				ProfileRevision:    challenge.ProfileRevision,
				CredentialRevision: challenge.CredentialRevision,
				Outcome:            outcome,
				RelayAddress:       relayAddress,
				ErrorCode:          errorCode,
			},
		})
		if recorder.Code != http.StatusNoContent {
			t.Fatalf("submission status = %d, body = %s", recorder.Code, recorder.Body.String())
		}
	}
	submit(TURNProbeOutcomeSuccess, "203.0.113.20:49160", "")
	gateway.now = func() time.Time { return now.Add(10 * time.Second) }
	submit(TURNProbeOutcomeFailure, "", "TURN_RELAY_UNAVAILABLE")

	profileRevision := gateway.profile.Revision()
	read := gatewayJSONRequest(t, gateway.Handler(), http.MethodGet, "/v1/evidence/"+profileRevision+"/host", "internal-token", nil)
	if read.Code != http.StatusOK {
		t.Fatalf("read status = %d, body = %s", read.Code, read.Body.String())
	}
	var snapshot TURNPathEvidenceSnapshot
	if err := json.Unmarshal(read.Body.Bytes(), &snapshot); err != nil {
		t.Fatal(err)
	}
	if snapshot.LatestAttempt.Outcome != TURNProbeOutcomeFailure || snapshot.LastSuccess == nil ||
		snapshot.LastSuccess.Outcome != TURNProbeOutcomeSuccess {
		t.Fatalf("snapshot did not retain bounded success: %#v", snapshot)
	}
}

func TestConnectivityEvidenceGatewayIssuesExpiringTURNRESTCredential(t *testing.T) {
	profile := validTURNProfile()
	profile.CredentialIssuer.Kind = TURNCredentialIssuerTURNREST
	profile.CredentialIssuer.TTLSeconds = 300
	profile.Evidence.RequiredFrontendVantages = []string{"host"}
	gateway, err := NewConnectivityEvidenceGateway(
		profile,
		"installation-1",
		"credential-7",
		`[{"urls":["turns:turn.example.com:5349"],"username":"","credential":""}]`,
		`{"host":"agent-token"}`,
		"internal-token",
		"turn-rest-shared-secret",
	)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 8, 5, 1, 2, 3, 0, time.UTC)
	gateway.now = func() time.Time { return now }
	challenge := issueGatewayChallenge(t, gateway)
	if len(challenge.ICEServers) != 1 {
		t.Fatalf("ICE server count = %d, want 1", len(challenge.ICEServers))
	}
	wantPrefix := "1785892023:installation-1:host"
	if challenge.ICEServers[0].Username != wantPrefix {
		t.Fatalf("TURN REST username = %q, want %q", challenge.ICEServers[0].Username, wantPrefix)
	}
	if challenge.ICEServers[0].Credential == "" ||
		challenge.ICEServers[0].Credential == "turn-rest-shared-secret" {
		t.Fatal("TURN REST credential must be an HMAC and must not expose the shared secret")
	}
}
