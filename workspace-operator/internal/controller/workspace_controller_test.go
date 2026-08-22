package controller

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"gopkg.in/yaml.v3"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	storagev1 "k8s.io/api/storage/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const (
	reviewedBrowserCompositeProbeScriptLength = 1731
	reviewedBrowserCompositeProbeScriptSHA256 = "83e6cbe28dc5bde234c4a36ca6a3a872d437b54e62c25a077356dd8c7d41d082"
)

type runtimePlatformEnvironmentContract struct {
	SchemaVersion int `json:"schemaVersion"`
	Required      []struct {
		Name         string `json:"name"`
		ValueKind    string `json:"valueKind"`
		ValuePattern string `json:"valuePattern"`
		Port         *struct {
			Required bool `json:"required"`
			Minimum  int  `json:"minimum"`
			Maximum  int  `json:"maximum"`
		} `json:"port"`
	} `json:"required"`
}

func loadRuntimePlatformEnvironmentContract() (runtimePlatformEnvironmentContract, error) {
	content, err := os.ReadFile("/contracts/platform-configuration/runtime-platform-environment.json")
	if err != nil {
		return runtimePlatformEnvironmentContract{}, fmt.Errorf("read Runtime platform environment contract: %w", err)
	}
	var contract runtimePlatformEnvironmentContract
	if err := json.Unmarshal(content, &contract); err != nil {
		return runtimePlatformEnvironmentContract{}, fmt.Errorf("decode Runtime platform environment contract: %w", err)
	}
	if contract.SchemaVersion != 1 {
		return runtimePlatformEnvironmentContract{}, fmt.Errorf("Runtime platform environment schemaVersion = %d, want 1", contract.SchemaVersion)
	}
	return contract, nil
}

func validateRuntimePlatformEnvironmentContract(environment map[string]string) error {
	contract, err := loadRuntimePlatformEnvironmentContract()
	if err != nil {
		return err
	}
	requiredNames := make(map[string]struct{}, len(contract.Required))
	for _, item := range contract.Required {
		if _, duplicate := requiredNames[item.Name]; duplicate {
			return fmt.Errorf("Runtime platform environment contract duplicates %s", item.Name)
		}
		requiredNames[item.Name] = struct{}{}
		value, present := environment[item.Name]
		if !present {
			return fmt.Errorf("Runtime platform environment is missing %s", item.Name)
		}
		pattern, err := regexp.Compile(item.ValuePattern)
		if err != nil {
			return fmt.Errorf("compile %s pattern for %s: %w", item.ValueKind, item.Name, err)
		}
		if !pattern.MatchString(value) {
			return fmt.Errorf("Runtime platform environment %s=%q does not satisfy %s", item.Name, value, item.ValueKind)
		}
		if item.Port != nil {
			parsed, err := url.Parse(value)
			if err != nil {
				return fmt.Errorf("Runtime platform environment %s has an invalid URL: %w", item.Name, err)
			}
			rawPort := parsed.Port()
			if item.Port.Required && rawPort == "" {
				return fmt.Errorf("Runtime platform environment %s requires an explicit port", item.Name)
			}
			if rawPort != "" {
				port, err := strconv.Atoi(rawPort)
				if err != nil || port < item.Port.Minimum || port > item.Port.Maximum {
					return fmt.Errorf("Runtime platform environment %s port is outside the allowed range", item.Name)
				}
			}
		}
	}
	if len(environment) != len(requiredNames) {
		return fmt.Errorf("Runtime platform environment key count = %d, want %d", len(environment), len(requiredNames))
	}
	return nil
}

func assertRuntimePlatformEnvironmentContract(t *testing.T, environment map[string]string) {
	t.Helper()
	if err := validateRuntimePlatformEnvironmentContract(environment); err != nil {
		t.Fatal(err)
	}
}

func validRuntimePlatformEnvironmentForContract(t *testing.T) (runtimePlatformEnvironmentContract, map[string]string) {
	t.Helper()
	contract, err := loadRuntimePlatformEnvironmentContract()
	if err != nil {
		t.Fatal(err)
	}
	valuesByKind := map[string]string{
		"non-empty-string":         "workspace-123",
		"absolute-path":            "/workspace",
		"canonical-uuid":           "f1e4b143-628e-46e2-8ab0-df8687eb163c",
		"non-negative-integer":     "1",
		"safe-relative-path":       ".worktrees",
		"secret-file-path":         "/run/secrets/credential",
		"internal-http-url":        "http://service:3001",
		"public-origin":            "https://aileron.example.test",
		"file-path":                "/run/config/jwks.json",
		"bounded-non-empty-string": "workspace-manager",
		"dns-service-name":         "workspace-runtime",
	}
	environment := make(map[string]string, len(contract.Required))
	for _, item := range contract.Required {
		value, present := valuesByKind[item.ValueKind]
		if !present {
			t.Fatalf("no test value for Runtime platform value kind %s", item.ValueKind)
		}
		environment[item.Name] = value
	}
	return contract, environment
}

func TestRuntimePlatformEnvironmentContractRejectsEmptyWorktreeAndInvalidURLPorts(t *testing.T) {
	contract, environment := validRuntimePlatformEnvironmentForContract(t)
	if err := validateRuntimePlatformEnvironmentContract(environment); err != nil {
		t.Fatalf("valid Runtime platform environment: %v", err)
	}

	emptyWorktree := cloneStringMap(environment)
	emptyWorktree["AILERON_WORKTREE_SUBDIR"] = ""
	if err := validateRuntimePlatformEnvironmentContract(emptyWorktree); err == nil || !strings.Contains(err.Error(), "safe-relative-path") {
		t.Fatalf("empty worktree error = %v, want safe-relative-path rejection", err)
	}

	for _, item := range contract.Required {
		if item.Port == nil {
			continue
		}
		for _, port := range []int{0, 65536} {
			invalidPort := cloneStringMap(environment)
			scheme := "http"
			if item.ValueKind == "public-origin" {
				scheme = "https"
			}
			invalidPort[item.Name] = fmt.Sprintf("%s://service:%d", scheme, port)
			err := validateRuntimePlatformEnvironmentContract(invalidPort)
			if err == nil || (!strings.Contains(err.Error(), "invalid URL") && !strings.Contains(err.Error(), "allowed range")) {
				t.Fatalf("%s port %d error = %v, want range rejection", item.Name, port, err)
			}
		}
	}
}

func cloneStringMap(source map[string]string) map[string]string {
	clone := make(map[string]string, len(source))
	for key, value := range source {
		clone[key] = value
	}
	return clone
}

const (
	testRuntimeInstanceID     = "11111111-1111-4111-8111-111111111111"
	testNextRuntimeInstanceID = "22222222-2222-4222-8222-222222222222"
	testKnowledgeBaseID1      = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
	testKnowledgeBaseID2      = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
	testKnowledgeBaseID3      = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
)

func testWorkspaceStorageSpec() workspacev1alpha1.WorkspaceStorageSpec {
	return workspacev1alpha1.WorkspaceStorageSpec{
		WorkspaceData: workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: 21_474_836_480, Revision: 1},
		RuntimeHome:   workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: 2_147_483_648, Revision: 1},
	}
}

type deploymentUpdateCountingClient struct {
	client.Client
	updates        map[types.NamespacedName]int
	serviceUpdates map[types.NamespacedName]int
}

type statusUpdateCountingClient struct {
	client.Client
	statusUpdates int
}

type persistentVolumeClaimDeleteHoldingClient struct {
	client.Client
	holdDeletes    bool
	deleteAttempts map[types.NamespacedName]int
}

func (c *persistentVolumeClaimDeleteHoldingClient) Delete(
	ctx context.Context,
	obj client.Object,
	opts ...client.DeleteOption,
) error {
	if _, ok := obj.(*corev1.PersistentVolumeClaim); ok {
		key := client.ObjectKeyFromObject(obj)
		c.deleteAttempts[key]++
		if c.holdDeletes {
			return nil
		}
	}
	return c.Client.Delete(ctx, obj, opts...)
}

type testBrowserCredentialDeriver struct{}

func (testBrowserCredentialDeriver) Derive(
	_ string,
	_ int64,
	_ string,
	_ string,
	purpose string,
) (string, error) {
	return "test-browser-" + purpose + "-credential", nil
}

func configureTestBrowserCredential(
	spec *workspacev1alpha1.WorkspaceOptionalComponentSpec,
	workspaceID string,
) {
	spec.CredentialRevision = 1
	spec.CredentialKeyID = "browser-key-test"
	spec.CredentialAlgorithm = browserCredentialAlgorithm
	spec.CredentialSecretName = fmt.Sprintf(
		"workspace-browser-credential-%s-r1",
		workspaceID,
	)
}

func TestParseTURNServerAddress(t *testing.T) {
	tests := []struct {
		name      string
		serverURL string
		address   turnServerAddress
		valid     bool
	}{
		{
			name:      "turn ipv4",
			serverURL: "turn:192.0.2.10:30478",
			address: turnServerAddress{
				host:      "192.0.2.10",
				port:      "30478",
				protocols: []string{"UDP", "TCP"},
			},
			valid: true,
		},
		{
			name:      "turn hostname default port",
			serverURL: "turn:turn.example.com",
			address: turnServerAddress{
				host:      "turn.example.com",
				port:      "3478",
				protocols: []string{"UDP", "TCP"},
			},
			valid: true,
		},
		{
			name:      "turns ipv6 default port",
			serverURL: "turns:[2001:db8::10]",
			address: turnServerAddress{
				host:      "2001:db8::10",
				port:      "5349",
				protocols: []string{"TCP"},
				secure:    true,
			},
			valid: true,
		},
		{
			name:      "tcp transport query",
			serverURL: "turn:turn.example.com:3479?transport=tcp",
			address: turnServerAddress{
				host:      "turn.example.com",
				port:      "3479",
				protocols: []string{"TCP"},
			},
			valid: true,
		},
		{
			name:      "udp transport query",
			serverURL: "turn:turn.example.com:3479?transport=UDP",
			address: turnServerAddress{
				host:      "turn.example.com",
				port:      "3479",
				protocols: []string{"UDP"},
			},
			valid: true,
		},
		{name: "unsupported scheme", serverURL: "stun:turn.example.com:3478", valid: false},
		{name: "unsupported transport", serverURL: "turn:turn.example.com:3478?transport=sctp", valid: false},
		{name: "secure udp transport", serverURL: "turns:turn.example.com:5349?transport=udp", valid: false},
		{name: "invalid port", serverURL: "turn:turn.example.com:70000", valid: false},
		{name: "missing host", serverURL: "turn:", valid: false},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			address, valid := parseTURNServerAddress(test.serverURL)
			if !reflect.DeepEqual(address, test.address) || valid != test.valid {
				t.Fatalf(
					"parseTURNServerAddress(%q) = (%#v, %t), want (%#v, %t)",
					test.serverURL,
					address,
					valid,
					test.address,
					test.valid,
				)
			}
		})
	}
}

type statusUpdateCountingWriter struct {
	client.SubResourceWriter
	client *statusUpdateCountingClient
}

func (c *statusUpdateCountingClient) Status() client.StatusWriter {
	return &statusUpdateCountingWriter{
		SubResourceWriter: c.Client.Status(),
		client:            c,
	}
}

func (w *statusUpdateCountingWriter) Update(
	ctx context.Context,
	obj client.Object,
	opts ...client.SubResourceUpdateOption,
) error {
	w.client.statusUpdates++
	return w.SubResourceWriter.Update(ctx, obj, opts...)
}

func (c *deploymentUpdateCountingClient) Update(
	ctx context.Context,
	obj client.Object,
	opts ...client.UpdateOption,
) error {
	if deployment, ok := obj.(*appsv1.Deployment); ok {
		key := types.NamespacedName{Name: deployment.Name, Namespace: deployment.Namespace}
		c.updates[key]++
	}
	if service, ok := obj.(*corev1.Service); ok && c.serviceUpdates != nil {
		key := types.NamespacedName{Name: service.Name, Namespace: service.Namespace}
		c.serviceUpdates[key]++
	}
	return c.Client.Update(ctx, obj, opts...)
}

func assertNoDeploymentUpdates(t *testing.T, countingClient *deploymentUpdateCountingClient) {
	t.Helper()
	for key, count := range countingClient.updates {
		if count != 0 {
			t.Fatalf("stable reconcile updated Deployment %s %d time(s), want 0", key, count)
		}
	}
}

func defaultPlatformPublicOrigin() string {
	return "https://aileron.example.com"
}

func TestRuntimeSecretNameUsesCanonicalWorkspaceGenerationDigest(t *testing.T) {
	name := runtimeSecretName("workspace-1")
	prefix := "workspace-generation-"
	if !strings.HasPrefix(name, prefix) {
		t.Fatalf("runtime secret name %q does not use prefix %q", name, prefix)
	}
	if len(strings.TrimPrefix(name, prefix)) != 16 {
		t.Fatalf("runtime secret name %q does not use the first 16 SHA-256 hex characters", name)
	}
}

func TestWorkspaceReconcilerCreatesCanonicalRuntimePodEnvironment(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-runtime-environment",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-runtime-environment",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				MountRevision:     7,
				AccessRevision:    3,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-runtime-environment"),
				DatabaseTrust: &workspacev1alpha1.WorkspaceDatabaseTrustSpec{
					SecretName: "platform-database-ca",
					SecretKey:  "ca.pem",
					Revision:   "ca-2026-08",
				},
				Assertion: workspacev1alpha1.WorkspaceRuntimeAssertionSpec{
					Issuer:                 "workspace-manager",
					PublicKeySetSecretName: "runtime-assertion-public-jwks",
				},
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				Revision:     1,
				Enabled:      true,
				Image:        testImmutableBrowserImage,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				Revision:     1,
				Enabled:      true,
				Image:        testImmutableCanvasImage,
			},
			WorkspacePath:  "/workspace",
			WorktreeSubdir: "feature/canonical-runtime-environment",
		},
	}
	configureTestBrowserCredential(&workspace.Spec.Browser, workspace.Spec.WorkspaceID)
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()
	reconciler := &WorkspaceReconciler{
		Client:                   cl,
		Scheme:                   scheme,
		CiliumEnabled:            false,
		PlatformPublicOrigin:     defaultPlatformPublicOrigin(),
		ManagerURL:               "http://workspace-manager.operator-system:3001",
		BrowserCredentialKeyring: testBrowserCredentialDeriver{},
	}
	request := ctrl.Request{NamespacedName: types.NamespacedName{
		Name: workspace.Name, Namespace: workspace.Namespace,
	}}
	for attempt := 1; attempt <= 2; attempt++ {
		if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
			t.Fatalf("reconcile attempt %d failed: %v", attempt, err)
		}
	}

	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      "workspace-runtime-ws-runtime-environment",
		Namespace: "team-a",
	}, &deployment); err != nil {
		t.Fatalf("get Runtime Deployment: %v", err)
	}
	podSpec := deployment.Spec.Template.Spec
	if len(podSpec.Containers) != 1 {
		t.Fatalf("Runtime container count = %d, want 1", len(podSpec.Containers))
	}
	runtimeContainer := podSpec.Containers[0]
	wantCanonical := map[string]string{
		"AILERON_WORKSPACE_ID":                          "ws-runtime-environment",
		"AILERON_WORKSPACE_PATH":                        "/workspace",
		"AILERON_RUNTIME_INSTANCE_ID":                   testRuntimeInstanceID,
		"AILERON_RUNTIME_ACCESS_REVISION":               "3",
		"AILERON_KB_MOUNT_REVISION":                     "7",
		"AILERON_WORKTREE_SUBDIR":                       "feature/canonical-runtime-environment",
		"AILERON_RUNTIME_DATABASE_CONNECTION_FILE":      "/etc/aileron/runtime-secrets/runtime-database-connection",
		"AILERON_RUNTIME_CONTROL_TOKEN_FILE":            "/etc/aileron/runtime-secrets/runtime-control-token",
		"AILERON_MANAGER_INTERNAL_URL":                  "http://workspace-manager.operator-system:3001",
		"AILERON_PLATFORM_PUBLIC_ORIGIN":                "https://aileron.example.com",
		"AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": "/etc/aileron/runtime-assertions/jwks.json",
		"AILERON_RUNTIME_ASSERTION_ISSUER":              "workspace-manager",
		"AILERON_BROWSER_SERVICE_NAME":                  "workspace-browser-ws-runtime-environment",
		"AILERON_BROWSER_WEBRTC_INTERNAL_URL":           "http://workspace-browser-ws-runtime-environment.team-a.svc.cluster.local:6080",
		"AILERON_BROWSER_CDP_URL":                       "http://workspace-browser-ws-runtime-environment.team-a.svc.cluster.local:9223",
		"AILERON_CANVAS_SERVICE_NAME":                   "workspace-canvas-ws-runtime-environment",
		"AILERON_CANVAS_INTERNAL_URL":                   "http://workspace-canvas-ws-runtime-environment.team-a.svc.cluster.local:3003",
		"AILERON_CANVAS_API_URL":                        "http://workspace-canvas-ws-runtime-environment.team-a.svc.cluster.local:3013",
	}
	actualCanonical := map[string]string{}
	for _, envVar := range runtimeContainer.Env {
		if envVar.ValueFrom != nil && envVar.ValueFrom.SecretKeyRef != nil {
			t.Fatalf("Runtime env %s must not use SecretKeyRef", envVar.Name)
		}
		if strings.HasPrefix(envVar.Name, "AILERON_") {
			actualCanonical[envVar.Name] = envVar.Value
		}
	}
	if !reflect.DeepEqual(actualCanonical, wantCanonical) {
		t.Fatalf("canonical Runtime env = %#v, want %#v", actualCanonical, wantCanonical)
	}
	assertRuntimePlatformEnvironmentContract(t, actualCanonical)

	forbidden := []string{
		"WORKSPACE_NAME", "PORT", "ENV", "NODE_ENV", "DEPLOYMENT_ENV", "ALLOWED_ORIGINS",
		"WORKSPACE_ID", "WORKSPACE_PATH", "WORKTREE_SUBDIR",
		"RUNTIME_CONTROL_TOKEN", "MANAGER_URL", "FRONTEND_PUBLIC_URL",
		"RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", "RUNTIME_ASSERTION_ISSUER",
		"BROWSER_CONTAINER_NAME", "BROWSER_WEBRTC_INTERNAL_URL", "BROWSER_CDP_URL",
		"CANVAS_CONTAINER_NAME", "CANVAS_INTERNAL_URL", "CANVAS_API_URL",
	}
	for _, envVar := range runtimeContainer.Env {
		for _, forbiddenName := range forbidden {
			if envVar.Name == forbiddenName {
				t.Fatalf("Runtime env contains legacy platform key %s", forbiddenName)
			}
		}
	}

	var runtimeSecretVolume *corev1.SecretVolumeSource
	for _, volume := range podSpec.Volumes {
		if volume.Name == "runtime-secrets" {
			runtimeSecretVolume = volume.Secret
		}
	}
	if runtimeSecretVolume == nil {
		t.Fatal("Runtime PodSpec has no runtime-secrets Secret volume")
	}
	if runtimeSecretVolume.SecretName != workspace.Spec.Runtime.RuntimeSecretName {
		t.Fatalf("runtime-secrets Secret = %q, want %q", runtimeSecretVolume.SecretName, workspace.Spec.Runtime.RuntimeSecretName)
	}
	wantSecretItems := []corev1.KeyToPath{
		{Key: "runtime-database-connection", Path: "runtime-database-connection", Mode: int32Ptr(0440)},
		{Key: "runtime-control-token", Path: "runtime-control-token", Mode: int32Ptr(0440)},
	}
	if !reflect.DeepEqual(runtimeSecretVolume.Items, wantSecretItems) {
		t.Fatalf("runtime-secrets items = %#v, want %#v", runtimeSecretVolume.Items, wantSecretItems)
	}
	foundReadOnlyMount := false
	for _, mount := range runtimeContainer.VolumeMounts {
		if mount.Name == "runtime-secrets" {
			foundReadOnlyMount = mount.MountPath == "/etc/aileron/runtime-secrets" && mount.ReadOnly
		}
	}
	if !foundReadOnlyMount {
		t.Fatal("Runtime container has no read-only /etc/aileron/runtime-secrets mount")
	}
	var databaseCAVolume *corev1.SecretVolumeSource
	foundDatabaseCAMount := false
	for _, volume := range podSpec.Volumes {
		if volume.Name == "platform-database-ca" {
			databaseCAVolume = volume.Secret
		}
	}
	for _, mount := range runtimeContainer.VolumeMounts {
		if mount.Name == "platform-database-ca" {
			foundDatabaseCAMount = mount.MountPath == "/etc/aileron/data-service-ca/platform-database" && mount.ReadOnly
		}
	}
	if databaseCAVolume == nil || databaseCAVolume.SecretName != "platform-database-ca" {
		t.Fatalf("Runtime database CA volume = %#v", databaseCAVolume)
	}
	if len(databaseCAVolume.Items) != 1 || databaseCAVolume.Items[0].Key != "ca.pem" || databaseCAVolume.Items[0].Path != "ca.crt" {
		t.Fatalf("Runtime database CA items = %#v", databaseCAVolume.Items)
	}
	if !foundDatabaseCAMount {
		t.Fatal("Runtime container has no read-only platform database CA mount")
	}
	if deployment.Spec.Template.Annotations[runtimeDatabaseCARevisionAnnotation] != "ca-2026-08" {
		t.Fatalf("Runtime database CA revision annotation = %q", deployment.Spec.Template.Annotations[runtimeDatabaseCARevisionAnnotation])
	}
}

func TestWorkspaceReconcilerCreatesManagedDeploymentsAndServices(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-test",
			Namespace: "team-a",
			UID:       types.UID("workspace-test-uid"),
			Annotations: map[string]string{
				firewallDeliveryIDAnnotation: testFirewallDeliveryID,
			},
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:   workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID: "ws-123",
			Storage: workspacev1alpha1.WorkspaceStorageSpec{
				WorkspaceData: workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: 26_843_545_600, Revision: 1},
				RuntimeHome:   workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: 2_147_483_648, Revision: 1},
			},
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				MountRevision:     7,
				AccessRevision:    3,
				Image:             testImmutableRuntimeImage,
				Resources:         testResourceRequirements("500m", "1Gi", "2000m", "3Gi"),
				RuntimeSecretName: runtimeSecretName("ws-123"),
				Assertion: workspacev1alpha1.WorkspaceRuntimeAssertionSpec{
					Issuer:                 "workspace-manager",
					PublicKeySetSecretName: "runtime-assertion-public-jwks",
				},
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1,
				Enabled: true,
				Image:   testImmutableBrowserImage,
				Resources: testResourceRequirements(
					"500m",
					"1Gi",
					"2000m",
					"2Gi",
				),
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1,
				Enabled: true,
				Image:   testImmutableCanvasImage,
				Resources: testResourceRequirements(
					"100m",
					"1Gi",
					"1000m",
					"2Gi",
				),
			},
			WorkspacePath:  "/workspace",
			WorktreeSubdir: ".worktrees",
			EnvVars: []workspacev1alpha1.WorkspaceEnvVar{
				{Key: "USER_FEATURE_FLAG", Value: "enabled"},
			},
			KnowledgeBases: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
				{KBID: testKnowledgeBaseID1, Alias: "docs"},
				{KBID: testKnowledgeBaseID2, Alias: "readonly-docs"},
			},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Revision: 7,
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"google.com"},
				},
			},
		},
	}
	configureTestBrowserCredential(&workspace.Spec.Browser, workspace.Spec.WorkspaceID)
	allowExpansion := false
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(
			workspace,
			testFirewallNode("node-a", true, false, nil),
			&storagev1.StorageClass{
				ObjectMeta:           metav1.ObjectMeta{Name: "shared-rwx"},
				AllowVolumeExpansion: &allowExpansion,
			},
			&storagev1.StorageClass{
				ObjectMeta:           metav1.ObjectMeta{Name: "runtime-rwx"},
				AllowVolumeExpansion: &allowExpansion,
			},
		).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                        cl,
		Scheme:                        scheme,
		ConfigNamespace:               "operator-system",
		CiliumEnabled:                 true,
		KnowledgeBasesPVCName:         "shared-knowledge-bases",
		PlatformStorageGID:            int64Ptr(2000),
		WorkspaceStorageClass:         "shared-rwx",
		RuntimeHomeStorageClass:       "runtime-rwx",
		RuntimeHomeAccessMode:         corev1.ReadWriteMany,
		WorkloadImagePullSecrets:      []string{"harbor-registry"},
		PlatformPublicOrigin:          defaultPlatformPublicOrigin(),
		ManagerURL:                    "http://workspace-manager.operator-system:3001",
		TURNProfile:                   turnProfileForTest("turn:turn.internal.example:3478"),
		BrowserConnectivityProbeImage: "workspace-operator:test",
		TURNICEServersSecretName:      "external-turn-ice",
		TURNBackendSecretKey:          "backend-ice-servers-json",
		TURNFrontendSecretKey:         "frontend-ice-servers-json",
		TURNCredentialRevision:        "7",
		BrowserCredentialKeyring:      testBrowserCredentialDeriver{},
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-123", testImmutableRuntimeImage)
	assertDeploymentResources(t, cl, "team-a", "workspace-runtime-ws-123", "500m", "1Gi", "2000m", "3Gi")
	assertRuntimeDeploymentReplacementPolicy(t, cl, "team-a", "workspace-runtime-ws-123")
	assertDeploymentImage(t, cl, "team-a", "workspace-browser-ws-123", testImmutableBrowserImage)
	assertDeploymentResources(t, cl, "team-a", "workspace-browser-ws-123", "500m", "1Gi", "2000m", "2Gi")
	assertBrowserConnectivityProbe(t, cl, "team-a", "workspace-browser-ws-123")
	assertDeploymentImage(t, cl, "team-a", "workspace-canvas-ws-123", testImmutableCanvasImage)
	assertDeploymentResources(t, cl, "team-a", "workspace-canvas-ws-123", "100m", "1Gi", "1000m", "2Gi")
	assertDeploymentGeneration(t, cl, "team-a", "workspace-runtime-ws-123", true)
	assertDeploymentGeneration(t, cl, "team-a", "workspace-browser-ws-123", false)
	assertDeploymentGeneration(t, cl, "team-a", "workspace-canvas-ws-123", false)
	assertObjectDeleted(t, cl, "team-a", "workspace-terminal-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-terminal-ws-123", &corev1.Service{})
	assertServiceExists(t, cl, "team-a", "workspace-runtime-ws-123")
	assertServiceExists(t, cl, "team-a", "workspace-browser-ws-123")
	assertServiceExists(t, cl, "team-a", "workspace-canvas-ws-123")
	assertWorkloadServiceAccount(t, cl, "team-a", "workspace-workload-ws-123")
	assertWorkloadServiceAccountPullSecrets(
		t,
		cl,
		"team-a",
		"workspace-workload-ws-123",
		[]corev1.LocalObjectReference{{Name: "harbor-registry"}},
	)
	for _, deploymentName := range []string{
		"workspace-runtime-ws-123",
		"workspace-browser-ws-123",
		"workspace-canvas-ws-123",
	} {
		assertDeploymentUsesServiceAccount(
			t,
			cl,
			"team-a",
			deploymentName,
			"workspace-workload-ws-123",
		)
		assertDeploymentHasNoImagePullSecrets(
			t,
			cl,
			"team-a",
			deploymentName,
		)
	}
	for _, ingressName := range []string{
		"workspace-runtime-ws-123",
		"workspace-browser-ws-123",
		"workspace-canvas-ws-123",
	} {
		assertObjectDeleted(t, cl, "team-a", ingressName, &networkingv1.Ingress{})
	}
	assertPVCExists(t, cl, "team-a", "workspace-pvc-ws-123")
	assertPVCProfile(
		t,
		cl,
		"team-a",
		"workspace-runtime-home-pvc-ws-123",
		[]corev1.PersistentVolumeAccessMode{corev1.ReadWriteMany},
		"runtime-rwx",
		"2Gi",
	)
	assertDeploymentUsesPVC(t, cl, "team-a", "workspace-runtime-ws-123", "workspace-pvc-ws-123")
	assertDeploymentUsesPVC(
		t,
		cl,
		"team-a",
		"workspace-runtime-ws-123",
		"workspace-runtime-home-pvc-ws-123",
	)
	assertRuntimeDeploymentHomeMount(
		t,
		cl,
		"team-a",
		"workspace-runtime-ws-123",
		"workspace-runtime-home-pvc-ws-123",
	)
	for _, deploymentName := range []string{
		"workspace-browser-ws-123",
		"workspace-canvas-ws-123",
	} {
		assertDeploymentDoesNotUsePVC(
			t,
			cl,
			"team-a",
			deploymentName,
			"workspace-runtime-home-pvc-ws-123",
		)
	}
	for _, deploymentName := range []string{
		"workspace-runtime-ws-123",
		"workspace-browser-ws-123",
		"workspace-canvas-ws-123",
	} {
		assertRestrictedDeploymentSecurityContext(t, cl, "team-a", deploymentName)
	}
	assertDeploymentComponentLabel(t, cl, "team-a", "workspace-runtime-ws-123", runtimeComponent)
	assertDeploymentComponentLabel(t, cl, "team-a", "workspace-browser-ws-123", browserComponent)
	assertDeploymentComponentLabel(t, cl, "team-a", "workspace-canvas-ws-123", canvasComponent)
	assertBrowserDeploymentRuntimeContract(t, cl, "team-a", "workspace-browser-ws-123")
	assertRuntimeDeploymentEnv(t, cl, "team-a", "workspace-browser-ws-123", map[string]string{
		"NEKO_WEBRTC_ICELITE":                       "false",
		"NEKO_LOG_LEVEL":                            "warn",
		"AILERON_TURN_CREDENTIAL_REVISION":          "7",
		"NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE":  "/run/secrets/browser-credentials/user-password",
		"NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": "/run/secrets/browser-credentials/admin-password",
	})
	assertBrowserSecretFileContract(t, cl, "team-a", "workspace-browser-ws-123")
	assertRuntimeDeploymentEnvAbsent(
		t,
		cl,
		"team-a",
		"workspace-browser-ws-123",
		[]string{
			"NEKO_WEBRTC_ICESERVERS_BACKEND",
			"NEKO_WEBRTC_ICESERVERS_FRONTEND",
			"NEKO_WEBRTC_IP_RETRIEVAL_URL",
			"NEKO_WEBRTC_NAT1TO1",
			"NEKO_WEBRTC_UDPMUX",
		},
	)
	assertCanvasDeploymentRuntimeContract(t, cl, "team-a", "workspace-canvas-ws-123")
	assertRuntimeDeploymentHomeInitializer(t, cl, "team-a", "workspace-runtime-ws-123")
	assertRuntimeDeploymentCodexTmpfs(t, cl, "team-a", "workspace-runtime-ws-123")
	assertRuntimeDeploymentKnowledgeBaseMounts(t, cl, "team-a", "workspace-runtime-ws-123", "shared-knowledge-bases")
	assertRuntimeDeploymentAssertionJWKS(t, cl, "team-a", "workspace-runtime-ws-123", "runtime-assertion-public-jwks")
	assertRuntimeDeploymentSetupScript(
		t,
		cl,
		"team-a",
		"workspace-runtime-ws-123",
		runtimeSecretName("ws-123"),
	)
	assertDeploymentHasNoKnowledgeBaseMounts(t, cl, "team-a", "workspace-browser-ws-123")
	assertDeploymentHasNoKnowledgeBaseMounts(t, cl, "team-a", "workspace-canvas-ws-123")
	assertDeploymentHasNoRuntimeAssertionJWKS(t, cl, "team-a", "workspace-browser-ws-123")
	assertDeploymentHasNoRuntimeAssertionJWKS(t, cl, "team-a", "workspace-canvas-ws-123")
	assertRuntimeDeploymentEnv(t, cl, "team-a", "workspace-runtime-ws-123", map[string]string{
		"AILERON_WORKSPACE_ID":                          "ws-123",
		"AILERON_WORKSPACE_PATH":                        "/workspace",
		"AILERON_RUNTIME_INSTANCE_ID":                   testRuntimeInstanceID,
		"AILERON_RUNTIME_ACCESS_REVISION":               "3",
		"AILERON_KB_MOUNT_REVISION":                     "7",
		"AILERON_WORKTREE_SUBDIR":                       ".worktrees",
		"AILERON_RUNTIME_DATABASE_CONNECTION_FILE":      "/etc/aileron/runtime-secrets/runtime-database-connection",
		"AILERON_RUNTIME_CONTROL_TOKEN_FILE":            "/etc/aileron/runtime-secrets/runtime-control-token",
		"AILERON_MANAGER_INTERNAL_URL":                  "http://workspace-manager.operator-system:3001",
		"AILERON_PLATFORM_PUBLIC_ORIGIN":                "https://aileron.example.com",
		"AILERON_RUNTIME_ASSERTION_ISSUER":              "workspace-manager",
		"AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": "/etc/aileron/runtime-assertions/jwks.json",
		"AILERON_BROWSER_SERVICE_NAME":                  "workspace-browser-ws-123",
		"AILERON_BROWSER_WEBRTC_INTERNAL_URL":           "http://workspace-browser-ws-123.team-a.svc.cluster.local:6080",
		"AILERON_BROWSER_CDP_URL":                       "http://workspace-browser-ws-123.team-a.svc.cluster.local:9223",
		"AILERON_CANVAS_SERVICE_NAME":                   "workspace-canvas-ws-123",
		"AILERON_CANVAS_INTERNAL_URL":                   "http://workspace-canvas-ws-123.team-a.svc.cluster.local:3003",
		"AILERON_CANVAS_API_URL":                        "http://workspace-canvas-ws-123.team-a.svc.cluster.local:3013",
		"HOME":                                          "/home/developer",
		"USER_FEATURE_FLAG":                             "enabled",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-123-workspace-egress", []string{
		"github.com",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-123-browser-egress", []string{
		"google.com",
	})
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-123-workspace-egress", "operator-system")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-123-browser-egress", "operator-system")
	assertPolicyAllowsTURN(
		t,
		cl,
		"team-a",
		"ws-ws-123-browser-egress",
		"turn:turn.internal.example:3478",
	)
	assertPolicyAllowsWorkspacePeers(t, cl, "team-a", "ws-ws-123-runtime-peer-egress", "ws-123")
	assertFirewallPolicyIdentity(
		t,
		cl,
		"team-a",
		"ws-ws-123-workspace-egress",
		"workspace-test",
		"7",
		testFirewallDeliveryID,
		"aileron.io/firewall-group",
		"workspace",
	)
	assertFirewallPolicyIdentity(
		t,
		cl,
		"team-a",
		"ws-ws-123-runtime-peer-egress",
		"workspace-test",
		"7",
		testFirewallDeliveryID,
		componentLabel,
		runtimeComponent,
	)
	assertFirewallPolicyIdentity(
		t,
		cl,
		"team-a",
		"ws-ws-123-browser-egress",
		"workspace-test",
		"7",
		testFirewallDeliveryID,
		"aileron.io/firewall-group",
		"browser",
	)
	assertWorkspaceStatus(t, cl, "team-a", "workspace-test", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.Firewall.ObservedRevision != 0 ||
			status.Firewall.TargetDeliveryID != testFirewallDeliveryID ||
			status.Firewall.Phase != "Applying" ||
			status.Firewall.ErrorCode != "" {
			t.Fatalf("firewall status must await Cilium enforcement: %+v", status.Firewall)
		}
	})
	browserPolicy := newCiliumNetworkPolicy("team-a", "ws-ws-123-browser-egress")
	if err := cl.Get(context.Background(), client.ObjectKeyFromObject(browserPolicy), browserPolicy); err != nil {
		t.Fatalf("get bootstrap-gated Browser policy: %v", err)
	}
	browserPolicy.SetUID(types.UID("policy-uid-ws-ws-123-browser-egress"))
	browserPolicy.SetGeneration(1)
	if err := cl.Update(context.Background(), browserPolicy); err != nil {
		t.Fatalf("persist bootstrap-gated Browser policy identity: %v", err)
	}
	markFirewallPoliciesEnforced(
		t,
		cl,
		"team-a",
		7,
		"ws-ws-123-workspace-egress",
		"ws-ws-123-runtime-peer-egress",
	)
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("third reconcile failed: %v", err)
	}
	assertWorkspaceStatus(t, cl, "team-a", "workspace-test", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.TargetNamespace != "team-a" {
			t.Fatalf("target namespace = %s, want team-a", status.TargetNamespace)
		}
		assertStorageStatus(
			t,
			status.Storage.WorkspaceData,
			0,
			1,
			false,
			"",
		)
		assertStorageStatus(
			t,
			status.Storage.RuntimeHome,
			0,
			1,
			false,
			"",
		)
		if status.Phase != "Reconciling" {
			t.Fatalf("phase = %s, want Reconciling", status.Phase)
		}
		if status.Components.Runtime.Phase != "Starting" {
			t.Fatalf("runtime phase = %s, want Starting", status.Components.Runtime.Phase)
		}
		if status.Components.Browser.Phase != "Pending" {
			t.Fatalf("browser phase = %s, want Pending", status.Components.Browser.Phase)
		}
		if status.Components.Canvas.Phase != "Pending" {
			t.Fatalf("canvas phase = %s, want Pending", status.Components.Canvas.Phase)
		}
		if status.Firewall.ObservedRevision != 7 ||
			status.Firewall.Phase != "Applied" ||
			status.Firewall.WorkspacePolicyName != "ws-ws-123-workspace-egress" ||
			status.Firewall.RuntimePeerPolicyName != "ws-ws-123-runtime-peer-egress" ||
			status.Firewall.BrowserPolicyName != "ws-ws-123-browser-egress" {
			t.Fatalf("unexpected firewall status metadata: %+v", status.Firewall)
		}
	})
}

func TestParseRuntimeHomeStorageAccessMode(t *testing.T) {
	for name, testCase := range map[string]struct {
		value string
		want  corev1.PersistentVolumeAccessMode
	}{
		"default":         {value: "", want: corev1.ReadWriteOnce},
		"read write once": {value: " ReadWriteOnce ", want: corev1.ReadWriteOnce},
		"read write many": {value: "ReadWriteMany", want: corev1.ReadWriteMany},
	} {
		t.Run(name, func(t *testing.T) {
			got, err := ParseRuntimeHomeStorageAccessMode(testCase.value)
			if err != nil {
				t.Fatalf("parse access mode: %v", err)
			}
			if got != testCase.want {
				t.Fatalf("access mode = %s, want %s", got, testCase.want)
			}
		})
	}

	if _, err := ParseRuntimeHomeStorageAccessMode("ReadWriteOncePod"); err == nil {
		t.Fatal("expected unsupported access mode to be rejected")
	}
}

func TestWorkspaceReconcilerDoesNotUpdateManagedDeploymentsAfterAPIDefaulting(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-defaulting",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-defaulting",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-defaulting"),
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1,
				Enabled: true,
				Image:   testImmutableBrowserImage,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1,
				Enabled: true,
				Image:   testImmutableCanvasImage,
			},
			WorkspacePath: "/workspace",
		},
	}
	configureTestBrowserCredential(&workspace.Spec.Browser, workspace.Spec.WorkspaceID)

	baseClient := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()
	reconciler := &WorkspaceReconciler{
		Client:                   baseClient,
		Scheme:                   scheme,
		CiliumEnabled:            false,
		PlatformPublicOrigin:     defaultPlatformPublicOrigin(),
		BrowserCredentialKeyring: testBrowserCredentialDeriver{},
	}
	request := ctrl.Request{NamespacedName: types.NamespacedName{
		Name: workspace.Name, Namespace: workspace.Namespace,
	}}
	for attempt := 1; attempt <= 2; attempt++ {
		if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
			t.Fatalf("reconcile attempt %d failed: %v", attempt, err)
		}
	}

	deploymentNames := []string{
		"workspace-runtime-ws-defaulting",
		"workspace-browser-ws-defaulting",
		"workspace-canvas-ws-defaulting",
	}
	generations := make(map[types.NamespacedName]int64, len(deploymentNames))
	for _, name := range deploymentNames {
		key := types.NamespacedName{Name: name, Namespace: "team-a"}
		var deployment appsv1.Deployment
		if err := baseClient.Get(context.Background(), key, &deployment); err != nil {
			t.Fatalf("get deployment %s before API defaulting: %v", key, err)
		}
		container := &deployment.Spec.Template.Spec.Containers[0]
		deployment.Annotations["deployment.kubernetes.io/revision"] = "7"
		deployment.Annotations["example.com/third-party"] = "keep"
		deployment.Spec.Template.Annotations["example.com/template"] = "keep"
		container.ImagePullPolicy = corev1.PullIfNotPresent
		container.TerminationMessagePath = corev1.TerminationMessagePathDefault
		container.TerminationMessagePolicy = corev1.TerminationMessageReadFile
		for portIndex := range container.Ports {
			container.Ports[portIndex].Protocol = corev1.ProtocolTCP
		}
		for _, probe := range []*corev1.Probe{
			container.StartupProbe,
			container.ReadinessProbe,
			container.LivenessProbe,
		} {
			if probe != nil && probe.HTTPGet != nil {
				probe.HTTPGet.Scheme = corev1.URISchemeHTTP
			}
		}
		if err := baseClient.Update(context.Background(), &deployment); err != nil {
			t.Fatalf("simulate API defaulting for deployment %s: %v", key, err)
		}
		if err := baseClient.Get(context.Background(), key, &deployment); err != nil {
			t.Fatalf("get deployment %s after API defaulting: %v", key, err)
		}
		generations[key] = deployment.Generation
	}
	serviceNames := []string{
		"workspace-runtime-ws-defaulting",
		"workspace-browser-ws-defaulting",
		"workspace-canvas-ws-defaulting",
	}
	for _, name := range serviceNames {
		key := types.NamespacedName{Name: name, Namespace: "team-a"}
		var service corev1.Service
		if err := baseClient.Get(context.Background(), key, &service); err != nil {
			t.Fatalf("get service %s before API defaulting: %v", key, err)
		}
		for portIndex := range service.Spec.Ports {
			service.Spec.Ports[portIndex].Protocol = corev1.ProtocolTCP
		}
		if err := baseClient.Update(context.Background(), &service); err != nil {
			t.Fatalf("simulate API defaulting for service %s: %v", key, err)
		}
	}

	countingClient := &deploymentUpdateCountingClient{
		Client:         baseClient,
		updates:        make(map[types.NamespacedName]int),
		serviceUpdates: make(map[types.NamespacedName]int),
	}
	reconciler.Client = countingClient
	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("stable reconcile failed: %v", err)
	}

	for _, name := range deploymentNames {
		key := types.NamespacedName{Name: name, Namespace: "team-a"}
		if updates := countingClient.updates[key]; updates != 0 {
			t.Errorf("deployment %s received %d update(s) after API defaulting, want 0", key, updates)
		}
		var deployment appsv1.Deployment
		if err := baseClient.Get(context.Background(), key, &deployment); err != nil {
			t.Fatalf("get stable deployment %s: %v", key, err)
		}
		if deployment.Generation != generations[key] {
			t.Errorf(
				"deployment %s generation = %d, want unchanged %d",
				key,
				deployment.Generation,
				generations[key],
			)
		}
		if deployment.Annotations["deployment.kubernetes.io/revision"] != "7" ||
			deployment.Annotations["example.com/third-party"] != "keep" ||
			deployment.Spec.Template.Annotations["example.com/template"] != "keep" {
			t.Errorf("deployment %s did not preserve non-operator annotations", key)
		}
		container := deployment.Spec.Template.Spec.Containers[0]
		if container.ImagePullPolicy != corev1.PullIfNotPresent ||
			container.TerminationMessagePath != corev1.TerminationMessagePathDefault ||
			container.TerminationMessagePolicy != corev1.TerminationMessageReadFile {
			t.Errorf("deployment %s container API defaults are not stable: %+v", key, container)
		}
		for _, port := range container.Ports {
			if port.Protocol != corev1.ProtocolTCP {
				t.Errorf("deployment %s port %s protocol = %q, want TCP", key, port.Name, port.Protocol)
			}
		}
		for _, probe := range []*corev1.Probe{
			container.StartupProbe,
			container.ReadinessProbe,
			container.LivenessProbe,
		} {
			if probe != nil && probe.HTTPGet != nil && probe.HTTPGet.Scheme != corev1.URISchemeHTTP {
				t.Errorf("deployment %s HTTP probe scheme = %q, want HTTP", key, probe.HTTPGet.Scheme)
			}
		}
	}
	for _, name := range serviceNames {
		key := types.NamespacedName{Name: name, Namespace: "team-a"}
		if updates := countingClient.serviceUpdates[key]; updates != 0 {
			t.Errorf("service %s received %d update(s) after API defaulting, want 0", key, updates)
		}
		var service corev1.Service
		if err := baseClient.Get(context.Background(), key, &service); err != nil {
			t.Fatalf("get stable service %s: %v", key, err)
		}
		for _, port := range service.Spec.Ports {
			if port.Protocol != corev1.ProtocolTCP {
				t.Errorf("service %s port %s protocol = %q, want TCP", key, port.Name, port.Protocol)
			}
		}
	}
}

func TestWorkspaceReconcilerRejectsMismatchedTargetNamespaceBeforeMutatingWorkloads(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-namespace-mismatch",
			Namespace:  "operator-system",
			Finalizers: []string{workspaceFinalizer},
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-mismatch",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-mismatch"),
			},
			WorkspacePath: "/workspace",
		},
	}
	foreignDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      resourceName(runtimeComponent, workspace.Spec.WorkspaceID),
			Namespace: "team-a",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{Spec: corev1.PodSpec{
				Containers: []corev1.Container{{Name: runtimeComponent, Image: "foreign:test"}},
			}},
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, foreignDeployment).
		Build()
	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err == nil || !strings.Contains(err.Error(), "must match metadata namespace") {
		t.Fatalf("namespace mismatch error = %v, want fail-closed mismatch", err)
	}

	var unchanged appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: foreignDeployment.Name, Namespace: foreignDeployment.Namespace,
	}, &unchanged); err != nil {
		t.Fatalf("get foreign deployment: %v", err)
	}
	if unchanged.Spec.Replicas == nil || *unchanged.Spec.Replicas != 1 {
		t.Fatalf("foreign deployment replicas = %v, want 1", unchanged.Spec.Replicas)
	}
	if got := unchanged.Spec.Template.Spec.Containers[0].Image; got != "foreign:test" {
		t.Fatalf("foreign deployment image = %q, want foreign:test", got)
	}
	assertObjectDeleted(
		t,
		cl,
		"operator-system",
		resourceName(runtimeComponent, workspace.Spec.WorkspaceID),
		&appsv1.Deployment{},
	)
}

func TestWorkspaceReconcilerOmitsKnowledgeBaseVolumeWhenNoAttachments(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-empty-kb",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-empty",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-empty"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: false},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: false},
			WorkspacePath: "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        false,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}
	assertDeploymentHasNoKnowledgeBaseMounts(t, cl, "team-a", "workspace-runtime-ws-empty")
}

func TestValidateKnowledgeBaseAttachmentsRejectsNonCanonicalInput(t *testing.T) {
	tests := []struct {
		name        string
		attachments []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment
	}{
		{
			name: "uppercase uuid",
			attachments: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{{
				KBID: strings.ToUpper(testKnowledgeBaseID1), Alias: "docs",
			}},
		},
		{
			name: "path alias",
			attachments: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{{
				KBID: testKnowledgeBaseID1, Alias: "../docs",
			}},
		},
		{
			name: "reserved alias",
			attachments: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{{
				KBID: testKnowledgeBaseID1, Alias: "runtime",
			}},
		},
		{
			name: "duplicate alias",
			attachments: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
				{KBID: testKnowledgeBaseID1, Alias: "docs"},
				{KBID: testKnowledgeBaseID2, Alias: "docs"},
			},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if err := validateKnowledgeBaseAttachments(tc.attachments); err == nil {
				t.Fatal("expected validation error")
			}
		})
	}
	if err := validateKnowledgeBaseAttachments([]workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{{
		KBID: testKnowledgeBaseID1, Alias: "docs",
	}}); err != nil {
		t.Fatalf("valid attachment rejected: %v", err)
	}
}

func TestValidateWorkspaceEnvVarsRejectsPlatformAndFixedKeys(t *testing.T) {
	tests := []struct {
		name          string
		items         []workspacev1alpha1.WorkspaceEnvVar
		errorContains string
	}{
		{
			name:          "future Aileron variable",
			items:         []workspacev1alpha1.WorkspaceEnvVar{{Key: "AILERON_FUTURE_PLATFORM_KEY", Value: "attacker"}},
			errorContains: "reserved",
		},
		{
			name:          "Aileron publishing variable",
			items:         []workspacev1alpha1.WorkspaceEnvVar{{Key: "AILERON_PUBLISH_GITLAB_TOKEN", Value: "attacker"}},
			errorContains: "reserved",
		},
		{
			name:          "fixed tool variable",
			items:         []workspacev1alpha1.WorkspaceEnvVar{{Key: "CODEX_HOME", Value: "/tmp/attacker"}},
			errorContains: "reserved",
		},
		{
			name: "duplicate custom variable",
			items: []workspacev1alpha1.WorkspaceEnvVar{
				{Key: "USER_FEATURE_FLAG", Value: "one"},
				{Key: "USER_FEATURE_FLAG", Value: "two"},
			},
			errorContains: "duplicated",
		},
		{
			name:          "invalid variable name",
			items:         []workspacev1alpha1.WorkspaceEnvVar{{Key: "INVALID-NAME", Value: "value"}},
			errorContains: "invalid",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := validateWorkspaceEnvVars(tc.items)
			if tc.errorContains == "" {
				if err != nil {
					t.Fatalf("valid workspace environment rejected: %v", err)
				}
				return
			}
			if err == nil || !strings.Contains(err.Error(), tc.errorContains) {
				t.Fatalf("validation error = %v, want text %q", err, tc.errorContains)
			}
		})
	}
	for fixedKey := range fixedWorkspaceEnvKeys {
		t.Run("fixed "+fixedKey, func(t *testing.T) {
			err := validateWorkspaceEnvVars([]workspacev1alpha1.WorkspaceEnvVar{{
				Key: fixedKey, Value: "attacker",
			}})
			if err == nil || !strings.Contains(err.Error(), "reserved") {
				t.Fatalf("validation error = %v, want reserved", err)
			}
		})
	}
	if err := validateWorkspaceEnvVars([]workspacev1alpha1.WorkspaceEnvVar{
		{Key: "USER_FEATURE_FLAG", Value: "enabled"},
		{Key: "CUSTOM_ENDPOINT", Value: "https://example.com"},
		{Key: "DATABASE_URL", Value: "postgresql://example"},
		{Key: "RUNTIME_ASSERTION_CUSTOM", Value: "workspace-owned"},
	}); err != nil {
		t.Fatalf("valid workspace environment rejected: %v", err)
	}
}

func TestWorkspaceReconcilerRejectsInvalidEnvBeforeCreatingWorkloads(t *testing.T) {
	tests := []struct {
		name  string
		items []workspacev1alpha1.WorkspaceEnvVar
	}{
		{
			name:  "reserved",
			items: []workspacev1alpha1.WorkspaceEnvVar{{Key: "INTERNAL_API_TOKEN", Value: "attacker"}},
		},
		{
			name: "duplicate",
			items: []workspacev1alpha1.WorkspaceEnvVar{
				{Key: "USER_FEATURE_FLAG", Value: "one"},
				{Key: "USER_FEATURE_FLAG", Value: "two"},
			},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			scheme := runtime.NewScheme()
			mustAddSchemes(t, scheme)
			workspace := &workspacev1alpha1.Workspace{
				ObjectMeta: metav1.ObjectMeta{
					Name:       "workspace-invalid-env",
					Namespace:  "team-a",
					Finalizers: []string{workspaceFinalizer},
				},
				Spec: workspacev1alpha1.WorkspaceSpec{
					Bootstrap:   workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
					WorkspaceID: "invalid-env",
					Storage:     testWorkspaceStorageSpec(),
					Runtime: workspacev1alpha1.WorkspaceResourceSpec{
						DesiredState:      "Running",
						InstanceID:        testRuntimeInstanceID,
						Revision:          1,
						Image:             testImmutableRuntimeImage,
						RuntimeSecretName: runtimeSecretName("invalid-env"),
					},
					WorkspacePath: "/workspace",
					EnvVars:       tc.items,
				},
			}
			cl := fake.NewClientBuilder().
				WithScheme(scheme).
				WithStatusSubresource(&workspacev1alpha1.Workspace{}).
				WithObjects(workspace).
				Build()
			reconciler := &WorkspaceReconciler{Client: cl, Scheme: scheme}

			if _, err := reconciler.Reconcile(context.Background(), ctrl.Request{
				NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
			}); err == nil {
				t.Fatal("expected invalid workspace environment to fail reconciliation")
			}
			assertObjectDeleted(t, cl, "team-a", resourceName(runtimeComponent, workspace.Spec.WorkspaceID), &appsv1.Deployment{})
			assertObjectDeleted(t, cl, "team-a", resourceName(pvcComponent, workspace.Spec.WorkspaceID), &corev1.PersistentVolumeClaim{})
		})
	}
}

func TestWorkspaceReconcilerUpdatesKnowledgeBaseMountsAfterSpecChange(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-update-kb",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-update",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-update"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: false},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: false},
			WorkspacePath: "/workspace",
			KnowledgeBases: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
				{KBID: testKnowledgeBaseID1, Alias: "docs"},
				{KBID: testKnowledgeBaseID2, Alias: "readonly-docs"},
			},
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                cl,
		Scheme:                scheme,
		CiliumEnabled:         false,
		KnowledgeBasesPVCName: "shared-knowledge-bases",
		PlatformPublicOrigin:  defaultPlatformPublicOrigin(),
	}

	request := ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	}

	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	assertRuntimeDeploymentKnowledgeBaseMountSet(t, cl, "team-a", "workspace-runtime-ws-update", "shared-knowledge-bases", map[string]corev1.VolumeMount{
		"/knowledge/docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/docs",
			SubPath:   testKnowledgeBaseID1,
			ReadOnly:  true,
		},
		"/knowledge/readonly-docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/readonly-docs",
			SubPath:   testKnowledgeBaseID2,
			ReadOnly:  true,
		},
	})

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), request.NamespacedName, &updated); err != nil {
		t.Fatalf("get workspace for update: %v", err)
	}
	updated.Spec.KnowledgeBases = []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
		{KBID: testKnowledgeBaseID3, Alias: "playbooks"},
	}
	updated.Spec.Runtime.MountRevision++
	updated.Spec.Runtime.Revision++
	updated.Spec.Runtime.InstanceID = testNextRuntimeInstanceID
	if err := cl.Update(context.Background(), &updated); err != nil {
		t.Fatalf("update workspace knowledge bases: %v", err)
	}

	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("third reconcile failed: %v", err)
	}
	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("fourth reconcile failed: %v", err)
	}

	assertRuntimeDeploymentKnowledgeBaseMountSet(t, cl, "team-a", "workspace-runtime-ws-update", "shared-knowledge-bases", map[string]corev1.VolumeMount{
		"/knowledge/playbooks": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/playbooks",
			SubPath:   testKnowledgeBaseID3,
			ReadOnly:  true,
		},
	})
}

func TestShouldRequeueWorkspaceStatus(t *testing.T) {
	testCases := []struct {
		name   string
		status workspacev1alpha1.WorkspaceStatus
		want   bool
	}{
		{name: "pending", status: workspacev1alpha1.WorkspaceStatus{Phase: "Pending"}, want: true},
		{name: "reconciling", status: workspacev1alpha1.WorkspaceStatus{Phase: "Reconciling"}, want: true},
		{name: "running", status: workspacev1alpha1.WorkspaceStatus{Phase: "Running"}, want: false},
		{name: "failed", status: workspacev1alpha1.WorkspaceStatus{Phase: "Failed"}, want: false},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			got := shouldRequeueWorkspaceStatus(tc.status)
			if got != tc.want {
				t.Fatalf("shouldRequeueWorkspaceStatus(%s) = %v, want %v", tc.status.Phase, got, tc.want)
			}
		})
	}
}

func TestComponentRevisionFenceDoesNotScaleUnchangedComponents(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	workspace := &workspacev1alpha1.Workspace{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-fence", Namespace: "team-a"},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-fence",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testNextRuntimeInstanceID,
				Revision:          2,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-fence"),
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      true,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      true,
			},
			WorkspacePath: "/workspace",
		},
	}
	objects := []client.Object{workspace}
	for _, component := range []string{runtimeComponent, browserComponent, canvasComponent} {
		annotations := map[string]string{componentRevisionAnnotation: "1"}
		if component == runtimeComponent {
			annotations[runtimeInstanceAnnotation] = testRuntimeInstanceID
		}
		objects = append(objects, &appsv1.Deployment{
			ObjectMeta: metav1.ObjectMeta{Name: resourceName(component, "ws-fence"), Namespace: "team-a"},
			Spec: appsv1.DeploymentSpec{
				Replicas: int32Ptr(1),
				Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
					Annotations: annotations,
				}},
			},
		})
		objects = append(objects, readyPod(
			component+"-old",
			component+"-old-uid",
			"ws-fence",
			component,
			testRuntimeInstanceID,
		))
	}
	cl := fake.NewClientBuilder().WithScheme(scheme).WithObjects(objects...).Build()
	reconciler := &WorkspaceReconciler{Client: cl, Scheme: scheme}

	pending, err := reconciler.fenceComponentRevision(
		context.Background(),
		workspace,
		"team-a",
		runtimeComponent,
	)
	if err != nil || !pending {
		t.Fatalf("first fence = pending %v, error %v", pending, err)
	}
	for _, component := range []string{runtimeComponent, browserComponent, canvasComponent} {
		var deployment appsv1.Deployment
		key := types.NamespacedName{Name: resourceName(component, "ws-fence"), Namespace: "team-a"}
		if err := cl.Get(context.Background(), key, &deployment); err != nil {
			t.Fatalf("get %s: %v", component, err)
		}
		expectedReplicas := int32(1)
		if component == runtimeComponent {
			expectedReplicas = 0
		}
		if deployment.Spec.Replicas == nil || *deployment.Spec.Replicas != expectedReplicas {
			t.Fatalf("%s replicas = %v, want %d", component, deployment.Spec.Replicas, expectedReplicas)
		}
	}

	pending, err = reconciler.fenceComponentRevision(
		context.Background(),
		workspace,
		"team-a",
		runtimeComponent,
	)
	if err != nil || !pending {
		t.Fatalf("second fence = pending %v, error %v", pending, err)
	}
	pod := &corev1.Pod{ObjectMeta: metav1.ObjectMeta{
		Name: runtimeComponent + "-old", Namespace: "team-a",
	}}
	if err := cl.Delete(context.Background(), pod); err != nil {
		t.Fatalf("delete runtime old Pod: %v", err)
	}
	pending, err = reconciler.fenceComponentRevision(
		context.Background(),
		workspace,
		"team-a",
		runtimeComponent,
	)
	if err != nil || pending {
		t.Fatalf("final fence = pending %v, error %v", pending, err)
	}
}

func TestComponentRevisionFenceWaitsForTerminatingPodDeletion(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	workspace := &workspacev1alpha1.Workspace{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-fence", Namespace: "team-a"},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID: "ws-fence",
			Storage:     testWorkspaceStorageSpec(),
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				InstanceID: testNextRuntimeInstanceID,
				Revision:   2,
			},
		},
	}
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      resourceName(runtimeComponent, workspace.Spec.WorkspaceID),
			Namespace: workspace.Namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(0),
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
				Annotations: map[string]string{
					componentRevisionAnnotation: "1",
					runtimeInstanceAnnotation:   testRuntimeInstanceID,
				},
			}},
		},
	}
	pod := readyPod(
		runtimeComponent+"-terminating",
		runtimeComponent+"-terminating-uid",
		workspace.Spec.WorkspaceID,
		runtimeComponent,
		testRuntimeInstanceID,
	)
	deletionTimestamp := metav1.NewTime(time.Now().Add(2 * time.Minute))
	pod.DeletionTimestamp = &deletionTimestamp
	pod.Finalizers = []string{"test.aileron.io/retain"}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithObjects(workspace, deployment, pod).
		Build()
	reconciler := &WorkspaceReconciler{Client: cl, Scheme: scheme}

	pending, err := reconciler.fenceComponentRevision(
		context.Background(),
		workspace,
		workspace.Namespace,
		runtimeComponent,
	)
	if err != nil || !pending {
		t.Fatalf("terminating Pod fence = pending %v, error %v", pending, err)
	}
}

func TestWorkspaceStatusAdvancesRuntimeAndBootstrapIndependently(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	workspace := &workspacev1alpha1.Workspace{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-ready", Namespace: "team-a"},
		Status: workspacev1alpha1.WorkspaceStatus{
			Bootstrap: workspacev1alpha1.WorkspaceBootstrapStatus{
				ObservedRevision: 1,
				Phase:            "Succeeded",
			},
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-ready",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				MountRevision:     8,
				AccessRevision:    5,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-ready"),
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      true,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      true,
			},
			WorkspacePath: "/workspace",
		},
	}
	objects := []client.Object{workspace}
	componentPorts := map[string]int32{runtimeComponent: 3002, browserComponent: 6080, canvasComponent: 3003}
	for _, component := range []string{runtimeComponent, browserComponent, canvasComponent} {
		objects = append(objects, &appsv1.Deployment{
			ObjectMeta: metav1.ObjectMeta{Name: resourceName(component, "ws-ready"), Namespace: "team-a", Generation: 1},
			Spec: appsv1.DeploymentSpec{
				Replicas: int32Ptr(1),
				Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
					Annotations: componentAnnotations(workspace, component),
				}},
			},
			Status: appsv1.DeploymentStatus{
				ObservedGeneration: 1,
				ReadyReplicas:      1,
				AvailableReplicas:  1,
			},
		})
		objects = append(objects, &corev1.Service{
			ObjectMeta: metav1.ObjectMeta{Name: resourceName(component, "ws-ready"), Namespace: "team-a"},
			Spec:       corev1.ServiceSpec{Ports: []corev1.ServicePort{{Port: componentPorts[component]}}},
		})
		objects = append(objects, readyPod(
			component+"-ready",
			component+"-ready-uid",
			"ws-ready",
			component,
			testRuntimeInstanceID,
		))
	}
	cl := fake.NewClientBuilder().WithScheme(scheme).WithObjects(objects...).Build()
	reconciler := &WorkspaceReconciler{Client: cl, Scheme: scheme, PlatformPublicOrigin: defaultPlatformPublicOrigin()}

	if err := reconciler.populateWorkspaceStatus(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("populate status: %v", err)
	}
	if workspace.Status.Components.Runtime.MountObservedRevision != 8 ||
		workspace.Status.Components.Runtime.AccessObservedRevision != 5 {
		t.Fatalf("observed generation was not advanced: %+v", workspace.Status)
	}
	if workspace.Status.Components.Runtime.LastKnownGoodMountRevision != 8 {
		t.Fatalf(
			"last-known-good mount revision = %d, want 8",
			workspace.Status.Components.Runtime.LastKnownGoodMountRevision,
		)
	}
	if !workspace.Status.Components.Runtime.Ready || !workspace.Status.Components.Runtime.TerminalReady {
		t.Fatalf("runtime or terminal is not ready: %+v", workspace.Status.Components.Runtime)
	}
	if workspace.Status.Components.Runtime.PodUID != runtimeComponent+"-ready-uid" ||
		workspace.Status.Components.Browser.PodUID != browserComponent+"-ready-uid" ||
		workspace.Status.Components.Canvas.PodUID != canvasComponent+"-ready-uid" {
		t.Fatalf("unexpected Pod identities: %+v", workspace.Status.Components)
	}

	workspace.Spec.Runtime.MountRevision = 9
	if err := reconciler.populateWorkspaceStatus(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("populate candidate status: %v", err)
	}
	if workspace.Status.Components.Runtime.MountObservedRevision != 8 ||
		workspace.Status.Components.Runtime.LastKnownGoodMountRevision != 8 {
		t.Fatalf("unready candidate replaced last-known-good status: %+v", workspace.Status.Components.Runtime)
	}

	workspace.Spec.Runtime.MountRevision = 8
	if err := reconciler.populateWorkspaceStatus(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("populate compensation status: %v", err)
	}
	if workspace.Status.Components.Runtime.MountObservedRevision != 8 ||
		workspace.Status.Components.Runtime.LastKnownGoodMountRevision != 8 {
		t.Fatalf("compensation did not restore last-known-good revision: %+v", workspace.Status.Components.Runtime)
	}
}

func TestReconcileReturnsRequeueWhenWorkspaceNotReady(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-test",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-123",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-123"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableBrowserImage},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableCanvasImage},
			WorkspacePath: "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        false,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}

	result, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}
	if result.RequeueAfter != 5*time.Second {
		t.Fatalf("requeueAfter = %s, want %s", result.RequeueAfter, 5*time.Second)
	}
}

func TestWorkspaceReconcilerSkipsFirewallPoliciesWhenCiliumDisabled(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-test",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-123",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-123"),
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			Canvas:  workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"google.com"},
				},
			},
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        false,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-workspace-egress", ciliumNetworkPolicyGVK)
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-runtime-peer-egress", ciliumNetworkPolicyGVK)
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-browser-egress", ciliumNetworkPolicyGVK)
}

func TestWorkspaceReconcilerUpdatesExistingDeploymentImages(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-test",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-123",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeV2,
				RuntimeSecretName: runtimeSecretName("ws-123"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"google.com"},
				},
			},
		},
	}
	existingRuntime := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-runtime-ws-123",
			Namespace: "team-a",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(4),
			Strategy: appsv1.DeploymentStrategy{
				Type:          appsv1.RollingUpdateDeploymentStrategyType,
				RollingUpdate: &appsv1.RollingUpdateDeployment{},
			},
			Template: corev1.PodTemplateSpec{
				Spec: corev1.PodSpec{
					TerminationGracePeriodSeconds: int64Ptr(30),
					Containers: []corev1.Container{
						{
							Name:  "runtime",
							Image: testImmutableRuntimeV1,
							StartupProbe: &corev1.Probe{
								PeriodSeconds: 1,
							},
						},
					},
				},
			},
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, existingRuntime).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		ConfigNamespace:      "operator-system",
		CiliumEnabled:        true,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{
			Name:      workspace.Name,
			Namespace: workspace.Namespace,
		},
	})
	if err != nil {
		t.Fatalf("third reconcile failed: %v", err)
	}

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-123", testImmutableRuntimeV2)
	assertRuntimeDeploymentReplacementPolicy(t, cl, "team-a", "workspace-runtime-ws-123")
}

func TestRuntimeGenerationRoutingFencesPreviousInstance(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-generation-routing",
			Namespace: "team-a",
			UID:       types.UID("workspace-generation-routing-uid"),
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID: "ws-generation-routing",
			Storage:     testWorkspaceStorageSpec(),
			OwnerID:     "user-123",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Image:        testImmutableRuntimeImage,
			},
		},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithObjects(workspace).
		Build()
	reconciler := &WorkspaceReconciler{
		Client: cl,
		Scheme: scheme,
	}

	if err := reconciler.reconcileRuntimeDeployment(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile initial Runtime Deployment: %v", err)
	}
	if err := reconciler.reconcileRuntimeService(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile initial Runtime Service: %v", err)
	}
	name := resourceName(runtimeComponent, workspace.Spec.WorkspaceID)
	assertRuntimeGenerationRouting(
		t,
		cl,
		workspace.Namespace,
		name,
		testRuntimeInstanceID,
	)
	previousDeployment, previousService := runtimeGenerationRoutingResources(
		t,
		cl,
		workspace.Namespace,
		name,
	)

	workspace.Spec.Runtime.InstanceID = testNextRuntimeInstanceID
	workspace.Spec.Runtime.Revision = 2
	if err := reconciler.reconcileRuntimeDeployment(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile replacement Runtime Deployment: %v", err)
	}
	if err := reconciler.reconcileRuntimeService(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile replacement Runtime Service: %v", err)
	}
	assertRuntimeGenerationRouting(
		t,
		cl,
		workspace.Namespace,
		name,
		testNextRuntimeInstanceID,
	)
	currentDeployment, currentService := runtimeGenerationRoutingResources(
		t,
		cl,
		workspace.Namespace,
		name,
	)
	if !reflect.DeepEqual(
		previousDeployment.Spec.Selector.MatchLabels,
		currentDeployment.Spec.Selector.MatchLabels,
	) {
		t.Fatalf(
			"Runtime Deployment selector changed across instances: before=%v after=%v",
			previousDeployment.Spec.Selector.MatchLabels,
			currentDeployment.Spec.Selector.MatchLabels,
		)
	}

	if reflect.DeepEqual(previousService.Spec.Selector, currentService.Spec.Selector) {
		t.Fatalf(
			"Runtime Service selector did not advance across instances: %v",
			currentService.Spec.Selector,
		)
	}
	previousPodStillMatches := true
	for key, value := range currentService.Spec.Selector {
		if previousDeployment.Spec.Template.Labels[key] != value {
			previousPodStillMatches = false
			break
		}
	}
	if previousPodStillMatches {
		t.Fatalf(
			"previous Runtime Pod labels still match replacement Service selector: pod=%v service=%v",
			previousDeployment.Spec.Template.Labels,
			currentService.Spec.Selector,
		)
	}
}

func TestBrowserGenerationIdentityReplacesOnlyBrowserPodTemplate(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-browser-generation",
			Namespace: "team-a",
			UID:       types.UID("workspace-browser-generation-uid"),
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID: "ws-browser-generation",
			Storage:     testWorkspaceStorageSpec(),
			Bootstrap: workspacev1alpha1.WorkspaceBootstrapSpec{
				Revision: 1,
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				Enabled:      true,
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Image:        testImmutableBrowserImage,
			},
		},
		Status: workspacev1alpha1.WorkspaceStatus{
			Bootstrap: workspacev1alpha1.WorkspaceBootstrapStatus{
				ObservedRevision: 1,
				Phase:            "Succeeded",
			},
		},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithObjects(workspace).
		Build()
	reconciler := &WorkspaceReconciler{
		Client: cl,
		Scheme: scheme,
	}

	if err := reconciler.reconcileBrowserDeployment(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile initial Browser Deployment: %v", err)
	}
	name := resourceName(browserComponent, workspace.Spec.WorkspaceID)
	previous := &appsv1.Deployment{}
	if err := cl.Get(
		context.Background(),
		client.ObjectKey{Namespace: workspace.Namespace, Name: name},
		previous,
	); err != nil {
		t.Fatalf("get initial Browser Deployment: %v", err)
	}

	workspace.Spec.Browser.InstanceID = testNextRuntimeInstanceID
	if err := reconciler.reconcileBrowserDeployment(
		context.Background(),
		workspace,
		workspace.Namespace,
	); err != nil {
		t.Fatalf("reconcile replacement Browser Deployment: %v", err)
	}
	current := &appsv1.Deployment{}
	if err := cl.Get(
		context.Background(),
		client.ObjectKey{Namespace: workspace.Namespace, Name: name},
		current,
	); err != nil {
		t.Fatalf("get replacement Browser Deployment: %v", err)
	}

	if previous.Spec.Template.Annotations[componentInstanceAnnotation] !=
		testRuntimeInstanceID {
		t.Fatalf(
			"initial Browser instance annotation mismatch: %v",
			previous.Spec.Template.Annotations,
		)
	}
	if current.Spec.Template.Annotations[componentInstanceAnnotation] !=
		testNextRuntimeInstanceID {
		t.Fatalf(
			"replacement Browser instance annotation mismatch: %v",
			current.Spec.Template.Annotations,
		)
	}
	if !reflect.DeepEqual(
		previous.Spec.Selector.MatchLabels,
		current.Spec.Selector.MatchLabels,
	) {
		t.Fatalf(
			"Browser Deployment selector changed across instances: before=%v after=%v",
			previous.Spec.Selector.MatchLabels,
			current.Spec.Selector.MatchLabels,
		)
	}
}

func TestWorkspaceReconcilerDeleteCleansManagedResourcesAndRemovesFinalizer(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	now := metav1.Now()
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:              "workspace-test",
			Namespace:         "team-a",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-123",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-123"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"google.com"},
				},
			},
		},
	}

	managedObjects := []client.Object{
		workspace,
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-123", Namespace: "team-a"}},
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-123", Namespace: "team-a"}},
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-canvas-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-canvas-ws-123", Namespace: "team-a"}},
		&corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Name: "workspace-pvc-ws-123", Namespace: "team-a"}},
		&corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-home-pvc-ws-123", Namespace: "team-a"}},
		&corev1.ServiceAccount{ObjectMeta: metav1.ObjectMeta{Name: "workspace-workload-ws-123", Namespace: "team-a"}},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(managedObjects...).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        true,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("reconcile delete failed: %v", err)
	}

	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-browser-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-canvas-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-browser-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-canvas-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-pvc-ws-123", &corev1.PersistentVolumeClaim{})
	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-home-pvc-ws-123", &corev1.PersistentVolumeClaim{})
	assertObjectDeleted(t, cl, "team-a", "workspace-workload-ws-123", &corev1.ServiceAccount{})
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-workspace-egress", ciliumNetworkPolicyGVK)
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-runtime-peer-egress", ciliumNetworkPolicyGVK)
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-browser-egress", ciliumNetworkPolicyGVK)

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      workspace.Name,
		Namespace: workspace.Namespace,
	}, &updated); err != nil {
		return
	}
	if len(updated.Finalizers) != 0 {
		t.Fatalf("expected finalizers to be removed, got %v", updated.Finalizers)
	}
}

func TestWorkspaceReconcilerDeleteWaitsForManagedPodsAndBothPVCsBeforeRemovingFinalizer(
	t *testing.T,
) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	now := metav1.Now()
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:              "workspace-delete-wait",
			Namespace:         "team-a",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-delete-wait",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
		},
	}
	workspacePVC := &corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{
		Name:      resourceName(pvcComponent, workspace.Spec.WorkspaceID),
		Namespace: workspace.Namespace,
	}}
	runtimeHomePVC := &corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{
		Name:      resourceName(runtimeHomePVCComponent, workspace.Spec.WorkspaceID),
		Namespace: workspace.Namespace,
	}}
	objects := []client.Object{workspace, workspacePVC, runtimeHomePVC}
	managedPods := make([]*corev1.Pod, 0, 3)
	for _, component := range []string{
		runtimeComponent,
		browserComponent,
		canvasComponent,
	} {
		pod := &corev1.Pod{ObjectMeta: metav1.ObjectMeta{
			Name:      component + "-delete-wait",
			Namespace: workspace.Namespace,
			Labels: map[string]string{
				workspaceIDLabel: workspace.Spec.WorkspaceID,
				componentLabel:   component,
			},
		}}
		managedPods = append(managedPods, pod)
		objects = append(objects, pod)
	}
	baseClient := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(objects...).
		Build()
	holdingClient := &persistentVolumeClaimDeleteHoldingClient{
		Client:         baseClient,
		holdDeletes:    true,
		deleteAttempts: map[types.NamespacedName]int{},
	}
	reconciler := &WorkspaceReconciler{
		Client:               holdingClient,
		Scheme:               scheme,
		CiliumEnabled:        false,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}
	request := ctrl.Request{NamespacedName: types.NamespacedName{
		Name: workspace.Name, Namespace: workspace.Namespace,
	}}

	for attempt := 1; attempt <= 2; attempt++ {
		result, err := reconciler.Reconcile(context.Background(), request)
		if err != nil {
			t.Fatalf("delete reconcile attempt %d failed: %v", attempt, err)
		}
		if result.RequeueAfter <= 0 {
			t.Fatalf("delete reconcile attempt %d did not requeue", attempt)
		}
		assertWorkspaceFinalizerPresent(t, baseClient, workspace.Namespace, workspace.Name)
	}
	for _, pvc := range []*corev1.PersistentVolumeClaim{workspacePVC, runtimeHomePVC} {
		key := types.NamespacedName{Name: pvc.Name, Namespace: pvc.Namespace}
		if holdingClient.deleteAttempts[key] != 2 {
			t.Fatalf(
				"PVC %s delete attempts = %d, want 2",
				key,
				holdingClient.deleteAttempts[key],
			)
		}
	}

	for _, pod := range managedPods {
		if err := baseClient.Delete(context.Background(), pod); err != nil {
			t.Fatalf("delete managed Pod %s: %v", pod.Name, err)
		}
	}
	result, err := reconciler.Reconcile(context.Background(), request)
	if err != nil {
		t.Fatalf("delete reconcile while PVCs remain failed: %v", err)
	}
	if result.RequeueAfter <= 0 {
		t.Fatal("delete reconcile did not wait for persistent volume claims")
	}
	assertWorkspaceFinalizerPresent(t, baseClient, workspace.Namespace, workspace.Name)
	for _, pvc := range []*corev1.PersistentVolumeClaim{workspacePVC, runtimeHomePVC} {
		var retained corev1.PersistentVolumeClaim
		if err := baseClient.Get(
			context.Background(),
			client.ObjectKeyFromObject(pvc),
			&retained,
		); err != nil {
			t.Fatalf("get retained PVC %s/%s: %v", pvc.Namespace, pvc.Name, err)
		}
	}

	holdingClient.holdDeletes = false
	result, err = reconciler.Reconcile(context.Background(), request)
	if err != nil {
		t.Fatalf("final delete reconcile failed: %v", err)
	}
	if result.RequeueAfter != 0 {
		t.Fatalf("final delete reconcile requeue = %s, want 0", result.RequeueAfter)
	}
	assertObjectDeleted(
		t,
		baseClient,
		workspace.Namespace,
		workspacePVC.Name,
		&corev1.PersistentVolumeClaim{},
	)
	assertObjectDeleted(
		t,
		baseClient,
		workspace.Namespace,
		runtimeHomePVC.Name,
		&corev1.PersistentVolumeClaim{},
	)
	assertWorkspaceFinalizerRemovedOrWorkspaceDeleted(
		t,
		baseClient,
		workspace.Namespace,
		workspace.Name,
	)
}

func TestWorkspaceReconcilerStatusIncludesRunningPhase(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-ws-running",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-running",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-running"),
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      true,
				Image:        testImmutableBrowserImage,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				DesiredState: "Running",
				InstanceID:   testRuntimeInstanceID,
				Revision:     1,
				Enabled:      false,
				Image:        testImmutableCanvasImage,
			},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"google.com"},
				},
			},
		},
	}
	configureTestBrowserCredential(&workspace.Spec.Browser, workspace.Spec.WorkspaceID)

	runtimeDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-runtime-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
				Annotations: componentAnnotations(workspace, runtimeComponent),
			}},
		},
		Status: appsv1.DeploymentStatus{
			ObservedGeneration: 1,
			ReadyReplicas:      1,
			AvailableReplicas:  1,
			Replicas:           1,
		},
	}
	browserDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-browser-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
				Annotations: componentAnnotations(workspace, browserComponent),
			}},
		},
		Status: appsv1.DeploymentStatus{
			ObservedGeneration: 1,
			ReadyReplicas:      1,
			AvailableReplicas:  1,
			Replicas:           1,
		},
	}
	canvasDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-canvas-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(0),
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{
				Annotations: componentAnnotations(workspace, canvasComponent),
			}},
		},
	}
	runtimePod := readyPod("runtime-pod", "runtime-pod-uid", "ws-running", runtimeComponent, testRuntimeInstanceID)
	browserPod := readyPod("browser-pod", "browser-pod-uid", "ws-running", browserComponent, testRuntimeInstanceID)
	runtimeService := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-running", Namespace: "team-a"},
		Spec: corev1.ServiceSpec{
			Ports: []corev1.ServicePort{{Name: "http", Port: 3002}},
		},
	}
	browserService := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-running", Namespace: "team-a"},
		Spec: corev1.ServiceSpec{
			Type:  corev1.ServiceTypeLoadBalancer,
			Ports: []corev1.ServicePort{{Name: "webrtc", Port: 6080}},
		},
		Status: corev1.ServiceStatus{
			LoadBalancer: corev1.LoadBalancerStatus{
				Ingress: []corev1.LoadBalancerIngress{{Hostname: "browser.example.com"}},
			},
		},
	}
	canvasService := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-canvas-ws-running", Namespace: "team-a"},
		Spec: corev1.ServiceSpec{
			Ports: []corev1.ServicePort{{Name: "http", Port: 3003}},
		},
	}
	pvc := &corev1.PersistentVolumeClaim{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-pvc-ws-running", Namespace: "team-a"},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(
			workspace,
			runtimeDeployment,
			browserDeployment,
			canvasDeployment,
			runtimePod,
			browserPod,
			runtimeService,
			browserService,
			canvasService,
			pvc,
		).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                   cl,
		Scheme:                   scheme,
		ConfigNamespace:          "operator-system",
		CiliumEnabled:            true,
		PlatformPublicOrigin:     defaultPlatformPublicOrigin(),
		BrowserCredentialKeyring: testBrowserCredentialDeriver{},
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("third reconcile failed: %v", err)
	}

	assertWorkspaceStatus(t, cl, "team-a", "workspace-ws-running", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.Phase != "Running" {
			t.Fatalf("phase = %s, want Running; components = %+v", status.Phase, status.Components)
		}
		if status.Components.Runtime.Phase != "Running" {
			t.Fatalf("runtime phase = %s, want Running", status.Components.Runtime.Phase)
		}
		if status.Components.Browser.Phase != "Running" {
			t.Fatalf("browser phase = %s, want Running", status.Components.Browser.Phase)
		}
		if status.Components.Canvas.Phase != "Disabled" {
			t.Fatalf("canvas phase = %s, want Disabled", status.Components.Canvas.Phase)
		}
	})

	deploymentCountingClient := &deploymentUpdateCountingClient{
		Client:  cl,
		updates: map[types.NamespacedName]int{},
	}
	countingClient := &statusUpdateCountingClient{Client: deploymentCountingClient}
	reconciler.Client = countingClient
	if _, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	}); err != nil {
		t.Fatalf("stable reconcile failed: %v", err)
	}
	if countingClient.statusUpdates != 0 {
		t.Fatalf("stable Running reconcile sent %d status update(s), want 0", countingClient.statusUpdates)
	}
	assertNoDeploymentUpdates(t, deploymentCountingClient)

	replacementRuntimePod := readyPod(
		"runtime-pod-replacement",
		"runtime-pod-replacement-uid",
		"ws-running",
		runtimeComponent,
		testRuntimeInstanceID,
	)
	unmanagedPod := replacementRuntimePod.DeepCopy()
	unmanagedPod.Labels[componentLabel] = "unmanaged-component"
	if requests := reconciler.requestsForManagedPod(context.Background(), unmanagedPod); len(requests) != 0 {
		t.Fatalf("unmanaged Pod mapped to Workspace requests: %v", requests)
	}
	unlabeledPod := replacementRuntimePod.DeepCopy()
	delete(unlabeledPod.Labels, workspaceIDLabel)
	if requests := reconciler.requestsForManagedPod(context.Background(), unlabeledPod); len(requests) != 0 {
		t.Fatalf("Pod without workspace label mapped to Workspace requests: %v", requests)
	}

	requests := reconciler.requestsForManagedPod(context.Background(), replacementRuntimePod)
	wantRequest := reconcile.Request{NamespacedName: types.NamespacedName{
		Name:      workspace.Name,
		Namespace: workspace.Namespace,
	}}
	if len(requests) != 1 || requests[0] != wantRequest {
		t.Fatalf("managed replacement Pod requests = %v, want [%v]", requests, wantRequest)
	}
	if err := cl.Delete(context.Background(), runtimePod); err != nil {
		t.Fatalf("delete original runtime Pod: %v", err)
	}
	if err := cl.Create(context.Background(), replacementRuntimePod); err != nil {
		t.Fatalf("create replacement runtime Pod: %v", err)
	}

	countingClient.statusUpdates = 0
	deploymentCountingClient.updates = map[types.NamespacedName]int{}
	if _, err := reconciler.Reconcile(context.Background(), requests[0]); err != nil {
		t.Fatalf("replacement Pod reconcile failed: %v", err)
	}
	if countingClient.statusUpdates != 1 {
		t.Fatalf("replacement Pod reconcile sent %d status update(s), want 1", countingClient.statusUpdates)
	}
	assertNoDeploymentUpdates(t, deploymentCountingClient)
	assertWorkspaceStatus(t, cl, workspace.Namespace, workspace.Name, func(status workspacev1alpha1.WorkspaceStatus) {
		if status.Components.Runtime.PodUID != string(replacementRuntimePod.UID) {
			t.Fatalf(
				"runtime Pod UID = %s, want %s",
				status.Components.Runtime.PodUID,
				replacementRuntimePod.UID,
			)
		}
	})

	countingClient.statusUpdates = 0
	deploymentCountingClient.updates = map[types.NamespacedName]int{}
	if _, err := reconciler.Reconcile(context.Background(), requests[0]); err != nil {
		t.Fatalf("stable replacement Pod reconcile failed: %v", err)
	}
	if countingClient.statusUpdates != 0 {
		t.Fatalf("stable replacement Pod reconcile sent %d status update(s), want 0", countingClient.statusUpdates)
	}
	assertNoDeploymentUpdates(t, deploymentCountingClient)
}

func TestWorkspaceReconcilerDeleteUsesMetadataNamespaceWhenTargetNamespaceMismatches(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	now := metav1.Now()
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:              "workspace-delete-mismatch",
			Namespace:         "operator-system",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-delete-mismatch",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
		},
	}
	deploymentName := resourceName(runtimeComponent, workspace.Spec.WorkspaceID)
	canonicalDeployment := &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{
		Name: deploymentName, Namespace: workspace.Namespace,
	}}
	foreignDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: deploymentName, Namespace: "team-a"},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{Spec: corev1.PodSpec{
				Containers: []corev1.Container{{Name: runtimeComponent, Image: "foreign:test"}},
			}},
		},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, canonicalDeployment, foreignDeployment).
		Build()
	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        false,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	if _, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	}); err != nil {
		t.Fatalf("reconcile delete with namespace mismatch: %v", err)
	}

	assertObjectDeleted(t, cl, workspace.Namespace, deploymentName, &appsv1.Deployment{})
	var unchanged appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: deploymentName, Namespace: foreignDeployment.Namespace,
	}, &unchanged); err != nil {
		t.Fatalf("get foreign deployment: %v", err)
	}
	if got := unchanged.Spec.Template.Spec.Containers[0].Image; got != "foreign:test" {
		t.Fatalf("foreign deployment image = %q, want foreign:test", got)
	}

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: workspace.Name, Namespace: workspace.Namespace,
	}, &updated); err == nil && len(updated.Finalizers) != 0 {
		t.Fatalf("expected finalizers to be removed, got %v", updated.Finalizers)
	}
}

func TestWorkspaceReconcilerUpdatesWorkspaceFirewallPolicy(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-firewall",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-fw",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-fw"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableBrowserImage},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableCanvasImage},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Revision: 7,
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"internal.example.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"browser.example.com"},
				},
			},
		},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		ConfigNamespace:      "operator-system",
		CiliumEnabled:        true,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-fw-workspace-egress", []string{
		"internal.example.com",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-fw-browser-egress", []string{
		"browser.example.com",
	})
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-fw-workspace-egress", "operator-system")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-fw-browser-egress", "operator-system")
	assertFirewallPolicyIdentity(
		t,
		cl,
		"team-a",
		"ws-ws-fw-workspace-egress",
		"workspace-firewall",
		"7",
		"",
		"aileron.io/firewall-group",
		"workspace",
	)
	assertFirewallPolicyIdentity(
		t,
		cl,
		"team-a",
		"ws-ws-fw-browser-egress",
		"workspace-firewall",
		"7",
		"",
		"aileron.io/firewall-group",
		"browser",
	)
}

func TestWorkspaceReconcilerUsesMetadataNamespaceWhenTargetNamespaceIsEmpty(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-fallback",
			Namespace: "team-a",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:   workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID: "ws-fallback",
			Storage:     testWorkspaceStorageSpec(),
			OwnerID:     "user-123",
			Provisioner: "kubernetes",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             testImmutableRuntimeImage,
				RuntimeSecretName: runtimeSecretName("ws-fallback"),
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableBrowserImage},
			Canvas:        workspacev1alpha1.WorkspaceOptionalComponentSpec{DesiredState: "Running", Revision: 1, Enabled: true, Image: testImmutableCanvasImage},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Revision: 1,
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
				},
			},
		},
	}
	configureTestBrowserCredential(&workspace.Spec.Browser, workspace.Spec.WorkspaceID)

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                   cl,
		Scheme:                   scheme,
		CiliumEnabled:            true,
		PlatformPublicOrigin:     defaultPlatformPublicOrigin(),
		BrowserCredentialKeyring: testBrowserCredentialDeriver{},
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	_, err = reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-fallback", testImmutableRuntimeImage)
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-runtime-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-browser-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-canvas-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-runtime-ws-fallback", &corev1.Service{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-pvc-ws-fallback", &corev1.PersistentVolumeClaim{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-runtime-home-pvc-ws-fallback", &corev1.PersistentVolumeClaim{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-workload-ws-fallback", &corev1.ServiceAccount{}, "Workspace", "workspace-fallback")
	assertWorkspaceStatus(t, cl, "team-a", "workspace-fallback", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.TargetNamespace != "team-a" {
			t.Fatalf("target namespace = %s, want team-a", status.TargetNamespace)
		}
	})
}

func TestWorkspaceReconcilerDeleteWithoutManagedResourcesStillRemovesFinalizer(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	now := metav1.Now()
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:              "workspace-empty-delete",
			Namespace:         "team-a",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-empty-delete",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:               cl,
		Scheme:               scheme,
		CiliumEnabled:        true,
		PlatformPublicOrigin: defaultPlatformPublicOrigin(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("delete reconcile failed: %v", err)
	}

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      workspace.Name,
		Namespace: workspace.Namespace,
	}, &updated); err != nil {
		return
	}
	if len(updated.Finalizers) != 0 {
		t.Fatalf("expected finalizers to be removed, got %v", updated.Finalizers)
	}
}

func mustAddSchemes(t *testing.T, scheme *runtime.Scheme) {
	t.Helper()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		t.Fatalf("add client-go scheme: %v", err)
	}
	if err := workspacev1alpha1.AddToScheme(scheme); err != nil {
		t.Fatalf("add workspace scheme: %v", err)
	}
}

func readyPod(
	name string,
	uid string,
	workspaceID string,
	component string,
	runtimeInstanceID string,
) *corev1.Pod {
	annotations := map[string]string{
		componentRevisionAnnotation: "1",
		componentInstanceAnnotation: runtimeInstanceID,
	}
	if component == runtimeComponent {
		annotations[runtimeInstanceAnnotation] = runtimeInstanceID
	}
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: "team-a",
			UID:       types.UID(uid),
			Labels: map[string]string{
				"aileron.io/workspace-id": workspaceID,
				"aileron.io/component":    component,
			},
			Annotations: annotations,
		},
		Status: corev1.PodStatus{Conditions: []corev1.PodCondition{{
			Type: corev1.PodReady, Status: corev1.ConditionTrue,
		}}},
	}
}

func assertDeploymentImage(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	expectedImage string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if got := deployment.Spec.Template.Spec.Containers[0].Image; got != expectedImage {
		t.Fatalf("deployment %s/%s image = %s, want %s", namespace, name, got, expectedImage)
	}
}

func testResourceRequirements(
	requestCPU string,
	requestMemory string,
	limitCPU string,
	limitMemory string,
) *corev1.ResourceRequirements {
	return &corev1.ResourceRequirements{
		Requests: corev1.ResourceList{
			corev1.ResourceCPU:    resource.MustParse(requestCPU),
			corev1.ResourceMemory: resource.MustParse(requestMemory),
		},
		Limits: corev1.ResourceList{
			corev1.ResourceCPU:    resource.MustParse(limitCPU),
			corev1.ResourceMemory: resource.MustParse(limitMemory),
		},
	}
}

func assertDeploymentResources(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	requestCPU string,
	requestMemory string,
	limitCPU string,
	limitMemory string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if len(deployment.Spec.Template.Spec.Containers) == 0 {
		t.Fatalf("deployment %s/%s has no containers", namespace, name)
	}

	got := deployment.Spec.Template.Spec.Containers[0].Resources
	want := testResourceRequirements(requestCPU, requestMemory, limitCPU, limitMemory)
	if !equality.Semantic.DeepEqual(got, *want) {
		t.Fatalf("deployment %s/%s resources = %#v, want %#v", namespace, name, got, *want)
	}
}

func assertBrowserConnectivityProbe(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	for _, container := range deployment.Spec.Template.Spec.Containers {
		if container.Name != "connectivity-probe" {
			continue
		}
		if container.Image != "workspace-operator:test" ||
			container.SecurityContext == nil ||
			deployment.Spec.Template.Spec.AutomountServiceAccountToken == nil ||
			*deployment.Spec.Template.Spec.AutomountServiceAccountToken {
			t.Fatalf("Browser connectivity probe is not isolated: %#v", container)
		}
		envByName := map[string]corev1.EnvVar{}
		for _, env := range container.Env {
			if env.ValueFrom != nil {
				t.Fatalf("Browser connectivity probe materializes a Secret as env: %#v", env)
			}
			envByName[env.Name] = env
		}
		if envByName["TURN_REST_SHARED_SECRET_FILE"].Value != "/run/secrets/turn-rest/turn-rest-shared-secret" ||
			envByName["TURN_BACKEND_ICE_SERVERS_JSON_FILE"].Value != "/run/secrets/browser-turn/backend-ice-servers.json" ||
			envByName["TURN_BACKEND_ICE_SERVERS_JSON"].Name != "" ||
			envByName["TURN_PROBE_IDENTITY"].Value != "backend:ws-123" {
			t.Fatalf("Browser connectivity probe has no file-only TURN REST issuer: %#v", container.Env)
		}
		backendMountFound := false
		turnRESTMountFound := false
		for _, mount := range container.VolumeMounts {
			if mount.Name == "browser-turn-ice" && mount.MountPath == "/run/secrets/browser-turn" && mount.ReadOnly {
				backendMountFound = true
			}
			if mount.Name == "turn-rest" && mount.MountPath == "/run/secrets/turn-rest" && mount.ReadOnly {
				turnRESTMountFound = true
			}
		}
		if !backendMountFound || !turnRESTMountFound {
			t.Fatalf("Browser connectivity probe has incomplete read-only TURN mounts: %#v", container.VolumeMounts)
		}
		return
	}
	t.Fatalf("deployment %s/%s has no connectivity probe", namespace, name)
}

func assertBrowserSecretFileContract(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if len(deployment.Spec.Template.Spec.Containers) == 0 {
		t.Fatalf("deployment %s/%s has no Browser container", namespace, name)
	}
	browser := deployment.Spec.Template.Spec.Containers[0]
	for _, env := range browser.Env {
		if env.ValueFrom != nil {
			t.Fatalf("Browser materializes a Secret as env: %#v", env)
		}
		if strings.Contains(env.Name, "PASSWORD") && !strings.HasSuffix(env.Name, "_FILE") {
			t.Fatalf("Browser exposes a password value through env: %#v", env)
		}
	}
	if len(browser.Command) != 2 || browser.Command[0] != "/bin/sh" || browser.Command[1] != "-ec" || len(browser.Args) != 1 {
		t.Fatalf("Browser has no fail-closed Secret-file startup wrapper: %#v %#v", browser.Command, browser.Args)
	}
	if !strings.Contains(browser.Args[0], "chmod 0600") ||
		!strings.Contains(browser.Args[0], "env -u NEKO_MEMBER_MULTIUSER_USER_PASSWORD") {
		t.Fatalf("Browser startup wrapper does not sanitize transient credentials: %s", browser.Args[0])
	}
	if !strings.Contains(
		browser.Args[0],
		`install -m 0600 /dev/null "${generated_config}"`,
	) {
		t.Fatalf("Browser startup wrapper does not create writable generated configuration: %s", browser.Args[0])
	}
	if !strings.Contains(browser.Args[0], `/^(member|webrtc):[[:space:]]*$/`) {
		t.Fatalf("Browser startup wrapper does not replace existing top-level Neko sections: %s", browser.Args[0])
	}
	assertBrowserGeneratedConfigComposer(t, browser.Args[0])
	if strings.Contains(browser.Args[0], `export NEKO_MEMBER_MULTIUSER_USER_PASSWORD="${browser_user_password}"`) ||
		strings.Contains(browser.Args[0], `export NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD="${browser_admin_password}"`) {
		t.Fatalf("Browser startup wrapper exports a mounted Secret: %s", browser.Args[0])
	}
	mountFound := false
	for _, mount := range browser.VolumeMounts {
		if mount.Name == "browser-credentials" && mount.MountPath == "/run/secrets/browser-credentials" && mount.ReadOnly {
			mountFound = true
		}
	}
	if !mountFound {
		t.Fatalf("Browser has no read-only credential mount: %#v", browser.VolumeMounts)
	}
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.Name != "browser-credentials" || volume.Secret == nil {
			continue
		}
		if volume.Secret.SecretName != "workspace-browser-credential-ws-123-r1" ||
			volume.Secret.DefaultMode == nil || *volume.Secret.DefaultMode != 0440 {
			t.Fatalf("Browser credential volume is not fail-closed: %#v", volume.Secret)
		}
		return
	}
	t.Fatalf("deployment %s/%s has no Browser credential Secret volume", namespace, name)
}

func assertBrowserGeneratedConfigComposer(t *testing.T, startupScript string) {
	t.Helper()
	fixtureDir, err := os.MkdirTemp("/tmp", "browser-composer-fixture-")
	if err != nil {
		t.Fatalf("create Browser composer fixture directory: %v", err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(fixtureDir) })
	if err := os.Chmod(fixtureDir, 0o755); err != nil {
		t.Fatalf("make Browser composer fixture directory traversable: %v", err)
	}
	secretPaths := map[string]string{
		"NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE":  strings.Repeat("a", 43),
		"NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": strings.Repeat("b", 43),
	}
	commandEnvironment := os.Environ()
	for name, value := range secretPaths {
		path := filepath.Join(fixtureDir, name)
		if err := os.WriteFile(path, []byte(value), 0o644); err != nil {
			t.Fatalf("write Browser composer secret fixture: %v", err)
		}
		commandEnvironment = append(commandEnvironment, name+"="+path)
	}

	seedPath := "/etc/neko/neko.kubernetes.yaml"
	supervisorPath := "/etc/neko/supervisord.kubernetes.conf"
	entrypointPath := "/usr/local/bin/aileron-browser-kubernetes-entrypoint"
	for _, path := range []string{seedPath, supervisorPath, entrypointPath} {
		if _, err := os.Stat(path); err == nil {
			t.Fatalf("Browser composer test refuses to overwrite existing %s", path)
		} else if !os.IsNotExist(err) {
			t.Fatalf("inspect Browser composer fixture target %s: %v", path, err)
		}
	}
	if err := os.MkdirAll(filepath.Dir(seedPath), 0o755); err != nil {
		t.Fatalf("create Neko fixture directory: %v", err)
	}
	if err := os.WriteFile(seedPath, []byte("server:\n  bind: :8080\nmember:\n  provider: singleuser\nwebrtc:\n  icelite: true\nother:\n  enabled: true\n"), 0o644); err != nil {
		t.Fatalf("write Neko seed fixture: %v", err)
	}
	if err := os.WriteFile(supervisorPath, []byte("command=/usr/bin/neko --config /etc/neko/neko.kubernetes.yaml\n"), 0o644); err != nil {
		t.Fatalf("write Neko supervisor fixture: %v", err)
	}
	if err := os.WriteFile(entrypointPath, []byte("#!/bin/sh\nexit 0\n"), 0o755); err != nil {
		t.Fatalf("write Browser entrypoint fixture: %v", err)
	}
	stateDir := "/tmp/aileron-browser"
	if err := os.RemoveAll(stateDir); err != nil {
		t.Fatalf("reset Browser generated state: %v", err)
	}
	t.Cleanup(func() {
		_ = os.RemoveAll(stateDir)
		_ = os.Remove(seedPath)
		_ = os.Remove(supervisorPath)
		_ = os.Remove(entrypointPath)
	})

	runComposer := func() []byte {
		command := exec.Command("/bin/sh", "-ec", startupScript)
		command.Env = commandEnvironment
		command.SysProcAttr = &syscall.SysProcAttr{Credential: &syscall.Credential{Uid: 65532, Gid: 65532}}
		if output, err := command.CombinedOutput(); err != nil {
			t.Fatalf("execute Browser config composer as runtime UID: %v\n%s", err, output)
		}
		generatedPath := filepath.Join(stateDir, "neko.generated.yaml")
		content, err := os.ReadFile(generatedPath)
		if err != nil {
			t.Fatalf("read generated Browser config: %v", err)
		}
		info, err := os.Stat(generatedPath)
		if err != nil {
			t.Fatalf("stat generated Browser config: %v", err)
		}
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("generated Browser config mode = %04o, want 0600", info.Mode().Perm())
		}
		stat, ok := info.Sys().(*syscall.Stat_t)
		if !ok || stat.Uid != 65532 {
			t.Fatalf("generated Browser config owner UID = %v, want 65532", stat)
		}
		return content
	}

	first := runComposer()
	second := runComposer()
	if !reflect.DeepEqual(first, second) {
		t.Fatal("Browser config composer is not idempotent")
	}
	var document yaml.Node
	if err := yaml.Unmarshal(second, &document); err != nil {
		t.Fatalf("generated Browser config is not unambiguous YAML: %v", err)
	}
	if len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode {
		t.Fatalf("generated Browser config has no top-level mapping: %#v", document)
	}
	sectionCounts := map[string]int{}
	for index := 0; index < len(document.Content[0].Content); index += 2 {
		sectionCounts[document.Content[0].Content[index].Value]++
	}
	for _, section := range []string{"member", "webrtc"} {
		if sectionCounts[section] != 1 {
			t.Fatalf("generated Browser config section %s count = %d, want 1", section, sectionCounts[section])
		}
	}
	if sectionCounts["server"] != 1 || sectionCounts["other"] != 1 {
		t.Fatalf("Browser config composer did not preserve unmanaged sections: %#v", sectionCounts)
	}
	var generated map[string]map[string]interface{}
	if err := yaml.Unmarshal(second, &generated); err != nil {
		t.Fatalf("decode generated Browser config behavior: %v", err)
	}
	if generated["member"]["provider"] != "multiuser" || generated["webrtc"]["icelite"] != false {
		t.Fatalf("Browser config composer did not replace managed sections: %#v", generated)
	}
}

func assertRuntimeDeploymentReplacementPolicy(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	if deployment.Spec.Replicas == nil || *deployment.Spec.Replicas != 1 {
		t.Fatalf("deployment %s/%s replicas = %v, want 1", namespace, name, deployment.Spec.Replicas)
	}
	if deployment.Spec.Strategy.Type != appsv1.RecreateDeploymentStrategyType {
		t.Fatalf("deployment %s/%s strategy = %s, want Recreate", namespace, name, deployment.Spec.Strategy.Type)
	}
	if deployment.Spec.Strategy.RollingUpdate != nil {
		t.Fatalf("deployment %s/%s retained rolling update settings", namespace, name)
	}
	if deployment.Spec.Template.Spec.TerminationGracePeriodSeconds == nil ||
		*deployment.Spec.Template.Spec.TerminationGracePeriodSeconds != 120 {
		t.Fatalf(
			"deployment %s/%s termination grace = %v, want 120",
			namespace,
			name,
			deployment.Spec.Template.Spec.TerminationGracePeriodSeconds,
		)
	}

	container := deployment.Spec.Template.Spec.Containers[0]
	assertHTTPHealthProbe(t, "startup", container.StartupProbe, 5, 2, 60)
	assertRuntimeAndTerminalReadinessProbe(t, container.ReadinessProbe)
	assertHTTPHealthProbe(t, "liveness", container.LivenessProbe, 10, 2, 3)
}

func assertRuntimeAndTerminalReadinessProbe(t *testing.T, probe *corev1.Probe) {
	t.Helper()
	if probe == nil || probe.Exec == nil || len(probe.Exec.Command) != 3 {
		t.Fatalf("readiness probe = %v, want composite exec probe", probe)
	}
	if probe.Exec.Command[0] != "python3" ||
		!strings.Contains(probe.Exec.Command[2], "terminal_service") {
		t.Fatalf("readiness command = %v, want runtime and terminal check", probe.Exec.Command)
	}
	if probe.PeriodSeconds != 5 || probe.TimeoutSeconds != 2 ||
		probe.FailureThreshold != 3 || probe.SuccessThreshold != 1 {
		t.Fatalf("unexpected readiness probe timings: %+v", probe)
	}
}

func assertDeploymentGeneration(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	includeMountRevision bool,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if deployment.Spec.Strategy.Type != appsv1.RecreateDeploymentStrategyType ||
		deployment.Spec.Strategy.RollingUpdate != nil {
		t.Fatalf("deployment %s/%s does not use Recreate", namespace, name)
	}
	annotations := deployment.Spec.Template.Annotations
	if annotations[componentRevisionAnnotation] != "1" {
		t.Fatalf("deployment %s/%s component revision = %q", namespace, name, annotations[componentRevisionAnnotation])
	}
	if includeMountRevision {
		if annotations[runtimeInstanceAnnotation] != testRuntimeInstanceID {
			t.Fatalf("deployment %s/%s runtime instance = %q", namespace, name, annotations[runtimeInstanceAnnotation])
		}
		if annotations[runtimeAccessRevisionAnnotation] != "3" {
			t.Fatalf("deployment %s/%s access revision = %q", namespace, name, annotations[runtimeAccessRevisionAnnotation])
		}
		if annotations[mountRevisionAnnotation] != "7" {
			t.Fatalf("deployment %s/%s mount revision = %q", namespace, name, annotations[mountRevisionAnnotation])
		}
	} else if _, exists := annotations[runtimeInstanceAnnotation]; exists {
		t.Fatalf("deployment %s/%s unexpectedly has runtime identity", namespace, name)
	}
}

func assertHTTPHealthProbe(
	t *testing.T,
	name string,
	probe *corev1.Probe,
	periodSeconds int32,
	timeoutSeconds int32,
	failureThreshold int32,
) {
	t.Helper()
	assertHTTPProbeTarget(t, name, probe, "http", "/health", periodSeconds, timeoutSeconds, failureThreshold)
}

func assertHTTPProbeTarget(
	t *testing.T,
	name string,
	probe *corev1.Probe,
	port string,
	path string,
	periodSeconds int32,
	timeoutSeconds int32,
	failureThreshold int32,
) {
	t.Helper()
	if probe == nil || probe.HTTPGet == nil {
		t.Fatalf("%s probe = %v, want HTTP GET probe", name, probe)
	}
	if probe.HTTPGet.Path != path || probe.HTTPGet.Port.StrVal != port {
		t.Fatalf(
			"%s probe target = %s:%s, want %s:%s",
			name,
			probe.HTTPGet.Port.String(),
			probe.HTTPGet.Path,
			port,
			path,
		)
	}
	if probe.PeriodSeconds != periodSeconds || probe.TimeoutSeconds != timeoutSeconds ||
		probe.FailureThreshold != failureThreshold || probe.SuccessThreshold != 1 {
		t.Fatalf(
			"%s probe timings = period %d timeout %d failure %d success %d",
			name,
			probe.PeriodSeconds,
			probe.TimeoutSeconds,
			probe.FailureThreshold,
			probe.SuccessThreshold,
		)
	}
}

func assertServiceExists(t *testing.T, cl client.Reader, namespace string, name string) {
	t.Helper()
	var service corev1.Service
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &service); err != nil {
		t.Fatalf("get service %s/%s: %v", namespace, name, err)
	}
}

func assertRuntimeGenerationRouting(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	runtimeInstanceID string,
) {
	t.Helper()
	deployment, service := runtimeGenerationRoutingResources(
		t,
		cl,
		namespace,
		name,
	)
	if deployment.Spec.Selector == nil {
		t.Fatalf("deployment %s/%s has no selector", namespace, name)
	}
	if value, exists := deployment.Spec.Selector.MatchLabels[runtimeInstanceAnnotation]; exists {
		t.Fatalf(
			"deployment %s/%s stable selector contains runtime instance %q",
			namespace,
			name,
			value,
		)
	}
	for key, value := range deployment.Spec.Selector.MatchLabels {
		if deployment.Spec.Template.Labels[key] != value {
			t.Fatalf(
				"deployment %s/%s Pod template does not preserve stable selector %s=%q",
				namespace,
				name,
				key,
				value,
			)
		}
	}
	if got := deployment.Spec.Template.Labels[runtimeInstanceAnnotation]; got != runtimeInstanceID {
		t.Fatalf(
			"deployment %s/%s Pod template runtime instance = %q, want %q",
			namespace,
			name,
			got,
			runtimeInstanceID,
		)
	}

	if got := service.Spec.Selector[runtimeInstanceAnnotation]; got != runtimeInstanceID {
		t.Fatalf(
			"service %s/%s runtime instance selector = %q, want %q",
			namespace,
			name,
			got,
			runtimeInstanceID,
		)
	}
	for key, value := range deployment.Spec.Selector.MatchLabels {
		if service.Spec.Selector[key] != value {
			t.Fatalf(
				"service %s/%s does not preserve stable selector %s=%q",
				namespace,
				name,
				key,
				value,
			)
		}
	}
}

func runtimeGenerationRoutingResources(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) (appsv1.Deployment, corev1.Service) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	var service corev1.Service
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &service); err != nil {
		t.Fatalf("get service %s/%s: %v", namespace, name, err)
	}
	return deployment, service
}

func assertWorkloadServiceAccount(t *testing.T, cl client.Reader, namespace string, name string) {
	t.Helper()
	var serviceAccount corev1.ServiceAccount
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &serviceAccount); err != nil {
		t.Fatalf("get service account %s/%s: %v", namespace, name, err)
	}
	if serviceAccount.AutomountServiceAccountToken == nil || *serviceAccount.AutomountServiceAccountToken {
		t.Fatalf(
			"service account %s/%s automount token = %v, want false",
			namespace,
			name,
			serviceAccount.AutomountServiceAccountToken,
		)
	}
}

func assertWorkloadServiceAccountPullSecrets(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	want []corev1.LocalObjectReference,
) {
	t.Helper()
	var serviceAccount corev1.ServiceAccount
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &serviceAccount); err != nil {
		t.Fatalf("get service account %s/%s: %v", namespace, name, err)
	}
	if !reflect.DeepEqual(serviceAccount.ImagePullSecrets, want) {
		t.Fatalf(
			"service account %s/%s imagePullSecrets = %#v, want %#v",
			namespace,
			name,
			serviceAccount.ImagePullSecrets,
			want,
		)
	}
}

func assertDeploymentHasNoImagePullSecrets(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if len(deployment.Spec.Template.Spec.ImagePullSecrets) != 0 {
		t.Fatalf(
			"deployment %s/%s must inherit imagePullSecrets from its ServiceAccount",
			namespace,
			name,
		)
	}
}

func assertDeploymentUsesServiceAccount(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	serviceAccountName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	podSpec := deployment.Spec.Template.Spec
	if podSpec.ServiceAccountName != serviceAccountName {
		t.Fatalf(
			"deployment %s/%s service account = %q, want %q",
			namespace,
			name,
			podSpec.ServiceAccountName,
			serviceAccountName,
		)
	}
	if podSpec.AutomountServiceAccountToken == nil || *podSpec.AutomountServiceAccountToken {
		t.Fatalf(
			"deployment %s/%s automount token = %v, want false",
			namespace,
			name,
			podSpec.AutomountServiceAccountToken,
		)
	}
}

func assertPVCExists(t *testing.T, cl client.Reader, namespace string, name string) {
	assertPVCProfile(
		t,
		cl,
		namespace,
		name,
		[]corev1.PersistentVolumeAccessMode{corev1.ReadWriteMany},
		"shared-rwx",
		"25Gi",
	)
}

func assertPVCProfile(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	accessModes []corev1.PersistentVolumeAccessMode,
	storageClass string,
	size string,
) {
	t.Helper()
	var pvc corev1.PersistentVolumeClaim
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &pvc); err != nil {
		t.Fatalf("get pvc %s/%s: %v", namespace, name, err)
	}
	if !reflect.DeepEqual(pvc.Spec.AccessModes, accessModes) {
		t.Fatalf("pvc %s/%s access modes = %v, want %v", namespace, name, pvc.Spec.AccessModes, accessModes)
	}
	if pvc.Spec.StorageClassName == nil || *pvc.Spec.StorageClassName != storageClass {
		t.Fatalf("pvc %s/%s storage class = %v, want %s", namespace, name, pvc.Spec.StorageClassName, storageClass)
	}
	if pvc.Spec.Resources.Requests.Storage().String() != size {
		t.Fatalf("pvc %s/%s size = %s, want %s", namespace, name, pvc.Spec.Resources.Requests.Storage().String(), size)
	}
}

func assertDeploymentUsesPVC(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	claimName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.PersistentVolumeClaim != nil &&
			volume.PersistentVolumeClaim.ClaimName == claimName {
			return
		}
	}
	t.Fatalf("deployment %s/%s does not use pvc %s", namespace, name, claimName)
}

func assertDeploymentDoesNotUsePVC(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	claimName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.PersistentVolumeClaim != nil &&
			volume.PersistentVolumeClaim.ClaimName == claimName {
			t.Fatalf("deployment %s/%s unexpectedly uses pvc %s", namespace, name, claimName)
		}
	}
}

func assertRuntimeDeploymentHomeMount(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	claimName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	volumeFound := false
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.Name == "runtime-home" &&
			volume.PersistentVolumeClaim != nil &&
			volume.PersistentVolumeClaim.ClaimName == claimName {
			volumeFound = true
			break
		}
	}
	if !volumeFound {
		t.Fatalf(
			"deployment %s/%s missing runtime-home volume for pvc %s",
			namespace,
			name,
			claimName,
		)
	}

	for _, mount := range deployment.Spec.Template.Spec.Containers[0].VolumeMounts {
		if mount.Name == "runtime-home" && mount.MountPath == "/home/developer" {
			return
		}
	}
	t.Fatalf(
		"deployment %s/%s missing runtime-home mount at /home/developer",
		namespace,
		name,
	)
}

func assertRuntimeDeploymentKnowledgeBaseMounts(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	claimName string,
) {
	t.Helper()
	assertRuntimeDeploymentKnowledgeBaseMountSet(t, cl, namespace, name, claimName, map[string]corev1.VolumeMount{
		"/knowledge/docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/docs",
			SubPath:   testKnowledgeBaseID1,
			ReadOnly:  true,
		},
		"/knowledge/readonly-docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/readonly-docs",
			SubPath:   testKnowledgeBaseID2,
			ReadOnly:  true,
		},
	})
}

func assertRuntimeDeploymentKnowledgeBaseMountSet(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	claimName string,
	expectedMounts map[string]corev1.VolumeMount,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	var knowledgeBaseVolume *corev1.Volume
	for i := range deployment.Spec.Template.Spec.Volumes {
		volume := &deployment.Spec.Template.Spec.Volumes[i]
		if volume.Name == "knowledge-bases" {
			knowledgeBaseVolume = volume
			break
		}
	}
	if knowledgeBaseVolume == nil {
		t.Fatalf("deployment %s/%s missing knowledge-bases volume", namespace, name)
	}
	if knowledgeBaseVolume.PersistentVolumeClaim == nil || knowledgeBaseVolume.PersistentVolumeClaim.ClaimName != claimName {
		t.Fatalf("knowledge-bases pvc = %v, want %s", knowledgeBaseVolume.PersistentVolumeClaim, claimName)
	}

	container := deployment.Spec.Template.Spec.Containers[0]
	mounts := map[string]corev1.VolumeMount{}
	for _, mount := range container.VolumeMounts {
		if mount.Name == "knowledge-bases" || strings.HasPrefix(mount.MountPath, "/knowledge/") {
			mounts[mount.MountPath] = mount
		}
	}

	if len(mounts) != len(expectedMounts) {
		t.Fatalf("knowledge base mounts = %+v, want %+v", mounts, expectedMounts)
	}

	for mountPath, expected := range expectedMounts {
		actual, ok := mounts[mountPath]
		if !ok {
			t.Fatalf("deployment %s/%s missing %s mount", namespace, name, mountPath)
		}
		if actual.Name != expected.Name || actual.SubPath != expected.SubPath || actual.ReadOnly != expected.ReadOnly {
			t.Fatalf("mount %s = %+v, want %+v", mountPath, actual, expected)
		}
	}
}

func assertDeploymentHasNoKnowledgeBaseMounts(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.Name == "knowledge-bases" {
			t.Fatalf("deployment %s/%s unexpectedly has knowledge base volume", namespace, name)
		}
	}
	for _, container := range deployment.Spec.Template.Spec.Containers {
		for _, mount := range container.VolumeMounts {
			if mount.Name == "knowledge-bases" || strings.HasPrefix(mount.MountPath, "/knowledge/") {
				t.Fatalf("deployment %s/%s unexpectedly has knowledge base mount %+v", namespace, name, mount)
			}
		}
	}
}

func assertRuntimeDeploymentAssertionJWKS(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	secretName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	var assertionVolume *corev1.Volume
	for i := range deployment.Spec.Template.Spec.Volumes {
		volume := &deployment.Spec.Template.Spec.Volumes[i]
		if volume.Name == runtimeAssertionJWKSVolumeName {
			assertionVolume = volume
			break
		}
	}
	if assertionVolume == nil || assertionVolume.Secret == nil {
		t.Fatalf("deployment %s/%s missing assertion JWKS Secret volume", namespace, name)
	}
	secret := assertionVolume.Secret
	if secret.SecretName != secretName {
		t.Fatalf("assertion JWKS Secret = %q, want %q", secret.SecretName, secretName)
	}
	if secret.DefaultMode == nil || *secret.DefaultMode != 0444 {
		t.Fatalf("assertion JWKS mode = %v, want 0444", secret.DefaultMode)
	}
	if len(secret.Items) != 1 || secret.Items[0].Key != runtimeAssertionJWKSSecretKey || secret.Items[0].Path != runtimeAssertionJWKSSecretKey {
		t.Fatalf("assertion JWKS items = %+v, want only %s", secret.Items, runtimeAssertionJWKSSecretKey)
	}

	for _, mount := range deployment.Spec.Template.Spec.Containers[0].VolumeMounts {
		if mount.Name == runtimeAssertionJWKSVolumeName && mount.MountPath == runtimeAssertionJWKSMountPath && mount.ReadOnly {
			return
		}
	}
	t.Fatalf("deployment %s/%s missing read-only assertion JWKS mount", namespace, name)
}

func assertRuntimeDeploymentSetupScript(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	secretName string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	var setupVolume *corev1.Volume
	for index := range deployment.Spec.Template.Spec.Volumes {
		volume := &deployment.Spec.Template.Spec.Volumes[index]
		if volume.Name == runtimeSetupVolumeName {
			setupVolume = volume
			break
		}
	}
	if setupVolume == nil || setupVolume.Secret == nil {
		t.Fatalf("deployment %s/%s has no Runtime setup Secret volume", namespace, name)
	}
	if setupVolume.Secret.SecretName != secretName ||
		setupVolume.Secret.DefaultMode == nil ||
		*setupVolume.Secret.DefaultMode != 0440 ||
		len(setupVolume.Secret.Items) != 1 ||
		setupVolume.Secret.Items[0].Key != runtimeSetupSecretKey ||
		setupVolume.Secret.Items[0].Path != runtimeSetupSecretKey ||
		setupVolume.Secret.Items[0].Mode == nil ||
		*setupVolume.Secret.Items[0].Mode != 0440 {
		t.Fatalf("deployment %s/%s Runtime setup Secret volume is invalid: %+v", namespace, name, setupVolume.Secret)
	}
	container := deployment.Spec.Template.Spec.Containers[0]
	for _, mount := range container.VolumeMounts {
		if mount.Name == runtimeSetupVolumeName &&
			mount.MountPath == runtimeSetupMountPath &&
			mount.SubPath == runtimeSetupSecretKey &&
			mount.ReadOnly {
			return
		}
	}
	t.Fatalf("deployment %s/%s Runtime setup Secret mount is invalid", namespace, name)
}

func assertDeploymentHasNoRuntimeAssertionJWKS(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.Name == runtimeAssertionJWKSVolumeName {
			t.Fatalf("deployment %s/%s unexpectedly has assertion JWKS volume", namespace, name)
		}
	}
	for _, container := range deployment.Spec.Template.Spec.Containers {
		for _, mount := range container.VolumeMounts {
			if mount.Name == runtimeAssertionJWKSVolumeName {
				t.Fatalf("deployment %s/%s unexpectedly has assertion JWKS mount", namespace, name)
			}
		}
		for _, envVar := range container.Env {
			if envVar.Name == "AILERON_RUNTIME_ASSERTION_ISSUER" || envVar.Name == "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE" {
				t.Fatalf("deployment %s/%s unexpectedly has assertion env %s", namespace, name, envVar.Name)
			}
		}
	}
}

func assertRestrictedDeploymentSecurityContext(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	securityContext := deployment.Spec.Template.Spec.SecurityContext
	if securityContext == nil || securityContext.FSGroup == nil || *securityContext.FSGroup != 2000 {
		t.Fatalf("deployment %s/%s fsGroup = %v, want 2000", namespace, name, securityContext)
	}
	if securityContext.RunAsNonRoot == nil || !*securityContext.RunAsNonRoot {
		t.Fatalf("deployment %s/%s does not require non-root", namespace, name)
	}
	if securityContext.SeccompProfile == nil || securityContext.SeccompProfile.Type != corev1.SeccompProfileTypeRuntimeDefault {
		t.Fatalf("deployment %s/%s seccompProfile = %v, want RuntimeDefault", namespace, name, securityContext.SeccompProfile)
	}
	containerContext := deployment.Spec.Template.Spec.Containers[0].SecurityContext
	if containerContext == nil || containerContext.ReadOnlyRootFilesystem == nil || !*containerContext.ReadOnlyRootFilesystem {
		t.Fatalf("deployment %s/%s root filesystem is writable", namespace, name)
	}
	if containerContext.AllowPrivilegeEscalation == nil || *containerContext.AllowPrivilegeEscalation {
		t.Fatalf("deployment %s/%s allows privilege escalation", namespace, name)
	}
	if containerContext.Capabilities == nil || !reflect.DeepEqual(containerContext.Capabilities.Drop, []corev1.Capability{"ALL"}) {
		t.Fatalf("deployment %s/%s capabilities = %v, want drop ALL", namespace, name, containerContext.Capabilities)
	}
}

func assertBrowserDeploymentRuntimeContract(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	var sharedMemory *corev1.Volume
	for index := range deployment.Spec.Template.Spec.Volumes {
		volume := &deployment.Spec.Template.Spec.Volumes[index]
		if volume.Name == "shared-memory" {
			sharedMemory = volume
			break
		}
	}
	if sharedMemory == nil || sharedMemory.EmptyDir == nil ||
		sharedMemory.EmptyDir.Medium != corev1.StorageMediumMemory ||
		sharedMemory.EmptyDir.SizeLimit == nil || sharedMemory.EmptyDir.SizeLimit.String() != "512Mi" {
		t.Fatalf("deployment %s/%s shared memory volume = %+v", namespace, name, sharedMemory)
	}

	container := deployment.Spec.Template.Spec.Containers[0]
	foundSharedMemoryMount := false
	for _, mount := range container.VolumeMounts {
		if mount.Name == "shared-memory" && mount.MountPath == "/dev/shm" {
			foundSharedMemoryMount = true
			break
		}
	}
	if !foundSharedMemoryMount {
		t.Fatalf("deployment %s/%s missing /dev/shm mount", namespace, name)
	}
	assertBrowserCompositeProbe(t, "startup", container.StartupProbe, 5, 2, 60)
	assertBrowserCompositeProbe(t, "readiness", container.ReadinessProbe, 5, 2, 3)
	assertHTTPProbeTarget(t, "liveness", container.LivenessProbe, "webrtc", "/health", 10, 2, 3)
}

func assertDeploymentComponentLabel(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	component string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if deployment.Spec.Template.Labels[componentLabel] != component {
		t.Fatalf(
			"deployment %s/%s component label = %q, want %q",
			namespace,
			name,
			deployment.Spec.Template.Labels[componentLabel],
			component,
		)
	}
}

func assertCanvasDeploymentRuntimeContract(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	container := deployment.Spec.Template.Spec.Containers[0]
	assertHTTPProbeTarget(t, "startup", container.StartupProbe, "api", "/ready", 5, 2, 60)
	assertHTTPProbeTarget(t, "readiness", container.ReadinessProbe, "api", "/ready", 5, 2, 3)
	assertHTTPProbeTarget(t, "liveness", container.LivenessProbe, "api", "/health", 10, 2, 3)
}

const expectedBrowserCompositeProbeScript = `exec >/dev/null 2>&1
browser_config=/tmp/aileron-browser/neko.generated.yaml
[ -f "${browser_config}" ] &&
[ ! -L "${browser_config}" ] &&
[ "$(stat -c '%a:%u' "${browser_config}")" = "600:$(id -u)" ] &&
awk '
/^[^[:space:]#]/ {
  if ($0 !~ /^[A-Za-z_][A-Za-z0-9_-]*:[[:space:]]*$/) {
    noncanonical_top_level_lines++
    next
  }
  section = $0
  sub(/:[[:space:]]*$/, "", section)
  managed_nested = 0
  if (section == "member") member_sections++
  if (section == "webrtc") webrtc_sections++
  next
}
(section == "member" || section == "webrtc") {
  if ($0 ~ /^[[:space:]]*$/ || $0 ~ /^[[:space:]]*#/) next
  if ($0 ~ /^  [^[:space:]]/) {
    if ($0 !~ /^  [A-Za-z_][A-Za-z0-9_-]*:([[:space:]]|$)/) {
      noncanonical_managed_children++
      next
    }
    managed_nested = $0 ~ /^  [A-Za-z_][A-Za-z0-9_-]*:[[:space:]]*(#.*)?$/
  } else if ($0 ~ /^    / && managed_nested) {
    next
  } else {
    noncanonical_managed_children++
    next
  }
}
section == "member" && /^  provider:[[:space:]]*/ {
  member_providers++
  if ($0 ~ /^  provider:[[:space:]]*multiuser[[:space:]]*$/) valid_member_providers++
}
section == "webrtc" && /^  icelite:[[:space:]]*/ {
  webrtc_icelite_values++
  if ($0 ~ /^  icelite:[[:space:]]*false[[:space:]]*$/) valid_webrtc_icelite_values++
}
END {
  valid = member_sections == 1 && webrtc_sections == 1 &&
    member_providers == 1 && valid_member_providers == 1 &&
    webrtc_icelite_values == 1 && valid_webrtc_icelite_values == 1 &&
    noncanonical_top_level_lines == 0 && noncanonical_managed_children == 0
  exit valid ? 0 : 1
}
' "${browser_config}" &&
curl --fail --silent --max-time 1 http://127.0.0.1:6080/health &&
curl --fail --silent --max-time 1 http://127.0.0.1:9223/json/version`

func TestBrowserCompositeProbeScriptMatchesReviewedIdentity(t *testing.T) {
	if actualLength := len(browserCompositeProbeScript); actualLength != reviewedBrowserCompositeProbeScriptLength {
		t.Fatalf(
			"Browser composite probe script length = %d, want reviewed length %d",
			actualLength,
			reviewedBrowserCompositeProbeScriptLength,
		)
	}
	actualSHA256 := fmt.Sprintf("%x", sha256.Sum256([]byte(browserCompositeProbeScript)))
	if actualSHA256 != reviewedBrowserCompositeProbeScriptSHA256 {
		t.Fatalf(
			"Browser composite probe script SHA-256 = %s, want reviewed SHA-256 %s",
			actualSHA256,
			reviewedBrowserCompositeProbeScriptSHA256,
		)
	}
}

func assertBrowserCompositeProbe(
	t *testing.T,
	name string,
	probe *corev1.Probe,
	periodSeconds int32,
	timeoutSeconds int32,
	failureThreshold int32,
) {
	t.Helper()
	if probe == nil || probe.Exec == nil || len(probe.Exec.Command) != 3 {
		t.Fatalf("%s probe = %v, want Browser composite exec probe", name, probe)
	}
	command := probe.Exec.Command
	wantCommand := []string{"/bin/sh", "-ec", expectedBrowserCompositeProbeScript}
	if !reflect.DeepEqual(command, wantCommand) {
		t.Fatalf("%s command = %#v, want exact Browser readiness command %#v", name, command, wantCommand)
	}
	if probe.PeriodSeconds != periodSeconds || probe.TimeoutSeconds != timeoutSeconds ||
		probe.FailureThreshold != failureThreshold || probe.SuccessThreshold != 1 {
		t.Fatalf("unexpected %s probe timings: %+v", name, probe)
	}
}

const validBrowserGeneratedConfigFixture = `member:
  provider: multiuser
  multiuser:
    user_password: "probe-user-password-secret"
    admin_password: "probe-admin-password-secret"
webrtc:
  icelite: false
`

func TestBrowserCompositeProbeUsesExactCommand(t *testing.T) {
	assertBrowserCompositeProbe(t, "readiness", browserCompositeProbe(5, 2, 3), 5, 2, 3)
}

func resetBrowserCompositeProbeConfigPath(t *testing.T) string {
	t.Helper()
	stateDirectory := "/tmp/aileron-browser"
	if err := os.RemoveAll(stateDirectory); err != nil {
		t.Fatalf("reset Browser probe fixture directory: %v", err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(stateDirectory) })
	if err := os.Mkdir(stateDirectory, 0o711); err != nil {
		t.Fatalf("create Browser probe fixture directory: %v", err)
	}
	return filepath.Join(stateDirectory, "neko.generated.yaml")
}

func executeBrowserCompositeProbe(
	t *testing.T,
	config string,
	mode os.FileMode,
	ownerUID int,
) error {
	t.Helper()
	configPath := resetBrowserCompositeProbeConfigPath(t)
	if err := os.WriteFile(configPath, []byte(config), mode); err != nil {
		t.Fatalf("write Browser probe config fixture: %v", err)
	}
	if err := os.Chmod(configPath, mode); err != nil {
		t.Fatalf("set Browser probe config mode: %v", err)
	}
	if err := os.Chown(configPath, ownerUID, ownerUID); err != nil {
		t.Fatalf("set Browser probe config owner: %v", err)
	}
	return runBrowserCompositeProbe(t)
}

func runBrowserCompositeProbe(t *testing.T) error {
	t.Helper()
	commandDirectory := t.TempDir()
	if err := os.Chmod(filepath.Dir(commandDirectory), 0o755); err != nil {
		t.Fatalf("make Browser probe command parent directory traversable: %v", err)
	}
	if err := os.Chmod(commandDirectory, 0o755); err != nil {
		t.Fatalf("make Browser probe command directory traversable: %v", err)
	}
	if err := os.WriteFile(
		filepath.Join(commandDirectory, "curl"),
		[]byte("#!/bin/sh\nexit 0\n"),
		0o755,
	); err != nil {
		t.Fatalf("write Browser probe curl fixture: %v", err)
	}

	probe := browserCompositeProbe(5, 2, 3)
	command := exec.Command(probe.Exec.Command[0], probe.Exec.Command[1:]...)
	command.Env = append(os.Environ(), "PATH="+commandDirectory+":"+os.Getenv("PATH"))
	command.SysProcAttr = &syscall.SysProcAttr{
		Credential: &syscall.Credential{Uid: 65532, Gid: 65532},
	}
	output, err := command.CombinedOutput()
	if len(output) != 0 {
		t.Fatalf("Browser composite probe exposed output: %q", output)
	}
	return err
}

func TestBrowserCompositeProbeAcceptsValidGeneratedConfig(t *testing.T) {
	if err := executeBrowserCompositeProbe(t, validBrowserGeneratedConfigFixture, 0o600, 65532); err != nil {
		t.Fatalf("Browser composite probe rejected valid generated config: %v", err)
	}
}

func TestBrowserCompositeProbeRejectsWrongGeneratedConfigMode(t *testing.T) {
	if err := executeBrowserCompositeProbe(t, validBrowserGeneratedConfigFixture, 0o644, 65532); err == nil {
		t.Fatal("Browser composite probe accepted mode 0644 generated config")
	}
}

func TestBrowserCompositeProbeRejectsWrongGeneratedConfigOwner(t *testing.T) {
	if err := executeBrowserCompositeProbe(t, validBrowserGeneratedConfigFixture, 0o600, 0); err == nil {
		t.Fatal("Browser composite probe accepted generated config owned by a different UID")
	}
}

func TestBrowserCompositeProbeRejectsGeneratedConfigSymlink(t *testing.T) {
	configPath := resetBrowserCompositeProbeConfigPath(t)
	targetPath := filepath.Join(filepath.Dir(configPath), "neko.target.yaml")
	if err := os.WriteFile(targetPath, []byte(validBrowserGeneratedConfigFixture), 0o600); err != nil {
		t.Fatalf("write Browser probe symlink target: %v", err)
	}
	if err := os.Chown(targetPath, 65532, 65532); err != nil {
		t.Fatalf("set Browser probe symlink target owner: %v", err)
	}
	if err := os.Symlink(targetPath, configPath); err != nil {
		t.Fatalf("create Browser probe config symlink: %v", err)
	}
	if err := runBrowserCompositeProbe(t); err == nil {
		t.Fatal("Browser composite probe accepted generated config symlink")
	}
}

func TestBrowserCompositeProbeRejectsNonRegularGeneratedConfig(t *testing.T) {
	configPath := resetBrowserCompositeProbeConfigPath(t)
	if err := syscall.Mkfifo(configPath, 0o600); err != nil {
		t.Fatalf("create Browser probe config FIFO: %v", err)
	}
	if err := os.Chown(configPath, 65532, 65532); err != nil {
		t.Fatalf("set Browser probe config FIFO owner: %v", err)
	}
	if err := runBrowserCompositeProbe(t); err == nil {
		t.Fatal("Browser composite probe accepted non-regular generated config")
	}
}

func TestBrowserCompositeProbeRejectsDuplicateGeneratedConfigSections(t *testing.T) {
	tests := map[string]string{
		"member canonical": validBrowserGeneratedConfigFixture + `member:
  provider: multiuser
`,
		"member inline":                         validBrowserGeneratedConfigFixture + "member: {}\n",
		"member colon whitespace":               validBrowserGeneratedConfigFixture + "member : {}\n",
		"member double quoted":                  validBrowserGeneratedConfigFixture + "\"member\": {}\n",
		"member double quoted colon whitespace": validBrowserGeneratedConfigFixture + "\"member\" : {}\n",
		"member double quoted escaped": validBrowserGeneratedConfigFixture + `"\u006dember": {}
`,
		"member single quoted":                  validBrowserGeneratedConfigFixture + "'member': {}\n",
		"member single quoted colon whitespace": validBrowserGeneratedConfigFixture + "'member' : {}\n",
		"webrtc canonical": validBrowserGeneratedConfigFixture + `webrtc:
  icelite: false
`,
		"webrtc inline":                         validBrowserGeneratedConfigFixture + "webrtc: {}\n",
		"webrtc colon whitespace":               validBrowserGeneratedConfigFixture + "webrtc : {}\n",
		"webrtc double quoted":                  validBrowserGeneratedConfigFixture + "\"webrtc\": {}\n",
		"webrtc double quoted colon whitespace": validBrowserGeneratedConfigFixture + "\"webrtc\" : {}\n",
		"webrtc double quoted escaped": validBrowserGeneratedConfigFixture + `"we\u0062rtc": {}
`,
		"webrtc single quoted":                  validBrowserGeneratedConfigFixture + "'webrtc': {}\n",
		"webrtc single quoted colon whitespace": validBrowserGeneratedConfigFixture + "'webrtc' : {}\n",
	}
	for name, config := range tests {
		t.Run(name, func(t *testing.T) {
			if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err == nil {
				t.Fatalf("Browser composite probe accepted duplicate %s section", name)
			}
		})
	}
}

func TestBrowserCompositeProbeRejectsUnsupportedGeneratedConfigTopLevelSyntax(t *testing.T) {
	tests := map[string]string{
		"tagged managed key": validBrowserGeneratedConfigFixture + `!!str member: {}
`,
		"tagged quoted managed key": validBrowserGeneratedConfigFixture + `!!str "member": {}
`,
		"anchored managed key": validBrowserGeneratedConfigFixture + `&managed member: {}
`,
		"inline document flow mapping": validBrowserGeneratedConfigFixture + `--- {"member": {}, "webrtc": {}}
`,
		"inline document quoted key": validBrowserGeneratedConfigFixture + `--- "member": {}
`,
		"inline document explicit key": validBrowserGeneratedConfigFixture + `--- ? member
`,
		"explicit managed key": validBrowserGeneratedConfigFixture + `? member
: {}
`,
		"explicit escaped managed key": validBrowserGeneratedConfigFixture + `? "\u006dember"
: {}
`,
		"flow document": validBrowserGeneratedConfigFixture + `---
{"member": {}, "webrtc": {}}
`,
	}
	for name, config := range tests {
		t.Run(name, func(t *testing.T) {
			if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err == nil {
				t.Fatalf("Browser composite probe accepted %s top-level syntax", name)
			}
		})
	}
}

func TestBrowserCompositeProbeRejectsNoncanonicalManagedSectionChildren(t *testing.T) {
	tests := map[string]struct {
		needle      string
		replacement string
	}{
		"member double quoted key": {
			"  provider: multiuser",
			"  provider: multiuser\n  \"provider\": noauth",
		},
		"member single quoted key": {
			"  provider: multiuser",
			"  provider: multiuser\n  'provider': noauth",
		},
		"member escaped key": {
			"  provider: multiuser",
			`  provider: multiuser
  "\u0070rovider": noauth`,
		},
		"member tagged key": {
			"  provider: multiuser",
			"  provider: multiuser\n  !!str provider: noauth",
		},
		"member anchored key": {
			"  provider: multiuser",
			"  provider: multiuser\n  &managed provider: noauth",
		},
		"member explicit key": {
			"  provider: multiuser",
			"  provider: multiuser\n  ? provider\n  : noauth",
		},
		"member merge key": {
			"  provider: multiuser",
			"  provider: multiuser\n  <<: *member_defaults",
		},
		"member flow mapping": {
			"  provider: multiuser",
			`  provider: multiuser
  {"provider": noauth}`,
		},
		"member document marker": {
			"  provider: multiuser",
			"  provider: multiuser\n  --- provider: noauth",
		},
		"member one-space indentation": {
			"  provider: multiuser",
			"  provider: multiuser\n provider: noauth",
		},
		"member three-space indentation": {
			"  provider: multiuser",
			"  provider: multiuser\n   provider: noauth",
		},
		"member tab indentation": {
			"  provider: multiuser",
			"  provider: multiuser\n\tprovider: noauth",
		},
		"member nested content after scalar": {
			"  provider: multiuser",
			"  provider: multiuser\n    provider: noauth",
		},
		"webrtc double quoted key": {
			"  icelite: false",
			"  icelite: false\n  \"icelite\": true",
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			config := strings.Replace(
				validBrowserGeneratedConfigFixture,
				test.needle,
				test.replacement,
				1,
			)
			if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err == nil {
				t.Fatalf("Browser composite probe accepted noncanonical %s", name)
			}
		})
	}
}

func TestBrowserCompositeProbeAcceptsCanonicalManagedSectionNestedMappings(t *testing.T) {
	config := strings.Replace(
		validBrowserGeneratedConfigFixture,
		"  icelite: false",
		`  icelite: false

  # Optional nested generated section.
  iceservers:
    backend: []
    frontend: []`,
		1,
	)
	if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err != nil {
		t.Fatalf("Browser composite probe rejected canonical nested mappings: %v", err)
	}
}

func TestBrowserCompositeProbeRejectsInvalidGeneratedConfigProvider(t *testing.T) {
	tests := map[string]string{
		"wrong value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  provider: multiuser",
			"  provider: singleuser",
			1,
		),
		"duplicate value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  provider: multiuser",
			"  provider: multiuser\n  provider: singleuser",
			1,
		),
		"quoted value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  provider: multiuser",
			`  provider: "multiuser"`,
			1,
		),
		"wrong parent": `member:
  multiuser:
    user_password: "probe-user-password-secret"
    admin_password: "probe-admin-password-secret"
webrtc:
  provider: multiuser
  icelite: false
`,
	}
	for name, config := range tests {
		t.Run(name, func(t *testing.T) {
			if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err == nil {
				t.Fatalf("Browser composite probe accepted provider with %s", name)
			}
		})
	}
}

func TestBrowserCompositeProbeRejectsInvalidGeneratedConfigICELite(t *testing.T) {
	tests := map[string]string{
		"wrong value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  icelite: false",
			"  icelite: true",
			1,
		),
		"duplicate value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  icelite: false",
			"  icelite: false\n  icelite: true",
			1,
		),
		"quoted value": strings.Replace(
			validBrowserGeneratedConfigFixture,
			"  icelite: false",
			`  icelite: "false"`,
			1,
		),
		"wrong parent": `member:
  provider: multiuser
  icelite: false
  multiuser:
    user_password: "probe-user-password-secret"
    admin_password: "probe-admin-password-secret"
webrtc:
`,
	}
	for name, config := range tests {
		t.Run(name, func(t *testing.T) {
			if err := executeBrowserCompositeProbe(t, config, 0o600, 65532); err == nil {
				t.Fatalf("Browser composite probe accepted icelite with %s", name)
			}
		})
	}
}

func assertRuntimeDeploymentCodexTmpfs(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	var codexTmpVolume *corev1.Volume
	for i := range deployment.Spec.Template.Spec.Volumes {
		volume := &deployment.Spec.Template.Spec.Volumes[i]
		if volume.Name == runtimeCodexTmpVolumeName {
			codexTmpVolume = volume
			break
		}
	}
	if codexTmpVolume == nil || codexTmpVolume.EmptyDir == nil {
		t.Fatalf("deployment %s/%s missing %s emptyDir volume", namespace, name, runtimeCodexTmpVolumeName)
	}
	if codexTmpVolume.EmptyDir.Medium != corev1.StorageMediumMemory {
		t.Fatalf("deployment %s/%s codex tmp medium = %s, want Memory", namespace, name, codexTmpVolume.EmptyDir.Medium)
	}
	if codexTmpVolume.EmptyDir.SizeLimit == nil || codexTmpVolume.EmptyDir.SizeLimit.String() != "16Mi" {
		t.Fatalf("deployment %s/%s codex tmp sizeLimit = %v, want 16Mi", namespace, name, codexTmpVolume.EmptyDir.SizeLimit)
	}

	for _, mount := range deployment.Spec.Template.Spec.Containers[0].VolumeMounts {
		if mount.Name == runtimeCodexTmpVolumeName &&
			mount.MountPath == runtimeCodexTmpMountPath &&
			mount.SubPath == "" {
			return
		}
	}
	t.Fatalf("deployment %s/%s missing root %s mount at %s", namespace, name, runtimeCodexTmpVolumeName, runtimeCodexTmpMountPath)
}

func assertRuntimeDeploymentHomeInitializer(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	initContainers := deployment.Spec.Template.Spec.InitContainers
	if len(initContainers) != 1 {
		t.Fatalf("deployment %s/%s init containers = %d, want 1", namespace, name, len(initContainers))
	}
	initializer := initContainers[0]
	if initializer.Name != runtimeHomeInitializerName {
		t.Fatalf("deployment %s/%s init container = %s, want %s", namespace, name, initializer.Name, runtimeHomeInitializerName)
	}
	if initializer.Image != deployment.Spec.Template.Spec.Containers[0].Image {
		t.Fatalf("deployment %s/%s init image = %s, want runtime image", namespace, name, initializer.Image)
	}
	if initializer.ImagePullPolicy != corev1.PullIfNotPresent {
		t.Fatalf("deployment %s/%s init image pull policy = %s, want IfNotPresent", namespace, name, initializer.ImagePullPolicy)
	}
	if !reflect.DeepEqual(initializer.Command, []string{"/bin/sh", "-ec"}) {
		t.Fatalf("deployment %s/%s init command = %v", namespace, name, initializer.Command)
	}
	wantArgs := []string{`umask 0007
mkdir -p "${HOME}/.codex"
chmod 2770 "${HOME}/.codex"`}
	if !reflect.DeepEqual(initializer.Args, wantArgs) {
		t.Fatalf("deployment %s/%s init args = %v", namespace, name, initializer.Args)
	}
	if strings.Contains(strings.Join(initializer.Args, "\n"), ".codex/tmp") {
		t.Fatalf("deployment %s/%s initializer must not manage Codex tmp", namespace, name)
	}
	if !reflect.DeepEqual(initializer.Env, []corev1.EnvVar{{Name: "HOME", Value: runtimeHomeMountPath}}) {
		t.Fatalf("deployment %s/%s init env = %v", namespace, name, initializer.Env)
	}
	wantMounts := []corev1.VolumeMount{{
		Name:      runtimeHomeVolumeName,
		MountPath: runtimeHomeMountPath,
	}}
	if !reflect.DeepEqual(initializer.VolumeMounts, wantMounts) {
		t.Fatalf("deployment %s/%s init mounts = %v, want only runtime HOME", namespace, name, initializer.VolumeMounts)
	}
	if !reflect.DeepEqual(initializer.SecurityContext, restrictedContainerSecurityContext()) {
		t.Fatalf("deployment %s/%s init security context = %v, want restricted", namespace, name, initializer.SecurityContext)
	}
}

func assertRuntimeDeploymentEnv(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	expected map[string]string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	if len(deployment.Spec.Template.Spec.Containers) == 0 {
		t.Fatalf("deployment %s/%s has no containers", namespace, name)
	}

	actual := map[string]string{}
	for _, envVar := range deployment.Spec.Template.Spec.Containers[0].Env {
		actual[envVar.Name] = envVar.Value
	}

	for key, want := range expected {
		if got := actual[key]; got != want {
			t.Fatalf("deployment %s/%s env %s = %q, want %q", namespace, name, key, got, want)
		}
	}
}

func assertRuntimeDeploymentEnvSecretKey(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	envName string,
	secretName string,
	secretKey string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}

	for _, envVar := range deployment.Spec.Template.Spec.Containers[0].Env {
		if envVar.Name != envName {
			continue
		}
		if envVar.Value != "" || envVar.ValueFrom == nil || envVar.ValueFrom.SecretKeyRef == nil {
			t.Fatalf("deployment %s/%s env %s is not a Secret key reference", namespace, name, envName)
		}
		if envVar.ValueFrom.SecretKeyRef.Name != secretName ||
			envVar.ValueFrom.SecretKeyRef.Key != secretKey {
			t.Fatalf(
				"deployment %s/%s env %s Secret key = %s/%s, want %s/%s",
				namespace,
				name,
				envName,
				envVar.ValueFrom.SecretKeyRef.Name,
				envVar.ValueFrom.SecretKeyRef.Key,
				secretName,
				secretKey,
			)
		}
		return
	}
	t.Fatalf("deployment %s/%s missing env %s", namespace, name, envName)
}

func assertRuntimeDeploymentEnvAbsent(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	forbidden []string,
) {
	t.Helper()
	var deployment appsv1.Deployment
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &deployment); err != nil {
		t.Fatalf("get deployment %s/%s: %v", namespace, name, err)
	}
	if len(deployment.Spec.Template.Spec.Containers) == 0 {
		t.Fatalf("deployment %s/%s has no containers", namespace, name)
	}

	present := map[string]struct{}{}
	for _, envVar := range deployment.Spec.Template.Spec.Containers[0].Env {
		present[envVar.Name] = struct{}{}
	}
	for _, forbiddenName := range forbidden {
		if _, found := present[forbiddenName]; found {
			t.Fatalf("deployment %s/%s retains forbidden env %s", namespace, name, forbiddenName)
		}
	}
}

func assertWorkspaceFinalizerPresent(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var workspace workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &workspace); err != nil {
		t.Fatalf("get workspace %s/%s: %v", namespace, name, err)
	}
	for _, finalizer := range workspace.Finalizers {
		if finalizer == workspaceFinalizer {
			return
		}
	}
	t.Fatalf("workspace %s/%s does not retain finalizer", namespace, name)
}

func assertWorkspaceFinalizerRemovedOrWorkspaceDeleted(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
) {
	t.Helper()
	var workspace workspacev1alpha1.Workspace
	err := cl.Get(context.Background(), types.NamespacedName{
		Name: name, Namespace: namespace,
	}, &workspace)
	if apierrors.IsNotFound(err) {
		return
	}
	if err != nil {
		t.Fatalf("get workspace %s/%s: %v", namespace, name, err)
	}
	for _, finalizer := range workspace.Finalizers {
		if finalizer == workspaceFinalizer {
			t.Fatalf("workspace %s/%s retains finalizer", namespace, name)
		}
	}
}

func assertObjectDeleted(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	obj client.Object,
) {
	t.Helper()
	obj.SetName(name)
	obj.SetNamespace(namespace)
	err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, obj)
	if err == nil {
		t.Fatalf("expected %T %s/%s to be deleted", obj, namespace, name)
	}
}

func assertWorkspaceStatus(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	assertFn func(status workspacev1alpha1.WorkspaceStatus),
) {
	t.Helper()
	var workspace workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &workspace); err != nil {
		t.Fatalf("get workspace %s/%s: %v", namespace, name, err)
	}
	assertFn(workspace.Status)
}

func assertWorkspaceFirewallPolicy(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	expectedDomains []string,
) {
	t.Helper()
	policy := newCiliumNetworkPolicy(namespace, name)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, policy); err != nil {
		t.Fatalf("get cilium policy %s/%s: %v", namespace, name, err)
	}

	entries, found, err := unstructured.NestedSlice(policy.Object, "spec", "egress")
	if err != nil || !found || len(entries) == 0 {
		t.Fatalf("policy %s/%s missing egress entries: found=%v err=%v", namespace, name, found, err)
	}
	gotDomains := make([]string, 0, len(expectedDomains))
	for _, rawEntry := range entries {
		entry, ok := rawEntry.(map[string]interface{})
		if !ok {
			continue
		}
		fqdns, found, err := unstructured.NestedSlice(entry, "toFQDNs")
		if err != nil || !found {
			continue
		}
		for _, item := range fqdns {
			fqdnEntry, ok := item.(map[string]interface{})
			if !ok {
				t.Fatalf("policy %s/%s fqdn entry has unexpected type %T", namespace, name, item)
			}
			matchName, ok := fqdnEntry["matchName"].(string)
			if !ok {
				t.Fatalf("policy %s/%s fqdn entry missing matchName: %v", namespace, name, fqdnEntry)
			}
			gotDomains = append(gotDomains, matchName)
		}
		break
	}

	if len(gotDomains) == 0 && len(expectedDomains) > 0 {
		t.Fatalf("policy %s/%s missing toFQDNs entry", namespace, name)
	}

	if !reflect.DeepEqual(gotDomains, expectedDomains) {
		t.Fatalf("policy %s/%s domains = %v, want %v", namespace, name, gotDomains, expectedDomains)
	}
}

func assertFirewallPolicyIdentity(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	workspaceName string,
	revision string,
	deliveryID string,
	selectorKey string,
	selectorValue string,
) {
	t.Helper()
	policy := newCiliumNetworkPolicy(namespace, name)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, policy); err != nil {
		t.Fatalf("get cilium policy %s/%s: %v", namespace, name, err)
	}

	annotations := policy.GetAnnotations()
	actualDeliveryID, deliveryIDFound := annotations[firewallDeliveryIDAnnotation]
	if annotations[firewallRevisionAnnotation] != revision ||
		annotations[workspaceResourceAnnotation] != workspaceName ||
		!deliveryIDFound ||
		actualDeliveryID != deliveryID {
		t.Fatalf("policy %s/%s annotations = %#v", namespace, name, annotations)
	}
	ownerReferences := policy.GetOwnerReferences()
	if len(ownerReferences) != 1 ||
		ownerReferences[0].Name != workspaceName ||
		ownerReferences[0].Kind != "Workspace" ||
		ownerReferences[0].Controller == nil ||
		!*ownerReferences[0].Controller {
		t.Fatalf("policy %s/%s owner references = %#v", namespace, name, ownerReferences)
	}
	selector, found, err := unstructured.NestedStringMap(
		policy.Object,
		"spec",
		"endpointSelector",
		"matchLabels",
	)
	if err != nil || !found {
		t.Fatalf("policy %s/%s endpoint selector: found=%v err=%v", namespace, name, found, err)
	}
	if selector[workspaceIDLabel] == "" || selector[selectorKey] != selectorValue {
		t.Fatalf("policy %s/%s endpoint selector = %#v", namespace, name, selector)
	}
}

func assertPolicyPreservesBaseConnectivity(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	configNamespace string,
) {
	t.Helper()
	policy := newCiliumNetworkPolicy(namespace, name)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, policy); err != nil {
		t.Fatalf("get cilium policy %s/%s: %v", namespace, name, err)
	}

	egressEntries, found, err := unstructured.NestedSlice(policy.Object, "spec", "egress")
	if err != nil || !found {
		t.Fatalf("policy %s/%s missing egress entries: found=%v err=%v", namespace, name, found, err)
	}

	if !policyHasDNSRule(egressEntries) {
		t.Fatalf("policy %s/%s missing dns rule", namespace, name)
	}

	for _, component := range requiredInternalServiceComponents() {
		if !policyHasInternalServiceRule(egressEntries, configNamespace, component) {
			t.Fatalf("policy %s/%s missing internal service rule for %s", namespace, name, component)
		}
	}
	if policyHasInternalServiceRule(egressEntries, configNamespace, "redis") {
		t.Fatalf("policy %s/%s retains obsolete Runtime Redis egress", namespace, name)
	}
}

func assertPolicyAllowsTURN(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	serverURL string,
) {
	t.Helper()
	policy := newCiliumNetworkPolicy(namespace, name)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, policy); err != nil {
		t.Fatalf("get cilium policy %s/%s: %v", namespace, name, err)
	}

	egressEntries, found, err := unstructured.NestedSlice(policy.Object, "spec", "egress")
	if err != nil || !found {
		t.Fatalf("policy %s/%s missing egress entries: found=%v err=%v", namespace, name, found, err)
	}
	for _, expectedRule := range browserTURNEgressRules(turnProfileForTest(serverURL)) {
		foundRule := false
		for _, actualRule := range egressEntries {
			if reflect.DeepEqual(actualRule, expectedRule) {
				foundRule = true
				break
			}
		}
		if !foundRule {
			t.Fatalf("policy %s/%s missing TURN rule %v", namespace, name, expectedRule)
		}
	}
}

func policyHasDNSRule(egressEntries []interface{}) bool {
	for _, entry := range egressEntries {
		rule, ok := entry.(map[string]interface{})
		if !ok {
			continue
		}

		endpoints, found, _ := unstructured.NestedSlice(rule, "toEndpoints")
		if !found || len(endpoints) != 1 {
			continue
		}
		endpoint, ok := endpoints[0].(map[string]interface{})
		if !ok {
			continue
		}
		matchLabels, found, _ := unstructured.NestedStringMap(endpoint, "matchLabels")
		if !found {
			continue
		}
		if matchLabels["k8s:io.kubernetes.pod.namespace"] != "kube-system" {
			continue
		}
		if matchLabels["k8s:k8s-app"] != "kube-dns" {
			continue
		}

		ports, found, _ := unstructured.NestedSlice(rule, "toPorts")
		if !found || len(ports) == 0 {
			continue
		}
		firstPorts, ok := ports[0].(map[string]interface{})
		if !ok {
			continue
		}
		portEntries, found, _ := unstructured.NestedSlice(firstPorts, "ports")
		if !found || len(portEntries) < 2 {
			continue
		}

		hasUDP := false
		hasTCP := false
		for _, portEntry := range portEntries {
			portMap, ok := portEntry.(map[string]interface{})
			if !ok {
				continue
			}
			if portMap["port"] != "53" {
				continue
			}
			if portMap["protocol"] == "UDP" {
				hasUDP = true
			}
			if portMap["protocol"] == "TCP" {
				hasTCP = true
			}
		}

		dnsRules, found, _ := unstructured.NestedSlice(firstPorts, "rules", "dns")
		if !found || len(dnsRules) != 1 {
			continue
		}
		dnsRule, ok := dnsRules[0].(map[string]interface{})
		if !ok || dnsRule["matchPattern"] != "*" {
			continue
		}

		if hasUDP && hasTCP {
			return true
		}
	}
	return false
}

func policyHasInternalServiceRule(
	egressEntries []interface{},
	namespace string,
	component string,
) bool {
	for _, entry := range egressEntries {
		rule, ok := entry.(map[string]interface{})
		if !ok {
			continue
		}
		endpoints, found, _ := unstructured.NestedSlice(rule, "toEndpoints")
		if !found || len(endpoints) != 1 {
			continue
		}
		endpoint, ok := endpoints[0].(map[string]interface{})
		if !ok {
			continue
		}
		matchLabels, found, _ := unstructured.NestedStringMap(endpoint, "matchLabels")
		if !found {
			continue
		}
		if matchLabels["k8s:app.kubernetes.io/part-of"] != "aileron" {
			continue
		}
		if matchLabels["k8s:app.kubernetes.io/component"] != component {
			continue
		}
		if namespace != "" && matchLabels["k8s:io.kubernetes.pod.namespace"] != namespace {
			continue
		}
		return true
	}
	return false
}

func assertPolicyAllowsWorkspacePeers(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	workspaceID string,
) {
	t.Helper()
	wantPortsByComponent := map[string][]interface{}{
		canvasComponent: {
			map[string]interface{}{"port": "3003", "protocol": "TCP"},
			map[string]interface{}{"port": "3013", "protocol": "TCP"},
		},
		browserComponent: {
			map[string]interface{}{"port": "6080", "protocol": "TCP"},
			map[string]interface{}{"port": "9223", "protocol": "TCP"},
		},
	}
	policy := newCiliumNetworkPolicy(namespace, name)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, policy); err != nil {
		t.Fatalf("get cilium policy %s/%s: %v", namespace, name, err)
	}

	selector, found, err := unstructured.NestedStringMap(
		policy.Object,
		"spec",
		"endpointSelector",
		"matchLabels",
	)
	if err != nil || !found {
		t.Fatalf("policy %s/%s missing endpoint selector: found=%v err=%v", namespace, name, found, err)
	}
	wantSelector := map[string]string{
		"aileron.io/workspace-id": workspaceID,
		"aileron.io/component":    runtimeComponent,
	}
	if !reflect.DeepEqual(selector, wantSelector) {
		t.Fatalf("policy %s/%s endpoint selector = %v, want %v", namespace, name, selector, wantSelector)
	}

	egressEntries, found, err := unstructured.NestedSlice(policy.Object, "spec", "egress")
	if err != nil || !found {
		t.Fatalf("policy %s/%s missing egress entries: found=%v err=%v", namespace, name, found, err)
	}
	if len(egressEntries) < len(wantPortsByComponent) {
		t.Fatalf("policy %s/%s peer egress entries = %d, want at least %d", namespace, name, len(egressEntries), len(wantPortsByComponent))
	}

	foundComponents := map[string]bool{}
	for _, entry := range egressEntries {
		rule, ok := entry.(map[string]interface{})
		if !ok {
			t.Fatalf("same-workspace peer rule = %T", entry)
		}
		endpoints, found, _ := unstructured.NestedSlice(rule, "toEndpoints")
		if !found || len(endpoints) != 1 {
			t.Fatalf("same-workspace peer rule endpoints = %v", endpoints)
		}
		endpoint, ok := endpoints[0].(map[string]interface{})
		if !ok {
			t.Fatalf("same-workspace peer endpoint = %T", endpoints[0])
		}
		matchLabels, found, _ := unstructured.NestedStringMap(endpoint, "matchLabels")
		if !found {
			t.Fatalf("same-workspace peer rule missing target labels")
		}
		if matchLabels["k8s:aileron.io/workspace-id"] != workspaceID {
			continue
		}
		component := matchLabels["k8s:aileron.io/component"]
		wantPorts, expectedComponent := wantPortsByComponent[component]
		if !expectedComponent || foundComponents[component] {
			t.Fatalf("same-workspace peer target component = %q", component)
		}
		wantLabels := map[string]string{
			"k8s:io.kubernetes.pod.namespace": namespace,
			"k8s:app.kubernetes.io/part-of":   "aileron",
			"k8s:aileron.io/workspace-id":     workspaceID,
			"k8s:aileron.io/component":        component,
		}
		if !reflect.DeepEqual(matchLabels, wantLabels) {
			t.Fatalf("same-workspace %s target labels = %v, want %v", component, matchLabels, wantLabels)
		}

		toPorts, found, _ := unstructured.NestedSlice(rule, "toPorts")
		if !found || len(toPorts) != 1 {
			t.Fatalf("same-workspace %s rule toPorts = %v", component, toPorts)
		}
		portRule, ok := toPorts[0].(map[string]interface{})
		if !ok {
			t.Fatalf("same-workspace %s port rule = %T", component, toPorts[0])
		}
		ports, found, _ := unstructured.NestedSlice(portRule, "ports")
		if !found || !reflect.DeepEqual(ports, wantPorts) {
			t.Fatalf("same-workspace %s ports = %v, want %v", component, ports, wantPorts)
		}
		foundComponents[component] = true
	}

	for component := range wantPortsByComponent {
		if !foundComponents[component] {
			t.Fatalf("policy %s/%s missing %s peer egress", namespace, name, component)
		}
	}
}

func assertUnstructuredDeleted(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	gvk schema.GroupVersionKind,
) {
	t.Helper()
	obj := &unstructured.Unstructured{}
	obj.SetGroupVersionKind(gvk)
	err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, obj)
	if err == nil {
		t.Fatalf("expected unstructured %s %s/%s to be deleted", gvk.Kind, namespace, name)
	}
}

func assertOwnerReferenceExists(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
	obj client.Object,
	expectedKind string,
	expectedName string,
) {
	t.Helper()
	obj.SetName(name)
	obj.SetNamespace(namespace)
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, obj); err != nil {
		t.Fatalf("get %T %s/%s: %v", obj, namespace, name, err)
	}

	for _, ownerRef := range obj.GetOwnerReferences() {
		if ownerRef.Kind == expectedKind && ownerRef.Name == expectedName {
			return
		}
	}
	t.Fatalf("%T %s/%s missing owner reference %s/%s", obj, namespace, name, expectedKind, expectedName)
}
