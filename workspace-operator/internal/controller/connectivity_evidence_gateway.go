package controller

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1" //nolint:gosec // TURN REST credentials require HMAC-SHA1 by protocol.
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

const maxConnectivityEvidenceBodyBytes = 64 * 1024

const ConnectivityEvidenceGatewayPublicPath = "/api/v1/connectivity-evidence"

type ExternalProbeChallengeRequest struct {
	InstallationID string `json:"installationId"`
	VantageID      string `json:"vantageId"`
}

type ExternalProbeChallenge struct {
	ChallengeID        string          `json:"challengeId"`
	Nonce              string          `json:"nonce"`
	InstallationID     string          `json:"installationId"`
	VantageID          string          `json:"vantageId"`
	ProfileRevision    string          `json:"profileRevision"`
	CredentialRevision string          `json:"credentialRevision"`
	FrontendURLs       []string        `json:"frontendUrls"`
	ICEServers         []turnICEServer `json:"iceServers"`
	IssuedAt           time.Time       `json:"issuedAt"`
	ExpiresAt          time.Time       `json:"expiresAt"`
}

type ExternalProbeSubmission struct {
	ChallengeID    string           `json:"challengeId"`
	Nonce          string           `json:"nonce"`
	InstallationID string           `json:"installationId"`
	VantageID      string           `json:"vantageId"`
	Attempt        TURNProbeAttempt `json:"attempt"`
}

type storedExternalChallenge struct {
	challenge ExternalProbeChallenge
	used      bool
}

type ConnectivityEvidenceGateway struct {
	profile              TURNReachabilityProfile
	installationID       string
	credentialRevision   string
	iceServers           []turnICEServer
	agentTokens          map[string]string
	internalToken        string
	turnRESTSharedSecret string
	now                  func() time.Time

	mu         sync.RWMutex
	challenges map[string]*storedExternalChallenge
	evidence   map[string]TURNPathEvidenceSnapshot
}

func NewConnectivityEvidenceGateway(
	profile TURNReachabilityProfile,
	installationID string,
	credentialRevision string,
	iceServersJSON string,
	agentTokensJSON string,
	internalToken string,
	turnRESTSharedSecret string,
) (*ConnectivityEvidenceGateway, error) {
	installationID = strings.TrimSpace(installationID)
	credentialRevision = strings.TrimSpace(credentialRevision)
	internalToken = strings.TrimSpace(internalToken)
	if installationID == "" || credentialRevision == "" || internalToken == "" {
		return nil, fmt.Errorf("installation ID, credential revision, and internal token are required")
	}
	var iceServers []turnICEServer
	if strings.TrimSpace(iceServersJSON) == "" {
		for _, endpoint := range profile.Frontend.URLs {
			encoded, err := json.Marshal([]string{endpoint})
			if err != nil {
				return nil, fmt.Errorf("encode frontend TURN endpoint: %w", err)
			}
			iceServers = append(iceServers, turnICEServer{URLs: encoded})
		}
	} else if err := json.Unmarshal([]byte(iceServersJSON), &iceServers); err != nil {
		return nil, fmt.Errorf("decode external probe ICE servers")
	}
	if len(iceServers) == 0 {
		return nil, fmt.Errorf("external probe ICE servers are required")
	}
	for index, server := range iceServers {
		if _, err := decodeTURNURLs(server.URLs); err != nil {
			return nil, fmt.Errorf("external probe ICE server %d requires TURN URLs", index)
		}
	}
	turnRESTSharedSecret = strings.TrimSpace(turnRESTSharedSecret)
	if turnRESTSharedSecret == "" {
		return nil, fmt.Errorf("TURN REST shared secret is required")
	}
	var agentTokens map[string]string
	if err := json.Unmarshal([]byte(agentTokensJSON), &agentTokens); err != nil || len(agentTokens) == 0 {
		return nil, fmt.Errorf("decode external probe agent tokens")
	}
	for vantage, token := range agentTokens {
		if strings.TrimSpace(vantage) == "" || strings.TrimSpace(token) == "" {
			return nil, fmt.Errorf("external probe agent token entries must not be empty")
		}
		if !containsString(profile.Evidence.RequiredFrontendVantages, vantage) {
			return nil, fmt.Errorf("external probe vantage %q is not declared by the TURN profile", vantage)
		}
	}
	for _, vantage := range profile.Evidence.RequiredFrontendVantages {
		if strings.TrimSpace(agentTokens[vantage]) == "" {
			return nil, fmt.Errorf("external probe vantage %q has no credential", vantage)
		}
	}
	return &ConnectivityEvidenceGateway{
		profile:              profile,
		installationID:       installationID,
		credentialRevision:   credentialRevision,
		iceServers:           iceServers,
		agentTokens:          agentTokens,
		internalToken:        internalToken,
		turnRESTSharedSecret: turnRESTSharedSecret,
		now:                  func() time.Time { return time.Now().UTC() },
		challenges:           map[string]*storedExternalChallenge{},
		evidence:             map[string]TURNPathEvidenceSnapshot{},
	}, nil
}

func (gateway *ConnectivityEvidenceGateway) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(writer http.ResponseWriter, _ *http.Request) {
		writer.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST "+ConnectivityEvidenceGatewayPublicPath+"/v1/challenges", gateway.handleChallenge)
	mux.HandleFunc("POST "+ConnectivityEvidenceGatewayPublicPath+"/v1/evidence", gateway.handleSubmission)
	mux.HandleFunc("GET /v1/evidence/{profileRevision}/{vantage}", gateway.handleReadEvidence)
	return mux
}

func (gateway *ConnectivityEvidenceGateway) handleChallenge(writer http.ResponseWriter, request *http.Request) {
	var body ExternalProbeChallengeRequest
	if !decodeBoundedJSON(writer, request, &body) {
		return
	}
	if body.InstallationID != gateway.installationID || !gateway.authorizeAgent(request, body.VantageID) {
		writeGatewayError(writer, http.StatusUnauthorized)
		return
	}
	challengeID, err := randomHex(16)
	if err != nil {
		writeGatewayError(writer, http.StatusInternalServerError)
		return
	}
	nonce, err := randomHex(32)
	if err != nil {
		writeGatewayError(writer, http.StatusInternalServerError)
		return
	}
	now := gateway.now()
	challenge := ExternalProbeChallenge{
		ChallengeID:        challengeID,
		Nonce:              nonce,
		InstallationID:     gateway.installationID,
		VantageID:          body.VantageID,
		ProfileRevision:    gateway.profile.Revision(),
		CredentialRevision: gateway.credentialRevision,
		FrontendURLs:       append([]string(nil), gateway.profile.Frontend.URLs...),
		ICEServers:         gateway.challengeICEServers(now, body.VantageID),
		IssuedAt:           now,
		ExpiresAt:          now.Add(time.Duration(gateway.profile.CredentialIssuer.TTLSeconds) * time.Second),
	}
	gateway.mu.Lock()
	gateway.pruneLocked(now)
	gateway.challenges[challengeID] = &storedExternalChallenge{challenge: challenge}
	gateway.mu.Unlock()
	writeGatewayJSON(writer, http.StatusCreated, challenge)
}

func (gateway *ConnectivityEvidenceGateway) challengeICEServers(now time.Time, vantageID string) []turnICEServer {
	servers := append([]turnICEServer(nil), gateway.iceServers...)
	if gateway.profile.CredentialIssuer.Kind != TURNCredentialIssuerTURNREST {
		return servers
	}
	username, credential := issueTURNRESTCredential(
		now,
		gateway.profile.CredentialIssuer.TTLSeconds,
		gateway.turnRESTSharedSecret,
		gateway.installationID+":"+vantageID,
	)
	for index := range servers {
		servers[index].Username = username
		servers[index].Credential = credential
	}
	return servers
}

func issueTURNRESTCredential(
	now time.Time,
	ttlSeconds int32,
	sharedSecret string,
	identity string,
) (string, string) {
	expiry := now.Add(time.Duration(ttlSeconds) * time.Second).Unix()
	username := fmt.Sprintf("%d:%s", expiry, identity)
	mac := hmac.New(sha1.New, []byte(sharedSecret))
	_, _ = mac.Write([]byte(username))
	return username, base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

func (gateway *ConnectivityEvidenceGateway) handleSubmission(writer http.ResponseWriter, request *http.Request) {
	var submission ExternalProbeSubmission
	if !decodeBoundedJSON(writer, request, &submission) {
		return
	}
	if submission.InstallationID != gateway.installationID ||
		!gateway.authorizeAgent(request, submission.VantageID) {
		writeGatewayError(writer, http.StatusUnauthorized)
		return
	}
	now := gateway.now()
	gateway.mu.Lock()
	defer gateway.mu.Unlock()
	gateway.pruneLocked(now)
	stored, ok := gateway.challenges[submission.ChallengeID]
	if !ok || stored.used || stored.challenge.Nonce != submission.Nonce ||
		stored.challenge.InstallationID != submission.InstallationID ||
		stored.challenge.VantageID != submission.VantageID ||
		!now.Before(stored.challenge.ExpiresAt) {
		writeGatewayError(writer, http.StatusConflict)
		return
	}
	stored.used = true
	if err := gateway.validateAttempt(submission.Attempt, stored.challenge); err != nil {
		writeGatewayError(writer, http.StatusUnprocessableEntity)
		return
	}
	key := gateway.evidenceKey(
		submission.Attempt.ProfileRevision,
		submission.Attempt.CredentialRevision,
		submission.VantageID,
	)
	var previousSuccess *TURNPathEvidence
	if previous, exists := gateway.evidence[key]; exists {
		previousSuccess = previous.LastSuccess
	}
	gateway.evidence[key] = newTURNPathEvidenceSnapshot(
		submission.Attempt,
		now,
		gateway.profile.Evidence.TTLSeconds,
		previousSuccess,
	)
	writer.WriteHeader(http.StatusNoContent)
}

func (gateway *ConnectivityEvidenceGateway) handleReadEvidence(writer http.ResponseWriter, request *http.Request) {
	if !constantTimeTokenEqual(bearerToken(request), gateway.internalToken) {
		writeGatewayError(writer, http.StatusUnauthorized)
		return
	}
	now := gateway.now()
	gateway.mu.RLock()
	evidence, ok := gateway.evidence[gateway.evidenceKey(
		request.PathValue("profileRevision"),
		gateway.credentialRevision,
		request.PathValue("vantage"),
	)]
	gateway.mu.RUnlock()
	if !ok || !evidence.LatestAttempt.ExpiresAt.After(now) {
		writeGatewayError(writer, http.StatusNotFound)
		return
	}
	writeGatewayJSON(writer, http.StatusOK, evidence)
}

func (gateway *ConnectivityEvidenceGateway) validateAttempt(
	attempt TURNProbeAttempt,
	challenge ExternalProbeChallenge,
) error {
	if attempt.ContractVersion != BrowserConnectivityContractVersion ||
		attempt.Producer.InstallationID != challenge.InstallationID ||
		attempt.Producer.VantageID != challenge.VantageID ||
		attempt.ProfileRevision != challenge.ProfileRevision ||
		attempt.CredentialRevision != challenge.CredentialRevision {
		return fmt.Errorf("evidence identity is invalid")
	}
	if attempt.Outcome == TURNProbeOutcomeSuccess {
		if strings.TrimSpace(attempt.RelayAddress) == "" || attempt.ErrorCode != "" {
			return fmt.Errorf("successful evidence payload is invalid")
		}
		return nil
	}
	if attempt.Outcome != TURNProbeOutcomeFailure || strings.TrimSpace(attempt.ErrorCode) == "" || attempt.RelayAddress != "" {
		return fmt.Errorf("failed evidence payload is invalid")
	}
	return nil
}

func (gateway *ConnectivityEvidenceGateway) authorizeAgent(request *http.Request, vantage string) bool {
	expected, ok := gateway.agentTokens[vantage]
	return ok && constantTimeTokenEqual(bearerToken(request), expected)
}

func (gateway *ConnectivityEvidenceGateway) pruneLocked(now time.Time) {
	for id, challenge := range gateway.challenges {
		if challenge.used || !challenge.challenge.ExpiresAt.After(now) {
			delete(gateway.challenges, id)
		}
	}
	for key, evidence := range gateway.evidence {
		if !evidence.LatestAttempt.ExpiresAt.After(now) {
			delete(gateway.evidence, key)
		}
	}
}

func (gateway *ConnectivityEvidenceGateway) evidenceKey(profileRevision string, credentialRevision string, vantage string) string {
	return profileRevision + "\x00" + credentialRevision + "\x00" + vantage
}

func decodeBoundedJSON(writer http.ResponseWriter, request *http.Request, target any) bool {
	reader := http.MaxBytesReader(writer, request.Body, maxConnectivityEvidenceBodyBytes)
	decoder := json.NewDecoder(reader)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		writeGatewayError(writer, http.StatusBadRequest)
		return false
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		writeGatewayError(writer, http.StatusBadRequest)
		return false
	}
	return true
}

func bearerToken(request *http.Request) string {
	value := strings.TrimSpace(request.Header.Get("Authorization"))
	if !strings.HasPrefix(value, "Bearer ") {
		return ""
	}
	return strings.TrimSpace(strings.TrimPrefix(value, "Bearer "))
}

func constantTimeTokenEqual(actual string, expected string) bool {
	if actual == "" || expected == "" || len(actual) != len(expected) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(actual), []byte(expected)) == 1
}

func randomHex(size int) (string, error) {
	value := make([]byte, size)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

func writeGatewayJSON(writer http.ResponseWriter, status int, value any) {
	writer.Header().Set("Content-Type", "application/json")
	writer.Header().Set("Cache-Control", "no-store")
	writer.WriteHeader(status)
	if err := json.NewEncoder(writer).Encode(value); err != nil {
		return
	}
}

func writeGatewayError(writer http.ResponseWriter, status int) {
	writer.Header().Set("Cache-Control", "no-store")
	http.Error(writer, http.StatusText(status), status)
}

type ExternalConnectivityProbeAgent struct {
	GatewayURL     string
	InstallationID string
	VantageID      string
	Token          string
	Client         *http.Client
}

func (agent *ExternalConnectivityProbeAgent) RunOnce(ctx context.Context) error {
	challengeRequest := ExternalProbeChallengeRequest{
		InstallationID: agent.InstallationID,
		VantageID:      agent.VantageID,
	}
	var challenge ExternalProbeChallenge
	if err := agent.exchangeJSON(ctx, http.MethodPost, "/v1/challenges", challengeRequest, http.StatusCreated, &challenge); err != nil {
		return fmt.Errorf("request external probe challenge: %w", err)
	}
	if challenge.InstallationID != agent.InstallationID || challenge.VantageID != agent.VantageID ||
		challenge.ProfileRevision == "" || challenge.CredentialRevision == "" || !time.Now().Before(challenge.ExpiresAt) {
		return fmt.Errorf("external probe challenge identity is invalid")
	}
	now := time.Now().UTC()
	attempt := TURNProbeAttempt{
		ContractVersion: BrowserConnectivityContractVersion,
		Producer: TURNPathEvidenceProducer{
			InstallationID: agent.InstallationID,
			VantageID:      agent.VantageID,
		},
		ProfileRevision:    challenge.ProfileRevision,
		CredentialRevision: challenge.CredentialRevision,
		Outcome:            TURNProbeOutcomeFailure,
		MeasuredAt:         &now,
		ErrorCode:          "TURN_RELAY_UNAVAILABLE",
	}
	var lastProbeError error
	for _, iceServer := range challenge.ICEServers {
		urls, err := decodeTURNURLs(iceServer.URLs)
		if err != nil {
			continue
		}
		for _, endpoint := range urls {
			if !containsString(challenge.FrontendURLs, endpoint) {
				continue
			}
			relayAddress, probeErr := probeTURNEndpoint(ctx, endpoint, iceServer.Username, iceServer.Credential)
			if probeErr != nil {
				lastProbeError = probeErr
				continue
			}
			attempt.Outcome = TURNProbeOutcomeSuccess
			attempt.RelayAddress = relayAddress
			attempt.ErrorCode = ""
			break
		}
		if attempt.Outcome == TURNProbeOutcomeSuccess {
			break
		}
	}
	submission := ExternalProbeSubmission{
		ChallengeID:    challenge.ChallengeID,
		Nonce:          challenge.Nonce,
		InstallationID: agent.InstallationID,
		VantageID:      agent.VantageID,
		Attempt:        attempt,
	}
	if err := agent.exchangeJSON(ctx, http.MethodPost, "/v1/evidence", submission, http.StatusNoContent, nil); err != nil {
		return err
	}
	if attempt.Outcome == TURNProbeOutcomeFailure {
		if lastProbeError != nil {
			return fmt.Errorf("external TURN relay probe failed: %w", lastProbeError)
		}
		return fmt.Errorf("external TURN relay probe failed")
	}
	return nil
}

func (agent *ExternalConnectivityProbeAgent) exchangeJSON(
	ctx context.Context,
	method string,
	path string,
	body any,
	expectedStatus int,
	target any,
) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return err
	}
	request, err := http.NewRequestWithContext(
		ctx,
		method,
		strings.TrimRight(agent.GatewayURL, "/")+path,
		bytes.NewReader(payload),
	)
	if err != nil {
		return err
	}
	request.Header.Set("Authorization", "Bearer "+agent.Token)
	request.Header.Set("Content-Type", "application/json")
	client := agent.Client
	if client == nil {
		client = &http.Client{Timeout: 15 * time.Second}
	}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != expectedStatus {
		return fmt.Errorf("gateway returned HTTP %d", response.StatusCode)
	}
	if target == nil {
		return nil
	}
	decoder := json.NewDecoder(io.LimitReader(response.Body, maxConnectivityEvidenceBodyBytes))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}
