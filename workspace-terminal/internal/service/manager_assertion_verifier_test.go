package service

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type assertionTestKey struct {
	keyID      string
	publicKey  ed25519.PublicKey
	privateKey ed25519.PrivateKey
}

func newAssertionTestKey(t *testing.T, keyID string) assertionTestKey {
	t.Helper()
	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	require.NoError(t, err)
	return assertionTestKey{keyID: keyID, publicKey: publicKey, privateKey: privateKey}
}

func writeAssertionJWKS(t *testing.T, keys ...assertionTestKey) string {
	t.Helper()
	jwks := map[string]interface{}{"keys": []map[string]string{}}
	encodedKeys := make([]map[string]string, 0, len(keys))
	for _, key := range keys {
		encodedKeys = append(encodedKeys, map[string]string{
			"kty": "OKP",
			"crv": "Ed25519",
			"use": "sig",
			"alg": "EdDSA",
			"kid": key.keyID,
			"x":   base64.RawURLEncoding.EncodeToString(key.publicKey),
		})
	}
	jwks["keys"] = encodedKeys
	encoded, err := json.Marshal(jwks)
	require.NoError(t, err)
	path := filepath.Join(t.TempDir(), "manager-jwks.json")
	require.NoError(t, os.WriteFile(path, encoded, 0o600))
	return path
}

func signDrainAssertion(t *testing.T, key assertionTestKey, claims map[string]interface{}) string {
	t.Helper()
	header, err := json.Marshal(map[string]string{
		"alg": "EdDSA",
		"kid": key.keyID,
		"typ": "JWT",
	})
	require.NoError(t, err)
	payload, err := json.Marshal(claims)
	require.NoError(t, err)
	encodedHeader := base64.RawURLEncoding.EncodeToString(header)
	encodedPayload := base64.RawURLEncoding.EncodeToString(payload)
	signingInput := encodedHeader + "." + encodedPayload
	signature := ed25519.Sign(key.privateKey, []byte(signingInput))
	return signingInput + "." + base64.RawURLEncoding.EncodeToString(signature)
}

func validDrainClaims(now time.Time) map[string]interface{} {
	return map[string]interface{}{
		"iss":                       "workspace-manager",
		"aud":                       TerminalDrainAudience,
		"action":                    "drain",
		"workspaceId":               "workspace-123",
		"expectedRuntimeInstanceId": "runtime-instance-123",
		"expectedMountedRevision":   int64(7),
		"targetRevision":            int64(8),
		"drainAttemptId":            "attempt-123",
		"deadline":                  now.Add(45 * time.Second).Unix(),
		"jobId":                     "job-123",
		"iat":                       now.Unix(),
		"exp":                       now.Add(45 * time.Second).Unix(),
		"jti":                       "jti-123",
	}
}

func newTestAssertionVerifier(
	t *testing.T,
	path string,
	now time.Time,
) *ManagerAssertionVerifier {
	t.Helper()
	verifier, err := newManagerAssertionVerifier(
		path,
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
		func() time.Time { return now },
	)
	require.NoError(t, err)
	return verifier
}

func TestManagerAssertionVerifierAcceptsSignedTerminalDrain(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-key-v2")
	verifier := newTestAssertionVerifier(t, writeAssertionJWKS(t, key), now)

	claims, err := verifier.Verify(signDrainAssertion(t, key, validDrainClaims(now)))

	require.NoError(t, err)
	assert.Equal(t, "attempt-123", claims.DrainAttemptID)
	assert.Equal(t, int64(8), claims.TargetRevision)
	assert.Equal(t, "runtime-instance-123", claims.ExpectedRuntimeInstanceID)
}

func TestManagerAssertionVerifierSupportsPublicKeyRotation(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	oldKey := newAssertionTestKey(t, "manager-key-v1")
	newKey := newAssertionTestKey(t, "manager-key-v2")
	path := writeAssertionJWKS(t, oldKey, newKey)

	oldVerifier := newTestAssertionVerifier(t, path, now)
	_, oldErr := oldVerifier.Verify(signDrainAssertion(t, oldKey, validDrainClaims(now)))
	newClaims := validDrainClaims(now)
	newClaims["jti"] = "jti-new"
	newVerifier := newTestAssertionVerifier(t, path, now)
	_, newErr := newVerifier.Verify(signDrainAssertion(t, newKey, newClaims))

	require.NoError(t, oldErr)
	require.NoError(t, newErr)
}

func TestManagerAssertionVerifierRejectsBadSignatureAndAudience(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	trustedKey := newAssertionTestKey(t, "manager-key-v1")
	untrustedKey := newAssertionTestKey(t, "manager-key-v1")
	path := writeAssertionJWKS(t, trustedKey)

	verifier := newTestAssertionVerifier(t, path, now)
	_, signatureErr := verifier.Verify(signDrainAssertion(t, untrustedKey, validDrainClaims(now)))

	claims := validDrainClaims(now)
	claims["aud"] = "workspace-runtime-drain"
	_, audienceErr := verifier.Verify(signDrainAssertion(t, trustedKey, claims))

	assert.Equal(t, DrainAssertionInvalidErrorCode, AsDrainAssertionError(signatureErr).ErrorCode)
	assert.Equal(t, DrainAssertionInvalidErrorCode, AsDrainAssertionError(audienceErr).ErrorCode)
}

func TestManagerAssertionVerifierRejectsInstanceAndMountedRevisionMismatch(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-key-v1")
	path := writeAssertionJWKS(t, key)

	instanceClaims := validDrainClaims(now)
	instanceClaims["expectedRuntimeInstanceId"] = "runtime-instance-old"
	_, instanceErr := newTestAssertionVerifier(t, path, now).Verify(
		signDrainAssertion(t, key, instanceClaims),
	)

	revisionClaims := validDrainClaims(now)
	revisionClaims["expectedMountedRevision"] = int64(6)
	revisionClaims["jti"] = "jti-revision"
	_, revisionErr := newTestAssertionVerifier(t, path, now).Verify(
		signDrainAssertion(t, key, revisionClaims),
	)

	assert.Equal(t, DrainContextMismatchErrorCode, AsDrainAssertionError(instanceErr).ErrorCode)
	assert.Equal(t, DrainContextMismatchErrorCode, AsDrainAssertionError(revisionErr).ErrorCode)
}

func TestManagerAssertionVerifierDoesNotCompareTargetRevisionToMountedRevision(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-key-v1")
	claims := validDrainClaims(now)
	claims["targetRevision"] = int64(42)
	verifier := newTestAssertionVerifier(t, writeAssertionJWKS(t, key), now)

	verified, err := verifier.Verify(signDrainAssertion(t, key, claims))

	require.NoError(t, err)
	assert.Equal(t, int64(42), verified.TargetRevision)
}

func TestManagerAssertionVerifierRejectsExpiredAndOverlongAssertions(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-key-v1")
	path := writeAssertionJWKS(t, key)

	expiredClaims := validDrainClaims(now)
	expiredClaims["iat"] = now.Add(-45 * time.Second).Unix()
	expiredClaims["exp"] = now.Unix()
	_, expiredErr := newTestAssertionVerifier(t, path, now).Verify(
		signDrainAssertion(t, key, expiredClaims),
	)

	overlongClaims := validDrainClaims(now)
	overlongClaims["exp"] = now.Add(61 * time.Second).Unix()
	overlongClaims["deadline"] = now.Add(61 * time.Second).Unix()
	overlongClaims["jti"] = "jti-overlong"
	_, overlongErr := newTestAssertionVerifier(t, path, now).Verify(
		signDrainAssertion(t, key, overlongClaims),
	)

	assert.Equal(t, DrainAssertionInvalidErrorCode, AsDrainAssertionError(expiredErr).ErrorCode)
	assert.Equal(t, DrainAssertionInvalidErrorCode, AsDrainAssertionError(overlongErr).ErrorCode)
}

func TestManagerAssertionVerifierRejectsJTIReplayButAllowsSameAttemptWithNewJTI(t *testing.T) {
	now := time.Unix(2_000_000_000, 0).UTC()
	key := newAssertionTestKey(t, "manager-key-v1")
	verifier := newTestAssertionVerifier(t, writeAssertionJWKS(t, key), now)
	firstAssertion := signDrainAssertion(t, key, validDrainClaims(now))

	_, firstErr := verifier.Verify(firstAssertion)
	_, replayErr := verifier.Verify(firstAssertion)
	retryClaims := validDrainClaims(now)
	retryClaims["jti"] = "jti-retry"
	verifiedRetry, retryErr := verifier.Verify(signDrainAssertion(t, key, retryClaims))

	require.NoError(t, firstErr)
	assert.Equal(t, DrainAssertionInvalidErrorCode, AsDrainAssertionError(replayErr).ErrorCode)
	require.NoError(t, retryErr)
	assert.Equal(t, "attempt-123", verifiedRetry.DrainAttemptID)
}

func TestManagerAssertionVerifierRejectsPrivateMaterialInPublicKeySet(t *testing.T) {
	key := newAssertionTestKey(t, "manager-key-v1")
	encoded, err := json.Marshal(map[string]interface{}{
		"keys": []map[string]string{{
			"kty": "OKP",
			"crv": "Ed25519",
			"kid": key.keyID,
			"x":   base64.RawURLEncoding.EncodeToString(key.publicKey),
			"d":   "private-material",
		}},
	})
	require.NoError(t, err)
	path := filepath.Join(t.TempDir(), "invalid-jwks.json")
	require.NoError(t, os.WriteFile(path, encoded, 0o600))

	_, err = NewManagerAssertionVerifier(
		path,
		"workspace-manager",
		"workspace-123",
		"runtime-instance-123",
		7,
	)

	require.Error(t, err)
}
