package service

import (
	"encoding/base64"
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// buildTestJWT assembles an unsigned (or arbitrarily signed) test JWT.
// Only works when KEYCLOAK_JWKS_URL is not set (skips signature verification).
func buildTestJWT(sub string, exp int64) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"RS256","typ":"JWT","kid":"test-kid"}`))
	payload, _ := json.Marshal(map[string]interface{}{
		"sub": sub,
		"exp": exp,
		"iat": time.Now().Unix(),
	})
	body := base64.RawURLEncoding.EncodeToString(payload)
	sig := base64.RawURLEncoding.EncodeToString([]byte("fake-sig"))
	return header + "." + body + "." + sig
}

func TestVerifyToken_ValidJWT(t *testing.T) {
	// When KEYCLOAK_JWKS_URL is not set, skip signature verification and only verify claims
	tm := NewTokenManager()
	tm.jwksURL = "" // Ensure test environment does not verify signature

	token := buildTestJWT("user-abc", time.Now().Add(time.Hour).Unix())
	result, err := tm.VerifyToken(token)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "user-abc", result.UserID)
	assert.Equal(t, "jwt", result.TokenType)
}

func TestVerifyToken_ExpiredJWT(t *testing.T) {
	tm := NewTokenManager()
	tm.jwksURL = ""

	token := buildTestJWT("user-abc", time.Now().Add(-time.Hour).Unix())
	result, err := tm.VerifyToken(token)

	assert.Error(t, err)
	assert.Nil(t, result)
	assert.Contains(t, err.Error(), "expired")
}

func TestVerifyToken_MissingSub(t *testing.T) {
	tm := NewTokenManager()
	tm.jwksURL = ""

	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"RS256","typ":"JWT","kid":"test-kid"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(`{"exp":9999999999}`))
	sig := base64.RawURLEncoding.EncodeToString([]byte("fake-sig"))
	token := header + "." + payload + "." + sig

	result, err := tm.VerifyToken(token)

	assert.Error(t, err)
	assert.Nil(t, result)
	assert.Contains(t, err.Error(), "sub")
}

func TestVerifyToken_NotJWT(t *testing.T) {
	tm := NewTokenManager()

	result, err := tm.VerifyToken("not-a-jwt-token")

	assert.Error(t, err)
	assert.Nil(t, result)
	assert.Contains(t, err.Error(), "JWT format")
}

func TestVerifyToken_MalformedPayload(t *testing.T) {
	tm := NewTokenManager()
	tm.jwksURL = ""

	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"RS256"}`))
	token := header + ".!!!invalid!!!.sig"

	result, err := tm.VerifyToken(token)

	assert.Error(t, err)
	assert.Nil(t, result)
}
