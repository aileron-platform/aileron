package controller

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/pion/logging"
	"github.com/pion/turn/v4"
)

type TURNPathEvidenceProducer struct {
	InstallationID string `json:"installationId"`
	VantageID      string `json:"vantageId"`
}

type TURNProbeAttempt struct {
	ContractVersion    string                   `json:"contractVersion"`
	Producer           TURNPathEvidenceProducer `json:"producer"`
	ProfileRevision    string                   `json:"profileRevision"`
	CredentialRevision string                   `json:"credentialRevision"`
	Outcome            string                   `json:"outcome"`
	MeasuredAt         *time.Time               `json:"measuredAt,omitempty"`
	RelayAddress       string                   `json:"relayAddress,omitempty"`
	ErrorCode          string                   `json:"errorCode,omitempty"`
}

type TURNPathEvidence struct {
	TURNProbeAttempt
	AcceptedAt time.Time `json:"acceptedAt"`
	ExpiresAt  time.Time `json:"expiresAt"`
}

type TURNPathEvidenceSnapshot struct {
	ContractVersion string            `json:"contractVersion"`
	LatestAttempt   TURNPathEvidence  `json:"latestAttempt"`
	LastSuccess     *TURNPathEvidence `json:"lastSuccess,omitempty"`
}

type turnICEServer struct {
	URLs       json.RawMessage `json:"urls"`
	Username   string          `json:"username"`
	Credential string          `json:"credential"`
}

type TURNProbeServer struct {
	profile              TURNReachabilityProfile
	credentialRevision   string
	iceServers           []turnICEServer
	turnRESTSharedSecret string
	turnRESTIdentity     string
	requestTimeout       time.Duration

	mu       sync.RWMutex
	evidence TURNPathEvidenceSnapshot
}

func NewTURNProbeServer(
	profile TURNReachabilityProfile,
	credentialRevision string,
	iceServersJSON string,
	turnRESTSharedSecret string,
	turnRESTIdentity string,
	installationID string,
) (*TURNProbeServer, error) {
	credentialRevision = strings.TrimSpace(credentialRevision)
	if credentialRevision == "" {
		return nil, fmt.Errorf("TURN credential revision is required")
	}
	var iceServers []turnICEServer
	if strings.TrimSpace(iceServersJSON) == "" {
		for _, endpoint := range profile.Backend.URLs {
			encoded, err := json.Marshal([]string{endpoint})
			if err != nil {
				return nil, fmt.Errorf("encode backend TURN endpoint: %w", err)
			}
			iceServers = append(iceServers, turnICEServer{URLs: encoded})
		}
	} else if err := json.Unmarshal([]byte(iceServersJSON), &iceServers); err != nil {
		return nil, fmt.Errorf("decode TURN ICE servers: %w", err)
	}
	if len(iceServers) == 0 {
		return nil, fmt.Errorf("at least one TURN ICE server is required")
	}
	turnRESTSharedSecret = strings.TrimSpace(turnRESTSharedSecret)
	turnRESTIdentity = strings.TrimSpace(turnRESTIdentity)
	installationID = strings.TrimSpace(installationID)
	if installationID == "" || turnRESTIdentity == "" {
		return nil, fmt.Errorf("TURN probe producer identity is required")
	}
	if profile.CredentialIssuer.Kind == TURNCredentialIssuerTURNREST &&
		(turnRESTSharedSecret == "" || turnRESTIdentity == "") {
		return nil, fmt.Errorf("TURN REST shared secret and probe identity are required")
	}
	for index, server := range iceServers {
		if profile.CredentialIssuer.Kind == TURNCredentialIssuerStaticSecret &&
			(strings.TrimSpace(server.Username) == "" || strings.TrimSpace(server.Credential) == "") {
			return nil, fmt.Errorf("TURN ICE server %d requires username and credential", index)
		}
	}
	return &TURNProbeServer{
		profile:              profile,
		credentialRevision:   credentialRevision,
		iceServers:           iceServers,
		turnRESTSharedSecret: turnRESTSharedSecret,
		turnRESTIdentity:     turnRESTIdentity,
		requestTimeout:       10 * time.Second,
		evidence: newTURNPathEvidenceSnapshot(TURNProbeAttempt{
			ContractVersion: BrowserConnectivityContractVersion,
			Producer:        TURNPathEvidenceProducer{InstallationID: installationID, VantageID: turnRESTIdentity},
			ProfileRevision: profile.Revision(), CredentialRevision: credentialRevision,
			Outcome: TURNProbeOutcomeFailure, ErrorCode: "TURN_PROBE_PENDING",
		}, time.Now().UTC(), profile.Evidence.TTLSeconds, nil),
	}, nil
}

func (server *TURNProbeServer) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/evidence", func(writer http.ResponseWriter, _ *http.Request) {
		server.mu.RLock()
		evidence := server.evidence
		server.mu.RUnlock()
		writer.Header().Set("Content-Type", "application/json")
		writer.Header().Set("Cache-Control", "no-store")
		if err := json.NewEncoder(writer).Encode(evidence); err != nil {
			http.Error(writer, http.StatusText(http.StatusInternalServerError), http.StatusInternalServerError)
		}
	})
	return mux
}

func (server *TURNProbeServer) Run(ctx context.Context) {
	failureCount := 0
	for {
		attempt := server.probe(ctx)
		server.mu.Lock()
		server.evidence = newTURNPathEvidenceSnapshot(
			attempt, time.Now().UTC(), server.profile.Evidence.TTLSeconds, server.evidence.LastSuccess,
		)
		server.mu.Unlock()

		wait := time.Duration(server.profile.Evidence.IntervalSeconds) * time.Second
		if attempt.Outcome != TURNProbeOutcomeSuccess {
			failureCount++
			backoff := []time.Duration{time.Second, 2 * time.Second, 4 * time.Second, 8 * time.Second, 10 * time.Second}
			index := failureCount - 1
			if index >= len(backoff) {
				index = len(backoff) - 1
			}
			wait = backoff[index]
		} else {
			failureCount = 0
		}
		wait = jitterDuration(wait)
		timer := time.NewTimer(wait)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
	}
}

func (server *TURNProbeServer) probe(parent context.Context) TURNProbeAttempt {
	ctx, cancel := context.WithTimeout(parent, server.requestTimeout)
	defer cancel()
	now := time.Now().UTC()
	attempt := TURNProbeAttempt{
		ContractVersion:    BrowserConnectivityContractVersion,
		Producer:           server.evidence.LatestAttempt.Producer,
		ProfileRevision:    server.profile.Revision(),
		CredentialRevision: server.credentialRevision,
		Outcome:            TURNProbeOutcomeFailure,
		MeasuredAt:         &now,
		ErrorCode:          "TURN_RELAY_UNAVAILABLE",
	}
	iceServers := server.iceServers
	if server.profile.CredentialIssuer.Kind == TURNCredentialIssuerTURNREST {
		iceServers = append([]turnICEServer(nil), server.iceServers...)
		username, credential := issueTURNRESTCredential(
			now,
			server.profile.CredentialIssuer.TTLSeconds,
			server.turnRESTSharedSecret,
			server.turnRESTIdentity,
		)
		for index := range iceServers {
			iceServers[index].Username = username
			iceServers[index].Credential = credential
		}
	}
	for _, iceServer := range iceServers {
		urls, err := decodeTURNURLs(iceServer.URLs)
		if err != nil {
			continue
		}
		for _, endpoint := range urls {
			if !containsString(server.profile.Backend.URLs, endpoint) {
				continue
			}
			relayAddress, probeErr := probeTURNEndpoint(
				ctx,
				endpoint,
				iceServer.Username,
				iceServer.Credential,
			)
			if probeErr != nil {
				continue
			}
			attempt.Outcome = TURNProbeOutcomeSuccess
			attempt.RelayAddress = relayAddress
			attempt.ErrorCode = ""
			return attempt
		}
	}
	return attempt
}

func newTURNPathEvidenceSnapshot(
	attempt TURNProbeAttempt,
	acceptedAt time.Time,
	ttlSeconds int32,
	previousSuccess *TURNPathEvidence,
) TURNPathEvidenceSnapshot {
	evidence := TURNPathEvidence{
		TURNProbeAttempt: attempt,
		AcceptedAt:       acceptedAt.UTC(),
		ExpiresAt:        acceptedAt.UTC().Add(time.Duration(ttlSeconds) * time.Second),
	}
	snapshot := TURNPathEvidenceSnapshot{
		ContractVersion: BrowserConnectivityContractVersion,
		LatestAttempt:   evidence,
		LastSuccess:     previousSuccess,
	}
	if attempt.Outcome == TURNProbeOutcomeSuccess {
		success := evidence
		snapshot.LastSuccess = &success
	}
	return snapshot
}

func decodeTURNURLs(raw json.RawMessage) ([]string, error) {
	var single string
	if err := json.Unmarshal(raw, &single); err == nil && strings.TrimSpace(single) != "" {
		return []string{single}, nil
	}
	var multiple []string
	if err := json.Unmarshal(raw, &multiple); err != nil || len(multiple) == 0 {
		return nil, fmt.Errorf("TURN ICE server urls must be a string or non-empty array")
	}
	return multiple, nil
}

func probeTURNEndpoint(
	ctx context.Context,
	endpoint string,
	username string,
	credential string,
) (string, error) {
	server, ok := parseTURNServerAddress(endpoint)
	if !ok {
		return "", fmt.Errorf("invalid TURN endpoint")
	}
	address := net.JoinHostPort(server.host, server.port)
	var failures []error
	for _, protocol := range server.protocols {
		var packetConn net.PacketConn
		var err error
		switch protocol {
		case "UDP":
			packetConn, err = net.ListenPacket("udp4", "0.0.0.0:0")
		case "TCP":
			dialer := &net.Dialer{}
			var stream net.Conn
			if server.secure {
				tlsDialer := &tls.Dialer{
					NetDialer: dialer,
					Config: &tls.Config{
						MinVersion: tls.VersionTLS12,
						ServerName: server.host,
					},
				}
				stream, err = tlsDialer.DialContext(ctx, "tcp", address)
			} else {
				stream, err = dialer.DialContext(ctx, "tcp", address)
			}
			if err == nil {
				packetConn = turn.NewSTUNConn(stream)
			}
		default:
			err = fmt.Errorf("unsupported TURN transport %q", protocol)
		}
		if err != nil {
			failures = append(failures, err)
			continue
		}
		relayAddress, err := allocateAndRelay(ctx, address, packetConn, username, credential)
		if err == nil {
			return relayAddress, nil
		}
		failures = append(failures, err)
	}
	return "", errors.Join(failures...)
}

func allocateAndRelay(
	ctx context.Context,
	serverAddress string,
	packetConn net.PacketConn,
	username string,
	credential string,
) (string, error) {
	defer packetConn.Close()
	if deadline, ok := ctx.Deadline(); ok {
		if err := packetConn.SetDeadline(deadline); err != nil {
			return "", err
		}
	}
	loggerFactory := logging.NewDefaultLoggerFactory()
	loggerFactory.DefaultLogLevel = logging.LogLevelDisabled
	client, err := turn.NewClient(&turn.ClientConfig{
		STUNServerAddr: serverAddress,
		TURNServerAddr: serverAddress,
		Conn:           packetConn,
		Username:       username,
		Password:       credential,
		LoggerFactory:  loggerFactory,
	})
	if err != nil {
		return "", err
	}
	defer client.Close()
	if err := client.Listen(); err != nil {
		return "", err
	}
	relayConn, err := client.Allocate()
	if err != nil {
		return "", err
	}
	defer relayConn.Close()

	mappedAddress, err := client.SendBindingRequest()
	if err != nil {
		return "", err
	}
	if _, err := relayConn.WriteTo([]byte("permission"), mappedAddress); err != nil {
		return "", err
	}
	echoConn, err := net.ListenPacket("udp4", "0.0.0.0:0")
	if err != nil {
		return "", err
	}
	defer echoConn.Close()
	deadline, ok := ctx.Deadline()
	if !ok {
		deadline = time.Now().Add(10 * time.Second)
	}
	if err := relayConn.SetDeadline(deadline); err != nil {
		return "", err
	}
	if err := echoConn.SetDeadline(deadline); err != nil {
		return "", err
	}

	relayResult := make(chan error, 1)
	go func() {
		buffer := make([]byte, 128)
		count, source, readErr := relayConn.ReadFrom(buffer)
		if readErr == nil {
			_, readErr = relayConn.WriteTo(buffer[:count], source)
		}
		relayResult <- readErr
	}()
	nonceBytes := make([]byte, 16)
	if _, err := rand.Read(nonceBytes); err != nil {
		return "", err
	}
	nonce := hex.EncodeToString(nonceBytes)
	if _, err := echoConn.WriteTo([]byte(nonce), relayConn.LocalAddr()); err != nil {
		return "", err
	}
	buffer := make([]byte, 128)
	count, _, err := echoConn.ReadFrom(buffer)
	if err != nil {
		return "", err
	}
	if err := <-relayResult; err != nil {
		return "", err
	}
	if string(buffer[:count]) != nonce {
		return "", fmt.Errorf("TURN relay returned unexpected payload")
	}
	return relayConn.LocalAddr().String(), nil
}

func jitterDuration(duration time.Duration) time.Duration {
	buffer := []byte{0}
	if _, err := rand.Read(buffer); err != nil {
		return duration
	}
	percent := 90 + int(buffer[0])%21
	return duration * time.Duration(percent) / 100
}

func JitterDuration(duration time.Duration) time.Duration {
	return jitterDuration(duration)
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
