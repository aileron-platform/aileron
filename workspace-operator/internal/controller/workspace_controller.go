package controller

import (
	"context"
	"fmt"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/util/intstr"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/yaml"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const workspaceFinalizer = "platform.aileron.io/workspace-finalizer"

const (
	runtimeComponent = "workspace-runtime"
	browserComponent = "workspace-browser"
	canvasComponent  = "workspace-canvas"
	pvcComponent     = "workspace-pvc"
)

const (
	runtimeCodexArg0VolumeName = "codex-arg0-tmp"
	runtimeCodexArg0MountPath  = "/home/developer/.codex/tmp/arg0"
)

var ciliumNetworkPolicyGVK = schema.GroupVersionKind{
	Group:   "cilium.io",
	Version: "v2",
	Kind:    "CiliumNetworkPolicy",
}

type WorkspaceReconciler struct {
	client.Client
	Scheme                     *runtime.Scheme
	ConfigNamespace            string
	CiliumEnabled              bool
	FirewallDefaultsConfigName string
	PublicRouting              PublicRoutingConfig
	ManagerURL                 string
	KeycloakURL                string
	KeycloakRealm              string
	KeycloakClientID           string
	KeycloakClientSecret       string
	RedisURL                   string
	DatabaseURL                string
	InternalAPIToken           string
	// TURN server for WebRTC (browser component)
	TURNServerURL         string // backend (neko pod → TURN) URL
	TURNServerFrontendURL string // frontend (browser → TURN) URL; may differ in local K8s
	TURNServerExternalIP  string // relay IP announced to clients / NAT1TO1
	TURNServerUsername    string
	TURNServerCredential  string
	KnowledgeBasesPVCName string
}

type firewallDefaultsFile struct {
	Workspace firewallDefaultsGroup `yaml:"workspace"`
	Browser   firewallDefaultsGroup `yaml:"browser"`
}

type firewallDefaultsGroup struct {
	AllowedDomains []string `yaml:"allowedDomains"`
}

func (r *WorkspaceReconciler) Reconcile(
	ctx context.Context,
	req ctrl.Request,
) (ctrl.Result, error) {
	logger := log.FromContext(ctx).WithValues("workspace", req.NamespacedName.String())

	var workspace workspacev1alpha1.Workspace
	if err := r.Get(ctx, req.NamespacedName, &workspace); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, err
	}

	if !workspace.DeletionTimestamp.IsZero() {
		return r.reconcileDelete(ctx, &workspace, logger)
	}

	if controllerutil.AddFinalizer(&workspace, workspaceFinalizer) {
		if err := r.Update(ctx, &workspace); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info("added workspace finalizer")
		return ctrl.Result{Requeue: true}, nil
	}

	targetNamespace := workspace.Spec.TargetNamespace
	if targetNamespace == "" {
		targetNamespace = workspace.Namespace
	}

	if err := r.reconcileWorkspacePVC(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile workspace pvc")
		return ctrl.Result{}, err
	}
	if err := r.reconcileRuntimeDeployment(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile runtime deployment")
		return ctrl.Result{}, err
	}
	if err := r.reconcileRuntimeService(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile runtime service")
		return ctrl.Result{}, err
	}
	if err := r.reconcileRuntimeIngress(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile runtime ingress")
		return ctrl.Result{}, err
	}
	if err := r.reconcileBrowserDeployment(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile browser deployment")
		return ctrl.Result{}, err
	}
	if err := r.reconcileBrowserService(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile browser service")
		return ctrl.Result{}, err
	}
	if err := r.reconcileComponentIngress(
		ctx,
		&workspace,
		targetNamespace,
		browserComponent,
		workspace.Spec.Browser.Enabled,
	); err != nil {
		logger.Error(err, "unable to reconcile browser ingress")
		return ctrl.Result{}, err
	}
	if err := r.reconcileCanvasDeployment(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile canvas deployment")
		return ctrl.Result{}, err
	}
	if err := r.reconcileCanvasService(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to reconcile canvas service")
		return ctrl.Result{}, err
	}
	if err := r.reconcileComponentIngress(
		ctx,
		&workspace,
		targetNamespace,
		canvasComponent,
		workspace.Spec.Canvas.Enabled,
	); err != nil {
		logger.Error(err, "unable to reconcile canvas ingress")
		return ctrl.Result{}, err
	}

	workspace.Status.ObservedGeneration = workspace.Generation
	workspace.Status.TargetNamespace = targetNamespace
	firewallStatus := r.effectiveFirewallStatus(ctx, &workspace)
	workspace.Status.Firewall = firewallStatus
	if r.CiliumEnabled {
		if err := r.reconcileWorkspaceFirewallPolicy(
			ctx,
			&workspace,
			targetNamespace,
			firewallStatus.Workspace.EffectiveAllowedDomains,
		); err != nil {
			logger.Error(err, "unable to reconcile workspace firewall policy")
			return ctrl.Result{}, err
		}
		if err := r.reconcileBrowserFirewallPolicy(
			ctx,
			&workspace,
			targetNamespace,
			firewallStatus.Browser.EffectiveAllowedDomains,
		); err != nil {
			logger.Error(err, "unable to reconcile browser firewall policy")
			return ctrl.Result{}, err
		}
	} else {
		if err := r.deleteFirewallPolicies(ctx, &workspace, targetNamespace); err != nil {
			logger.Error(err, "unable to cleanup disabled firewall policies")
			return ctrl.Result{}, err
		}
	}
	if err := r.populateWorkspaceStatus(ctx, &workspace, targetNamespace); err != nil {
		logger.Error(err, "unable to populate workspace status")
		return ctrl.Result{}, err
	}

	if err := r.Status().Update(ctx, &workspace); err != nil {
		logger.Error(err, "unable to update workspace status")
		return ctrl.Result{}, err
	}

	logger.Info(
		"reconciled workspace placeholder state",
		"targetNamespace", targetNamespace,
		"workspaceId", workspace.Spec.WorkspaceID,
	)
	if shouldRequeueWorkspaceStatus(workspace.Status) {
		return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
	}
	return ctrl.Result{}, nil
}

func (r *WorkspaceReconciler) reconcileRuntimeDeployment(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(runtimeComponent, workspace.Spec.WorkspaceID)
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, deployment, func() error {
		labels := componentLabels(workspace, runtimeComponent, "workspace")
		deployment.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		deployment.Spec.Replicas = int32Ptr(1)
		deployment.Spec.Template.ObjectMeta.Labels = labels
		deployment.Spec.Template.Spec.SecurityContext = &corev1.PodSecurityContext{
			FSGroup:        int64Ptr(1000),
			SeccompProfile: &corev1.SeccompProfile{Type: corev1.SeccompProfileTypeUnconfined},
		}
		deployment.Spec.Template.Spec.Volumes = runtimeVolumes(workspace, r.knowledgeBasesPVCName())
		container := corev1.Container{
			Name:  "runtime",
			Image: resolveRuntimeImage(workspace),
			Ports: []corev1.ContainerPort{
				{Name: "http", ContainerPort: 3002},
				{Name: "terminal", ContainerPort: 3004},
			},
			Env:          append(runtimeEnvVars(workspace, r), toEnvVars(workspace.Spec.EnvVars)...),
			VolumeMounts: runtimeVolumeMounts(workspace),
		}
		if workspace.Spec.Runtime.Resources != nil {
			container.Resources = *workspace.Spec.Runtime.Resources
		}
		deployment.Spec.Template.Spec.Containers = []corev1.Container{container}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileRuntimeService(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(runtimeComponent, workspace.Spec.WorkspaceID)
	svc := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, svc, func() error {
		labels := componentLabels(workspace, runtimeComponent, "workspace")
		svc.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = labels
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "http", Port: 3002, TargetPort: intstrFromInt32(3002)},
			{Name: "terminal", Port: 3004, TargetPort: intstrFromInt32(3004)},
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileBrowserDeployment(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(browserComponent, workspace.Spec.WorkspaceID)
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, deployment, func() error {
		labels := componentLabels(workspace, browserComponent, "browser")
		replicas := int32(0)
		if workspace.Spec.Browser.Enabled {
			replicas = 1
		}
		deployment.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		deployment.Spec.Replicas = &replicas
		deployment.Spec.Template.ObjectMeta.Labels = labels
		deployment.Spec.Template.Spec.Volumes = []corev1.Volume{
			{
				Name: "workspace-data",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
						ClaimName: resourceName(pvcComponent, workspace.Spec.WorkspaceID),
					},
				},
			},
		}
		container := corev1.Container{
			Name:  "browser",
			Image: resolveOptionalImage(workspace.Spec.Browser.Image, "ailerondocker/workspace-chrome:latest"),
			Ports: []corev1.ContainerPort{
				{Name: "webrtc", ContainerPort: 6080},
				{Name: "cdp", ContainerPort: 9223},
			},
			Env: browserEnvVars(r),
			VolumeMounts: []corev1.VolumeMount{
				{
					Name:      "workspace-data",
					MountPath: workspaceMountPath(workspace),
				},
			},
		}
		if workspace.Spec.Browser.Resources != nil {
			container.Resources = *workspace.Spec.Browser.Resources
		}
		deployment.Spec.Template.Spec.Containers = []corev1.Container{container}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileBrowserService(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(browserComponent, workspace.Spec.WorkspaceID)
	svc := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, svc, func() error {
		labels := componentLabels(workspace, browserComponent, "browser")
		svc.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = labels
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "webrtc", Port: 6080, TargetPort: intstrFromInt32(6080)},
			{Name: "cdp", Port: 9223, TargetPort: intstrFromInt32(9223)},
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileCanvasDeployment(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(canvasComponent, workspace.Spec.WorkspaceID)
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, deployment, func() error {
		labels := componentLabels(workspace, canvasComponent, "workspace")
		replicas := int32(0)
		if workspace.Spec.Canvas.Enabled {
			replicas = 1
		}
		deployment.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		deployment.Spec.Replicas = &replicas
		deployment.Spec.Template.ObjectMeta.Labels = labels
		deployment.Spec.Template.Spec.Volumes = []corev1.Volume{
			{
				Name: "workspace-data",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
						ClaimName: resourceName(pvcComponent, workspace.Spec.WorkspaceID),
					},
				},
			},
		}
		container := corev1.Container{
			Name:  "canvas",
			Image: resolveOptionalImage(workspace.Spec.Canvas.Image, "ailerondocker/workspace-canvas:latest"),
			Ports: []corev1.ContainerPort{
				{Name: "http", ContainerPort: 3003},
				{Name: "api", ContainerPort: 3013},
			},
			VolumeMounts: []corev1.VolumeMount{
				{
					Name:      "workspace-data",
					MountPath: workspaceMountPath(workspace),
				},
			},
		}
		if workspace.Spec.Canvas.Resources != nil {
			container.Resources = *workspace.Spec.Canvas.Resources
		}
		deployment.Spec.Template.Spec.Containers = []corev1.Container{container}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileCanvasService(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(canvasComponent, workspace.Spec.WorkspaceID)
	svc := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, svc, func() error {
		labels := componentLabels(workspace, canvasComponent, "workspace")
		svc.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = labels
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "http", Port: 3003, TargetPort: intstrFromInt32(3003)},
			{Name: "api", Port: 3013, TargetPort: intstrFromInt32(3013)},
		}
		return nil
	})
	return err
}

// reconcileRuntimeIngress creates the runtime ingress with two path rules:
//   - /ws/terminal  → port 3004 (Go terminal service)
//   - /             → port 3002 (FastAPI)
func (r *WorkspaceReconciler) reconcileRuntimeIngress(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	name := resourceName(runtimeComponent, workspace.Spec.WorkspaceID)
	ingress := &networkingv1.Ingress{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	host, err := r.PublicRouting.ResolveHost(r.PublicRouting.RuntimeHostPattern, workspace.Spec.WorkspaceID)
	if err != nil {
		return err
	}

	pathTypePrefix := networkingv1.PathTypePrefix
	_, err = controllerutil.CreateOrUpdate(ctx, r.Client, ingress, func() error {
		labels := componentLabels(workspace, runtimeComponent+"-ingress", "workspace")
		ingress.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, ingress); err != nil {
			return err
		}
		if ingress.Annotations == nil {
			ingress.Annotations = make(map[string]string)
		}
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "3600"
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "3600"
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-http-version"] = "1.1"
		if strings.TrimSpace(r.PublicRouting.IngressClassName) != "" {
			ingress.Spec.IngressClassName = &r.PublicRouting.IngressClassName
		} else {
			ingress.Spec.IngressClassName = nil
		}
		ingress.Spec.Rules = []networkingv1.IngressRule{
			{
				Host: host,
				IngressRuleValue: networkingv1.IngressRuleValue{
					HTTP: &networkingv1.HTTPIngressRuleValue{
						Paths: []networkingv1.HTTPIngressPath{
							{
								// Terminal WebSocket path — must come before "/" to take precedence
								Path:     "/ws/terminal",
								PathType: &pathTypePrefix,
								Backend: networkingv1.IngressBackend{
									Service: &networkingv1.IngressServiceBackend{
										Name: name,
										Port: networkingv1.ServiceBackendPort{Number: 3004},
									},
								},
							},
							{
								Path:     "/",
								PathType: &pathTypePrefix,
								Backend: networkingv1.IngressBackend{
									Service: &networkingv1.IngressServiceBackend{
										Name: name,
										Port: networkingv1.ServiceBackendPort{Number: 3002},
									},
								},
							},
						},
					},
				},
			},
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileComponentIngress(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
	enabled bool,
) error {
	name := resourceName(component, workspace.Spec.WorkspaceID)
	ingress := &networkingv1.Ingress{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
	}

	if !enabled {
		if err := r.Delete(ctx, ingress); err != nil && !apierrors.IsNotFound(err) {
			return err
		}
		return nil
	}

	host, servicePort, err := r.componentIngressSpec(component, workspace.Spec.WorkspaceID)
	if err != nil {
		return err
	}

	pathType := networkingv1.PathTypePrefix
	_, err = controllerutil.CreateOrUpdate(ctx, r.Client, ingress, func() error {
		labels := componentLabels(workspace, component+"-ingress", "workspace")
		ingress.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, ingress); err != nil {
			return err
		}
		// WebSocket support: nginx ingress controller needs extended timeouts and HTTP/1.1
		// to properly handle WebSocket upgrade handshake and long-lived connections.
		if ingress.Annotations == nil {
			ingress.Annotations = make(map[string]string)
		}
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "3600"
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "3600"
		ingress.Annotations["nginx.ingress.kubernetes.io/proxy-http-version"] = "1.1"
		if strings.TrimSpace(r.PublicRouting.IngressClassName) != "" {
			ingress.Spec.IngressClassName = &r.PublicRouting.IngressClassName
		} else {
			ingress.Spec.IngressClassName = nil
		}
		ingress.Spec.Rules = []networkingv1.IngressRule{
			{
				Host: host,
				IngressRuleValue: networkingv1.IngressRuleValue{
					HTTP: &networkingv1.HTTPIngressRuleValue{
						Paths: []networkingv1.HTTPIngressPath{
							{
								Path:     "/",
								PathType: &pathType,
								Backend: networkingv1.IngressBackend{
									Service: &networkingv1.IngressServiceBackend{
										Name: name,
										Port: networkingv1.ServiceBackendPort{Number: servicePort},
									},
								},
							},
						},
					},
				},
			},
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) componentIngressSpec(component string, workspaceID string) (string, int32, error) {
	switch component {
	case runtimeComponent:
		host, err := r.PublicRouting.ResolveHost(r.PublicRouting.RuntimeHostPattern, workspaceID)
		return host, 3002, err
	case browserComponent:
		host, err := r.PublicRouting.ResolveHost(r.PublicRouting.BrowserHostPattern, workspaceID)
		return host, 6080, err
	case canvasComponent:
		host, err := r.PublicRouting.ResolveHost(r.PublicRouting.CanvasHostPattern, workspaceID)
		return host, 3003, err
	default:
		return "", 0, fmt.Errorf("unsupported ingress component: %s", component)
	}
}

func (r *WorkspaceReconciler) reconcileDelete(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	logger logrLike,
) (ctrl.Result, error) {
	if !controllerutil.ContainsFinalizer(workspace, workspaceFinalizer) {
		return ctrl.Result{}, nil
	}

	targetNamespace := workspace.Spec.TargetNamespace
	if targetNamespace == "" {
		targetNamespace = workspace.Namespace
	}

	logger.Info("cleaning up managed workspace resources", "targetNamespace", targetNamespace)
	if err := r.deleteManagedResources(ctx, workspace, targetNamespace); err != nil {
		return ctrl.Result{}, err
	}

	controllerutil.RemoveFinalizer(workspace, workspaceFinalizer)
	if err := r.Update(ctx, workspace); err != nil {
		return ctrl.Result{}, err
	}

	return ctrl.Result{}, nil
}

func (r *WorkspaceReconciler) reconcileWorkspaceFirewallPolicy(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	allowedDomains []string,
) error {
	policy := newCiliumNetworkPolicy(namespace, workspaceFirewallPolicyName(workspace.Spec.WorkspaceID))

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, policy, func() error {
		labels := componentLabels(workspace, "workspace-firewall-policy", "workspace")
		policy.SetLabels(labels)

		spec := map[string]interface{}{
			"endpointSelector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"aileron.io/workspace-id":   workspace.Spec.WorkspaceID,
					"aileron.io/firewall-group": "workspace",
				},
			},
			"egress": r.baseEgressRules(allowedDomains),
		}

		if err := unstructured.SetNestedField(policy.Object, spec, "spec"); err != nil {
			return err
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileBrowserFirewallPolicy(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	allowedDomains []string,
) error {
	policy := newCiliumNetworkPolicy(namespace, browserFirewallPolicyName(workspace.Spec.WorkspaceID))

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, policy, func() error {
		labels := componentLabels(workspace, "browser-firewall-policy", "browser")
		policy.SetLabels(labels)

		spec := map[string]interface{}{
			"endpointSelector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"aileron.io/workspace-id":   workspace.Spec.WorkspaceID,
					"aileron.io/firewall-group": "browser",
				},
			},
			"egress": r.baseEgressRules(allowedDomains),
		}

		if err := unstructured.SetNestedField(policy.Object, spec, "spec"); err != nil {
			return err
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileWorkspacePVC(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	pvc := &corev1.PersistentVolumeClaim{
		ObjectMeta: metav1.ObjectMeta{
			Name:      resourceName(pvcComponent, workspace.Spec.WorkspaceID),
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, pvc, func() error {
		labels := componentLabels(workspace, pvcComponent, "workspace")
		pvc.Labels = labels
		if err := r.setOwnerReferenceIfSameNamespace(workspace, pvc); err != nil {
			return err
		}
		pvc.Spec.AccessModes = []corev1.PersistentVolumeAccessMode{
			corev1.ReadWriteOnce,
		}
		pvc.Spec.Resources.Requests = corev1.ResourceList{
			corev1.ResourceStorage: resource.MustParse("20Gi"),
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) deleteManagedResources(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	resourceNames := []struct {
		name string
		obj  client.Object
	}{
		{name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), obj: &networkingv1.Ingress{}},
		{name: resourceName(browserComponent, workspace.Spec.WorkspaceID), obj: &networkingv1.Ingress{}},
		{name: resourceName(canvasComponent, workspace.Spec.WorkspaceID), obj: &networkingv1.Ingress{}},
		{name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(browserComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(canvasComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(browserComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(canvasComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(pvcComponent, workspace.Spec.WorkspaceID), obj: &corev1.PersistentVolumeClaim{}},
	}

	for _, item := range resourceNames {
		item.obj.SetName(item.name)
		item.obj.SetNamespace(namespace)
		if err := r.Delete(ctx, item.obj); err != nil && !apierrors.IsNotFound(err) {
			return err
		}
	}

	return r.deleteFirewallPolicies(ctx, workspace, namespace)
}

func (r *WorkspaceReconciler) deleteFirewallPolicies(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	workspacePolicy := newCiliumNetworkPolicy(namespace, workspaceFirewallPolicyName(workspace.Spec.WorkspaceID))
	if err := r.Delete(ctx, workspacePolicy); err != nil &&
		!apierrors.IsNotFound(err) &&
		!meta.IsNoMatchError(err) {
		return err
	}
	browserPolicy := newCiliumNetworkPolicy(namespace, browserFirewallPolicyName(workspace.Spec.WorkspaceID))
	if err := r.Delete(ctx, browserPolicy); err != nil &&
		!apierrors.IsNotFound(err) &&
		!meta.IsNoMatchError(err) {
		return err
	}

	return nil
}

func (r *WorkspaceReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&workspacev1alpha1.Workspace{}).
		Named("workspace-controller").
		Complete(r)
}

func (r *WorkspaceReconciler) effectiveFirewallStatus(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
) workspacev1alpha1.WorkspaceFirewallStatus {
	if !r.CiliumEnabled {
		return workspacev1alpha1.WorkspaceFirewallStatus{}
	}
	defaults := r.loadFirewallDefaults(ctx)
	return workspacev1alpha1.WorkspaceFirewallStatus{
		Workspace: workspacev1alpha1.WorkspaceFirewallGroupStatus{
			EffectiveAllowedDomains: mergeAllowedDomains(
				defaults.Workspace.AllowedDomains,
				workspace.Spec.Firewall.Workspace.AllowedDomains,
			),
		},
		Browser: workspacev1alpha1.WorkspaceFirewallGroupStatus{
			EffectiveAllowedDomains: mergeAllowedDomains(
				defaults.Browser.AllowedDomains,
				workspace.Spec.Firewall.Browser.AllowedDomains,
			),
		},
	}
}

func (r *WorkspaceReconciler) loadFirewallDefaults(ctx context.Context) firewallDefaultsFile {
	if r.FirewallDefaultsConfigName == "" {
		return firewallDefaultsFile{}
	}

	configNamespace := r.ConfigNamespace
	if configNamespace == "" {
		configNamespace = "default"
	}

	configMap := &corev1.ConfigMap{}
	if err := r.Get(ctx, client.ObjectKey{
		Name:      r.FirewallDefaultsConfigName,
		Namespace: configNamespace,
	}, configMap); err != nil {
		return firewallDefaultsFile{}
	}

	raw := configMap.Data["firewall-defaults.yaml"]
	if strings.TrimSpace(raw) == "" {
		return firewallDefaultsFile{}
	}

	var defaults firewallDefaultsFile
	if err := yaml.Unmarshal([]byte(raw), &defaults); err != nil {
		return firewallDefaultsFile{}
	}
	return defaults
}

func (r *WorkspaceReconciler) populateWorkspaceStatus(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	runtimeStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		runtimeComponent,
		true,
		3002,
		workspace.Spec.Operations.RestartRuntimeAt,
	)
	if err != nil {
		return err
	}

	browserStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		browserComponent,
		workspace.Spec.Browser.Enabled,
		6080,
		workspace.Spec.Operations.RestartBrowserAt,
	)
	if err != nil {
		return err
	}

	canvasStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		canvasComponent,
		workspace.Spec.Canvas.Enabled,
		3003,
		workspace.Spec.Operations.RestartCanvasAt,
	)
	if err != nil {
		return err
	}

	workspace.Status.Components = workspacev1alpha1.WorkspaceComponentsStatus{
		Runtime: runtimeStatus,
		Browser: browserStatus,
		Canvas:  canvasStatus,
	}
	workspace.Status.Phase = calculateWorkspacePhase(
		workspace.Spec,
		workspace.Status.Components,
	)

	return nil
}

func (r *WorkspaceReconciler) buildComponentStatus(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
	enabled bool,
	internalPort int32,
	componentRestartAt *metav1.Time,
) (workspacev1alpha1.WorkspaceComponentStatus, error) {
	status := workspacev1alpha1.WorkspaceComponentStatus{
		LastRestartedAt: mostRecentTime(
			workspace.Spec.Operations.RestartWorkspaceAt,
			componentRestartAt,
		),
		ExternalURL: r.componentExternalURL(component, workspace.Spec.WorkspaceID),
	}

	if !enabled {
		status.Phase = "Disabled"
		return status, nil
	}

	service := &corev1.Service{}
	if err := r.Get(ctx, client.ObjectKey{
		Name:      resourceName(component, workspace.Spec.WorkspaceID),
		Namespace: namespace,
	}, service); err != nil {
		if apierrors.IsNotFound(err) {
			status.Phase = "Pending"
			return status, nil
		}
		return status, err
	}

	status.InternalURL = serviceInternalURL(service, internalPort)

	deployment := &appsv1.Deployment{}
	if err := r.Get(ctx, client.ObjectKey{
		Name:      resourceName(component, workspace.Spec.WorkspaceID),
		Namespace: namespace,
	}, deployment); err != nil {
		if apierrors.IsNotFound(err) {
			status.Phase = "Pending"
			return status, nil
		}
		return status, err
	}

	status.Phase = deploymentPhase(deployment)
	return status, nil
}

func calculateWorkspacePhase(
	spec workspacev1alpha1.WorkspaceSpec,
	components workspacev1alpha1.WorkspaceComponentsStatus,
) string {
	requiredPhases := []string{components.Runtime.Phase}
	if spec.Browser.Enabled {
		requiredPhases = append(requiredPhases, components.Browser.Phase)
	}
	if spec.Canvas.Enabled {
		requiredPhases = append(requiredPhases, components.Canvas.Phase)
	}

	allRunning := true
	for _, phase := range requiredPhases {
		if phase == "" {
			return "Pending"
		}
		if phase == "Failed" {
			return "Failed"
		}
		if phase != "Running" {
			allRunning = false
		}
	}

	if allRunning {
		return "Running"
	}
	return "Reconciling"
}

func shouldRequeueWorkspaceStatus(status workspacev1alpha1.WorkspaceStatus) bool {
	switch status.Phase {
	case "", "Pending", "Reconciling":
		return true
	default:
		return false
	}
}

func deploymentPhase(deployment *appsv1.Deployment) string {
	if deployment == nil {
		return "Pending"
	}

	if deployment.Spec.Replicas != nil && *deployment.Spec.Replicas == 0 {
		return "Disabled"
	}

	for _, condition := range deployment.Status.Conditions {
		if condition.Type == appsv1.DeploymentReplicaFailure &&
			condition.Status == corev1.ConditionTrue {
			return "Failed"
		}
	}

	desired := int32(1)
	if deployment.Spec.Replicas != nil {
		desired = *deployment.Spec.Replicas
	}
	if desired == 0 {
		return "Disabled"
	}
	if deployment.Status.ReadyReplicas >= desired {
		return "Running"
	}
	return "Reconciling"
}

func serviceInternalURL(service *corev1.Service, fallbackPort int32) string {
	if service == nil {
		return ""
	}

	port := fallbackPort
	if len(service.Spec.Ports) > 0 {
		port = service.Spec.Ports[0].Port
	}
	return fmt.Sprintf(
		"http://%s.%s.svc.cluster.local:%d",
		service.Name,
		service.Namespace,
		port,
	)
}

func serviceExternalURL(service *corev1.Service) string {
	if service == nil {
		return ""
	}

	switch service.Spec.Type {
	case corev1.ServiceTypeLoadBalancer:
		if len(service.Status.LoadBalancer.Ingress) > 0 {
			ingress := service.Status.LoadBalancer.Ingress[0]
			host := strings.TrimSpace(ingress.Hostname)
			if host == "" {
				host = strings.TrimSpace(ingress.IP)
			}
			if host == "" {
				return ""
			}

			port := int32(80)
			if len(service.Spec.Ports) > 0 {
				port = service.Spec.Ports[0].Port
			}
			return fmt.Sprintf("http://%s:%d", host, port)
		}
	}

	return ""
}

func (r *WorkspaceReconciler) componentExternalURL(component string, workspaceID string) string {
	var template string
	switch component {
	case runtimeComponent:
		template = r.PublicRouting.RuntimeHostPattern
	case browserComponent:
		template = r.PublicRouting.BrowserHostPattern
	case canvasComponent:
		template = r.PublicRouting.CanvasHostPattern
	default:
		return ""
	}

	url, err := r.PublicRouting.BuildURL(template, workspaceID)
	if err != nil {
		return ""
	}
	return url
}

func mostRecentTime(first *metav1.Time, second *metav1.Time) *metav1.Time {
	if first == nil && second == nil {
		return nil
	}
	if first == nil {
		return second.DeepCopy()
	}
	if second == nil {
		return first.DeepCopy()
	}
	if second.After(first.Time) {
		return second.DeepCopy()
	}
	return first.DeepCopy()
}

func mergeAllowedDomains(groups ...[]string) []string {
	merged := make([]string, 0)
	seen := make(map[string]struct{})

	for _, group := range groups {
		for _, domain := range group {
			normalized := strings.TrimSpace(domain)
			if normalized == "" {
				continue
			}
			if _, exists := seen[normalized]; exists {
				continue
			}
			seen[normalized] = struct{}{}
			merged = append(merged, normalized)
		}
	}

	return merged
}

func (r *WorkspaceReconciler) baseEgressRules(allowedDomains []string) []interface{} {
	rules := []interface{}{
		dnsEgressRule(),
	}

	for _, component := range requiredInternalServiceComponents() {
		rules = append(rules, internalServiceEgressRule(r.ConfigNamespace, component))
	}

	fqdnEntries := toFQDNEntries(allowedDomains)
	if len(fqdnEntries) > 0 {
		rules = append(rules, map[string]interface{}{
			"toFQDNs": fqdnEntries,
		})
	}

	return rules
}

func workspaceFirewallPolicyName(workspaceID string) string {
	return fmt.Sprintf("ws-%s-workspace-egress", workspaceID)
}

func browserFirewallPolicyName(workspaceID string) string {
	return fmt.Sprintf("ws-%s-browser-egress", workspaceID)
}

func newCiliumNetworkPolicy(namespace string, name string) *unstructured.Unstructured {
	policy := &unstructured.Unstructured{}
	policy.SetGroupVersionKind(ciliumNetworkPolicyGVK)
	policy.SetNamespace(namespace)
	policy.SetName(name)
	return policy
}

func toFQDNEntries(domains []string) []interface{} {
	entries := make([]interface{}, 0, len(domains))
	for _, domain := range domains {
		normalized := strings.TrimSpace(domain)
		if normalized == "" {
			continue
		}
		entries = append(entries, map[string]interface{}{
			"matchName": normalized,
		})
	}
	return entries
}

func dnsEgressRule() map[string]interface{} {
	return map[string]interface{}{
		"toEndpoints": []interface{}{
			map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"k8s:io.kubernetes.pod.namespace": "kube-system",
					"k8s:k8s-app":                     "kube-dns",
				},
			},
		},
		"toPorts": []interface{}{
			map[string]interface{}{
				"ports": []interface{}{
					map[string]interface{}{
						"port":     "53",
						"protocol": "UDP",
					},
					map[string]interface{}{
						"port":     "53",
						"protocol": "TCP",
					},
				},
			},
		},
	}
}

func internalServiceEgressRule(namespace string, component string) map[string]interface{} {
	matchLabels := map[string]interface{}{
		"k8s:app.kubernetes.io/part-of":   "aileron",
		"k8s:app.kubernetes.io/component": component,
	}
	if strings.TrimSpace(namespace) != "" {
		matchLabels["k8s:io.kubernetes.pod.namespace"] = namespace
	}

	return map[string]interface{}{
		"toEndpoints": []interface{}{
			map[string]interface{}{
				"matchLabels": matchLabels,
			},
		},
	}
}

func requiredInternalServiceComponents() []string {
	return []string{
		"workspace-manager",
		"postgres",
		"redis",
		"keycloak",
	}
}

type logrLike interface {
	Info(msg string, keysAndValues ...interface{})
	Error(err error, msg string, keysAndValues ...interface{})
}

func resourceName(component string, workspaceID string) string {
	return fmt.Sprintf("%s-%s", component, workspaceID)
}

func componentLabels(
	workspace *workspacev1alpha1.Workspace,
	component string,
	firewallGroup string,
) map[string]string {
	return map[string]string{
		"app.kubernetes.io/part-of": "aileron",
		"aileron.io/workspace-id":   workspace.Spec.WorkspaceID,
		"aileron.io/owner-id":       workspace.Spec.OwnerID,
		"aileron.io/component":      component,
		"aileron.io/firewall-group": firewallGroup,
	}
}

func runtimeVolumes(
	workspace *workspacev1alpha1.Workspace,
	knowledgeBasesPVCName string,
) []corev1.Volume {
	volumes := []corev1.Volume{
		{
			Name: "workspace-data",
			VolumeSource: corev1.VolumeSource{
				PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
					ClaimName: resourceName(pvcComponent, workspace.Spec.WorkspaceID),
				},
			},
		},
		{
			Name: runtimeCodexArg0VolumeName,
			VolumeSource: corev1.VolumeSource{
				EmptyDir: &corev1.EmptyDirVolumeSource{
					Medium:    corev1.StorageMediumMemory,
					SizeLimit: resourceQuantityPtr("16Mi"),
				},
			},
		},
	}
	if len(workspace.Spec.KnowledgeBases) > 0 {
		volumes = append(volumes, corev1.Volume{
			Name: "knowledge-bases",
			VolumeSource: corev1.VolumeSource{
				PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
					ClaimName: knowledgeBasesPVCName,
				},
			},
		})
	}
	return volumes
}

func (r *WorkspaceReconciler) knowledgeBasesPVCName() string {
	if r.KnowledgeBasesPVCName != "" {
		return r.KnowledgeBasesPVCName
	}
	return "knowledge-bases-pvc"
}

func runtimeVolumeMounts(workspace *workspacev1alpha1.Workspace) []corev1.VolumeMount {
	mounts := []corev1.VolumeMount{
		{
			Name:      "workspace-data",
			MountPath: workspaceMountPath(workspace),
		},
		{
			Name:      "workspace-data",
			MountPath: "/home/developer/.codex",
			SubPath:   ".system/codex-auth",
		},
		{
			Name:      "workspace-data",
			MountPath: "/home/developer/.codex-sessions",
			SubPath:   ".system/codex-sessions",
		},
		{
			Name:      runtimeCodexArg0VolumeName,
			MountPath: runtimeCodexArg0MountPath,
		},
	}
	for _, attachment := range workspace.Spec.KnowledgeBases {
		if attachment.KBID == "" || attachment.MountAlias == "" {
			continue
		}
		mounts = append(mounts, corev1.VolumeMount{
			Name:      "knowledge-bases",
			MountPath: "/knowledge/" + attachment.MountAlias,
			SubPath:   attachment.KBID,
			ReadOnly:  attachment.ReadOnly,
		})
	}
	return mounts
}

func resolveRuntimeImage(workspace *workspacev1alpha1.Workspace) string {
	if workspace.Spec.Runtime.Image != "" {
		return workspace.Spec.Runtime.Image
	}
	if workspace.Spec.Runtime.ImageKey != "" {
		return workspace.Spec.Runtime.ImageKey
	}
	return "ailerondocker/workspace-runtime:latest"
}

func resolveOptionalImage(specImage string, fallback string) string {
	if specImage != "" {
		return specImage
	}
	return fallback
}

func runtimeEnvVars(
	workspace *workspacev1alpha1.Workspace,
	reconciler *WorkspaceReconciler,
) []corev1.EnvVar {
	envVars := []corev1.EnvVar{
		{Name: "WORKSPACE_ID", Value: workspace.Spec.WorkspaceID},
		{Name: "WORKSPACE_PATH", Value: workspaceMountPath(workspace)},
		{Name: "PORT", Value: "3002"},
		{Name: "NODE_ENV", Value: "production"},
		{Name: "DEPLOYMENT_ENV", Value: "kubernetes"},
	}

	if reconciler.ManagerURL != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "MANAGER_URL", Value: reconciler.ManagerURL})
	}
	if reconciler.KeycloakURL != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "KEYCLOAK_SERVER_URL", Value: reconciler.KeycloakURL})
	}
	if reconciler.KeycloakRealm != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "KEYCLOAK_REALM", Value: reconciler.KeycloakRealm})
	}
	if reconciler.KeycloakClientID != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "KEYCLOAK_CLIENT_ID", Value: reconciler.KeycloakClientID})
	}
	if reconciler.KeycloakClientSecret != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "KEYCLOAK_CLIENT_SECRET", Value: reconciler.KeycloakClientSecret})
	}
	if reconciler.RedisURL != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "REDIS_URL", Value: reconciler.RedisURL})
	}
	if reconciler.DatabaseURL != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "DATABASE_URL", Value: reconciler.DatabaseURL})
	}
	if reconciler.InternalAPIToken != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "INTERNAL_API_TOKEN", Value: reconciler.InternalAPIToken})
	}
	if frontendPublicURL, err := reconciler.PublicRouting.BuildURL(
		reconciler.PublicRouting.FrontendHost,
		"",
	); err == nil && frontendPublicURL != "" {
		envVars = append(envVars, corev1.EnvVar{Name: "FRONTEND_PUBLIC_URL", Value: frontendPublicURL})
		// ALLOWED_ORIGINS must be a JSON array for pydantic-settings to parse correctly.
		allowedOriginsJSON := fmt.Sprintf(`[%q]`, frontendPublicURL)
		envVars = append(envVars, corev1.EnvVar{Name: "ALLOWED_ORIGINS", Value: allowedOriginsJSON})
	}

	return envVars
}

// browserEnvVars builds the env var list for the neko browser container.
// When TURN is configured, ICE lite is disabled and TURN servers are injected
// so that WebRTC media can traverse the k8s ingress layer.
//
// neko v3 distinguishes backend (server→TURN) from frontend (browser→TURN) ICE
// servers. In local K8s on Docker Desktop the two addresses differ:
//   - backend:  uses the node IP (e.g. 192.168.65.3) — reachable from pods
//   - frontend: uses 127.0.0.1  — Docker Desktop proxies NodePort through localhost
func browserEnvVars(reconciler *WorkspaceReconciler) []corev1.EnvVar {
	if reconciler.TURNServerURL == "" {
		return nil
	}

	// backend ICE servers: neko pod → TURN
	backendJSON := fmt.Sprintf(
		`[{"urls":[%q],"username":%q,"credential":%q}]`,
		reconciler.TURNServerURL,
		reconciler.TURNServerUsername,
		reconciler.TURNServerCredential,
	)

	// frontend ICE servers: browser → TURN (may use a different host)
	frontendURL := reconciler.TURNServerFrontendURL
	if frontendURL == "" {
		frontendURL = reconciler.TURNServerURL // fallback to same URL
	}
	frontendJSON := fmt.Sprintf(
		`[{"urls":[%q],"username":%q,"credential":%q}]`,
		frontendURL,
		reconciler.TURNServerUsername,
		reconciler.TURNServerCredential,
	)

	externalIP := reconciler.TURNServerExternalIP
	if externalIP == "" {
		externalIP = strings.TrimPrefix(frontendURL, "turn:")
		externalIP = strings.TrimPrefix(externalIP, "turns:")
		if idx := strings.LastIndex(externalIP, ":"); idx > 0 {
			externalIP = externalIP[:idx]
		}
	}

	return []corev1.EnvVar{
		// Disable ICE lite so the server uses the provided ICE servers
		{Name: "NEKO_WEBRTC_ICELITE", Value: "false"},
		// neko v3 reads iceservers from these two separate flags (backend=server-side, frontend=client-side)
		{Name: "NEKO_WEBRTC_ICESERVERS_BACKEND", Value: backendJSON},
		{Name: "NEKO_WEBRTC_ICESERVERS_FRONTEND", Value: frontendJSON},
		// Disable public-IP auto-fetch; TURN relay is the intended path in K8s
		{Name: "NEKO_WEBRTC_IP_RETRIEVAL_URL", Value: ""},
		{Name: "NEKO_WEBRTC_NAT1TO1", Value: externalIP},
	}
}

func toEnvVars(items []workspacev1alpha1.WorkspaceEnvVar) []corev1.EnvVar {
	envVars := make([]corev1.EnvVar, 0, len(items))
	for _, item := range items {
		envVars = append(envVars, corev1.EnvVar{
			Name:  item.Key,
			Value: item.Value,
		})
	}
	return envVars
}

func int32Ptr(v int32) *int32 {
	return &v
}

func int64Ptr(v int64) *int64 {
	return &v
}

func resourceQuantityPtr(v string) *resource.Quantity {
	quantity := resource.MustParse(v)
	return &quantity
}

func intstrFromInt32(v int32) intstr.IntOrString {
	return intstr.FromInt32(v)
}

func workspaceMountPath(workspace *workspacev1alpha1.Workspace) string {
	if workspace.Spec.WorkspacePath != "" {
		return workspace.Spec.WorkspacePath
	}
	return "/workspace"
}

func (r *WorkspaceReconciler) setOwnerReferenceIfSameNamespace(
	workspace *workspacev1alpha1.Workspace,
	obj client.Object,
) error {
	if workspace.Namespace != obj.GetNamespace() {
		return nil
	}
	return controllerutil.SetControllerReference(workspace, obj, r.Scheme)
}
