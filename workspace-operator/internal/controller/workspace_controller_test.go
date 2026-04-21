package controller

import (
	"context"
	"reflect"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

func defaultPublicRoutingConfig() PublicRoutingConfig {
	return PublicRoutingConfig{
		Scheme:               "https",
		BaseDomain:           "example.com",
		IngressClassName:     "nginx",
		FrontendHost:         "aileron.{baseDomain}",
		WorkspaceManagerHost: "workspace-manager.{baseDomain}",
		KeycloakHost:         "keycloak.{baseDomain}",
		RuntimeHostPattern:   "workspace-runtime-{workspaceId}.{baseDomain}",
		BrowserHostPattern:   "workspace-browser-{workspaceId}.{baseDomain}",
		NextjsHostPattern:    "workspace-nextjs-{workspaceId}.{baseDomain}",
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-123",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				Image: "runtime:test",
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				Enabled: true,
				Image:   "browser:test",
			},
			Nextjs: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				Enabled: true,
				Image:   "nextjs:test",
			},
			WorkspacePath: "/workspace",
			KnowledgeBases: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
				{KBID: "kb-1", MountAlias: "docs", ReadOnly: false},
				{KBID: "kb-2", MountAlias: "readonly-docs", ReadOnly: true},
			},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"google.com"},
				},
			},
		},
	}
	firewallDefaults := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "firewall-defaults",
			Namespace: "operator-system",
		},
		Data: map[string]string{
			"firewall-defaults.yaml": "workspace:\n  allowedDomains:\n    - github.com\n    - registry.npmjs.org\nbrowser:\n  allowedDomains:\n    - google.com\n    - gstatic.com\n",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, firewallDefaults).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                     cl,
		Scheme:                     scheme,
		ConfigNamespace:            "operator-system",
		CiliumEnabled:              true,
		KnowledgeBasesPVCName:      "shared-knowledge-bases",
		FirewallDefaultsConfigName: "firewall-defaults",
		PublicRouting:              defaultPublicRoutingConfig(),
		ManagerURL:                 "http://workspace-manager.operator-system:3001",
		KeycloakURL:                "http://keycloak.operator-system:8080",
		KeycloakRealm:              "aileron",
		KeycloakClientID:           "aileron-frontend",
		RedisURL:                   "redis://redis.operator-system:6379/0",
		DatabaseURL:                "postgresql://postgres:postgres@postgres.operator-system:5432/aileron",
		InternalAPIToken:           "dev-internal-token",
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

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-123", "runtime:test")
	assertDeploymentImage(t, cl, "team-a", "workspace-browser-ws-123", "browser:test")
	assertDeploymentImage(t, cl, "team-a", "workspace-nextjs-ws-123", "nextjs:test")
	assertServiceExists(t, cl, "team-a", "workspace-runtime-ws-123")
	assertServiceExists(t, cl, "team-a", "workspace-browser-ws-123")
	assertServiceExists(t, cl, "team-a", "workspace-nextjs-ws-123")
	assertIngressHost(t, cl, "team-a", "workspace-runtime-ws-123", "workspace-runtime-ws-123.example.com", "nginx")
	assertIngressHost(t, cl, "team-a", "workspace-browser-ws-123", "workspace-browser-ws-123.example.com", "nginx")
	assertIngressHost(t, cl, "team-a", "workspace-nextjs-ws-123", "workspace-nextjs-ws-123.example.com", "nginx")
	assertPVCExists(t, cl, "team-a", "workspace-pvc-ws-123")
	assertDeploymentUsesPVC(t, cl, "team-a", "workspace-runtime-ws-123", "workspace-pvc-ws-123")
	assertRuntimeDeploymentSecurityContext(t, cl, "team-a", "workspace-runtime-ws-123")
	assertRuntimeDeploymentKnowledgeBaseMounts(t, cl, "team-a", "workspace-runtime-ws-123", "shared-knowledge-bases")
	assertRuntimeDeploymentEnv(t, cl, "team-a", "workspace-runtime-ws-123", map[string]string{
		"WORKSPACE_ID":        "ws-123",
		"WORKSPACE_PATH":      "/workspace",
		"PORT":                "3002",
		"NODE_ENV":            "production",
		"DEPLOYMENT_ENV":      "kubernetes",
		"MANAGER_URL":         "http://workspace-manager.operator-system:3001",
		"KEYCLOAK_SERVER_URL": "http://keycloak.operator-system:8080",
		"KEYCLOAK_REALM":      "aileron",
		"KEYCLOAK_CLIENT_ID":  "aileron-frontend",
		"REDIS_URL":           "redis://redis.operator-system:6379/0",
		"DATABASE_URL":        "postgresql://postgres:postgres@postgres.operator-system:5432/aileron",
		"INTERNAL_API_TOKEN":  "dev-internal-token",
		"FRONTEND_PUBLIC_URL": "https://aileron.example.com",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-123-workspace-egress", []string{
		"github.com",
		"registry.npmjs.org",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-123-browser-egress", []string{
		"google.com",
		"gstatic.com",
	})
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-123-workspace-egress", "operator-system")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-123-browser-egress", "operator-system")
	assertWorkspaceStatus(t, cl, "operator-system", "workspace-test", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.TargetNamespace != "team-a" {
			t.Fatalf("target namespace = %s, want team-a", status.TargetNamespace)
		}
		if status.Phase != "Reconciling" {
			t.Fatalf("phase = %s, want Reconciling", status.Phase)
		}
		if status.Components.Runtime.Phase != "Reconciling" {
			t.Fatalf("runtime phase = %s, want Reconciling", status.Components.Runtime.Phase)
		}
		if status.Components.Browser.Phase != "Reconciling" {
			t.Fatalf("browser phase = %s, want Reconciling", status.Components.Browser.Phase)
		}
		if status.Components.Nextjs.Phase != "Reconciling" {
			t.Fatalf("nextjs phase = %s, want Reconciling", status.Components.Nextjs.Phase)
		}
		if status.Components.Runtime.InternalURL != "http://workspace-runtime-ws-123.team-a.svc.cluster.local:3002" {
			t.Fatalf("unexpected runtime internal url: %s", status.Components.Runtime.InternalURL)
		}
		if status.Components.Runtime.ExternalURL != "https://workspace-runtime-ws-123.example.com" {
			t.Fatalf("unexpected runtime external url: %s", status.Components.Runtime.ExternalURL)
		}
		if status.Components.Browser.InternalURL != "http://workspace-browser-ws-123.team-a.svc.cluster.local:6080" {
			t.Fatalf("unexpected browser internal url: %s", status.Components.Browser.InternalURL)
		}
		if status.Components.Browser.ExternalURL != "https://workspace-browser-ws-123.example.com" {
			t.Fatalf("unexpected browser external url: %s", status.Components.Browser.ExternalURL)
		}
		if status.Components.Nextjs.InternalURL != "http://workspace-nextjs-ws-123.team-a.svc.cluster.local:3003" {
			t.Fatalf("unexpected nextjs internal url: %s", status.Components.Nextjs.InternalURL)
		}
		if status.Components.Nextjs.ExternalURL != "https://workspace-nextjs-ws-123.example.com" {
			t.Fatalf("unexpected nextjs external url: %s", status.Components.Nextjs.ExternalURL)
		}
		expectedWorkspaceDomains := []string{"github.com", "registry.npmjs.org"}
		if !reflect.DeepEqual(status.Firewall.Workspace.EffectiveAllowedDomains, expectedWorkspaceDomains) {
			t.Fatalf("workspace domains = %v, want %v", status.Firewall.Workspace.EffectiveAllowedDomains, expectedWorkspaceDomains)
		}
		expectedBrowserDomains := []string{"google.com", "gstatic.com"}
		if !reflect.DeepEqual(status.Firewall.Browser.EffectiveAllowedDomains, expectedBrowserDomains) {
			t.Fatalf("browser domains = %v, want %v", status.Firewall.Browser.EffectiveAllowedDomains, expectedBrowserDomains)
		}
	})
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-empty",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false},
			WorkspacePath:   "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: false,
		PublicRouting: defaultPublicRoutingConfig(),
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

	assertRuntimeDeploymentHasNoKnowledgeBaseVolume(t, cl, "team-a", "workspace-runtime-ws-empty")
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-update",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false},
			WorkspacePath:   "/workspace",
			KnowledgeBases: []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
				{KBID: "kb-1", MountAlias: "docs", ReadOnly: false},
				{KBID: "kb-2", MountAlias: "readonly-docs", ReadOnly: true},
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
		PublicRouting:         defaultPublicRoutingConfig(),
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
			SubPath:   "kb-1",
			ReadOnly:  false,
		},
		"/knowledge/readonly-docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/readonly-docs",
			SubPath:   "kb-2",
			ReadOnly:  true,
		},
	})

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), request.NamespacedName, &updated); err != nil {
		t.Fatalf("get workspace for update: %v", err)
	}
	updated.Spec.KnowledgeBases = []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment{
		{KBID: "kb-3", MountAlias: "playbooks", ReadOnly: false},
	}
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
			SubPath:   "kb-3",
			ReadOnly:  false,
		},
	})
}

func assertIngressHost(
	t *testing.T,
	cl client.Client,
	namespace string,
	name string,
	wantHost string,
	wantClass string,
) {
	t.Helper()

	var ingress networkingv1.Ingress
	if err := cl.Get(context.Background(), types.NamespacedName{Name: name, Namespace: namespace}, &ingress); err != nil {
		t.Fatalf("expected ingress %s/%s to exist: %v", namespace, name, err)
	}
	if len(ingress.Spec.Rules) != 1 || ingress.Spec.Rules[0].Host != wantHost {
		t.Fatalf("ingress host = %v, want %s", ingress.Spec.Rules, wantHost)
	}
	if ingress.Spec.IngressClassName == nil || *ingress.Spec.IngressClassName != wantClass {
		t.Fatalf("ingress class = %v, want %s", ingress.Spec.IngressClassName, wantClass)
	}
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-123",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "browser:test"},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "nextjs:test"},
			WorkspacePath:   "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: false,
		PublicRouting: defaultPublicRoutingConfig(),
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-123",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				Image: "runtime:test",
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			Nextjs:  workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"google.com"},
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
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: false,
		PublicRouting: defaultPublicRoutingConfig(),
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
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-browser-egress", ciliumNetworkPolicyGVK)
	assertWorkspaceStatus(t, cl, "operator-system", "workspace-test", func(status workspacev1alpha1.WorkspaceStatus) {
		if len(status.Firewall.Workspace.EffectiveAllowedDomains) != 0 {
			t.Fatalf("workspace firewall domains = %v, want empty", status.Firewall.Workspace.EffectiveAllowedDomains)
		}
		if len(status.Firewall.Browser.EffectiveAllowedDomains) != 0 {
			t.Fatalf("browser firewall domains = %v, want empty", status.Firewall.Browser.EffectiveAllowedDomains)
		}
	})
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-123",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				Image: "runtime:v2",
			},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			Nextjs:        workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			WorkspacePath: "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"google.com"},
				},
			},
		},
	}
	firewallDefaults := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "firewall-defaults",
			Namespace: "operator-system",
		},
		Data: map[string]string{
			"firewall-defaults.yaml": "workspace:\n  allowedDomains:\n    - github.com\nbrowser:\n  allowedDomains:\n    - google.com\n",
		},
	}

	existingRuntime := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-runtime-ws-123",
			Namespace: "team-a",
		},
		Spec: appsv1.DeploymentSpec{
			Template: corev1.PodTemplateSpec{
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{Name: "runtime", Image: "runtime:v1"},
					},
				},
			},
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, existingRuntime, firewallDefaults).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                     cl,
		Scheme:                     scheme,
		ConfigNamespace:            "operator-system",
		CiliumEnabled:              true,
		FirewallDefaultsConfigName: "firewall-defaults",
		PublicRouting:              defaultPublicRoutingConfig(),
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

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-123", "runtime:v2")
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
			Namespace:         "operator-system",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-123",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true},
			WorkspacePath:   "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"google.com"},
				},
			},
		},
	}

	managedObjects := []client.Object{
		workspace,
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-123", Namespace: "team-a"}},
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-123", Namespace: "team-a"}},
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "workspace-nextjs-ws-123", Namespace: "team-a"}},
		&networkingv1.Ingress{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-123", Namespace: "team-a"}},
		&networkingv1.Ingress{ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-123", Namespace: "team-a"}},
		&networkingv1.Ingress{ObjectMeta: metav1.ObjectMeta{Name: "workspace-nextjs-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-runtime-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-browser-ws-123", Namespace: "team-a"}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "workspace-nextjs-ws-123", Namespace: "team-a"}},
		&corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Name: "workspace-pvc-ws-123", Namespace: "team-a"}},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(managedObjects...).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: true,
		PublicRouting: defaultPublicRoutingConfig(),
	}

	_, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: workspace.Name, Namespace: workspace.Namespace},
	})
	if err != nil {
		t.Fatalf("reconcile delete failed: %v", err)
	}

	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-browser-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-nextjs-ws-123", &appsv1.Deployment{})
	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-ws-123", &networkingv1.Ingress{})
	assertObjectDeleted(t, cl, "team-a", "workspace-browser-ws-123", &networkingv1.Ingress{})
	assertObjectDeleted(t, cl, "team-a", "workspace-nextjs-ws-123", &networkingv1.Ingress{})
	assertObjectDeleted(t, cl, "team-a", "workspace-runtime-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-browser-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-nextjs-ws-123", &corev1.Service{})
	assertObjectDeleted(t, cl, "team-a", "workspace-pvc-ws-123", &corev1.PersistentVolumeClaim{})
	assertUnstructuredDeleted(t, cl, "team-a", "ws-ws-123-workspace-egress", ciliumNetworkPolicyGVK)
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

func TestWorkspaceReconcilerStatusIncludesRestartMetadataAndRunningPhase(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	restartWorkspaceAt := metav1.Now()
	restartRuntimeAt := metav1.NewTime(restartWorkspaceAt.Add(2))
	restartBrowserAt := metav1.NewTime(restartWorkspaceAt.Add(3))

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-running",
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-running",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "browser:test"},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false, Image: "nextjs:test"},
			WorkspacePath:   "/workspace",
			Operations: workspacev1alpha1.WorkspaceOperationsSpec{
				RestartWorkspaceAt: &restartWorkspaceAt,
				RestartRuntimeAt:   &restartRuntimeAt,
				RestartBrowserAt:   &restartBrowserAt,
			},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"github.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"google.com"},
				},
			},
		},
	}

	runtimeDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-runtime-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{Replicas: int32Ptr(1)},
		Status: appsv1.DeploymentStatus{
			ReadyReplicas:     1,
			AvailableReplicas: 1,
			Replicas:          1,
		},
	}
	browserDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-browser-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{Replicas: int32Ptr(1)},
		Status: appsv1.DeploymentStatus{
			ReadyReplicas:     1,
			AvailableReplicas: 1,
			Replicas:          1,
		},
	}
	nextjsDeployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "workspace-nextjs-ws-running",
			Namespace:  "team-a",
			Generation: 1,
		},
		Spec: appsv1.DeploymentSpec{Replicas: int32Ptr(0)},
	}
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
	nextjsService := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-nextjs-ws-running", Namespace: "team-a"},
		Spec: corev1.ServiceSpec{
			Ports: []corev1.ServicePort{{Name: "http", Port: 3003}},
		},
	}
	pvc := &corev1.PersistentVolumeClaim{
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-pvc-ws-running", Namespace: "team-a"},
	}
	firewallDefaults := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "firewall-defaults",
			Namespace: "operator-system",
		},
		Data: map[string]string{
			"firewall-defaults.yaml": "workspace:\n  allowedDomains:\n    - github.com\n    - registry.npmjs.org\nbrowser:\n  allowedDomains:\n    - google.com\n    - gstatic.com\n",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(
			workspace,
			runtimeDeployment,
			browserDeployment,
			nextjsDeployment,
			runtimeService,
			browserService,
			nextjsService,
			pvc,
			firewallDefaults,
		).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                     cl,
		Scheme:                     scheme,
		ConfigNamespace:            "operator-system",
		CiliumEnabled:              true,
		FirewallDefaultsConfigName: "firewall-defaults",
		PublicRouting:              defaultPublicRoutingConfig(),
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

	assertWorkspaceStatus(t, cl, "operator-system", "workspace-running", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.Phase != "Running" {
			t.Fatalf("phase = %s, want Running", status.Phase)
		}
		if status.Components.Runtime.Phase != "Running" {
			t.Fatalf("runtime phase = %s, want Running", status.Components.Runtime.Phase)
		}
		if status.Components.Browser.Phase != "Running" {
			t.Fatalf("browser phase = %s, want Running", status.Components.Browser.Phase)
		}
		if status.Components.Nextjs.Phase != "Disabled" {
			t.Fatalf("nextjs phase = %s, want Disabled", status.Components.Nextjs.Phase)
		}
		if status.Components.Runtime.ExternalURL != "https://workspace-runtime-ws-running.example.com" {
			t.Fatalf("runtime external url = %s, want https://workspace-runtime-ws-running.example.com", status.Components.Runtime.ExternalURL)
		}
		if status.Components.Browser.ExternalURL != "https://workspace-browser-ws-running.example.com" {
			t.Fatalf("browser external url = %s, want https://workspace-browser-ws-running.example.com", status.Components.Browser.ExternalURL)
		}
		if status.Components.Nextjs.ExternalURL != "https://workspace-nextjs-ws-running.example.com" {
			t.Fatalf("nextjs external url = %s, want https://workspace-nextjs-ws-running.example.com", status.Components.Nextjs.ExternalURL)
		}
		if status.Components.Runtime.LastRestartedAt == nil || status.Components.Runtime.LastRestartedAt.Unix() != restartRuntimeAt.Unix() {
			t.Fatalf("runtime last restart = %v, want %v", status.Components.Runtime.LastRestartedAt, restartRuntimeAt)
		}
		if status.Components.Browser.LastRestartedAt == nil || status.Components.Browser.LastRestartedAt.Unix() != restartBrowserAt.Unix() {
			t.Fatalf("browser last restart = %v, want %v", status.Components.Browser.LastRestartedAt, restartBrowserAt)
		}
		if status.Components.Nextjs.LastRestartedAt == nil || status.Components.Nextjs.LastRestartedAt.Unix() != restartWorkspaceAt.Unix() {
			t.Fatalf("nextjs last restart = %v, want %v", status.Components.Nextjs.LastRestartedAt, restartWorkspaceAt)
		}
		expectedWorkspaceDomains := []string{"github.com", "registry.npmjs.org"}
		if !reflect.DeepEqual(status.Firewall.Workspace.EffectiveAllowedDomains, expectedWorkspaceDomains) {
			t.Fatalf("workspace domains = %v, want %v", status.Firewall.Workspace.EffectiveAllowedDomains, expectedWorkspaceDomains)
		}
		expectedBrowserDomains := []string{"google.com", "gstatic.com"}
		if !reflect.DeepEqual(status.Firewall.Browser.EffectiveAllowedDomains, expectedBrowserDomains) {
			t.Fatalf("browser domains = %v, want %v", status.Firewall.Browser.EffectiveAllowedDomains, expectedBrowserDomains)
		}
	})
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
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-fw",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "browser:test"},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "nextjs:test"},
			WorkspacePath:   "/workspace",
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Workspace: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"internal.example.com"},
				},
				Browser: workspacev1alpha1.WorkspaceFirewallGroupSpec{
					NetworkAccessEnabled: true,
					DomainAccessMode:     "specific",
					AllowedDomains:       []string{"browser.example.com"},
				},
			},
		},
	}
	firewallDefaults := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "firewall-defaults",
			Namespace: "operator-system",
		},
		Data: map[string]string{
			"firewall-defaults.yaml": "workspace:\n  allowedDomains:\n    - github.com\nbrowser:\n  allowedDomains:\n    - google.com\n",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace, firewallDefaults).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:                     cl,
		Scheme:                     scheme,
		ConfigNamespace:            "operator-system",
		CiliumEnabled:              true,
		FirewallDefaultsConfigName: "firewall-defaults",
		PublicRouting:              defaultPublicRoutingConfig(),
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
		"github.com",
		"internal.example.com",
	})
	assertWorkspaceFirewallPolicy(t, cl, "team-a", "ws-ws-fw-browser-egress", []string{
		"google.com",
		"browser.example.com",
	})
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-fw-workspace-egress", "operator-system")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-fw-browser-egress", "operator-system")
}

func TestWorkspaceReconcilerFallsBackToWorkspaceNamespaceAndSetsOwnerReferences(t *testing.T) {
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
			WorkspaceID:   "ws-fallback",
			OwnerID:       "user-123",
			Provisioner:   "kubernetes",
			Runtime:       workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:       workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "browser:test"},
			Nextjs:        workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "nextjs:test"},
			WorkspacePath: "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: true,
		PublicRouting: defaultPublicRoutingConfig(),
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

	assertDeploymentImage(t, cl, "team-a", "workspace-runtime-ws-fallback", "runtime:test")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-runtime-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-browser-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-nextjs-ws-fallback", &appsv1.Deployment{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-runtime-ws-fallback", &corev1.Service{}, "Workspace", "workspace-fallback")
	assertOwnerReferenceExists(t, cl, "team-a", "workspace-pvc-ws-fallback", &corev1.PersistentVolumeClaim{}, "Workspace", "workspace-fallback")
	assertWorkspaceStatus(t, cl, "team-a", "workspace-fallback", func(status workspacev1alpha1.WorkspaceStatus) {
		if status.TargetNamespace != "team-a" {
			t.Fatalf("target namespace = %s, want team-a", status.TargetNamespace)
		}
	})
}

func TestWorkspaceReconcilerPolicyWithoutAllowedDomainsOmitsFQDNEntries(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)

	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-no-fqdn",
			Namespace: "operator-system",
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-no-fqdn",
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime:         workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:test"},
			Browser:         workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: true, Image: "browser:test"},
			Nextjs:          workspacev1alpha1.WorkspaceOptionalComponentSpec{Enabled: false},
			WorkspacePath:   "/workspace",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()

	reconciler := &WorkspaceReconciler{
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: true,
		PublicRouting: defaultPublicRoutingConfig(),
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

	assertPolicyHasNoFQDNEntries(t, cl, "team-a", "ws-ws-no-fqdn-workspace-egress")
	assertPolicyHasNoFQDNEntries(t, cl, "team-a", "ws-ws-no-fqdn-browser-egress")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-no-fqdn-workspace-egress", "")
	assertPolicyPreservesBaseConnectivity(t, cl, "team-a", "ws-ws-no-fqdn-browser-egress", "")
	assertWorkspaceStatus(t, cl, "operator-system", "workspace-no-fqdn", func(status workspacev1alpha1.WorkspaceStatus) {
		if len(status.Firewall.Workspace.EffectiveAllowedDomains) != 0 {
			t.Fatalf("workspace effective domains = %v, want empty", status.Firewall.Workspace.EffectiveAllowedDomains)
		}
		if len(status.Firewall.Browser.EffectiveAllowedDomains) != 0 {
			t.Fatalf("browser effective domains = %v, want empty", status.Firewall.Browser.EffectiveAllowedDomains)
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
			Namespace:         "operator-system",
			Finalizers:        []string{workspaceFinalizer},
			DeletionTimestamp: &now,
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID:     "ws-empty-delete",
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
		Client:        cl,
		Scheme:        scheme,
		CiliumEnabled: true,
		PublicRouting: defaultPublicRoutingConfig(),
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

func assertPVCExists(t *testing.T, cl client.Reader, namespace string, name string) {
	t.Helper()
	var pvc corev1.PersistentVolumeClaim
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      name,
		Namespace: namespace,
	}, &pvc); err != nil {
		t.Fatalf("get pvc %s/%s: %v", namespace, name, err)
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
	if len(deployment.Spec.Template.Spec.Volumes) == 0 {
		t.Fatalf("deployment %s/%s has no volumes", namespace, name)
	}
	got := deployment.Spec.Template.Spec.Volumes[0].PersistentVolumeClaim
	if got == nil || got.ClaimName != claimName {
		t.Fatalf("deployment %s/%s pvc = %v, want %s", namespace, name, got, claimName)
	}
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
			SubPath:   "kb-1",
			ReadOnly:  false,
		},
		"/knowledge/readonly-docs": {
			Name:      "knowledge-bases",
			MountPath: "/knowledge/readonly-docs",
			SubPath:   "kb-2",
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

func assertRuntimeDeploymentHasNoKnowledgeBaseVolume(
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

	for _, volume := range deployment.Spec.Template.Spec.Volumes {
		if volume.Name == "knowledge-bases" {
			t.Fatalf("deployment %s/%s unexpectedly has knowledge-bases volume", namespace, name)
		}
	}

	for _, mount := range deployment.Spec.Template.Spec.Containers[0].VolumeMounts {
		if mount.Name == "knowledge-bases" || strings.HasPrefix(mount.MountPath, "/knowledge/") {
			t.Fatalf("deployment %s/%s unexpectedly has knowledge base mount %+v", namespace, name, mount)
		}
	}
}

func assertRuntimeDeploymentSecurityContext(
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
	if securityContext == nil || securityContext.FSGroup == nil || *securityContext.FSGroup != 1000 {
		t.Fatalf("deployment %s/%s fsGroup = %v, want 1000", namespace, name, securityContext)
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

func assertPolicyHasNoFQDNEntries(
	t *testing.T,
	cl client.Reader,
	namespace string,
	name string,
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

	for _, rawEntry := range entries {
		entry, ok := rawEntry.(map[string]interface{})
		if !ok {
			continue
		}
		if _, found, _ := unstructured.NestedSlice(entry, "toFQDNs"); found {
			t.Fatalf("policy %s/%s unexpectedly contains toFQDNs entry", namespace, name)
		}
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
