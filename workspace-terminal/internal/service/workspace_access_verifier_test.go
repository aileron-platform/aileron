package service

import (
	"context"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func atomicallyReplaceFile(t *testing.T, target string, contents []byte) {
	t.Helper()
	next := filepath.Join(filepath.Dir(target), "manager-jwks.next")
	require.NoError(t, os.WriteFile(next, contents, 0o600))
	require.NoError(t, os.Rename(next, target))
}

func validTerminalGrantClaims(now time.Time) map[string]interface{} {
	return map[string]interface{}{
		"iss":                   "workspace-manager",
		"sub":                   "local-user-1",
		"aud":                   "workspace-terminal",
		"kind":                  "workspace-execution-access-grant",
		"workspaceId":           "workspace-123",
		"runtimeInstanceId":     "runtime-instance-123",
		"runtimeAccessRevision": int64(7),
		"actions":               []string{"terminal"},
		"iat":                   now.Unix(),
		"exp":                   now.Add(60 * time.Second).Unix(),
		"jti":                   "reusable-grant",
	}
}

func TestWorkspaceAccessVerifierAcceptsReusableLocalTerminalGrant(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-v1")
	verifier, err := newLocalWorkspaceAccessVerifier(
		writeAssertionJWKS(t, key),
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
		func() time.Time { return now },
	)
	require.NoError(t, err)
	grant := signDrainAssertion(t, key, validTerminalGrantClaims(now))

	require.NoError(t, verifier.VerifyTerminalAccess(context.Background(), grant, "workspace-123"))
	require.NoError(t, verifier.VerifyTerminalAccess(context.Background(), grant, "workspace-123"))
}

func TestWorkspaceAccessVerifierRejectsWrongAudienceActionAndRevision(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-v1")
	verifier, err := newLocalWorkspaceAccessVerifier(
		writeAssertionJWKS(t, key),
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
		func() time.Time { return now },
	)
	require.NoError(t, err)

	for _, mutate := range []func(map[string]interface{}){
		func(claims map[string]interface{}) { claims["aud"] = "workspace-runtime" },
		func(claims map[string]interface{}) { claims["actions"] = []string{"runtime_read"} },
		func(claims map[string]interface{}) { claims["runtimeAccessRevision"] = int64(8) },
	} {
		claims := validTerminalGrantClaims(now)
		mutate(claims)
		err = verifier.VerifyTerminalAccess(context.Background(), signDrainAssertion(t, key, claims), "workspace-123")
		accessError := AsWorkspaceAccessError(err)
		assert.NotEqual(t, http.StatusOK, accessError.HTTPStatus)
	}
}

func TestWorkspaceAccessVerifierReloadsAtomicallyProjectedJWKSForUnknownKey(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	oldKey := newAssertionTestKey(t, "manager-v1")
	newKey := newAssertionTestKey(t, "manager-v2")
	path := writeAssertionJWKS(t, oldKey)
	verifier, err := newLocalWorkspaceAccessVerifier(
		path,
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
		func() time.Time { return now },
	)
	require.NoError(t, err)

	rotatedPath := writeAssertionJWKS(t, newKey)
	rotatedJWKS, err := os.ReadFile(rotatedPath)
	require.NoError(t, err)
	atomicallyReplaceFile(t, path, rotatedJWKS)

	err = verifier.VerifyTerminalAccess(
		context.Background(),
		signDrainAssertion(t, newKey, validTerminalGrantClaims(now)),
		"workspace-123",
	)
	require.NoError(t, err)
}

func TestWorkspaceAccessVerifierRejectsMalformedReloadAndKeepsTrustedKeys(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	oldKey := newAssertionTestKey(t, "manager-v1")
	unknownKey := newAssertionTestKey(t, "manager-v2")
	path := writeAssertionJWKS(t, oldKey)
	verifier, err := newLocalWorkspaceAccessVerifier(
		path,
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
		func() time.Time { return now },
	)
	require.NoError(t, err)
	atomicallyReplaceFile(t, path, []byte("{malformed"))

	err = verifier.VerifyTerminalAccess(
		context.Background(),
		signDrainAssertion(t, unknownKey, validTerminalGrantClaims(now)),
		"workspace-123",
	)
	require.Error(t, err)
	require.Equal(t, http.StatusUnauthorized, AsWorkspaceAccessError(err).HTTPStatus)

	err = verifier.VerifyTerminalAccess(
		context.Background(),
		signDrainAssertion(t, oldKey, validTerminalGrantClaims(now)),
		"workspace-123",
	)
	require.NoError(t, err)
}
