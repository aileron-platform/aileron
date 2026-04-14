package service

import (
	"encoding/base64"
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// buildTestJWT 組裝一個未簽名（或任意簽名）的測試 JWT。
// 僅適用於 KEYCLOAK_JWKS_URL 未設定時（略過簽名驗證）。
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
	// KEYCLOAK_JWKS_URL 未設定時略過簽名驗證，僅驗證 claims
	tm := NewTokenManager()
	tm.jwksURL = "" // 確保測試環境不做簽名驗證

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
