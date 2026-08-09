package controller

import (
	"context"
	"reflect"
	"testing"

	corev1 "k8s.io/api/core/v1"
	storagev1 "k8s.io/api/storage/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const (
	testWorkspaceDataBytes int64 = 21_474_836_480
	testRuntimeHomeBytes   int64 = 2_147_483_648
)

func TestWorkspaceStorageReconcilerCreatesBothPVCsFromDesiredBytes(t *testing.T) {
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, nil, true)

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	assertStoragePVC(t, kubeClient, "workspace-pvc-ws-123", testWorkspaceDataBytes)
	assertStoragePVC(t, kubeClient, "workspace-runtime-home-pvc-ws-123", testRuntimeHomeBytes)
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, 0, 1, true, "")
	assertStorageStatus(t, workspace.Status.Storage.RuntimeHome, 0, 1, true, "")
}

func TestWorkspaceStorageReconcilerExpandsWorkspaceDataAndPreservesOtherSpec(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "20Gi", "20Gi")
	existing.Spec.AccessModes = []corev1.PersistentVolumeAccessMode{corev1.ReadWriteOnce}
	existing.Spec.VolumeName = "bound-volume"
	volumeMode := corev1.PersistentVolumeBlock
	existing.Spec.VolumeMode = &volumeMode
	existing.Spec.Selector = &metav1.LabelSelector{MatchLabels: map[string]string{"existing": "selector"}}
	existing.Spec.Resources.Limits = corev1.ResourceList{corev1.ResourceStorage: resource.MustParse("30Gi")}
	wantSpec := existing.Spec.DeepCopy()
	wantSpec.Resources.Requests[corev1.ResourceStorage] = resource.MustParse("25Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 26_843_545_600

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	got := getStoragePVC(t, kubeClient, existing.Name)
	if got.Spec.Resources.Requests.Storage().Value() != 26_843_545_600 {
		t.Fatalf("workspace data request = %d, want 26843545600", got.Spec.Resources.Requests.Storage().Value())
	}
	if !reflect.DeepEqual(got.Spec, *wantSpec) {
		t.Fatalf("PVC spec = %#v, want %#v", got.Spec, *wantSpec)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, true, "")
}

func TestWorkspaceStorageReconcilerExpandsRuntimeHome(t *testing.T) {
	existing := testStoragePVC("workspace-runtime-home-pvc-ws-123", "runtime-home", "2Gi", "2Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.RuntimeHome.CapacityBytes = 3_221_225_472

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	assertStoragePVC(t, kubeClient, existing.Name, 3_221_225_472)
	assertStorageStatus(t, workspace.Status.Storage.RuntimeHome, testRuntimeHomeBytes, 1, true, "")
}

func TestWorkspaceStorageReconcilerEchoesDesiredRevisionInObservedStatus(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "20Gi", "20Gi")
	workspace, reconciler, _ := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 26_843_545_600
	workspace.Spec.Storage.WorkspaceData.Revision = 7

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	if workspace.Status.Storage.WorkspaceData.ObservedRevision != 7 {
		t.Fatalf("observed revision = %d, want 7", workspace.Status.Storage.WorkspaceData.ObservedRevision)
	}
}

func TestWorkspaceStorageReconcilerRejectsUnsupportedExpansion(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "20Gi", "20Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, false)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 26_843_545_600

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	assertStoragePVC(t, kubeClient, existing.Name, testWorkspaceDataBytes)
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, false, workspacev1alpha1.WorkspaceStorageErrorExpansionUnsupported)
}

func TestWorkspaceStorageReconcilerRejectsShrink(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "20Gi", "20Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 17_179_869_184

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	assertStoragePVC(t, kubeClient, existing.Name, testWorkspaceDataBytes)
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, true, workspacev1alpha1.WorkspaceStorageErrorShrinkUnsupported)
}

func TestWorkspaceStorageReconcilerTreatsEqualRequestAsCompletedNoOp(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "20Gi", "20Gi")
	existing.Spec.VolumeName = "bound-volume"
	wantSpec := existing.Spec.DeepCopy()
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	got := getStoragePVC(t, kubeClient, existing.Name)
	if !reflect.DeepEqual(got.Spec, *wantSpec) {
		t.Fatalf("equal desired capacity changed PVC spec: %#v", got.Spec)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, true, "")
}

func TestWorkspaceStorageReconcilerCompletesOnlyAfterPVCStatusConverges(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "workspace-data", "25Gi", "20Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 26_843_545_600

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile applying workspace storage: %v", err)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, true, "")

	updated := getStoragePVC(t, kubeClient, existing.Name)
	updated.Status.Capacity = corev1.ResourceList{corev1.ResourceStorage: resource.MustParse("25Gi")}
	if err := kubeClient.Status().Update(context.Background(), updated); err != nil {
		t.Fatalf("update PVC status capacity: %v", err)
	}
	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile completed workspace storage: %v", err)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, 26_843_545_600, 1, true, "")
}

func TestWorkspaceStorageReconcilerReportsMissingStorageClassOnExpansion(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "missing-class", "20Gi", "20Gi")
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	workspace.Spec.Storage.WorkspaceData.CapacityBytes = 26_843_545_600

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	assertStoragePVC(t, kubeClient, existing.Name, testWorkspaceDataBytes)
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, false, workspacev1alpha1.WorkspaceStorageErrorClassNotFound)
}

func TestWorkspaceStorageReconcilerReportsMissingStorageClassBeforeCreatingPVC(t *testing.T) {
	workspace, reconciler, kubeClient := newWorkspaceStorageTest(t, nil, true)
	reconciler.WorkspaceStorageClass = "missing-class"

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile workspace storage: %v", err)
	}

	var pvc corev1.PersistentVolumeClaim
	err := kubeClient.Get(
		context.Background(),
		types.NamespacedName{Name: "workspace-pvc-ws-123", Namespace: "team-a"},
		&pvc,
	)
	if !apierrors.IsNotFound(err) {
		t.Fatalf("workspace PVC lookup error = %v, want not found", err)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, 0, 1, false, workspacev1alpha1.WorkspaceStorageErrorClassNotFound)
}

func TestWorkspaceStorageReconcilerDoesNotLookupAdmissionDefaultedStorageClass(t *testing.T) {
	existing := testStoragePVC("workspace-pvc-ws-123", "cluster-default", "20Gi", "20Gi")
	workspace, reconciler, _ := newWorkspaceStorageTest(t, []client.Object{existing}, true)
	reconciler.WorkspaceStorageClass = ""
	reconciler.RuntimeHomeStorageClass = ""
	coreScheme := runtime.NewScheme()
	if err := corev1.AddToScheme(coreScheme); err != nil {
		t.Fatalf("add core scheme: %v", err)
	}
	reconciler.APIReader = fake.NewClientBuilder().WithScheme(coreScheme).Build()

	if err := reconciler.Reconcile(context.Background(), workspace, "team-a"); err != nil {
		t.Fatalf("reconcile storage without configured StorageClass dependency: %v", err)
	}
	assertStorageStatus(t, workspace.Status.Storage.WorkspaceData, testWorkspaceDataBytes, 1, false, "")
}

func newWorkspaceStorageTest(t *testing.T, objects []client.Object, expansionSupported bool) (*workspacev1alpha1.Workspace, *WorkspaceStorageReconciler, client.Client) {
	t.Helper()
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	allowExpansion := expansionSupported
	objects = append(objects,
		&storagev1.StorageClass{ObjectMeta: metav1.ObjectMeta{Name: "workspace-data"}, AllowVolumeExpansion: &allowExpansion},
		&storagev1.StorageClass{ObjectMeta: metav1.ObjectMeta{Name: "runtime-home"}, AllowVolumeExpansion: &allowExpansion},
	)
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta:   metav1.TypeMeta{APIVersion: "platform.aileron.io/v1alpha1", Kind: "Workspace"},
		ObjectMeta: metav1.ObjectMeta{Name: "workspace-test", Namespace: "team-a", UID: types.UID("workspace-uid")},
		Spec: workspacev1alpha1.WorkspaceSpec{
			WorkspaceID: "ws-123",
			Storage: workspacev1alpha1.WorkspaceStorageSpec{
				WorkspaceData: workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: testWorkspaceDataBytes, Revision: 1},
				RuntimeHome:   workspacev1alpha1.WorkspaceStorageCapacitySpec{CapacityBytes: testRuntimeHomeBytes, Revision: 1},
			},
		},
	}
	kubeClient := fake.NewClientBuilder().WithScheme(scheme).WithStatusSubresource(&corev1.PersistentVolumeClaim{}).WithObjects(objects...).Build()
	return workspace, &WorkspaceStorageReconciler{
		Client:                  kubeClient,
		Scheme:                  scheme,
		WorkspaceStorageClass:   "workspace-data",
		RuntimeHomeStorageClass: "runtime-home",
		RuntimeHomeAccessMode:   corev1.ReadWriteOnce,
	}, kubeClient
}

func testStoragePVC(name string, storageClass string, requested string, allocated string) *corev1.PersistentVolumeClaim {
	return &corev1.PersistentVolumeClaim{
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: "team-a"},
		Spec: corev1.PersistentVolumeClaimSpec{
			StorageClassName: &storageClass,
			AccessModes:      []corev1.PersistentVolumeAccessMode{corev1.ReadWriteMany},
			Resources:        corev1.VolumeResourceRequirements{Requests: corev1.ResourceList{corev1.ResourceStorage: resource.MustParse(requested)}},
		},
		Status: corev1.PersistentVolumeClaimStatus{Phase: corev1.ClaimBound, Capacity: corev1.ResourceList{corev1.ResourceStorage: resource.MustParse(allocated)}},
	}
}

func getStoragePVC(t *testing.T, kubeClient client.Client, name string) *corev1.PersistentVolumeClaim {
	t.Helper()
	var pvc corev1.PersistentVolumeClaim
	if err := kubeClient.Get(context.Background(), types.NamespacedName{Name: name, Namespace: "team-a"}, &pvc); err != nil {
		t.Fatalf("get PVC %s: %v", name, err)
	}
	return &pvc
}

func assertStoragePVC(t *testing.T, kubeClient client.Client, name string, expectedBytes int64) {
	t.Helper()
	pvc := getStoragePVC(t, kubeClient, name)
	if actual := pvc.Spec.Resources.Requests.Storage().Value(); actual != expectedBytes {
		t.Fatalf("PVC %s requested bytes = %d, want %d", name, actual, expectedBytes)
	}
}

func assertStorageStatus(t *testing.T, status workspacev1alpha1.WorkspaceStorageCapacityStatus, allocatedBytes int64, observedRevision int64, expansionSupported bool, errorCode string) {
	t.Helper()
	if status.AllocatedBytes != allocatedBytes || status.ObservedRevision != observedRevision || status.ExpansionSupported != expansionSupported || status.ErrorCode != errorCode || status.ObservedAt == nil {
		t.Fatalf("storage status = %+v, want allocated=%d revision=%d expansionSupported=%t errorCode=%s observedAt set", status, allocatedBytes, observedRevision, expansionSupported, errorCode)
	}
}
