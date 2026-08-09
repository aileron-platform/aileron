package controller

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/google/uuid"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const browserCredentialAlgorithm = "hkdf-sha256-v1"

type browserCredentialKeyringFile struct {
	Algorithm   string            `json:"algorithm"`
	ActiveKeyID string            `json:"activeKeyId"`
	Keys        map[string]string `json:"keys"`
}

func (r *WorkspaceReconciler) reconcileBrowserCredentialSecret(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	spec := workspace.Spec.Browser
	if !spec.Enabled {
		return nil
	}
	expectedSecretName := fmt.Sprintf(
		"workspace-browser-credential-%s-r%d",
		workspace.Spec.WorkspaceID,
		spec.CredentialRevision,
	)
	if r.BrowserCredentialKeyring == nil ||
		spec.CredentialAlgorithm != browserCredentialAlgorithm ||
		spec.CredentialRevision < 1 ||
		spec.CredentialKeyID == "" ||
		spec.CredentialSecretName != expectedSecretName {
		return fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_UNAVAILABLE")
	}
	userPassword, err := r.BrowserCredentialKeyring.Derive(
		workspace.Spec.WorkspaceID,
		spec.CredentialRevision,
		spec.CredentialKeyID,
		spec.CredentialAlgorithm,
		"user",
	)
	if err != nil {
		return err
	}
	adminPassword, err := r.BrowserCredentialKeyring.Derive(
		workspace.Spec.WorkspaceID,
		spec.CredentialRevision,
		spec.CredentialKeyID,
		spec.CredentialAlgorithm,
		"admin",
	)
	if err != nil || userPassword == adminPassword {
		return fmt.Errorf("BROWSER_CREDENTIAL_INVALID")
	}
	desired := &corev1.Secret{
		ObjectMeta: metav1.ObjectMeta{
			Name:      spec.CredentialSecretName,
			Namespace: namespace,
			Annotations: map[string]string{
				"aileron.io/browser-credential-revision":  fmt.Sprintf("%d", spec.CredentialRevision),
				"aileron.io/browser-credential-key-id":    spec.CredentialKeyID,
				"aileron.io/browser-credential-algorithm": spec.CredentialAlgorithm,
			},
		},
		Immutable: boolPtr(true),
		Type:      corev1.SecretTypeOpaque,
		Data: map[string][]byte{
			"user-password":  []byte(userPassword),
			"admin-password": []byte(adminPassword),
		},
	}
	if err := r.setWorkspaceControllerReference(workspace, desired); err != nil {
		return err
	}
	existing := &corev1.Secret{}
	key := client.ObjectKeyFromObject(desired)
	if err := r.Get(ctx, key, existing); apierrors.IsNotFound(err) {
		return r.Create(ctx, desired)
	} else if err != nil {
		return err
	}
	if existing.Immutable == nil || !*existing.Immutable ||
		!metav1.IsControlledBy(existing, workspace) ||
		existing.Annotations["aileron.io/browser-credential-revision"] != desired.Annotations["aileron.io/browser-credential-revision"] ||
		existing.Annotations["aileron.io/browser-credential-key-id"] != spec.CredentialKeyID ||
		existing.Annotations["aileron.io/browser-credential-algorithm"] != spec.CredentialAlgorithm ||
		!hmac.Equal(existing.Data["user-password"], desired.Data["user-password"]) ||
		!hmac.Equal(existing.Data["admin-password"], desired.Data["admin-password"]) {
		return fmt.Errorf("BROWSER_CREDENTIAL_SECRET_CONFLICT")
	}
	return nil
}

type BrowserCredentialKeyring struct {
	ActiveKeyID string
	Keys        map[string][]byte
}

type BrowserCredentialDeriver interface {
	Derive(
		workspaceID string,
		revision int64,
		keyID string,
		algorithm string,
		purpose string,
	) (string, error)
}

func LoadBrowserCredentialKeyring(path string) (*BrowserCredentialKeyring, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_UNAVAILABLE")
	}
	info, err := os.Stat(path)
	if err != nil || !info.Mode().IsRegular() || info.Size() > 256*1024 {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_UNAVAILABLE")
	}
	if info.Mode().Perm()&0007 != 0 {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_PERMISSIONS_INVALID")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_UNAVAILABLE")
	}
	var payload browserCredentialKeyringFile
	if json.Unmarshal(raw, &payload) != nil || payload.Algorithm != browserCredentialAlgorithm {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_INVALID")
	}
	keys := make(map[string][]byte, len(payload.Keys))
	for keyID, encoded := range payload.Keys {
		material, decodeErr := base64.RawURLEncoding.DecodeString(encoded)
		if decodeErr != nil || len(material) != 32 || keyID == "" || len(keyID) > 128 {
			return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_INVALID")
		}
		keys[keyID] = material
	}
	if _, exists := keys[payload.ActiveKeyID]; !exists {
		return nil, fmt.Errorf("BROWSER_CREDENTIAL_KEYRING_INVALID")
	}
	return &BrowserCredentialKeyring{ActiveKeyID: payload.ActiveKeyID, Keys: keys}, nil
}

func (k *BrowserCredentialKeyring) Derive(
	workspaceID string,
	revision int64,
	keyID string,
	algorithm string,
	purpose string,
) (string, error) {
	if k == nil || algorithm != browserCredentialAlgorithm || revision < 1 ||
		(purpose != "user" && purpose != "admin") {
		return "", fmt.Errorf("BROWSER_CREDENTIAL_INVALID")
	}
	key, exists := k.Keys[keyID]
	workspaceUUID, parseErr := uuid.Parse(workspaceID)
	if !exists || parseErr != nil || workspaceUUID.String() != workspaceID {
		return "", fmt.Errorf("BROWSER_CREDENTIAL_INVALID")
	}
	revisionBytes := make([]byte, 8)
	binary.BigEndian.PutUint64(revisionBytes, uint64(revision))
	fields := [][]byte{
		[]byte("aileron-browser-credential"),
		[]byte(browserCredentialAlgorithm),
		workspaceUUID[:],
		revisionBytes,
		[]byte(keyID),
		[]byte(purpose),
	}
	info := make([]byte, 0, 160)
	for _, field := range fields {
		length := make([]byte, 4)
		binary.BigEndian.PutUint32(length, uint32(len(field)))
		info = append(info, length...)
		info = append(info, field...)
	}
	salt := []byte("aileron-browser-credential\x00hkdf-sha256-v1")
	extract := hmac.New(sha256.New, salt)
	_, _ = extract.Write(key)
	prk := extract.Sum(nil)
	expand := hmac.New(sha256.New, prk)
	_, _ = expand.Write(info)
	_, _ = expand.Write([]byte{1})
	return base64.RawURLEncoding.EncodeToString(expand.Sum(nil)), nil
}
