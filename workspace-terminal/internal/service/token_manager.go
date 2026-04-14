package service

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

type TokenInfo struct {
	UserID    string `json:"user_id"`
	TokenType string `json:"token_type"`
	IssuedAt  int64  `json:"issued_at"`
	ExpiresAt int64  `json:"expires_at"`
}

// JWT payload claims
type jwtClaims struct {
	Sub              string `json:"sub"`
	Exp              int64  `json:"exp"`
	Iat              int64  `json:"iat"`
	PreferredUsername string `json:"preferred_username"`
}

// JWK key (RSA)
type jwkKey struct {
	Kid string `json:"kid"`
	Kty string `json:"kty"`
	N   string `json:"n"`
	E   string `json:"e"`
	Use string `json:"use"`
	Alg string `json:"alg"`
}

type jwkSet struct {
	Keys []jwkKey `json:"keys"`
}

// JWKS 快取（全域，帶讀寫鎖）
var (
	jwksCache     *jwkSet
	jwksCacheTime time.Time
	jwksMu        sync.RWMutex
	jwksCacheTTL  = time.Hour
)

type TokenManager struct {
	jwksURL string
}

func NewTokenManager() *TokenManager {
	return &TokenManager{
		jwksURL: os.Getenv("KEYCLOAK_JWKS_URL"),
	}
}

// VerifyToken verifies a Keycloak JWT token.
func (tm *TokenManager) VerifyToken(token string) (*TokenInfo, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, fmt.Errorf("invalid token: expected JWT format")
	}

	// Decode payload
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, fmt.Errorf("failed to decode JWT payload: %w", err)
	}

	var claims jwtClaims
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil, fmt.Errorf("failed to parse JWT claims: %w", err)
	}

	if claims.Sub == "" {
		return nil, fmt.Errorf("JWT missing sub claim")
	}

	if claims.Exp > 0 && time.Now().Unix() >= claims.Exp {
		return nil, fmt.Errorf("JWT token expired")
	}

	if tm.jwksURL != "" {
		if err := tm.verifySignature(token, parts); err != nil {
			return nil, fmt.Errorf("JWT signature verification failed: %w", err)
		}
	}

	return &TokenInfo{
		UserID:    claims.Sub,
		TokenType: "jwt",
		IssuedAt:  claims.Iat,
		ExpiresAt: claims.Exp,
	}, nil
}

// verifySignature verifies the RS256 JWT signature using JWKS.
func (tm *TokenManager) verifySignature(token string, parts []string) error {
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return fmt.Errorf("invalid JWT header encoding")
	}

	var header struct {
		Kid string `json:"kid"`
		Alg string `json:"alg"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return fmt.Errorf("invalid JWT header")
	}

	if header.Alg != "RS256" {
		return fmt.Errorf("unsupported algorithm: %s (only RS256 is supported)", header.Alg)
	}

	set, err := fetchJWKS(tm.jwksURL)
	if err != nil {
		return fmt.Errorf("failed to fetch JWKS: %w", err)
	}

	matchingKey := findKey(set, header.Kid)
	if matchingKey == nil {
		// kid not found — refresh cache once and retry
		set, err = fetchJWKSForce(tm.jwksURL)
		if err != nil {
			return fmt.Errorf("failed to refresh JWKS: %w", err)
		}
		matchingKey = findKey(set, header.Kid)
		if matchingKey == nil {
			return fmt.Errorf("no matching JWKS key for kid: %q", header.Kid)
		}
	}

	nBytes, err := base64.RawURLEncoding.DecodeString(matchingKey.N)
	if err != nil {
		return fmt.Errorf("invalid JWK modulus: %w", err)
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(matchingKey.E)
	if err != nil {
		return fmt.Errorf("invalid JWK exponent: %w", err)
	}

	n := new(big.Int).SetBytes(nBytes)
	e := 0
	for _, b := range eBytes {
		e = e*256 + int(b)
	}
	pubKey := &rsa.PublicKey{N: n, E: e}

	signingInput := parts[0] + "." + parts[1]
	digest := sha256.Sum256([]byte(signingInput))

	sigBytes, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return fmt.Errorf("invalid JWT signature encoding")
	}

	return rsa.VerifyPKCS1v15(pubKey, crypto.SHA256, digest[:], sigBytes)
}

func findKey(set *jwkSet, kid string) *jwkKey {
	for i := range set.Keys {
		if set.Keys[i].Kid == kid {
			return &set.Keys[i]
		}
	}
	return nil
}

func fetchJWKS(jwksURL string) (*jwkSet, error) {
	jwksMu.RLock()
	if jwksCache != nil && time.Since(jwksCacheTime) < jwksCacheTTL {
		set := jwksCache
		jwksMu.RUnlock()
		return set, nil
	}
	jwksMu.RUnlock()

	return fetchJWKSForce(jwksURL)
}

func fetchJWKSForce(jwksURL string) (*jwkSet, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(jwksURL)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("JWKS endpoint returned HTTP %d", resp.StatusCode)
	}

	var set jwkSet
	if err := json.NewDecoder(resp.Body).Decode(&set); err != nil {
		return nil, fmt.Errorf("failed to decode JWKS response: %w", err)
	}

	jwksMu.Lock()
	jwksCache = &set
	jwksCacheTime = time.Now()
	jwksMu.Unlock()

	return &set, nil
}
