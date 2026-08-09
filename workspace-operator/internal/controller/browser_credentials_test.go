package controller

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestBrowserCredentialKeyringMatchesManagerVector(t *testing.T) {
	keyring := &BrowserCredentialKeyring{
		ActiveKeyID: "browser-key-1",
		Keys: map[string][]byte{
			"browser-key-1": []byte("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
		},
	}

	user, err := keyring.Derive(
		"11111111-1111-4111-8111-111111111111",
		1,
		"browser-key-1",
		browserCredentialAlgorithm,
		"user",
	)
	if err != nil {
		t.Fatalf("derive user credential: %v", err)
	}
	admin, err := keyring.Derive(
		"11111111-1111-4111-8111-111111111111",
		1,
		"browser-key-1",
		browserCredentialAlgorithm,
		"admin",
	)
	if err != nil {
		t.Fatalf("derive admin credential: %v", err)
	}

	if user != "e2juH4gIpQO1bkUF36KcdpN1YmycRV4PkUjbbUB0yAM" {
		t.Fatalf("user credential does not match Manager vector")
	}
	if admin != "Yp9YClGJiFzkz1RKnzcd__1wN4pu4xZTcqPnVDK2nh8" {
		t.Fatalf("admin credential does not match Manager vector")
	}
}

func TestLoadBrowserCredentialKeyringAcceptsProjectedSecretMode(t *testing.T) {
	path := filepath.Join(t.TempDir(), "keyring.json")
	payload := browserCredentialKeyringFile{
		Algorithm:   browserCredentialAlgorithm,
		ActiveKeyID: "browser-key-1",
		Keys: map[string]string{
			"browser-key-1": base64.RawURLEncoding.EncodeToString(
				[]byte("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
			),
		},
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal keyring: %v", err)
	}
	if err := os.WriteFile(path, raw, 0o440); err != nil {
		t.Fatalf("write keyring: %v", err)
	}

	keyring, err := LoadBrowserCredentialKeyring(path)
	if err != nil {
		t.Fatalf("load projected Secret keyring: %v", err)
	}
	if keyring.ActiveKeyID != "browser-key-1" {
		t.Fatalf("active key ID = %q", keyring.ActiveKeyID)
	}
}
