package controller

import (
	"context"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const (
	testImmutableRuntimeImage = "registry.example.com/aileron/runtime@sha256:1111111111111111111111111111111111111111111111111111111111111111"
	testImmutableBrowserImage = "registry.example.com/aileron/browser@sha256:2222222222222222222222222222222222222222222222222222222222222222"
	testImmutableCanvasImage  = "registry.example.com/aileron/canvas@sha256:3333333333333333333333333333333333333333333333333333333333333333"
	testImmutableRuntimeV1    = "registry.example.com/aileron/runtime@sha256:4444444444444444444444444444444444444444444444444444444444444444"
	testImmutableRuntimeV2    = "registry.example.com/aileron/runtime@sha256:5555555555555555555555555555555555555555555555555555555555555555"
)

func TestComponentImageErrorCodesRejectMutableReferences(t *testing.T) {
	workspace := &workspacev1alpha1.Workspace{Spec: workspacev1alpha1.WorkspaceSpec{
		Runtime: workspacev1alpha1.WorkspaceResourceSpec{Image: "runtime:latest"},
		Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{Image: testImmutableBrowserImage},
		Canvas:  workspacev1alpha1.WorkspaceOptionalComponentSpec{Image: "canvas:v1"},
	}}

	errors := componentImageErrorCodes(workspace)
	if errors[runtimeComponent] != "RUNTIME_IMAGE_REFERENCE_INVALID" {
		t.Fatalf("runtime error = %q", errors[runtimeComponent])
	}
	if _, found := errors[browserComponent]; found {
		t.Fatalf("valid browser image was rejected")
	}
	if errors[canvasComponent] != "CANVAS_IMAGE_REFERENCE_INVALID" {
		t.Fatalf("canvas error = %q", errors[canvasComponent])
	}
}

func TestInvalidRuntimeImageDoesNotBlockBrowserAndCanvasReconcile(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-image-test", Namespace: "team-a"},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Bootstrap:       workspacev1alpha1.WorkspaceBootstrapSpec{Revision: 1},
			WorkspaceID:     "ws-image-test",
			Storage:         testWorkspaceStorageSpec(),
			OwnerID:         "user-123",
			Provisioner:     "kubernetes",
			TargetNamespace: "team-a",
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{
				DesiredState:      "Running",
				InstanceID:        testRuntimeInstanceID,
				Revision:          1,
				Image:             "runtime:latest",
				RuntimeSecretName: runtimeSecretName("ws-image-test"),
				Assertion: workspacev1alpha1.WorkspaceRuntimeAssertionSpec{
					Issuer:                 "workspace-manager",
					PublicKeySetSecretName: "runtime-assertion-public-jwks",
				},
			},
			Browser: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				Enabled: true, DesiredState: "Running", Revision: 1, Image: testImmutableBrowserImage,
			},
			Canvas: workspacev1alpha1.WorkspaceOptionalComponentSpec{
				Enabled: true, DesiredState: "Running", Revision: 1, Image: testImmutableCanvasImage,
			},
			WorkspacePath:  "/workspace",
			WorktreeSubdir: ".worktrees",
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
		PlatformPublicOrigin:     defaultPlatformPublicOrigin(),
		BrowserCredentialKeyring: testBrowserCredentialDeriver{},
	}
	request := ctrl.Request{NamespacedName: types.NamespacedName{
		Name: workspace.Name, Namespace: workspace.Namespace,
	}}
	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("first reconcile: %v", err)
	}
	if _, err := reconciler.Reconcile(context.Background(), request); err != nil {
		t.Fatalf("second reconcile: %v", err)
	}

	runtimeDeployment := &appsv1.Deployment{}
	err := cl.Get(context.Background(), types.NamespacedName{
		Name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), Namespace: workspace.Namespace,
	}, runtimeDeployment)
	if !apierrors.IsNotFound(err) {
		t.Fatalf("invalid runtime deployment exists or lookup failed: %v", err)
	}
	assertDeploymentImage(
		t, cl, workspace.Namespace,
		resourceName(browserComponent, workspace.Spec.WorkspaceID),
		testImmutableBrowserImage,
	)
	assertDeploymentImage(
		t, cl, workspace.Namespace,
		resourceName(canvasComponent, workspace.Spec.WorkspaceID),
		testImmutableCanvasImage,
	)

	current := &workspacev1alpha1.Workspace{}
	if err := cl.Get(context.Background(), request.NamespacedName, current); err != nil {
		t.Fatalf("get Workspace: %v", err)
	}
	if current.Status.Components.Runtime.ErrorCode != "RUNTIME_IMAGE_REFERENCE_INVALID" {
		t.Fatalf("runtime error code = %q", current.Status.Components.Runtime.ErrorCode)
	}
}
