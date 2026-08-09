package service

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	TerminalDrainAudience          = "workspace-terminal-drain"
	DrainAssertionInvalidErrorCode = "RUNTIME_DRAIN_ASSERTION_INVALID"
	DrainContextMismatchErrorCode  = "RUNTIME_DRAIN_CONTEXT_MISMATCH"
	maximumAssertionTTLSeconds     = int64(60)
	maximumAssertionFileBytes      = 256 * 1024
	maximumAssertionSegmentBytes   = 16 * 1024
)

type DrainClaims struct {
	Issuer                    string
	Audience                  string
	Action                    string
	WorkspaceID               string
	ExpectedRuntimeInstanceID string
	ExpectedMountedRevision   int64
	TargetRevision            int64
	DrainAttemptID            string
	Deadline                  time.Time
	JobID                     string
	IssuedAt                  time.Time
	ExpiresAt                 time.Time
	JTI                       string
}

type DrainAssertionError struct {
	ErrorCode string
}

func (e *DrainAssertionError) Error() string {
	return e.ErrorCode
}

type drainAssertionWireClaims struct {
	Issuer                    string      `json:"iss"`
	Audience                  interface{} `json:"aud"`
	Action                    string      `json:"action"`
	WorkspaceID               string      `json:"workspaceId"`
	ExpectedRuntimeInstanceID string      `json:"expectedRuntimeInstanceId"`
	ExpectedMountedRevision   json.Number `json:"expectedMountedRevision"`
	TargetRevision            json.Number `json:"targetRevision"`
	DrainAttemptID            string      `json:"drainAttemptId"`
	Deadline                  json.Number `json:"deadline"`
	JobID                     string      `json:"jobId"`
	IssuedAt                  json.Number `json:"iat"`
	ExpiresAt                 json.Number `json:"exp"`
	JTI                       string      `json:"jti"`
}

type managerAssertionJWK struct {
	KeyType   string          `json:"kty"`
	Curve     string          `json:"crv"`
	Use       string          `json:"use"`
	Algorithm string          `json:"alg"`
	KeyID     string          `json:"kid"`
	X         string          `json:"x"`
	D         json.RawMessage `json:"d"`
}

type managerAssertionJWKS struct {
	Keys []managerAssertionJWK `json:"keys"`
}

type ManagerAssertionVerifier struct {
	publicKeys        map[string]ed25519.PublicKey
	issuer            string
	workspaceID       string
	runtimeInstanceID string
	mountedRevision   int64
	now               func() time.Time
	usedJTIs          map[string]time.Time
	mu                sync.Mutex
}

func NewManagerAssertionVerifier(
	publicKeySetFile string,
	issuer string,
	workspaceID string,
	runtimeInstanceID string,
	mountedRevision int64,
) (*ManagerAssertionVerifier, error) {
	return newManagerAssertionVerifier(
		publicKeySetFile,
		issuer,
		workspaceID,
		runtimeInstanceID,
		mountedRevision,
		time.Now,
	)
}

func newManagerAssertionVerifier(
	publicKeySetFile string,
	issuer string,
	workspaceID string,
	runtimeInstanceID string,
	mountedRevision int64,
	now func() time.Time,
) (*ManagerAssertionVerifier, error) {
	if !isCanonicalContextValue(issuer) {
		return nil, fmt.Errorf("runtime assertion issuer is invalid")
	}
	if !isCanonicalContextValue(workspaceID) {
		return nil, fmt.Errorf("workspace ID is invalid")
	}
	if !isCanonicalContextValue(runtimeInstanceID) {
		return nil, fmt.Errorf("runtime instance ID is invalid")
	}
	if mountedRevision < 0 {
		return nil, fmt.Errorf("mounted revision is invalid")
	}
	if now == nil {
		return nil, fmt.Errorf("clock is required")
	}

	publicKeys, err := loadManagerAssertionPublicKeys(publicKeySetFile)
	if err != nil {
		return nil, err
	}
	return &ManagerAssertionVerifier{
		publicKeys:        publicKeys,
		issuer:            issuer,
		workspaceID:       workspaceID,
		runtimeInstanceID: runtimeInstanceID,
		mountedRevision:   mountedRevision,
		now:               now,
		usedJTIs:          make(map[string]time.Time),
	}, nil
}

func (v *ManagerAssertionVerifier) Verify(assertion string) (*DrainClaims, error) {
	parts := strings.Split(assertion, ".")
	if len(parts) != 3 || len(assertion) > maximumAssertionSegmentBytes*3 {
		return nil, invalidDrainAssertion()
	}

	headerBytes, err := decodeAssertionSegment(parts[0])
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	var header struct {
		Algorithm string        `json:"alg"`
		KeyID     string        `json:"kid"`
		Critical  []interface{} `json:"crit"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil ||
		header.Algorithm != "EdDSA" || !isCanonicalContextValue(header.KeyID) ||
		len(header.Critical) != 0 {
		return nil, invalidDrainAssertion()
	}
	publicKey, exists := v.publicKeys[header.KeyID]
	if !exists {
		return nil, invalidDrainAssertion()
	}

	signature, err := decodeAssertionSegment(parts[2])
	if err != nil || len(signature) != ed25519.SignatureSize ||
		!ed25519.Verify(publicKey, []byte(parts[0]+"."+parts[1]), signature) {
		return nil, invalidDrainAssertion()
	}

	payloadBytes, err := decodeAssertionSegment(parts[1])
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	var wire drainAssertionWireClaims
	if err := json.Unmarshal(payloadBytes, &wire); err != nil {
		return nil, invalidDrainAssertion()
	}

	claims, err := v.validateClaims(wire)
	if err != nil {
		return nil, err
	}
	if err := v.consumeJTI(claims.JTI, claims.ExpiresAt); err != nil {
		return nil, err
	}
	if claims.WorkspaceID != v.workspaceID ||
		claims.ExpectedRuntimeInstanceID != v.runtimeInstanceID ||
		claims.ExpectedMountedRevision != v.mountedRevision {
		return nil, drainContextMismatch()
	}
	return claims, nil
}

func (v *ManagerAssertionVerifier) validateClaims(wire drainAssertionWireClaims) (*DrainClaims, error) {
	audience, ok := wire.Audience.(string)
	if !ok || audience != TerminalDrainAudience || wire.Issuer != v.issuer ||
		wire.Action != "drain" {
		return nil, invalidDrainAssertion()
	}
	if !isCanonicalContextValue(wire.WorkspaceID) ||
		!isCanonicalContextValue(wire.ExpectedRuntimeInstanceID) ||
		!isCanonicalContextValue(wire.DrainAttemptID) ||
		!isCanonicalContextValue(wire.JobID) ||
		!isCanonicalContextValue(wire.JTI) {
		return nil, invalidDrainAssertion()
	}

	expectedRevision, err := parseNonNegativeAssertionInteger(wire.ExpectedMountedRevision)
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	targetRevision, err := parseNonNegativeAssertionInteger(wire.TargetRevision)
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	deadlineUnix, err := parsePositiveAssertionInteger(wire.Deadline)
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	issuedAtUnix, err := parsePositiveAssertionInteger(wire.IssuedAt)
	if err != nil {
		return nil, invalidDrainAssertion()
	}
	expiresAtUnix, err := parsePositiveAssertionInteger(wire.ExpiresAt)
	if err != nil || expiresAtUnix <= issuedAtUnix ||
		expiresAtUnix-issuedAtUnix > maximumAssertionTTLSeconds || expiresAtUnix > deadlineUnix {
		return nil, invalidDrainAssertion()
	}

	now := v.now().UTC().Unix()
	if issuedAtUnix > now || expiresAtUnix <= now || deadlineUnix <= now {
		return nil, invalidDrainAssertion()
	}
	return &DrainClaims{
		Issuer:                    wire.Issuer,
		Audience:                  audience,
		Action:                    wire.Action,
		WorkspaceID:               wire.WorkspaceID,
		ExpectedRuntimeInstanceID: wire.ExpectedRuntimeInstanceID,
		ExpectedMountedRevision:   expectedRevision,
		TargetRevision:            targetRevision,
		DrainAttemptID:            wire.DrainAttemptID,
		Deadline:                  time.Unix(deadlineUnix, 0).UTC(),
		JobID:                     wire.JobID,
		IssuedAt:                  time.Unix(issuedAtUnix, 0).UTC(),
		ExpiresAt:                 time.Unix(expiresAtUnix, 0).UTC(),
		JTI:                       wire.JTI,
	}, nil
}

func (v *ManagerAssertionVerifier) consumeJTI(jti string, expiresAt time.Time) error {
	v.mu.Lock()
	defer v.mu.Unlock()

	now := v.now()
	for usedJTI, expiry := range v.usedJTIs {
		if !expiry.After(now) {
			delete(v.usedJTIs, usedJTI)
		}
	}
	if _, exists := v.usedJTIs[jti]; exists {
		return invalidDrainAssertion()
	}
	v.usedJTIs[jti] = expiresAt
	return nil
}

func loadManagerAssertionPublicKeys(filePath string) (map[string]ed25519.PublicKey, error) {
	if !isCanonicalContextValue(filePath) {
		return nil, fmt.Errorf("runtime assertion public key set file is required")
	}
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("runtime assertion public key set file could not be read")
	}
	defer file.Close()

	encoded, err := io.ReadAll(io.LimitReader(file, maximumAssertionFileBytes+1))
	if err != nil || len(encoded) == 0 || len(encoded) > maximumAssertionFileBytes {
		return nil, fmt.Errorf("runtime assertion public key set is invalid")
	}
	var keySet managerAssertionJWKS
	if err := json.Unmarshal(encoded, &keySet); err != nil || len(keySet.Keys) == 0 {
		return nil, fmt.Errorf("runtime assertion public key set is invalid")
	}

	publicKeys := make(map[string]ed25519.PublicKey, len(keySet.Keys))
	for _, key := range keySet.Keys {
		if key.KeyType != "OKP" || key.Curve != "Ed25519" ||
			(key.Use != "" && key.Use != "sig") ||
			(key.Algorithm != "" && key.Algorithm != "EdDSA") ||
			!isCanonicalContextValue(key.KeyID) || len(key.D) != 0 {
			return nil, fmt.Errorf("runtime assertion public key set is invalid")
		}
		if _, duplicate := publicKeys[key.KeyID]; duplicate {
			return nil, fmt.Errorf("runtime assertion public key IDs must be unique")
		}
		rawKey, err := base64.RawURLEncoding.DecodeString(key.X)
		if err != nil || len(rawKey) != ed25519.PublicKeySize {
			return nil, fmt.Errorf("runtime assertion public key set is invalid")
		}
		publicKeys[key.KeyID] = ed25519.PublicKey(append([]byte(nil), rawKey...))
	}
	return publicKeys, nil
}

func decodeAssertionSegment(value string) ([]byte, error) {
	if value == "" || len(value) > maximumAssertionSegmentBytes {
		return nil, fmt.Errorf("assertion segment is invalid")
	}
	return base64.RawURLEncoding.DecodeString(value)
}

func parseNonNegativeAssertionInteger(value json.Number) (int64, error) {
	parsed, err := value.Int64()
	if err != nil || parsed < 0 {
		return 0, fmt.Errorf("assertion integer is invalid")
	}
	return parsed, nil
}

func parsePositiveAssertionInteger(value json.Number) (int64, error) {
	parsed, err := value.Int64()
	if err != nil || parsed <= 0 {
		return 0, fmt.Errorf("assertion integer is invalid")
	}
	return parsed, nil
}

func invalidDrainAssertion() error {
	return &DrainAssertionError{ErrorCode: DrainAssertionInvalidErrorCode}
}

func drainContextMismatch() error {
	return &DrainAssertionError{ErrorCode: DrainContextMismatchErrorCode}
}

func AsDrainAssertionError(err error) *DrainAssertionError {
	var assertionError *DrainAssertionError
	if errors.As(err, &assertionError) {
		return assertionError
	}
	return &DrainAssertionError{ErrorCode: DrainAssertionInvalidErrorCode}
}
