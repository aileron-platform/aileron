package controller

import (
	"context"
	"fmt"
	"time"

	corev1 "k8s.io/api/core/v1"
	storagev1 "k8s.io/api/storage/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

type WorkspaceStorageReconciler struct {
	client.Client
	APIReader               client.Reader
	Scheme                  *runtime.Scheme
	WorkspaceStorageClass   string
	RuntimeHomeStorageClass string
	RuntimeHomeAccessMode   corev1.PersistentVolumeAccessMode
}

type workspaceStorageTarget struct {
	component        string
	name             string
	storageClassName string
	accessMode       corev1.PersistentVolumeAccessMode
	desiredBytes     int64
	desiredRevision  int64
	previousStatus   workspacev1alpha1.WorkspaceStorageCapacityStatus
	setStatus        func(workspacev1alpha1.WorkspaceStorageCapacityStatus)
}

func (r *WorkspaceStorageReconciler) Reconcile(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	runtimeHomeAccessMode := r.RuntimeHomeAccessMode
	if runtimeHomeAccessMode == "" {
		runtimeHomeAccessMode = corev1.ReadWriteOnce
	}
	targets := []workspaceStorageTarget{
		{
			component:        pvcComponent,
			name:             resourceName(pvcComponent, workspace.Spec.WorkspaceID),
			storageClassName: r.WorkspaceStorageClass,
			accessMode:       corev1.ReadWriteMany,
			desiredBytes:     workspace.Spec.Storage.WorkspaceData.CapacityBytes,
			desiredRevision:  workspace.Spec.Storage.WorkspaceData.Revision,
			previousStatus:   workspace.Status.Storage.WorkspaceData,
			setStatus: func(status workspacev1alpha1.WorkspaceStorageCapacityStatus) {
				workspace.Status.Storage.WorkspaceData = status
			},
		},
		{
			component:        runtimeHomePVCComponent,
			name:             resourceName(runtimeHomePVCComponent, workspace.Spec.WorkspaceID),
			storageClassName: r.RuntimeHomeStorageClass,
			accessMode:       runtimeHomeAccessMode,
			desiredBytes:     workspace.Spec.Storage.RuntimeHome.CapacityBytes,
			desiredRevision:  workspace.Spec.Storage.RuntimeHome.Revision,
			previousStatus:   workspace.Status.Storage.RuntimeHome,
			setStatus: func(status workspacev1alpha1.WorkspaceStorageCapacityStatus) {
				workspace.Status.Storage.RuntimeHome = status
			},
		},
	}

	for _, target := range targets {
		status, err := r.reconcileTarget(ctx, workspace, namespace, target)
		if err != nil {
			return err
		}
		target.setStatus(status)
	}
	return nil
}

func (r *WorkspaceStorageReconciler) reconcileTarget(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	target workspaceStorageTarget,
) (workspacev1alpha1.WorkspaceStorageCapacityStatus, error) {
	if target.desiredBytes <= 0 || target.desiredRevision <= 0 {
		return storageStatus(target.previousStatus, target.desiredRevision, 0, false, workspacev1alpha1.WorkspaceStorageErrorCapacityInvalid), nil
	}

	key := types.NamespacedName{Name: target.name, Namespace: namespace}
	pvc := &corev1.PersistentVolumeClaim{}
	err := r.Get(ctx, key, pvc)
	if apierrors.IsNotFound(err) {
		return r.createPVC(ctx, workspace, namespace, target)
	}
	if err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, fmt.Errorf("get storage PVC %s: %w", key, err)
	}

	requestedBytes := resourceBytes(pvc.Spec.Resources.Requests.Storage())
	allocatedBytes := resourceBytes(pvc.Status.Capacity.Storage())
	storageClassName := pvc.Spec.StorageClassName
	if target.storageClassName == "" {
		storageClassName = nil
	}
	expansionSupported, storageClassFound, err := r.storageClassExpansionSupport(ctx, storageClassName)
	if err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, err
	}
	if target.desiredBytes < requestedBytes {
		return storageStatus(target.previousStatus, target.desiredRevision, allocatedBytes, expansionSupported, workspacev1alpha1.WorkspaceStorageErrorShrinkUnsupported), nil
	}

	before := pvc.DeepCopy()
	pvc.Labels = componentLabels(workspace, target.component, "workspace")
	if err := controllerutil.SetControllerReference(workspace, pvc, r.Scheme); err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, fmt.Errorf("set storage PVC owner: %w", err)
	}
	if target.desiredBytes > requestedBytes {
		if !storageClassFound {
			return storageStatus(target.previousStatus, target.desiredRevision, allocatedBytes, false, workspacev1alpha1.WorkspaceStorageErrorClassNotFound), nil
		}
		if !expansionSupported {
			return storageStatus(target.previousStatus, target.desiredRevision, allocatedBytes, false, workspacev1alpha1.WorkspaceStorageErrorExpansionUnsupported), nil
		}
		pvc.Spec.Resources.Requests[corev1.ResourceStorage] = *resource.NewQuantity(target.desiredBytes, resource.BinarySI)
		requestedBytes = target.desiredBytes
	}
	if !equality.Semantic.DeepEqual(before, pvc) {
		if err := r.Update(ctx, pvc); err != nil {
			return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, fmt.Errorf("update storage PVC %s: %w", key, err)
		}
	}

	return storageStatus(target.previousStatus, target.desiredRevision, allocatedBytes, expansionSupported, ""), nil
}

func (r *WorkspaceStorageReconciler) createPVC(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	target workspaceStorageTarget,
) (workspacev1alpha1.WorkspaceStorageCapacityStatus, error) {
	pvc := &corev1.PersistentVolumeClaim{
		ObjectMeta: metav1.ObjectMeta{Name: target.name, Namespace: namespace, Labels: componentLabels(workspace, target.component, "workspace")},
		Spec: corev1.PersistentVolumeClaimSpec{
			AccessModes: []corev1.PersistentVolumeAccessMode{target.accessMode},
			Resources: corev1.VolumeResourceRequirements{Requests: corev1.ResourceList{
				corev1.ResourceStorage: *resource.NewQuantity(target.desiredBytes, resource.BinarySI),
			}},
		},
	}
	if target.storageClassName != "" {
		pvc.Spec.StorageClassName = &target.storageClassName
	}
	expansionSupported, storageClassFound, err := r.storageClassExpansionSupport(ctx, pvc.Spec.StorageClassName)
	if err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, err
	}
	if target.storageClassName != "" && !storageClassFound {
		return storageStatus(target.previousStatus, target.desiredRevision, 0, false, workspacev1alpha1.WorkspaceStorageErrorClassNotFound), nil
	}
	if err := controllerutil.SetControllerReference(workspace, pvc, r.Scheme); err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, fmt.Errorf("set storage PVC owner: %w", err)
	}
	if err := r.Create(ctx, pvc); err != nil {
		return workspacev1alpha1.WorkspaceStorageCapacityStatus{}, fmt.Errorf("create storage PVC %s/%s: %w", namespace, target.name, err)
	}
	return storageStatus(target.previousStatus, target.desiredRevision, 0, expansionSupported, ""), nil
}

func (r *WorkspaceStorageReconciler) storageClassExpansionSupport(
	ctx context.Context,
	storageClassName *string,
) (bool, bool, error) {
	if storageClassName == nil || *storageClassName == "" {
		return false, false, nil
	}
	storageClass := &storagev1.StorageClass{}
	reader := r.APIReader
	if reader == nil {
		reader = r.Client
	}
	if err := reader.Get(ctx, types.NamespacedName{Name: *storageClassName}, storageClass); err != nil {
		if apierrors.IsNotFound(err) {
			return false, false, nil
		}
		return false, false, fmt.Errorf("get StorageClass %s: %w", *storageClassName, err)
	}
	return storageClass.AllowVolumeExpansion != nil && *storageClass.AllowVolumeExpansion, true, nil
}

func storageStatus(
	previous workspacev1alpha1.WorkspaceStorageCapacityStatus,
	observedRevision int64,
	allocatedBytes int64,
	expansionSupported bool,
	errorCode string,
) workspacev1alpha1.WorkspaceStorageCapacityStatus {
	status := workspacev1alpha1.WorkspaceStorageCapacityStatus{
		AllocatedBytes: allocatedBytes, ObservedRevision: observedRevision,
		ExpansionSupported: expansionSupported, ErrorCode: errorCode,
	}
	comparablePrevious := previous
	comparablePrevious.ObservedAt = nil
	if equality.Semantic.DeepEqual(comparablePrevious, status) && previous.ObservedAt != nil {
		status.ObservedAt = previous.ObservedAt.DeepCopy()
		return status
	}
	observedAt := metav1.NewTime(time.Now().UTC())
	status.ObservedAt = &observedAt
	return status
}

func resourceBytes(quantity *resource.Quantity) int64 {
	if quantity == nil {
		return 0
	}
	return quantity.Value()
}
