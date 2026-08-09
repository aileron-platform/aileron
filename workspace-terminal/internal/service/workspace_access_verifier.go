package service

import (
	"context"
	"crypto/ed25519"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	TerminalRuntimeAction                        = "terminal"
	TerminalExecutionGrantAudience               = "workspace-terminal"
	ExecutionGrantKind                           = "workspace-execution-access-grant"
	RuntimeAccessUnavailableErrorCode            = "WORKSPACE_RUNTIME_ACCESS_UNAVAILABLE"
	RuntimeActionForbiddenErrorCode              = "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
	RuntimeActionInvalidErrorCode                = "WORKSPACE_RUNTIME_ACTION_INVALID"
	RuntimeInstanceMismatchErrorCode             = "WORKSPACE_RUNTIME_INSTANCE_MISMATCH"
	RuntimeAccessRevisionMismatchErrorCode       = "WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH"
	maximumExecutionGrantTTLSeconds        int64 = 60
)

type WorkspaceAccessError struct {
	HTTPStatus int
	ErrorCode  string
}

func (e *WorkspaceAccessError) Error() string { return e.ErrorCode }

type WorkspaceAccessVerifier interface {
	VerifyTerminalAccess(ctx context.Context, bearerToken string, workspaceID string) error
}

type LocalWorkspaceAccessVerifier struct {
	publicKeysMu          sync.RWMutex
	publicKeys            map[string]ed25519.PublicKey
	publicKeySetFile      string
	issuer                string
	workspaceID           string
	runtimeInstanceID     string
	runtimeAccessRevision int64
	now                   func() time.Time
}

func NewLocalWorkspaceAccessVerifier(
	publicKeySetFile string,
	issuer string,
	workspaceID string,
	runtimeInstanceID string,
	runtimeAccessRevision int64,
) (*LocalWorkspaceAccessVerifier, error) {
	return newLocalWorkspaceAccessVerifier(
		publicKeySetFile,
		issuer,
		workspaceID,
		runtimeInstanceID,
		runtimeAccessRevision,
		time.Now,
	)
}

func newLocalWorkspaceAccessVerifier(
	publicKeySetFile string,
	issuer string,
	workspaceID string,
	runtimeInstanceID string,
	runtimeAccessRevision int64,
	now func() time.Time,
) (*LocalWorkspaceAccessVerifier, error) {
	if !isCanonicalContextValue(issuer) || !isCanonicalContextValue(workspaceID) ||
		!isCanonicalContextValue(runtimeInstanceID) || runtimeAccessRevision < 0 || now == nil {
		return nil, fmt.Errorf("terminal execution grant configuration is invalid")
	}
	publicKeys, err := loadManagerAssertionPublicKeys(publicKeySetFile)
	if err != nil {
		return nil, err
	}
	return &LocalWorkspaceAccessVerifier{
		publicKeys:            publicKeys,
		publicKeySetFile:      publicKeySetFile,
		issuer:                issuer,
		workspaceID:           workspaceID,
		runtimeInstanceID:     runtimeInstanceID,
		runtimeAccessRevision: runtimeAccessRevision,
		now:                   now,
	}, nil
}

type terminalExecutionGrantWire struct {
	Issuer                string      `json:"iss"`
	Subject               string      `json:"sub"`
	Audience              interface{} `json:"aud"`
	Kind                  string      `json:"kind"`
	WorkspaceID           string      `json:"workspaceId"`
	RuntimeInstanceID     string      `json:"runtimeInstanceId"`
	RuntimeAccessRevision json.Number `json:"runtimeAccessRevision"`
	Actions               []string    `json:"actions"`
	IssuedAt              json.Number `json:"iat"`
	ExpiresAt             json.Number `json:"exp"`
	JTI                   string      `json:"jti"`
}

func (v *LocalWorkspaceAccessVerifier) VerifyTerminalAccess(
	ctx context.Context,
	bearerToken string,
	workspaceID string,
) error {
	_ = ctx
	if workspaceID != v.workspaceID {
		return accessError(http.StatusForbidden, RuntimeActionForbiddenErrorCode)
	}
	parts := strings.Split(bearerToken, ".")
	if len(parts) != 3 || len(bearerToken) > maximumAssertionSegmentBytes*3 {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	headerBytes, err := decodeAssertionSegment(parts[0])
	if err != nil {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	var header struct {
		Algorithm string `json:"alg"`
		KeyID     string `json:"kid"`
		Type      string `json:"typ"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil ||
		header.Algorithm != "EdDSA" || header.Type != "JWT" ||
		!isCanonicalContextValue(header.KeyID) {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	key := v.publicKey(header.KeyID)
	signature, signatureErr := decodeAssertionSegment(parts[2])
	if key == nil || signatureErr != nil || !ed25519.Verify(
		key,
		[]byte(parts[0]+"."+parts[1]),
		signature,
	) {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	payload, err := decodeAssertionSegment(parts[1])
	if err != nil {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	decoder := json.NewDecoder(strings.NewReader(string(payload)))
	decoder.UseNumber()
	var claims terminalExecutionGrantWire
	if err := decoder.Decode(&claims); err != nil {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	if claims.Issuer != v.issuer || claims.Audience != TerminalExecutionGrantAudience ||
		claims.Kind != ExecutionGrantKind || !isCanonicalContextValue(claims.Subject) ||
		!isCanonicalContextValue(claims.JTI) || len(claims.Actions) != 1 ||
		claims.Actions[0] != TerminalRuntimeAction {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	issuedAt, issuedErr := parsePositiveAssertionInteger(claims.IssuedAt)
	expiresAt, expiresErr := parsePositiveAssertionInteger(claims.ExpiresAt)
	if issuedErr != nil || expiresErr != nil || expiresAt-issuedAt != maximumExecutionGrantTTLSeconds ||
		issuedAt > v.now().UTC().Unix()+5 || expiresAt <= v.now().UTC().Unix() {
		return accessError(http.StatusUnauthorized, RuntimeActionForbiddenErrorCode)
	}
	if claims.WorkspaceID != v.workspaceID {
		return accessError(http.StatusForbidden, RuntimeActionForbiddenErrorCode)
	}
	if claims.RuntimeInstanceID != v.runtimeInstanceID {
		return accessError(http.StatusLocked, RuntimeInstanceMismatchErrorCode)
	}
	revision, err := parseNonNegativeAssertionInteger(claims.RuntimeAccessRevision)
	if err != nil || revision != v.runtimeAccessRevision {
		return accessError(http.StatusLocked, RuntimeAccessRevisionMismatchErrorCode)
	}
	return nil
}

func (v *LocalWorkspaceAccessVerifier) publicKey(keyID string) ed25519.PublicKey {
	v.publicKeysMu.RLock()
	key := v.publicKeys[keyID]
	v.publicKeysMu.RUnlock()
	if key != nil {
		return key
	}

	v.publicKeysMu.Lock()
	defer v.publicKeysMu.Unlock()
	if key = v.publicKeys[keyID]; key != nil {
		return key
	}
	reloaded, err := loadManagerAssertionPublicKeys(v.publicKeySetFile)
	if err != nil {
		return nil
	}
	v.publicKeys = reloaded
	return reloaded[keyID]
}

func accessError(status int, code string) error {
	return &WorkspaceAccessError{HTTPStatus: status, ErrorCode: code}
}

func AsWorkspaceAccessError(err error) *WorkspaceAccessError {
	var access *WorkspaceAccessError
	if errors.As(err, &access) {
		return access
	}
	return &WorkspaceAccessError{
		HTTPStatus: http.StatusServiceUnavailable,
		ErrorCode:  RuntimeAccessUnavailableErrorCode,
	}
}

func isCanonicalContextValue(value string) bool {
	return value != "" && value == strings.TrimSpace(value) &&
		!strings.ContainsAny(value, "\r\n\x00")
}
