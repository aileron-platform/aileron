package controller

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"maps"
	"net"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/equality"
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
	"sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
	controllerdependencies "workspace-operator/internal/controllerdependencies"
)

const workspaceFinalizer = "platform.aileron.io/workspace-finalizer"

var immutableImageReferencePattern = regexp.MustCompile(
	`^[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$`,
)

const (
	runtimeInstanceAnnotation            = "aileron.io/runtime-instance-id"
	runtimeAccessRevisionAnnotation      = "aileron.io/runtime-access-revision"
	mountRevisionAnnotation              = "aileron.io/knowledge-base-mount-revision"
	componentRevisionAnnotation          = "aileron.io/component-revision"
	componentInstanceAnnotation          = "aileron.io/component-instance-id"
	browserCredentialRevisionAnnotation  = "aileron.io/browser-credential-revision"
	browserCredentialKeyIDAnnotation     = "aileron.io/browser-credential-key-id"
	browserCredentialAlgorithmAnnotation = "aileron.io/browser-credential-algorithm"
	firewallRevisionAnnotation           = "aileron.io/firewall-revision"
	firewallDeliveryIDAnnotation         = "platform.aileron.io/firewall-delivery-id"
	workspaceResourceAnnotation          = "aileron.io/workspace-resource"
)

const (
	runtimeComponent                = "workspace-runtime"
	browserComponent                = "workspace-browser"
	canvasComponent                 = "workspace-canvas"
	pvcComponent                    = "workspace-pvc"
	runtimeHomePVCComponent         = "workspace-runtime-home-pvc"
	workloadServiceAccountComponent = "workspace-workload"
	firewallDomainBytesLimit        = 16 * 1024
)

const (
	workspaceIDLabel = "aileron.io/workspace-id"
	componentLabel   = "aileron.io/component"
)

var (
	canonicalUUIDPattern    = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)
	mountAliasPattern       = regexp.MustCompile(`^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$`)
	firewallDomainPattern   = regexp.MustCompile(`^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$`)
	workspaceEnvNamePattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	reservedMountAliases    = map[string]struct{}{
		"system": {}, "runtime": {}, "workspace": {}, "tmp": {}, "lost-found": {},
	}
	fixedWorkspaceEnvKeys = map[string]struct{}{
		"HOME":              {},
		"PATH":              {},
		"CODEX_HOME":        {},
		"NPM_CONFIG_CACHE":  {},
		"NPM_CONFIG_PREFIX": {},
		"UV_CACHE_DIR":      {},
		"XDG_CONFIG_HOME":   {},
		"XDG_DATA_HOME":     {},
		"XDG_STATE_HOME":    {},
	}
)

const (
	runtimeHomeVolumeName          = "runtime-home"
	runtimeHomeMountPath           = "/home/developer"
	runtimeHomeInitializerName     = "runtime-home-initializer"
	runtimeSetupVolumeName         = "runtime-setup"
	runtimeSetupSecretKey          = "custom-setup.sh"
	runtimeSetupMountPath          = "/scripts/custom-setup.sh"
	runtimeSecretsVolumeName       = "runtime-secrets"
	runtimeSecretsMountPath        = "/etc/aileron/runtime-secrets"
	runtimeStateDatabaseSecretKey  = "state-database-url"
	runtimeControlTokenSecretKey   = "runtime-control-token"
	runtimeCodexTmpVolumeName      = "codex-tmp"
	runtimeCodexTmpMountPath       = runtimeHomeMountPath + "/.codex/tmp"
	runtimeAssertionJWKSVolumeName = "runtime-assertion-public-jwks"
	runtimeAssertionJWKSSecretKey  = "jwks.json"
	runtimeAssertionJWKSMountPath  = "/etc/aileron/runtime-assertions"
	runtimeAssertionJWKSFilePath   = runtimeAssertionJWKSMountPath + "/" + runtimeAssertionJWKSSecretKey
	browserCredentialsVolumeName   = "browser-credentials"
	browserCredentialsMountPath    = "/run/secrets/browser-credentials"
	browserTURNVolumeName          = "browser-turn-ice"
	browserTURNMountPath           = "/run/secrets/browser-turn"
	turnRESTVolumeName             = "turn-rest"
	turnRESTMountPath              = "/run/secrets/turn-rest"
)

const browserSecretFileEntrypoint = `set -eu
fail() {
  printf '%s\n' 'BROWSER_CREDENTIAL_INVALID' >&2
  exit 78
}
read_secret() {
  secret_file="$1"
  [ -r "${secret_file}" ] || fail
  secret_value="$(cat "${secret_file}")"
  [ -n "${secret_value}" ] || fail
  case "${secret_value}" in
    *[!A-Za-z0-9_-]*) fail ;;
  esac
  [ "${#secret_value}" -eq 43 ] || fail
  printf '%s' "${secret_value}"
}
browser_user_password="$(read_secret "${NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE:?}")"
browser_admin_password="$(read_secret "${NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE:?}")"
[ "${browser_user_password}" != "${browser_admin_password}" ] || fail

state_dir=/tmp/aileron-browser
generated_config="${state_dir}/neko.generated.yaml"
generated_supervisor="${state_dir}/supervisord.generated.conf"
umask 0077
mkdir -p "${state_dir}"
cp /etc/neko/neko.kubernetes.yaml "${generated_config}"
cat >>"${generated_config}" <<EOF

member:
  provider: multiuser
  multiuser:
    user_password: "${browser_user_password}"
    admin_password: "${browser_admin_password}"
EOF

if [ -n "${NEKO_WEBRTC_ICESERVERS_BACKEND_FILE:-}" ] || [ -n "${NEKO_WEBRTC_ICESERVERS_FRONTEND_FILE:-}" ]; then
  [ -n "${NEKO_WEBRTC_ICESERVERS_BACKEND_FILE:-}" ] && [ -n "${NEKO_WEBRTC_ICESERVERS_FRONTEND_FILE:-}" ] || fail
  [ -r "${NEKO_WEBRTC_ICESERVERS_BACKEND_FILE}" ] && [ -r "${NEKO_WEBRTC_ICESERVERS_FRONTEND_FILE}" ] || fail
  backend_ice_servers="$(cat "${NEKO_WEBRTC_ICESERVERS_BACKEND_FILE}")"
  frontend_ice_servers="$(cat "${NEKO_WEBRTC_ICESERVERS_FRONTEND_FILE}")"
  [ "$(printf '%s' "${backend_ice_servers}" | wc -l | tr -d ' ')" -eq 0 ] || fail
  [ "$(printf '%s' "${frontend_ice_servers}" | wc -l | tr -d ' ')" -eq 0 ] || fail
  case "${backend_ice_servers}" in \[*\]) ;; *) fail ;; esac
  case "${frontend_ice_servers}" in \[*\]) ;; *) fail ;; esac
  cat >>"${generated_config}" <<EOF

webrtc:
  iceservers:
    backend: ${backend_ice_servers}
    frontend: ${frontend_ice_servers}
EOF
fi
chmod 0600 "${generated_config}"
sed "s|--config /etc/neko/neko.kubernetes.yaml|--config ${generated_config}|" \
  /etc/neko/supervisord.kubernetes.conf >"${generated_supervisor}"
chmod 0600 "${generated_supervisor}"

export NEKO_MEMBER_MULTIUSER_USER_PASSWORD="$(printf '%043d' 0)"
export NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD="$(printf '%043d' 1)"
unset browser_user_password browser_admin_password backend_ice_servers frontend_ice_servers
exec /usr/local/bin/aileron-browser-kubernetes-entrypoint \
  /usr/bin/env -u NEKO_MEMBER_MULTIUSER_USER_PASSWORD \
    -u NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD \
    /usr/bin/supervisord -c "${generated_supervisor}"
`

var ciliumNetworkPolicyGVK = schema.GroupVersionKind{
	Group:   "cilium.io",
	Version: "v2",
	Kind:    "CiliumNetworkPolicy",
}

var (
	ciliumNetworkPolicyListGVK = schema.GroupVersionKind{
		Group:   "cilium.io",
		Version: "v2",
		Kind:    "CiliumNetworkPolicyList",
	}
	ciliumEndpointGVK = schema.GroupVersionKind{
		Group:   "cilium.io",
		Version: "v2",
		Kind:    "CiliumEndpoint",
	}
	ciliumEndpointListGVK = schema.GroupVersionKind{
		Group:   "cilium.io",
		Version: "v2",
		Kind:    "CiliumEndpointList",
	}
)

type WorkspaceReconciler struct {
	client.Client
	APIReader                 client.Reader
	Scheme                    *runtime.Scheme
	ConfigNamespace           string
	CiliumEnabled             bool
	FirewallAttestationMaxAge time.Duration
	PlatformPublicOrigin      string
	ManagerURL                string
	// TURN configuration for the Browser component.
	TURNProfile                    *TURNReachabilityProfile
	TURNICEServersSecretName       string
	TURNBackendSecretKey           string
	TURNFrontendSecretKey          string
	TURNCredentialRevision         string
	BrowserConnectivityProbeImage  string
	ConnectivityEvidenceGatewayURL string
	ConnectivityInstallationID     string
	ConnectivityEvidenceReader     BrowserConnectivityEvidenceReader
	KnowledgeBasesPVCName          string
	PlatformStorageGID             *int64
	WorkspaceStorageClass          string
	RuntimeHomeStorageClass        string
	RuntimeHomeAccessMode          corev1.PersistentVolumeAccessMode
	WorkloadImagePullSecrets       []string
	BrowserCredentialKeyring       BrowserCredentialDeriver
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

	workspaceNamespace, err := canonicalWorkspaceNamespace(&workspace)
	if err != nil {
		logger.Error(err, "invalid workspace namespace contract")
		return ctrl.Result{}, err
	}

	if controllerutil.AddFinalizer(&workspace, workspaceFinalizer) {
		if err := r.Update(ctx, &workspace); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info("added workspace finalizer")
		return ctrl.Result{Requeue: true}, nil
	}
	originalStatus := workspace.DeepCopyObject().(*workspacev1alpha1.Workspace).Status

	if err := validateKnowledgeBaseAttachments(workspace.Spec.KnowledgeBases); err != nil {
		logger.Error(err, "invalid knowledge base attachment set")
		return ctrl.Result{}, err
	}
	if err := validateWorkspaceEnvVars(workspace.Spec.EnvVars); err != nil {
		logger.Error(err, "invalid workspace environment variables")
		return ctrl.Result{}, err
	}
	if r.CiliumEnabled {
		if err := validateFirewallSpec(workspace.Spec.Firewall); err != nil {
			logger.Error(err, "invalid workspace firewall contract")
			return ctrl.Result{}, err
		}
	}
	if workspace.Spec.Runtime.RuntimeSecretName != runtimeSecretName(workspace.Spec.WorkspaceID) {
		return ctrl.Result{}, fmt.Errorf("Runtime Secret name does not match workspace identity")
	}
	if err := validateLifecycleSpec(&workspace); err != nil {
		logger.Error(err, "invalid workspace lifecycle contract")
		return ctrl.Result{}, err
	}
	imageErrorCodes := componentImageErrorCodes(&workspace)

	if err := r.reconcileWorkloadServiceAccount(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to reconcile workspace workload service account")
		return ctrl.Result{}, err
	}
	storageReconciler := WorkspaceStorageReconciler{
		Client:                  r.Client,
		APIReader:               r.APIReader,
		Scheme:                  r.Scheme,
		WorkspaceStorageClass:   r.WorkspaceStorageClass,
		RuntimeHomeStorageClass: r.RuntimeHomeStorageClass,
		RuntimeHomeAccessMode:   r.RuntimeHomeAccessMode,
	}
	if err := storageReconciler.Reconcile(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to reconcile workspace storage")
		return ctrl.Result{}, err
	}
	requeueForFence := false
	runtimeFenced := false
	if _, invalid := imageErrorCodes[runtimeComponent]; invalid {
		if err := r.deleteComponentDeployment(
			ctx, &workspace, workspaceNamespace, runtimeComponent,
		); err != nil {
			return ctrl.Result{}, err
		}
	} else {
		runtimeFenced, err = r.fenceComponentRevision(
			ctx,
			&workspace,
			workspaceNamespace,
			runtimeComponent,
		)
		if err != nil {
			logger.Error(err, "unable to fence runtime revision")
			return ctrl.Result{}, err
		}
		requeueForFence = requeueForFence || runtimeFenced
		if !runtimeFenced {
			err = r.reconcileRuntimeDeployment(ctx, &workspace, workspaceNamespace)
		}
		if err != nil {
			logger.Error(err, "unable to reconcile runtime deployment")
			return ctrl.Result{}, err
		}
	}
	if err := r.reconcileRuntimeService(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to reconcile runtime service")
		return ctrl.Result{}, err
	}
	browserFenced := false
	if _, invalid := imageErrorCodes[browserComponent]; invalid {
		if err := r.deleteComponentDeployment(
			ctx, &workspace, workspaceNamespace, browserComponent,
		); err != nil {
			return ctrl.Result{}, err
		}
	} else {
		browserFenced, err = r.fenceComponentRevision(
			ctx,
			&workspace,
			workspaceNamespace,
			browserComponent,
		)
		if err != nil {
			logger.Error(err, "unable to fence browser revision")
			return ctrl.Result{}, err
		}
		requeueForFence = requeueForFence || browserFenced
	}
	browserCredentialErrorCode := ""
	if _, invalid := imageErrorCodes[browserComponent]; !invalid {
		err = r.reconcileBrowserCredentialSecret(
			ctx,
			&workspace,
			workspaceNamespace,
		)
	}
	if err != nil {
		logger.Error(err, "unable to reconcile browser credential")
		browserCredentialErrorCode = err.Error()
		if deleteErr := r.Delete(
			ctx,
			&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{
				Name:      resourceName(browserComponent, workspace.Spec.WorkspaceID),
				Namespace: workspaceNamespace,
			}},
		); deleteErr != nil && !apierrors.IsNotFound(deleteErr) {
			return ctrl.Result{}, deleteErr
		}
		err = nil
	}
	_, browserImageInvalid := imageErrorCodes[browserComponent]
	if browserCredentialErrorCode == "" && !browserFenced && !browserImageInvalid {
		err = r.reconcileBrowserDeployment(ctx, &workspace, workspaceNamespace)
	}
	if err != nil {
		logger.Error(err, "unable to reconcile browser deployment")
		return ctrl.Result{}, err
	}
	if err := r.reconcileBrowserService(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to reconcile browser service")
		return ctrl.Result{}, err
	}
	canvasFenced := false
	if _, invalid := imageErrorCodes[canvasComponent]; invalid {
		if err := r.deleteComponentDeployment(
			ctx, &workspace, workspaceNamespace, canvasComponent,
		); err != nil {
			return ctrl.Result{}, err
		}
	} else {
		canvasFenced, err = r.fenceComponentRevision(
			ctx,
			&workspace,
			workspaceNamespace,
			canvasComponent,
		)
		if err != nil {
			logger.Error(err, "unable to fence canvas revision")
			return ctrl.Result{}, err
		}
		requeueForFence = requeueForFence || canvasFenced
		if !canvasFenced {
			err = r.reconcileCanvasDeployment(ctx, &workspace, workspaceNamespace)
		}
		if err != nil {
			logger.Error(err, "unable to reconcile canvas deployment")
			return ctrl.Result{}, err
		}
	}
	if err := r.reconcileCanvasService(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to reconcile canvas service")
		return ctrl.Result{}, err
	}

	workspace.Status.ObservedGeneration = workspace.Generation
	workspace.Status.TargetNamespace = workspaceNamespace
	var (
		workspaceFirewallPolicy   *unstructured.Unstructured
		runtimePeerFirewallPolicy *unstructured.Unstructured
		browserFirewallPolicy     *unstructured.Unstructured
	)
	firewallEvaluation := firewallPolicyApplied("FirewallPolicyDisabled")
	if r.CiliumEnabled {
		workspaceFirewallPolicy, err = r.reconcileWorkspaceFirewallPolicy(
			ctx,
			&workspace,
			workspaceNamespace,
			workspace.Spec.Firewall.Workspace,
		)
		if err != nil {
			logger.Error(err, "unable to reconcile workspace firewall policy")
			r.persistFirewallError(ctx, &workspace)
			return ctrl.Result{}, err
		}
		runtimePeerFirewallPolicy, err = r.reconcileRuntimePeerFirewallPolicy(
			ctx,
			&workspace,
			workspaceNamespace,
		)
		if err != nil {
			logger.Error(err, "unable to reconcile runtime peer firewall policy")
			r.persistFirewallError(ctx, &workspace)
			return ctrl.Result{}, err
		}
		browserFirewallPolicy, err = r.reconcileBrowserFirewallPolicy(
			ctx,
			&workspace,
			workspaceNamespace,
			workspace.Spec.Firewall.Browser,
		)
		if err != nil {
			logger.Error(err, "unable to reconcile browser firewall policy")
			r.persistFirewallError(ctx, &workspace)
			return ctrl.Result{}, err
		}
		firewallEvaluation = r.evaluateFirewallPolicyAttestations(
			ctx,
			&workspace,
			workspaceNamespace,
			time.Now(),
			workspaceFirewallPolicy,
			runtimePeerFirewallPolicy,
			browserFirewallPolicy,
		)
		firewallEvaluation = expireFirewallPolicyApplying(
			workspace.Status.Firewall,
			firewallEvaluation,
			workspace.Spec.Firewall.Revision,
			workspaceFirewallDeliveryID(&workspace),
			time.Now(),
		)
		if firewallEvaluation.Detail != "" {
			logger.Info(
				"firewall policy enforcement is not converged",
				"reason", firewallEvaluation.Reason,
				"errorCode", firewallEvaluation.ErrorCode,
				"detail", firewallEvaluation.Detail,
			)
		}
	} else {
		if err := r.deleteFirewallPolicies(ctx, &workspace, workspaceNamespace); err != nil {
			logger.Error(err, "unable to cleanup disabled firewall policies")
			return ctrl.Result{}, err
		}
	}
	r.setFirewallStatus(
		&workspace,
		firewallEvaluation,
		workspaceFirewallPolicy,
		runtimePeerFirewallPolicy,
		browserFirewallPolicy,
	)
	if err := r.populateWorkspaceStatus(ctx, &workspace, workspaceNamespace); err != nil {
		logger.Error(err, "unable to populate workspace status")
		return ctrl.Result{}, err
	}
	if browserCredentialErrorCode != "" {
		workspace.Status.Components.Browser = workspacev1alpha1.WorkspaceComponentStatus{
			Phase:     "Error",
			Reason:    "BrowserCredentialUnavailable",
			ErrorCode: browserCredentialErrorCode,
		}
		workspace.Status.Phase = calculateWorkspacePhase(
			workspace.Spec,
			workspace.Status.Components,
		)
	}
	for component, errorCode := range imageErrorCodes {
		status := workspacev1alpha1.WorkspaceComponentStatus{
			Phase:     "Error",
			Reason:    errorCode,
			ErrorCode: errorCode,
		}
		switch component {
		case runtimeComponent:
			workspace.Status.Components.Runtime = status
		case browserComponent:
			workspace.Status.Components.Browser = status
		case canvasComponent:
			workspace.Status.Components.Canvas = status
		}
	}
	if len(imageErrorCodes) > 0 {
		workspace.Status.Phase = calculateWorkspacePhase(
			workspace.Spec,
			workspace.Status.Components,
		)
	}

	if !equality.Semantic.DeepEqual(originalStatus, workspace.Status) {
		if err := r.Status().Update(ctx, &workspace); err != nil {
			logger.Error(err, "unable to update workspace status")
			return ctrl.Result{}, err
		}
	}

	logger.Info(
		"reconciled workspace placeholder state",
		"workspaceNamespace", workspaceNamespace,
		"workspaceId", workspace.Spec.WorkspaceID,
	)
	if requeueForFence {
		return ctrl.Result{RequeueAfter: time.Second}, nil
	}
	requeueAfter := firewallEvaluationRequeueAfter(
		r.CiliumEnabled,
		firewallEvaluation,
		r.firewallAttestationMaxAge(),
	)
	if shouldRequeueWorkspaceStatus(workspace.Status) &&
		(requeueAfter == 0 || requeueAfter > 5*time.Second) {
		requeueAfter = 5 * time.Second
	}
	if r.ConnectivityEvidenceReader != nil &&
		workspace.Spec.Browser.Enabled &&
		workspace.Spec.Browser.DesiredState == "Running" &&
		(requeueAfter == 0 || requeueAfter > 30*time.Second) {
		requeueAfter = 30 * time.Second
	}
	if requeueAfter > 0 {
		return ctrl.Result{RequeueAfter: requeueAfter}, nil
	}
	return ctrl.Result{}, nil
}

func firewallEvaluationRequeueAfter(
	ciliumEnabled bool,
	evaluation firewallPolicyEvaluation,
	attestationMaxAge time.Duration,
) time.Duration {
	if evaluation.RequiresRequeue() {
		return 5 * time.Second
	}
	if ciliumEnabled {
		return attestationMaxAge / 2
	}
	return 0
}

func canonicalWorkspaceNamespace(workspace *workspacev1alpha1.Workspace) (string, error) {
	workspaceNamespace := workspace.Namespace
	declaredNamespace := workspace.Spec.TargetNamespace
	if declaredNamespace != "" && declaredNamespace != workspaceNamespace {
		return "", fmt.Errorf(
			"Workspace target namespace %q must match metadata namespace %q",
			declaredNamespace,
			workspaceNamespace,
		)
	}
	return workspaceNamespace, nil
}

func validateKnowledgeBaseAttachments(
	attachments []workspacev1alpha1.WorkspaceKnowledgeBaseAttachment,
) error {
	aliases := make(map[string]struct{}, len(attachments))
	knowledgeBases := make(map[string]struct{}, len(attachments))
	for _, attachment := range attachments {
		if !canonicalUUIDPattern.MatchString(attachment.KBID) {
			return fmt.Errorf("knowledge base identifier is not canonical")
		}
		if !mountAliasPattern.MatchString(attachment.Alias) {
			return fmt.Errorf("knowledge base mount alias is not canonical")
		}
		if _, reserved := reservedMountAliases[attachment.Alias]; reserved {
			return fmt.Errorf("knowledge base mount alias is reserved")
		}
		if _, exists := aliases[attachment.Alias]; exists {
			return fmt.Errorf("knowledge base mount alias is duplicated")
		}
		if _, exists := knowledgeBases[attachment.KBID]; exists {
			return fmt.Errorf("knowledge base attachment is duplicated")
		}
		aliases[attachment.Alias] = struct{}{}
		knowledgeBases[attachment.KBID] = struct{}{}
	}
	return nil
}

func validateWorkspaceEnvVars(items []workspacev1alpha1.WorkspaceEnvVar) error {
	seen := make(map[string]struct{}, len(items))
	for _, item := range items {
		key := item.Key
		if !workspaceEnvNamePattern.MatchString(key) {
			return fmt.Errorf("workspace environment variable name %q is invalid", key)
		}
		_, fixed := fixedWorkspaceEnvKeys[key]
		if fixed || strings.HasPrefix(key, "AILERON_") {
			return fmt.Errorf("workspace environment variable %q is reserved", key)
		}
		if _, exists := seen[key]; exists {
			return fmt.Errorf("workspace environment variable %q is duplicated", key)
		}
		seen[key] = struct{}{}
	}
	return nil
}

func validateFirewallSpec(spec workspacev1alpha1.WorkspaceFirewallSpec) error {
	if spec.Revision < 0 {
		return fmt.Errorf("workspace firewall revision must not be negative")
	}
	for name, group := range map[string]workspacev1alpha1.WorkspaceFirewallGroupSpec{
		"workspace": spec.Workspace,
		"browser":   spec.Browser,
	} {
		if err := validateFirewallGroup(group); err != nil {
			return fmt.Errorf("%s firewall group is invalid: %w", name, err)
		}
	}
	return nil
}

func validateFirewallGroup(
	group workspacev1alpha1.WorkspaceFirewallGroupSpec,
) error {
	switch group.EgressMode {
	case workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
		workspacev1alpha1.WorkspaceFirewallEgressModeUnrestricted:
		if len(group.AllowedDomains) > 0 {
			return fmt.Errorf("allowed domains require allowlist egress mode")
		}
		return nil
	case workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist:
		if len(group.AllowedDomains) == 0 {
			return fmt.Errorf("allowlist egress mode requires at least one allowed domain")
		}
	default:
		return fmt.Errorf("egress mode must be blocked, allowlist, or unrestricted")
	}
	if len(group.AllowedDomains) > 128 {
		return fmt.Errorf("allowed domain count exceeds 128")
	}
	seen := make(map[string]struct{}, len(group.AllowedDomains))
	totalBytes := 0
	for _, domain := range group.AllowedDomains {
		if len(domain) > 253 ||
			net.ParseIP(domain) != nil ||
			!firewallDomainPattern.MatchString(domain) {
			return fmt.Errorf("allowed domain %q is not a canonical exact hostname", domain)
		}
		if _, exists := seen[domain]; exists {
			return fmt.Errorf("allowed domain %q is duplicated", domain)
		}
		seen[domain] = struct{}{}
		totalBytes += len(domain)
	}
	if totalBytes > firewallDomainBytesLimit {
		return fmt.Errorf("allowed domains exceed %d bytes", firewallDomainBytesLimit)
	}
	return nil
}

func validateLifecycleSpec(workspace *workspacev1alpha1.Workspace) error {
	if !canonicalUUIDPattern.MatchString(workspace.Spec.Runtime.InstanceID) {
		return fmt.Errorf("runtime instance identifier is not canonical")
	}
	if workspace.Spec.Bootstrap.Revision < 1 ||
		workspace.Spec.Runtime.Revision < 1 ||
		workspace.Spec.Browser.Revision < 1 ||
		workspace.Spec.Canvas.Revision < 1 {
		return fmt.Errorf("workspace lifecycle revisions must start at one")
	}
	for component, desiredState := range map[string]string{
		runtimeComponent: workspace.Spec.Runtime.DesiredState,
		browserComponent: workspace.Spec.Browser.DesiredState,
		canvasComponent:  workspace.Spec.Canvas.DesiredState,
	} {
		if desiredState != "Running" && desiredState != "Stopped" {
			return fmt.Errorf("%s desired state is invalid", component)
		}
	}
	return nil
}

// fenceComponentRevision scales only the stale component to zero and waits for
// positive Pod absence before applying its new template revision.
func (r *WorkspaceReconciler) fenceComponentRevision(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
) (bool, error) {
	deployment := &appsv1.Deployment{}
	key := client.ObjectKey{
		Name:      resourceName(component, workspace.Spec.WorkspaceID),
		Namespace: namespace,
	}
	if err := r.Get(ctx, key, deployment); err != nil {
		if apierrors.IsNotFound(err) {
			return false, nil
		}
		return false, err
	}
	if deploymentMatchesDesiredRevision(deployment, workspace, component) {
		return false, nil
	}
	if deployment.Spec.Replicas == nil || *deployment.Spec.Replicas != 0 {
		deployment.Spec.Replicas = int32Ptr(0)
		deployment.Spec.Strategy.Type = appsv1.RecreateDeploymentStrategyType
		deployment.Spec.Strategy.RollingUpdate = nil
		if err := r.Update(ctx, deployment); err != nil {
			return false, err
		}
	}

	pods := &corev1.PodList{}
	if err := r.List(
		ctx,
		pods,
		client.InNamespace(namespace),
		client.MatchingLabels{
			workspaceIDLabel: workspace.Spec.WorkspaceID,
			componentLabel:   component,
		},
	); err != nil {
		return false, err
	}
	if len(pods.Items) > 0 {
		return true, nil
	}
	return false, nil
}

func deploymentMatchesDesiredRevision(
	deployment *appsv1.Deployment,
	workspace *workspacev1alpha1.Workspace,
	component string,
) bool {
	annotations := deployment.Spec.Template.Annotations
	if annotations[componentRevisionAnnotation] != fmt.Sprintf(
		"%d",
		componentRevision(workspace, component),
	) {
		return false
	}
	if annotations[componentInstanceAnnotation] != componentInstanceID(
		workspace,
		component,
	) {
		return false
	}
	if component == runtimeComponent {
		return annotations[runtimeInstanceAnnotation] == workspace.Spec.Runtime.InstanceID &&
			annotations[runtimeAccessRevisionAnnotation] == fmt.Sprintf(
				"%d",
				workspace.Spec.Runtime.AccessRevision,
			) &&
			annotations[mountRevisionAnnotation] == fmt.Sprintf(
				"%d",
				workspace.Spec.Runtime.MountRevision,
			)
	}
	if component == browserComponent {
		return annotations[browserCredentialRevisionAnnotation] == fmt.Sprintf(
			"%d",
			workspace.Spec.Browser.CredentialRevision,
		) &&
			annotations[browserCredentialKeyIDAnnotation] == workspace.Spec.Browser.CredentialKeyID &&
			annotations[browserCredentialAlgorithmAnnotation] == workspace.Spec.Browser.CredentialAlgorithm
	}
	_, hasRuntimeInstance := annotations[runtimeInstanceAnnotation]
	_, hasRuntimeAccess := annotations[runtimeAccessRevisionAnnotation]
	_, hasMountRevision := annotations[mountRevisionAnnotation]
	return !hasRuntimeInstance && !hasRuntimeAccess && !hasMountRevision
}

func componentImageErrorCodes(
	workspace *workspacev1alpha1.Workspace,
) map[string]string {
	images := map[string]struct {
		image     string
		errorCode string
	}{
		runtimeComponent: {
			image: workspace.Spec.Runtime.Image, errorCode: "RUNTIME_IMAGE_REFERENCE_INVALID",
		},
		browserComponent: {
			image: workspace.Spec.Browser.Image, errorCode: "BROWSER_IMAGE_REFERENCE_INVALID",
		},
		canvasComponent: {
			image: workspace.Spec.Canvas.Image, errorCode: "CANVAS_IMAGE_REFERENCE_INVALID",
		},
	}
	errorCodes := map[string]string{}
	for component, contract := range images {
		if !immutableImageReferencePattern.MatchString(contract.image) {
			errorCodes[component] = contract.errorCode
		}
	}
	return errorCodes
}

func (r *WorkspaceReconciler) deleteComponentDeployment(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
) error {
	deployment := &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{
		Name:      resourceName(component, workspace.Spec.WorkspaceID),
		Namespace: namespace,
	}}
	if err := r.Delete(ctx, deployment); err != nil && !apierrors.IsNotFound(err) {
		return err
	}
	return nil
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
		stableLabels := componentLabels(workspace, runtimeComponent, "workspace")
		runtimeLabels := maps.Clone(stableLabels)
		runtimeLabels[runtimeInstanceAnnotation] = workspace.Spec.Runtime.InstanceID
		deployment.Labels = stableLabels
		deployment.Annotations = mergeComponentAnnotations(
			deployment.Annotations,
			workspace,
			runtimeComponent,
		)
		if err := r.setWorkspaceControllerReference(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: stableLabels}
		deployment.Spec.Replicas = int32Ptr(componentReplicaCount(
			workspace.Spec.Runtime.DesiredState,
			true,
		))
		deployment.Spec.Strategy.Type = appsv1.RecreateDeploymentStrategyType
		deployment.Spec.Strategy.RollingUpdate = nil
		deployment.Spec.Template.ObjectMeta.Labels = runtimeLabels
		deployment.Spec.Template.ObjectMeta.Annotations = mergeComponentAnnotations(
			deployment.Spec.Template.ObjectMeta.Annotations,
			workspace,
			runtimeComponent,
		)
		deployment.Spec.Template.Spec.TerminationGracePeriodSeconds = int64Ptr(120)
		deployment.Spec.Template.Spec.ServiceAccountName = workloadServiceAccountName(workspace)
		deployment.Spec.Template.Spec.AutomountServiceAccountToken = boolPtr(false)
		deployment.Spec.Template.Spec.SecurityContext = restrictedPodSecurityContext(r.PlatformStorageGID)
		deployment.Spec.Template.Spec.Volumes = runtimeVolumes(
			workspace,
			r.knowledgeBasesPVCName(),
		)
		deployment.Spec.Template.Spec.InitContainers = []corev1.Container{
			runtimeHomeInitializer(workspace),
		}
		container := corev1.Container{
			Name:                     "runtime",
			Image:                    workspace.Spec.Runtime.Image,
			ImagePullPolicy:          corev1.PullIfNotPresent,
			TerminationMessagePath:   corev1.TerminationMessagePathDefault,
			TerminationMessagePolicy: corev1.TerminationMessageReadFile,
			Ports: []corev1.ContainerPort{
				{Name: "http", ContainerPort: 3002, Protocol: corev1.ProtocolTCP},
				{Name: "terminal", ContainerPort: 3004, Protocol: corev1.ProtocolTCP},
			},
			Env:             append(runtimeEnvVars(workspace, r), toEnvVars(workspace.Spec.EnvVars)...),
			VolumeMounts:    runtimeVolumeMounts(workspace),
			StartupProbe:    runtimeHealthProbe(5, 2, 60),
			ReadinessProbe:  runtimeAndTerminalReadinessProbe(),
			LivenessProbe:   runtimeHealthProbe(10, 2, 3),
			SecurityContext: restrictedContainerSecurityContext(),
		}
		if workspace.Spec.Runtime.Resources != nil {
			container.Resources = *workspace.Spec.Runtime.Resources
		}
		deployment.Spec.Template.Spec.Containers = []corev1.Container{container}
		return nil
	})
	return err
}

func runtimeAndTerminalReadinessProbe() *corev1.Probe {
	return &corev1.Probe{
		ProbeHandler: corev1.ProbeHandler{Exec: &corev1.ExecAction{Command: []string{
			"python3",
			"-c",
			`import json, urllib.request; data = json.load(urllib.request.urlopen("http://127.0.0.1:3002/health", timeout=1)); raise SystemExit(0 if data.get("status") == "healthy" and data.get("terminal_service", {}).get("status") == "ready" else 1)`,
		}}},
		PeriodSeconds:    5,
		TimeoutSeconds:   2,
		FailureThreshold: 3,
		SuccessThreshold: 1,
	}
}

func runtimeHealthProbe(periodSeconds, timeoutSeconds, failureThreshold int32) *corev1.Probe {
	return httpHealthProbe("http", "/health", periodSeconds, timeoutSeconds, failureThreshold)
}

func httpHealthProbe(
	port string,
	path string,
	periodSeconds int32,
	timeoutSeconds int32,
	failureThreshold int32,
) *corev1.Probe {
	return &corev1.Probe{
		ProbeHandler: corev1.ProbeHandler{
			HTTPGet: &corev1.HTTPGetAction{
				Path:   path,
				Port:   intstr.FromString(port),
				Scheme: corev1.URISchemeHTTP,
			},
		},
		PeriodSeconds:    periodSeconds,
		TimeoutSeconds:   timeoutSeconds,
		FailureThreshold: failureThreshold,
		SuccessThreshold: 1,
	}
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
		selector := maps.Clone(labels)
		selector[runtimeInstanceAnnotation] = workspace.Spec.Runtime.InstanceID
		svc.Labels = labels
		if err := r.setWorkspaceControllerReference(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = selector
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "http", Port: 3002, TargetPort: intstrFromInt32(3002), Protocol: corev1.ProtocolTCP},
			{Name: "terminal", Port: 3004, TargetPort: intstrFromInt32(3004), Protocol: corev1.ProtocolTCP},
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
		if workspace.Spec.Browser.Enabled &&
			bootstrapSucceeded(workspace) &&
			workspace.Spec.Browser.DesiredState == "Running" {
			replicas = 1
		}
		deployment.Labels = labels
		deployment.Annotations = mergeComponentAnnotations(
			deployment.Annotations,
			workspace,
			browserComponent,
		)
		if err := r.setWorkspaceControllerReference(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		deployment.Spec.Replicas = &replicas
		deployment.Spec.Strategy.Type = appsv1.RecreateDeploymentStrategyType
		deployment.Spec.Strategy.RollingUpdate = nil
		deployment.Spec.Template.ObjectMeta.Labels = labels
		deployment.Spec.Template.ObjectMeta.Annotations = mergeComponentAnnotations(
			deployment.Spec.Template.ObjectMeta.Annotations,
			workspace,
			browserComponent,
		)
		deployment.Spec.Template.Spec.ServiceAccountName = workloadServiceAccountName(workspace)
		deployment.Spec.Template.Spec.AutomountServiceAccountToken = boolPtr(false)
		deployment.Spec.Template.Spec.SecurityContext = restrictedPodSecurityContext(r.PlatformStorageGID)
		sharedMemorySize := resource.MustParse("512Mi")
		deployment.Spec.Template.Spec.Volumes = []corev1.Volume{
			{
				Name: "workspace-data",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
						ClaimName: resourceName(pvcComponent, workspace.Spec.WorkspaceID),
					},
				},
			},
			{
				Name:         "tmp",
				VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}},
			},
			{
				Name: "shared-memory",
				VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{
					Medium:    corev1.StorageMediumMemory,
					SizeLimit: &sharedMemorySize,
				}},
			},
			{
				Name: browserCredentialsVolumeName,
				VolumeSource: corev1.VolumeSource{Secret: &corev1.SecretVolumeSource{
					SecretName:  workspace.Spec.Browser.CredentialSecretName,
					DefaultMode: int32Ptr(0440),
					Items: []corev1.KeyToPath{
						{Key: "user-password", Path: "user-password"},
						{Key: "admin-password", Path: "admin-password"},
					},
				}},
			},
		}
		if r.TURNProfile != nil {
			turnICESecretItems := []corev1.KeyToPath{
				{Key: r.TURNBackendSecretKey, Path: "backend-ice-servers.json"},
			}
			if r.TURNProfile.CredentialIssuer.Kind == TURNCredentialIssuerStaticSecret {
				turnICESecretItems = append(turnICESecretItems, corev1.KeyToPath{
					Key: r.TURNFrontendSecretKey, Path: "frontend-ice-servers.json",
				})
			}
			deployment.Spec.Template.Spec.Volumes = append(deployment.Spec.Template.Spec.Volumes, corev1.Volume{
				Name: browserTURNVolumeName,
				VolumeSource: corev1.VolumeSource{Secret: &corev1.SecretVolumeSource{
					SecretName:  r.TURNICEServersSecretName,
					DefaultMode: int32Ptr(0440),
					Items:       turnICESecretItems,
				}},
			})
			if r.TURNProfile.CredentialIssuer.Kind == TURNCredentialIssuerTURNREST {
				deployment.Spec.Template.Spec.Volumes = append(deployment.Spec.Template.Spec.Volumes, corev1.Volume{
					Name: turnRESTVolumeName,
					VolumeSource: corev1.VolumeSource{Secret: &corev1.SecretVolumeSource{
						SecretName:  r.TURNProfile.CredentialIssuer.SecretRef,
						DefaultMode: int32Ptr(0440),
						Items:       []corev1.KeyToPath{{Key: "turn-rest-shared-secret", Path: "turn-rest-shared-secret"}},
					}},
				})
			}
		}
		container := corev1.Container{
			Name:                     "browser",
			Image:                    workspace.Spec.Browser.Image,
			ImagePullPolicy:          corev1.PullIfNotPresent,
			TerminationMessagePath:   corev1.TerminationMessagePathDefault,
			TerminationMessagePolicy: corev1.TerminationMessageReadFile,
			Ports: []corev1.ContainerPort{
				{Name: "webrtc", ContainerPort: 6080, Protocol: corev1.ProtocolTCP},
				{Name: "cdp", ContainerPort: 9223, Protocol: corev1.ProtocolTCP},
			},
			Command: []string{"/bin/sh", "-ec"},
			Args:    []string{browserSecretFileEntrypoint},
			Env:     browserEnvVars(r),
			VolumeMounts: []corev1.VolumeMount{
				{
					Name:      "workspace-data",
					MountPath: workspaceMountPath(workspace),
				},
				{Name: "tmp", MountPath: "/tmp"},
				{Name: "shared-memory", MountPath: "/dev/shm"},
				{Name: browserCredentialsVolumeName, MountPath: browserCredentialsMountPath, ReadOnly: true},
			},
			StartupProbe:    browserCompositeProbe(5, 2, 60),
			ReadinessProbe:  browserCompositeProbe(5, 2, 3),
			LivenessProbe:   httpHealthProbe("webrtc", "/health", 10, 2, 3),
			SecurityContext: restrictedContainerSecurityContext(),
		}
		if r.TURNProfile != nil && r.TURNProfile.CredentialIssuer.Kind == TURNCredentialIssuerStaticSecret {
			container.VolumeMounts = append(container.VolumeMounts, corev1.VolumeMount{
				Name: browserTURNVolumeName, MountPath: browserTURNMountPath, ReadOnly: true,
			})
		}
		if workspace.Spec.Browser.Resources != nil {
			container.Resources = *workspace.Spec.Browser.Resources
		}
		containers := []corev1.Container{container}
		if r.TURNProfile != nil {
			probeContainer, err := r.browserConnectivityProbeContainer(workspace.Spec.WorkspaceID)
			if err != nil {
				return err
			}
			containers = append(containers, probeContainer)
		}
		deployment.Spec.Template.Spec.Containers = containers
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
		if err := r.setWorkspaceControllerReference(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = labels
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "webrtc", Port: 6080, TargetPort: intstrFromInt32(6080), Protocol: corev1.ProtocolTCP},
			{Name: "cdp", Port: 9223, TargetPort: intstrFromInt32(9223), Protocol: corev1.ProtocolTCP},
		}
		if r.TURNProfile != nil {
			svc.Spec.Ports = append(svc.Spec.Ports, corev1.ServicePort{
				Name: "connectivity-evidence", Port: 8082,
				TargetPort: intstrFromInt32(8082), Protocol: corev1.ProtocolTCP,
			})
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) browserConnectivityProbeContainer(workspaceID string) (corev1.Container, error) {
	if r.TURNProfile == nil {
		return corev1.Container{}, fmt.Errorf("TURN reachability profile is required")
	}
	if strings.TrimSpace(r.BrowserConnectivityProbeImage) == "" {
		return corev1.Container{}, fmt.Errorf("Browser connectivity probe image is required")
	}
	profileJSON, err := json.Marshal(r.TURNProfile)
	if err != nil {
		return corev1.Container{}, fmt.Errorf("encode TURN reachability profile: %w", err)
	}
	env := []corev1.EnvVar{
		{Name: "TURN_REACHABILITY_PROFILE_JSON", Value: string(profileJSON)},
		{Name: "TURN_CREDENTIAL_REVISION", Value: r.TURNCredentialRevision},
		{Name: "AILERON_INSTALLATION_ID", Value: r.ConnectivityInstallationID},
		{Name: "TURN_PROBE_IDENTITY", Value: "backend:" + workspaceID},
		{Name: "TURN_BACKEND_ICE_SERVERS_JSON_FILE", Value: browserTURNMountPath + "/backend-ice-servers.json"},
	}
	volumeMounts := []corev1.VolumeMount{{
		Name: browserTURNVolumeName, MountPath: browserTURNMountPath, ReadOnly: true,
	}}
	if r.TURNProfile.CredentialIssuer.Kind == TURNCredentialIssuerTURNREST {
		env = append(env, corev1.EnvVar{
			Name: "TURN_REST_SHARED_SECRET_FILE", Value: turnRESTMountPath + "/turn-rest-shared-secret",
		})
		volumeMounts = append(volumeMounts, corev1.VolumeMount{
			Name: turnRESTVolumeName, MountPath: turnRESTMountPath, ReadOnly: true,
		})
	}
	return corev1.Container{
		Name:            "connectivity-probe",
		Image:           r.BrowserConnectivityProbeImage,
		ImagePullPolicy: corev1.PullIfNotPresent,
		Args: []string{
			"--mode=browser-connectivity-probe",
			"--connectivity-probe-bind-address=:8082",
		},
		Ports: []corev1.ContainerPort{{
			Name: "evidence", ContainerPort: 8082, Protocol: corev1.ProtocolTCP,
		}},
		Env:             env,
		VolumeMounts:    volumeMounts,
		ReadinessProbe:  httpHealthProbe("evidence", "/v1/evidence", 5, 2, 3),
		LivenessProbe:   httpHealthProbe("evidence", "/v1/evidence", 30, 2, 3),
		SecurityContext: restrictedContainerSecurityContext(),
	}, nil
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
		if workspace.Spec.Canvas.Enabled &&
			bootstrapSucceeded(workspace) &&
			workspace.Spec.Canvas.DesiredState == "Running" {
			replicas = 1
		}
		deployment.Labels = labels
		deployment.Annotations = mergeComponentAnnotations(
			deployment.Annotations,
			workspace,
			canvasComponent,
		)
		if err := r.setWorkspaceControllerReference(workspace, deployment); err != nil {
			return err
		}
		deployment.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		deployment.Spec.Replicas = &replicas
		deployment.Spec.Strategy.Type = appsv1.RecreateDeploymentStrategyType
		deployment.Spec.Strategy.RollingUpdate = nil
		deployment.Spec.Template.ObjectMeta.Labels = labels
		deployment.Spec.Template.ObjectMeta.Annotations = mergeComponentAnnotations(
			deployment.Spec.Template.ObjectMeta.Annotations,
			workspace,
			canvasComponent,
		)
		deployment.Spec.Template.Spec.ServiceAccountName = workloadServiceAccountName(workspace)
		deployment.Spec.Template.Spec.AutomountServiceAccountToken = boolPtr(false)
		deployment.Spec.Template.Spec.SecurityContext = restrictedPodSecurityContext(r.PlatformStorageGID)
		deployment.Spec.Template.Spec.Volumes = []corev1.Volume{
			{
				Name: "workspace-data",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
						ClaimName: resourceName(pvcComponent, workspace.Spec.WorkspaceID),
					},
				},
			},
			{
				Name:         "tmp",
				VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}},
			},
		}
		container := corev1.Container{
			Name:                     "canvas",
			Image:                    workspace.Spec.Canvas.Image,
			ImagePullPolicy:          corev1.PullIfNotPresent,
			TerminationMessagePath:   corev1.TerminationMessagePathDefault,
			TerminationMessagePolicy: corev1.TerminationMessageReadFile,
			Ports: []corev1.ContainerPort{
				{Name: "http", ContainerPort: 3003, Protocol: corev1.ProtocolTCP},
				{Name: "api", ContainerPort: 3013, Protocol: corev1.ProtocolTCP},
			},
			VolumeMounts: []corev1.VolumeMount{
				{
					Name:      "workspace-data",
					MountPath: workspaceMountPath(workspace),
				},
				{Name: "tmp", MountPath: "/tmp"},
			},
			StartupProbe:    httpHealthProbe("api", "/ready", 5, 2, 60),
			ReadinessProbe:  httpHealthProbe("api", "/ready", 5, 2, 3),
			LivenessProbe:   httpHealthProbe("api", "/health", 10, 2, 3),
			SecurityContext: restrictedContainerSecurityContext(),
		}
		if workspace.Spec.Canvas.Resources != nil {
			container.Resources = *workspace.Spec.Canvas.Resources
		}
		deployment.Spec.Template.Spec.Containers = []corev1.Container{container}
		return nil
	})
	return err
}

func browserCompositeProbe(periodSeconds, timeoutSeconds, failureThreshold int32) *corev1.Probe {
	return &corev1.Probe{
		ProbeHandler: corev1.ProbeHandler{Exec: &corev1.ExecAction{Command: []string{
			"/bin/sh",
			"-ec",
			`curl --fail --silent --show-error --max-time 1 http://127.0.0.1:6080/health >/dev/null && curl --fail --silent --show-error --max-time 1 http://127.0.0.1:9223/json/version >/dev/null`,
		}}},
		PeriodSeconds:    periodSeconds,
		TimeoutSeconds:   timeoutSeconds,
		FailureThreshold: failureThreshold,
		SuccessThreshold: 1,
	}
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
		if err := r.setWorkspaceControllerReference(workspace, svc); err != nil {
			return err
		}
		svc.Spec.Selector = labels
		svc.Spec.Ports = []corev1.ServicePort{
			{Name: "http", Port: 3003, TargetPort: intstrFromInt32(3003), Protocol: corev1.ProtocolTCP},
			{Name: "api", Port: 3013, TargetPort: intstrFromInt32(3013), Protocol: corev1.ProtocolTCP},
		}
		return nil
	})
	return err
}

func (r *WorkspaceReconciler) reconcileDelete(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	logger logrLike,
) (ctrl.Result, error) {
	if !controllerutil.ContainsFinalizer(workspace, workspaceFinalizer) {
		return ctrl.Result{}, nil
	}

	workspaceNamespace := workspace.Namespace
	logger.Info("cleaning up managed workspace resources", "workspaceNamespace", workspaceNamespace)
	if err := r.deleteManagedResources(ctx, workspace, workspaceNamespace); err != nil {
		return ctrl.Result{}, err
	}

	absent, err := r.managedPodsAndPVCsAbsent(ctx, workspace, workspaceNamespace)
	if err != nil {
		return ctrl.Result{}, err
	}
	if !absent {
		logger.Info(
			"waiting for managed workspace pods and persistent volume claims to be deleted",
			"workspaceNamespace",
			workspaceNamespace,
		)
		return ctrl.Result{RequeueAfter: time.Second}, nil
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
	group workspacev1alpha1.WorkspaceFirewallGroupSpec,
) (*unstructured.Unstructured, error) {
	policy := newCiliumNetworkPolicy(namespace, workspaceFirewallPolicyName(workspace.Spec.WorkspaceID))

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, policy, func() error {
		labels := componentLabels(workspace, "workspace-firewall-policy", "workspace")
		policy.SetLabels(labels)
		if err := r.setFirewallPolicyMetadata(workspace, policy); err != nil {
			return err
		}

		spec := map[string]interface{}{
			"endpointSelector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"aileron.io/workspace-id":   workspace.Spec.WorkspaceID,
					"aileron.io/firewall-group": "workspace",
				},
			},
			"egress": r.runtimeFirewallEgressRules(group),
		}

		if err := unstructured.SetNestedField(policy.Object, spec, "spec"); err != nil {
			return err
		}
		if err := setFirewallPolicyDeliveryMarkers(
			policy,
			workspace.UID,
			workspace.Spec.Firewall.Revision,
			workspaceFirewallDeliveryID(workspace),
		); err != nil {
			return err
		}
		return nil
	})
	return policy, err
}

func (r *WorkspaceReconciler) reconcileRuntimePeerFirewallPolicy(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) (*unstructured.Unstructured, error) {
	policy := newCiliumNetworkPolicy(namespace, runtimePeerFirewallPolicyName(workspace.Spec.WorkspaceID))

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, policy, func() error {
		labels := componentLabels(workspace, "runtime-peer-firewall-policy", "workspace")
		policy.SetLabels(labels)
		if err := r.setFirewallPolicyMetadata(workspace, policy); err != nil {
			return err
		}

		spec := map[string]interface{}{
			"endpointSelector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"aileron.io/workspace-id": workspace.Spec.WorkspaceID,
					"aileron.io/component":    runtimeComponent,
				},
			},
			"egress": workspacePeerEgressRules(namespace, workspace.Spec.WorkspaceID),
		}

		if err := unstructured.SetNestedField(policy.Object, spec, "spec"); err != nil {
			return err
		}
		if err := setFirewallPolicyDeliveryMarkers(
			policy,
			workspace.UID,
			workspace.Spec.Firewall.Revision,
			workspaceFirewallDeliveryID(workspace),
		); err != nil {
			return err
		}
		return nil
	})
	return policy, err
}

func (r *WorkspaceReconciler) reconcileBrowserFirewallPolicy(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	group workspacev1alpha1.WorkspaceFirewallGroupSpec,
) (*unstructured.Unstructured, error) {
	policy := newCiliumNetworkPolicy(namespace, browserFirewallPolicyName(workspace.Spec.WorkspaceID))

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, policy, func() error {
		labels := componentLabels(workspace, "browser-firewall-policy", "browser")
		policy.SetLabels(labels)
		if err := r.setFirewallPolicyMetadata(workspace, policy); err != nil {
			return err
		}

		egressRules := r.firewallEgressRules(group)
		egressRules = append(
			egressRules,
			browserTURNEgressRules(r.TURNProfile)...,
		)
		spec := map[string]interface{}{
			"endpointSelector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"aileron.io/workspace-id":   workspace.Spec.WorkspaceID,
					"aileron.io/firewall-group": "browser",
				},
			},
			"egress": egressRules,
		}

		if err := unstructured.SetNestedField(policy.Object, spec, "spec"); err != nil {
			return err
		}
		if err := setFirewallPolicyDeliveryMarkers(
			policy,
			workspace.UID,
			workspace.Spec.Firewall.Revision,
			workspaceFirewallDeliveryID(workspace),
		); err != nil {
			return err
		}
		return nil
	})
	return policy, err
}

func (r *WorkspaceReconciler) setFirewallPolicyMetadata(
	workspace *workspacev1alpha1.Workspace,
	policy *unstructured.Unstructured,
) error {
	revision := strconv.FormatInt(workspace.Spec.Firewall.Revision, 10)
	deliveryID := workspaceFirewallDeliveryID(workspace)
	current := policy.GetAnnotations()
	targetUnchanged := current[firewallRevisionAnnotation] == revision &&
		current[firewallDeliveryIDAnnotation] == deliveryID
	next := make(map[string]string, len(current)+3)
	for key, value := range current {
		if strings.HasPrefix(key, firewallAttestationAnnotationPrefix) && !targetUnchanged {
			continue
		}
		next[key] = value
	}
	next[firewallRevisionAnnotation] = revision
	next[firewallDeliveryIDAnnotation] = deliveryID
	next[workspaceResourceAnnotation] = workspace.Name
	policy.SetAnnotations(next)
	return r.setWorkspaceControllerReference(workspace, policy)
}

func ParseRuntimeHomeStorageAccessMode(
	value string,
) (corev1.PersistentVolumeAccessMode, error) {
	accessMode := corev1.PersistentVolumeAccessMode(strings.TrimSpace(value))
	if accessMode == "" {
		return corev1.ReadWriteOnce, nil
	}
	switch accessMode {
	case corev1.ReadWriteOnce, corev1.ReadWriteMany:
		return accessMode, nil
	default:
		return "", fmt.Errorf(
			"runtime home storage access mode must be ReadWriteOnce or ReadWriteMany, got %q",
			value,
		)
	}
}

func (r *WorkspaceReconciler) reconcileWorkloadServiceAccount(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	serviceAccount := &corev1.ServiceAccount{
		ObjectMeta: metav1.ObjectMeta{
			Name:      workloadServiceAccountName(workspace),
			Namespace: namespace,
		},
	}

	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, serviceAccount, func() error {
		serviceAccount.Labels = componentLabels(
			workspace,
			workloadServiceAccountComponent,
			"workspace",
		)
		serviceAccount.AutomountServiceAccountToken = boolPtr(false)
		serviceAccount.ImagePullSecrets = make(
			[]corev1.LocalObjectReference,
			0,
			len(r.WorkloadImagePullSecrets),
		)
		for _, secretName := range r.WorkloadImagePullSecrets {
			if normalized := strings.TrimSpace(secretName); normalized != "" {
				serviceAccount.ImagePullSecrets = append(
					serviceAccount.ImagePullSecrets,
					corev1.LocalObjectReference{Name: normalized},
				)
			}
		}
		return r.setWorkspaceControllerReference(workspace, serviceAccount)
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
		{name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(browserComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(canvasComponent, workspace.Spec.WorkspaceID), obj: &corev1.Service{}},
		{name: resourceName(runtimeComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(browserComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(canvasComponent, workspace.Spec.WorkspaceID), obj: &appsv1.Deployment{}},
		{name: resourceName(pvcComponent, workspace.Spec.WorkspaceID), obj: &corev1.PersistentVolumeClaim{}},
		{name: resourceName(runtimeHomePVCComponent, workspace.Spec.WorkspaceID), obj: &corev1.PersistentVolumeClaim{}},
		{name: workloadServiceAccountName(workspace), obj: &corev1.ServiceAccount{}},
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

func (r *WorkspaceReconciler) managedPodsAndPVCsAbsent(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) (bool, error) {
	var pods corev1.PodList
	if err := r.List(
		ctx,
		&pods,
		client.InNamespace(namespace),
		client.MatchingLabels{workspaceIDLabel: workspace.Spec.WorkspaceID},
	); err != nil {
		return false, err
	}
	for _, pod := range pods.Items {
		if isManagedWorkspaceComponent(pod.Labels[componentLabel]) {
			return false, nil
		}
	}

	for _, component := range []string{pvcComponent, runtimeHomePVCComponent} {
		var pvc corev1.PersistentVolumeClaim
		err := r.Get(ctx, client.ObjectKey{
			Name:      resourceName(component, workspace.Spec.WorkspaceID),
			Namespace: namespace,
		}, &pvc)
		if err == nil {
			return false, nil
		}
		if !apierrors.IsNotFound(err) {
			return false, err
		}
	}

	return true, nil
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
	runtimePeerPolicy := newCiliumNetworkPolicy(namespace, runtimePeerFirewallPolicyName(workspace.Spec.WorkspaceID))
	if err := r.Delete(ctx, runtimePeerPolicy); err != nil &&
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

func (r *WorkspaceReconciler) SetupWithManager(
	mgr ctrl.Manager,
	dependencies []controllerdependencies.Dependency,
) error {
	plan, err := BuildControllerWiringPlan(dependencies)
	if err != nil {
		return err
	}
	byIdentity := make(map[string]controllerdependencies.Dependency, len(dependencies))
	for _, dependency := range dependencies {
		byIdentity[dependency.Identity] = dependency
	}
	controllerBuilder := ctrl.NewControllerManagedBy(mgr)
	for _, registration := range plan {
		object, err := controllerDependencyObject(byIdentity[registration.Identity])
		if err != nil {
			return err
		}
		switch registration.Registration {
		case RegistrationPrimary:
			controllerBuilder = controllerBuilder.For(object)
		case RegistrationOwn:
			controllerBuilder = controllerBuilder.Owns(object)
		case RegistrationWatch:
			mapper, err := r.controllerDependencyMapper(registration.MapperIdentity)
			if err != nil {
				return err
			}
			controllerBuilder = controllerBuilder.Watches(object, handler.EnqueueRequestsFromMapFunc(mapper))
		}
	}
	return controllerBuilder.
		Named("workspace-controller").
		Complete(r)
}

func (r *WorkspaceReconciler) controllerDependencyMapper(identity string) (handler.MapFunc, error) {
	switch identity {
	case "managedPodToWorkspace":
		return r.requestsForManagedPod, nil
	case "ciliumEndpointToWorkspace":
		return r.requestsForCiliumEndpoint, nil
	default:
		return nil, fmt.Errorf("unsupported controller dependency mapper %q", identity)
	}
}

func (r *WorkspaceReconciler) requestsForCiliumEndpoint(
	ctx context.Context,
	object client.Object,
) []reconcile.Request {
	var pod corev1.Pod
	if err := r.Get(ctx, client.ObjectKeyFromObject(object), &pod); err != nil {
		return nil
	}
	return r.requestsForManagedPod(ctx, &pod)
}

func (r *WorkspaceReconciler) requestsForManagedPod(
	_ context.Context,
	object client.Object,
) []reconcile.Request {
	pod, ok := object.(*corev1.Pod)
	if !ok || !isManagedWorkspaceComponent(pod.Labels[componentLabel]) {
		return nil
	}

	workspaceID := pod.Labels[workspaceIDLabel]
	if workspaceID == "" {
		return nil
	}

	return []reconcile.Request{{NamespacedName: client.ObjectKey{
		Name:      resourceName("workspace", workspaceID),
		Namespace: pod.Namespace,
	}}}
}

func (r *WorkspaceReconciler) populateWorkspaceStatus(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
) error {
	previousRuntimeStatus := workspace.Status.Components.Runtime
	runtimeStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		runtimeComponent,
		true,
	)
	if err != nil {
		return err
	}
	runtimeStatus.MountObservedRevision = previousRuntimeStatus.MountObservedRevision
	runtimeStatus.LastKnownGoodMountRevision = previousRuntimeStatus.LastKnownGoodMountRevision
	runtimeStatus.AccessObservedRevision = previousRuntimeStatus.AccessObservedRevision
	if workspace.Status.Bootstrap.ObservedRevision != workspace.Spec.Bootstrap.Revision ||
		workspace.Status.Bootstrap.Phase != "Succeeded" {
		workspace.Status.Bootstrap.ObservedRevision = 0
		workspace.Status.Bootstrap.Phase = "Pending"
		workspace.Status.Bootstrap.Reason = "WorkspaceBootstrapPending"
		if runtimeStatus.Ready && runtimeStatus.TerminalReady {
			workspace.Status.Bootstrap.ObservedRevision = workspace.Spec.Bootstrap.Revision
			workspace.Status.Bootstrap.Phase = "Succeeded"
			workspace.Status.Bootstrap.Reason = "WorkspaceBootstrapSucceeded"
			workspace.Status.Bootstrap.ErrorCode = ""
		}
	}

	browserStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		browserComponent,
		workspace.Spec.Browser.Enabled,
	)
	if err != nil {
		return err
	}
	if browserStatus.Ready {
		browserStatus.CredentialObservedRevision = workspace.Spec.Browser.CredentialRevision
		browserStatus.CredentialObservedKeyID = workspace.Spec.Browser.CredentialKeyID
		browserStatus.CredentialObservedAlgorithm = workspace.Spec.Browser.CredentialAlgorithm
	}
	workspace.Status.BrowserConnectivity = r.evaluateBrowserConnectivity(
		ctx,
		workspace,
		namespace,
		browserStatus,
	)

	canvasStatus, err := r.buildComponentStatus(
		ctx,
		workspace,
		namespace,
		canvasComponent,
		workspace.Spec.Canvas.Enabled,
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
	if executionPlaneReady(workspace.Spec, workspace.Status.Components) {
		workspace.Status.Components.Runtime.MountObservedRevision = workspace.Spec.Runtime.MountRevision
		workspace.Status.Components.Runtime.LastKnownGoodMountRevision = workspace.Spec.Runtime.MountRevision
		workspace.Status.Components.Runtime.AccessObservedRevision = workspace.Spec.Runtime.AccessRevision
	}

	return nil
}

func (r *WorkspaceReconciler) buildComponentStatus(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
	enabled bool,
) (workspacev1alpha1.WorkspaceComponentStatus, error) {
	status := workspacev1alpha1.WorkspaceComponentStatus{}

	if !enabled {
		status.Phase = "Disabled"
		status.Reason = componentReason(component, "Disabled")
		return status, nil
	}
	if componentDesiredState(workspace, component) == "Stopped" {
		status.Phase = "Stopped"
		status.Reason = componentReason(component, "Stopped")
		return status, nil
	}
	if component != runtimeComponent && !bootstrapSucceeded(workspace) {
		status.Phase = "Pending"
		status.Reason = "WorkspaceBootstrapPending"
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
	if deploymentMatchesDesiredRevision(deployment, workspace, component) {
		status.ObservedRevision = componentRevision(workspace, component)
	} else {
		status.Phase = "Stopping"
		status.Reason = componentReason(component, "RevisionFencePending")
	}
	podUID, podReady, err := r.currentGenerationPodIdentity(
		ctx,
		workspace,
		namespace,
		component,
	)
	if err != nil {
		return workspacev1alpha1.WorkspaceComponentStatus{}, err
	}
	status.PodUID = podUID
	if podUID != "" {
		status.ObservedInstanceID = componentInstanceID(workspace, component)
	}
	status.Ready = status.Phase == "Running" && podReady
	if component == runtimeComponent {
		status.TerminalReady = status.Ready
	}
	if status.Phase == "Running" && !status.Ready {
		status.Phase = "Starting"
	}
	if status.Reason == "" {
		status.Reason = componentReason(component, status.Phase)
	}
	return status, nil
}

func (r *WorkspaceReconciler) currentGenerationPodIdentity(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	component string,
) (string, bool, error) {
	pods := &corev1.PodList{}
	if err := r.List(
		ctx,
		pods,
		client.InNamespace(namespace),
		client.MatchingLabels{
			"aileron.io/workspace-id": workspace.Spec.WorkspaceID,
			"aileron.io/component":    component,
		},
	); err != nil {
		return "", false, err
	}

	var current *corev1.Pod
	for i := range pods.Items {
		pod := &pods.Items[i]
		if pod.DeletionTimestamp != nil ||
			pod.Annotations[componentRevisionAnnotation] != fmt.Sprintf(
				"%d",
				componentRevision(workspace, component),
			) {
			continue
		}
		if pod.Annotations[componentInstanceAnnotation] != componentInstanceID(
			workspace,
			component,
		) {
			continue
		}
		if component == runtimeComponent &&
			pod.Annotations[runtimeInstanceAnnotation] != workspace.Spec.Runtime.InstanceID {
			continue
		}
		if current != nil {
			return "", false, nil
		}
		current = pod
	}
	if current == nil || current.UID == "" {
		return "", false, nil
	}
	for _, condition := range current.Status.Conditions {
		if condition.Type == corev1.PodReady && condition.Status == corev1.ConditionTrue {
			return string(current.UID), true, nil
		}
	}
	return string(current.UID), false, nil
}

func executionPlaneReady(
	spec workspacev1alpha1.WorkspaceSpec,
	components workspacev1alpha1.WorkspaceComponentsStatus,
) bool {
	if !components.Runtime.Ready ||
		!components.Runtime.TerminalReady ||
		components.Runtime.Phase != "Running" ||
		components.Runtime.PodUID == "" {
		return false
	}
	if spec.Browser.Enabled &&
		spec.Browser.DesiredState != "Stopped" &&
		(!components.Browser.Ready ||
			components.Browser.Phase != "Running" ||
			components.Browser.PodUID == "") {
		return false
	}
	if spec.Canvas.Enabled &&
		spec.Canvas.DesiredState != "Stopped" &&
		(!components.Canvas.Ready ||
			components.Canvas.Phase != "Running" ||
			components.Canvas.PodUID == "") {
		return false
	}
	return true
}

func calculateWorkspacePhase(
	spec workspacev1alpha1.WorkspaceSpec,
	components workspacev1alpha1.WorkspaceComponentsStatus,
) string {
	if spec.Runtime.DesiredState == "Stopped" &&
		(!spec.Browser.Enabled || spec.Browser.DesiredState == "Stopped") &&
		(!spec.Canvas.Enabled || spec.Canvas.DesiredState == "Stopped") {
		return "Stopped"
	}
	if components.Runtime.Phase == "Error" {
		return "Error"
	}
	if components.Runtime.Phase == "Running" &&
		((spec.Browser.Enabled && components.Browser.Phase == "Error") ||
			(spec.Canvas.Enabled && components.Canvas.Phase == "Error")) {
		return "Degraded"
	}

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
		if phase == "Error" {
			return "Degraded"
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
	case "", "Pending", "Reconciling", "Degraded":
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
		return "Stopped"
	}
	if deployment.Status.ObservedGeneration < deployment.Generation {
		return "Starting"
	}

	for _, condition := range deployment.Status.Conditions {
		if condition.Type == appsv1.DeploymentReplicaFailure &&
			condition.Status == corev1.ConditionTrue {
			return "Error"
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
	return "Starting"
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

func (r *WorkspaceReconciler) firewallEgressRules(
	group workspacev1alpha1.WorkspaceFirewallGroupSpec,
) []interface{} {
	rules := r.baseEgressRules(nil)
	switch group.EgressMode {
	case workspacev1alpha1.WorkspaceFirewallEgressModeUnrestricted:
		return append(rules, map[string]interface{}{
			"toEntities": []interface{}{"world"},
		})
	case workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist:
	default:
		return rules
	}
	fqdnEntries := toFQDNEntries(group.AllowedDomains)
	if len(fqdnEntries) > 0 {
		rules = append(rules, map[string]interface{}{"toFQDNs": fqdnEntries})
	}
	return rules
}

func (r *WorkspaceReconciler) runtimeFirewallEgressRules(
	group workspacev1alpha1.WorkspaceFirewallGroupSpec,
) []interface{} {
	return r.firewallEgressRules(group)
}

func (r *WorkspaceReconciler) persistFirewallError(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
) {
	now := metav1.Now()
	targetDeliveryID := workspaceFirewallDeliveryID(workspace)
	if workspace.Status.Firewall.TargetRevision != workspace.Spec.Firewall.Revision ||
		workspace.Status.Firewall.TargetDeliveryID != targetDeliveryID {
		workspace.Status.Firewall.WorkspacePolicyGeneration = 0
		workspace.Status.Firewall.RuntimePeerPolicyGeneration = 0
		workspace.Status.Firewall.BrowserPolicyGeneration = 0
	}
	workspace.Status.Firewall.TargetRevision = workspace.Spec.Firewall.Revision
	workspace.Status.Firewall.TargetDeliveryID = targetDeliveryID
	workspace.Status.Firewall.Phase = "Error"
	workspace.Status.Firewall.Reason = "FirewallPolicyApplyFailed"
	workspace.Status.Firewall.ErrorCode = "FIREWALL_POLICY_APPLY_FAILED"
	workspace.Status.Firewall.LastTransitionAt = &now
	_ = r.Status().Update(ctx, workspace)
}

func workspaceFirewallPolicyName(workspaceID string) string {
	return fmt.Sprintf("ws-%s-workspace-egress", workspaceID)
}

func runtimePeerFirewallPolicyName(workspaceID string) string {
	return fmt.Sprintf("ws-%s-runtime-peer-egress", workspaceID)
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
		entries = append(entries, map[string]interface{}{
			"matchName": domain,
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
				"rules": map[string]interface{}{
					"dns": []interface{}{
						map[string]interface{}{
							"matchPattern": "*",
						},
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

type turnServerAddress struct {
	host      string
	port      string
	protocols []string
	secure    bool
}

func parseTURNServerAddress(serverURL string) (turnServerAddress, bool) {
	address := strings.TrimSpace(serverURL)
	defaultPort := "3478"
	protocols := []string{"UDP", "TCP"}
	secure := false
	lowerAddress := strings.ToLower(address)
	switch {
	case strings.HasPrefix(lowerAddress, "turn:"):
		address = address[len("turn:"):]
	case strings.HasPrefix(lowerAddress, "turns:"):
		address = address[len("turns:"):]
		defaultPort = "5349"
		protocols = []string{"TCP"}
		secure = true
	default:
		return turnServerAddress{}, false
	}

	if queryIndex := strings.Index(address, "?"); queryIndex >= 0 {
		query, err := url.ParseQuery(address[queryIndex+1:])
		if err != nil {
			return turnServerAddress{}, false
		}
		if transports, found := query["transport"]; found {
			if len(transports) != 1 {
				return turnServerAddress{}, false
			}
			switch strings.ToLower(strings.TrimSpace(transports[0])) {
			case "udp":
				if secure {
					return turnServerAddress{}, false
				}
				protocols = []string{"UDP"}
			case "tcp":
				protocols = []string{"TCP"}
			default:
				return turnServerAddress{}, false
			}
		}
		address = address[:queryIndex]
	}
	address = strings.TrimPrefix(address, "//")
	if address == "" {
		return turnServerAddress{}, false
	}

	host := address
	port := defaultPort
	if parsedHost, parsedPort, err := net.SplitHostPort(address); err == nil {
		host = parsedHost
		port = parsedPort
	} else if strings.Contains(address, ":") {
		unwrapped := strings.Trim(address, "[]")
		if net.ParseIP(unwrapped) == nil {
			return turnServerAddress{}, false
		}
		host = unwrapped
	}
	host = strings.TrimSuffix(strings.ToLower(strings.TrimSpace(host)), ".")
	portNumber, err := strconv.Atoi(port)
	if host == "" || strings.ContainsAny(host, "/?# \t\r\n") ||
		err != nil || portNumber < 1 || portNumber > 65535 {
		return turnServerAddress{}, false
	}
	return turnServerAddress{
		host:      host,
		port:      strconv.Itoa(portNumber),
		protocols: protocols,
		secure:    secure,
	}, true
}

func workspacePeerEgressRules(namespace string, workspaceID string) []interface{} {
	return []interface{}{
		workspaceComponentEgressRule(namespace, workspaceID, canvasComponent, "3003", "3013"),
		workspaceComponentEgressRule(namespace, workspaceID, browserComponent, "6080", "9223"),
	}
}

func workspaceComponentEgressRule(
	namespace string,
	workspaceID string,
	component string,
	ports ...string,
) map[string]interface{} {
	portRules := make([]interface{}, 0, len(ports))
	for _, port := range ports {
		portRules = append(portRules, map[string]interface{}{
			"port":     port,
			"protocol": "TCP",
		})
	}

	return map[string]interface{}{
		"toEndpoints": []interface{}{
			map[string]interface{}{
				"matchLabels": map[string]interface{}{
					"k8s:io.kubernetes.pod.namespace": namespace,
					"k8s:app.kubernetes.io/part-of":   "aileron",
					"k8s:aileron.io/workspace-id":     workspaceID,
					"k8s:aileron.io/component":        component,
				},
			},
		},
		"toPorts": []interface{}{
			map[string]interface{}{
				"ports": portRules,
			},
		},
	}
}

func requiredInternalServiceComponents() []string {
	return []string{
		"workspace-manager",
		"postgres",
	}
}

type logrLike interface {
	Info(msg string, keysAndValues ...interface{})
	Error(err error, msg string, keysAndValues ...interface{})
}

func resourceName(component string, workspaceID string) string {
	return fmt.Sprintf("%s-%s", component, workspaceID)
}

func workloadServiceAccountName(workspace *workspacev1alpha1.Workspace) string {
	return resourceName(workloadServiceAccountComponent, workspace.Spec.WorkspaceID)
}

func isManagedWorkspaceComponent(component string) bool {
	switch component {
	case runtimeComponent, browserComponent, canvasComponent:
		return true
	default:
		return false
	}
}

func componentLabels(
	workspace *workspacev1alpha1.Workspace,
	component string,
	firewallGroup string,
) map[string]string {
	return map[string]string{
		"app.kubernetes.io/part-of": "aileron",
		workspaceIDLabel:            workspace.Spec.WorkspaceID,
		"aileron.io/owner-id":       workspace.Spec.OwnerID,
		componentLabel:              component,
		"aileron.io/firewall-group": firewallGroup,
	}
}

func componentAnnotations(
	workspace *workspacev1alpha1.Workspace,
	component string,
) map[string]string {
	annotations := map[string]string{
		componentRevisionAnnotation: fmt.Sprintf("%d", componentRevision(workspace, component)),
		componentInstanceAnnotation: componentInstanceID(workspace, component),
	}
	if component == runtimeComponent {
		annotations[runtimeInstanceAnnotation] = workspace.Spec.Runtime.InstanceID
		annotations[runtimeAccessRevisionAnnotation] = fmt.Sprintf(
			"%d",
			workspace.Spec.Runtime.AccessRevision,
		)
		annotations[mountRevisionAnnotation] = fmt.Sprintf(
			"%d",
			workspace.Spec.Runtime.MountRevision,
		)
	}
	if component == browserComponent {
		annotations[browserCredentialRevisionAnnotation] = fmt.Sprintf(
			"%d",
			workspace.Spec.Browser.CredentialRevision,
		)
		annotations[browserCredentialKeyIDAnnotation] = workspace.Spec.Browser.CredentialKeyID
		annotations[browserCredentialAlgorithmAnnotation] = workspace.Spec.Browser.CredentialAlgorithm
	}
	return annotations
}

func mergeComponentAnnotations(
	existing map[string]string,
	workspace *workspacev1alpha1.Workspace,
	component string,
) map[string]string {
	annotations := make(map[string]string, len(existing)+4)
	for key, value := range existing {
		annotations[key] = value
	}
	for key, value := range componentAnnotations(workspace, component) {
		annotations[key] = value
	}
	if component != runtimeComponent {
		delete(annotations, runtimeInstanceAnnotation)
		delete(annotations, runtimeAccessRevisionAnnotation)
		delete(annotations, mountRevisionAnnotation)
	}
	if component != browserComponent {
		delete(annotations, browserCredentialRevisionAnnotation)
		delete(annotations, browserCredentialKeyIDAnnotation)
		delete(annotations, browserCredentialAlgorithmAnnotation)
	}
	return annotations
}

func componentRevision(workspace *workspacev1alpha1.Workspace, component string) int64 {
	switch component {
	case runtimeComponent:
		return workspace.Spec.Runtime.Revision
	case browserComponent:
		return workspace.Spec.Browser.Revision
	case canvasComponent:
		return workspace.Spec.Canvas.Revision
	default:
		return 0
	}
}

func componentInstanceID(
	workspace *workspacev1alpha1.Workspace,
	component string,
) string {
	switch component {
	case runtimeComponent:
		return workspace.Spec.Runtime.InstanceID
	case browserComponent:
		return workspace.Spec.Browser.InstanceID
	case canvasComponent:
		return workspace.Spec.Canvas.InstanceID
	default:
		return ""
	}
}

func componentDesiredState(
	workspace *workspacev1alpha1.Workspace,
	component string,
) string {
	switch component {
	case runtimeComponent:
		return workspace.Spec.Runtime.DesiredState
	case browserComponent:
		return workspace.Spec.Browser.DesiredState
	case canvasComponent:
		return workspace.Spec.Canvas.DesiredState
	default:
		return "Stopped"
	}
}

func componentReplicaCount(desiredState string, enabled bool) int32 {
	if enabled && desiredState == "Running" {
		return 1
	}
	return 0
}

func bootstrapSucceeded(workspace *workspacev1alpha1.Workspace) bool {
	return workspace.Status.Bootstrap.Phase == "Succeeded" &&
		workspace.Status.Bootstrap.ObservedRevision == workspace.Spec.Bootstrap.Revision
}

func componentReason(component string, suffix string) string {
	var prefix string
	switch component {
	case runtimeComponent:
		prefix = "Runtime"
	case browserComponent:
		prefix = "Browser"
	case canvasComponent:
		prefix = "Canvas"
	default:
		prefix = "Component"
	}
	return prefix + suffix
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
			Name: runtimeHomeVolumeName,
			VolumeSource: corev1.VolumeSource{
				PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
					ClaimName: resourceName(runtimeHomePVCComponent, workspace.Spec.WorkspaceID),
				},
			},
		},
		{
			Name: runtimeSetupVolumeName,
			VolumeSource: corev1.VolumeSource{
				Secret: &corev1.SecretVolumeSource{
					SecretName: workspace.Spec.Runtime.RuntimeSecretName,
					Items: []corev1.KeyToPath{
						{
							Key:  runtimeSetupSecretKey,
							Path: runtimeSetupSecretKey,
							Mode: int32Ptr(0440),
						},
					},
					DefaultMode: int32Ptr(0440),
				},
			},
		},
		{
			Name: runtimeSecretsVolumeName,
			VolumeSource: corev1.VolumeSource{
				Secret: &corev1.SecretVolumeSource{
					SecretName: workspace.Spec.Runtime.RuntimeSecretName,
					Items: []corev1.KeyToPath{
						{Key: runtimeStateDatabaseSecretKey, Path: runtimeStateDatabaseSecretKey, Mode: int32Ptr(0440)},
						{Key: runtimeControlTokenSecretKey, Path: runtimeControlTokenSecretKey, Mode: int32Ptr(0440)},
					},
					DefaultMode: int32Ptr(0440),
				},
			},
		},
		{
			Name: runtimeCodexTmpVolumeName,
			VolumeSource: corev1.VolumeSource{
				EmptyDir: &corev1.EmptyDirVolumeSource{
					Medium:    corev1.StorageMediumMemory,
					SizeLimit: resourceQuantityPtr("16Mi"),
				},
			},
		},
		{
			Name: "tmp",
			VolumeSource: corev1.VolumeSource{
				EmptyDir: &corev1.EmptyDirVolumeSource{},
			},
		},
		{
			Name: runtimeAssertionJWKSVolumeName,
			VolumeSource: corev1.VolumeSource{
				Secret: &corev1.SecretVolumeSource{
					SecretName: workspace.Spec.Runtime.Assertion.PublicKeySetSecretName,
					Items: []corev1.KeyToPath{
						{Key: runtimeAssertionJWKSSecretKey, Path: runtimeAssertionJWKSSecretKey},
					},
					DefaultMode: int32Ptr(0444),
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

func runtimeVolumeMounts(
	workspace *workspacev1alpha1.Workspace,
) []corev1.VolumeMount {
	mounts := []corev1.VolumeMount{
		{
			Name:      "workspace-data",
			MountPath: workspaceMountPath(workspace),
		},
		{
			Name:      runtimeHomeVolumeName,
			MountPath: runtimeHomeMountPath,
		},
		{
			Name:      runtimeSetupVolumeName,
			MountPath: runtimeSetupMountPath,
			SubPath:   runtimeSetupSecretKey,
			ReadOnly:  true,
		},
		{
			Name:      runtimeSecretsVolumeName,
			MountPath: runtimeSecretsMountPath,
			ReadOnly:  true,
		},
		{Name: "tmp", MountPath: "/tmp"},
		{
			Name:      runtimeCodexTmpVolumeName,
			MountPath: runtimeCodexTmpMountPath,
		},
		{
			Name:      runtimeAssertionJWKSVolumeName,
			MountPath: runtimeAssertionJWKSMountPath,
			ReadOnly:  true,
		},
	}
	for _, attachment := range workspace.Spec.KnowledgeBases {
		mounts = append(mounts, corev1.VolumeMount{
			Name:      "knowledge-bases",
			MountPath: "/knowledge/" + attachment.Alias,
			SubPath:   attachment.KBID,
			ReadOnly:  true,
		})
	}
	return mounts
}

func runtimeHomeInitializer(workspace *workspacev1alpha1.Workspace) corev1.Container {
	return corev1.Container{
		Name:            runtimeHomeInitializerName,
		Image:           workspace.Spec.Runtime.Image,
		ImagePullPolicy: corev1.PullIfNotPresent,
		Command:         []string{"/bin/sh", "-ec"},
		Args: []string{`umask 0007
mkdir -p "${HOME}/.codex"
chmod 2770 "${HOME}/.codex"`},
		Env: []corev1.EnvVar{
			{Name: "HOME", Value: runtimeHomeMountPath},
		},
		VolumeMounts: []corev1.VolumeMount{
			{Name: runtimeHomeVolumeName, MountPath: runtimeHomeMountPath},
		},
		SecurityContext: restrictedContainerSecurityContext(),
	}
}

func runtimeEnvVars(
	workspace *workspacev1alpha1.Workspace,
	reconciler *WorkspaceReconciler,
) []corev1.EnvVar {
	browserServiceName := resourceName(browserComponent, workspace.Spec.WorkspaceID)
	canvasServiceName := resourceName(canvasComponent, workspace.Spec.WorkspaceID)
	return []corev1.EnvVar{
		{Name: "AILERON_WORKSPACE_ID", Value: workspace.Spec.WorkspaceID},
		{Name: "AILERON_WORKSPACE_PATH", Value: workspaceMountPath(workspace)},
		{Name: "AILERON_RUNTIME_INSTANCE_ID", Value: workspace.Spec.Runtime.InstanceID},
		{Name: "AILERON_RUNTIME_ACCESS_REVISION", Value: fmt.Sprintf("%d", workspace.Spec.Runtime.AccessRevision)},
		{Name: "AILERON_KB_MOUNT_REVISION", Value: fmt.Sprintf("%d", workspace.Spec.Runtime.MountRevision)},
		{Name: "AILERON_WORKTREE_SUBDIR", Value: workspace.Spec.WorktreeSubdir},
		{Name: "AILERON_RUNTIME_STATE_DATABASE_URL_FILE", Value: runtimeSecretsMountPath + "/" + runtimeStateDatabaseSecretKey},
		{Name: "AILERON_RUNTIME_CONTROL_TOKEN_FILE", Value: runtimeSecretsMountPath + "/" + runtimeControlTokenSecretKey},
		{Name: "AILERON_MANAGER_INTERNAL_URL", Value: reconciler.ManagerURL},
		{Name: "AILERON_PLATFORM_PUBLIC_ORIGIN", Value: reconciler.PlatformPublicOrigin},
		{Name: "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", Value: runtimeAssertionJWKSFilePath},
		{Name: "AILERON_RUNTIME_ASSERTION_ISSUER", Value: workspace.Spec.Runtime.Assertion.Issuer},
		{Name: "HOME", Value: runtimeHomeMountPath},
		{Name: "AILERON_BROWSER_SERVICE_NAME", Value: browserServiceName},
		{Name: "AILERON_BROWSER_WEBRTC_INTERNAL_URL", Value: fmt.Sprintf("http://%s:6080", browserServiceName)},
		{Name: "AILERON_BROWSER_CDP_URL", Value: fmt.Sprintf("http://%s:9223", browserServiceName)},
		{Name: "AILERON_CANVAS_SERVICE_NAME", Value: canvasServiceName},
		{Name: "AILERON_CANVAS_INTERNAL_URL", Value: fmt.Sprintf("http://%s:3003", canvasServiceName)},
		{Name: "AILERON_CANVAS_API_URL", Value: fmt.Sprintf("http://%s:3013", canvasServiceName)},
	}
}

func runtimeSecretName(workspaceID string) string {
	digest := sha256.Sum256([]byte(workspaceID))
	return fmt.Sprintf("workspace-runtime-db-%x", digest[:16])
}

// browserEnvVars exposes only non-sensitive configuration and mounted Secret file paths.
func browserEnvVars(reconciler *WorkspaceReconciler) []corev1.EnvVar {
	env := []corev1.EnvVar{
		{Name: "NEKO_MEMBER_PROVIDER", Value: "multiuser"},
		// Neko logs ICE server objects at info level, including credentials.
		{Name: "NEKO_LOG_LEVEL", Value: "warn"},
		{Name: "NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE", Value: browserCredentialsMountPath + "/user-password"},
		{Name: "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE", Value: browserCredentialsMountPath + "/admin-password"},
	}
	if reconciler.TURNProfile == nil {
		return env
	}
	env = append(env,
		corev1.EnvVar{Name: "NEKO_WEBRTC_ICELITE", Value: "false"},
		corev1.EnvVar{Name: "AILERON_TURN_CREDENTIAL_REVISION", Value: reconciler.TURNCredentialRevision},
	)
	if reconciler.TURNProfile.CredentialIssuer.Kind == TURNCredentialIssuerTURNREST {
		return env
	}
	return append(env,
		corev1.EnvVar{Name: "NEKO_WEBRTC_ICESERVERS_BACKEND_FILE", Value: browserTURNMountPath + "/backend-ice-servers.json"},
		corev1.EnvVar{Name: "NEKO_WEBRTC_ICESERVERS_FRONTEND_FILE", Value: browserTURNMountPath + "/frontend-ice-servers.json"},
	)
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

func boolPtr(v bool) *bool {
	return &v
}

func restrictedPodSecurityContext(fsGroup *int64) *corev1.PodSecurityContext {
	context := &corev1.PodSecurityContext{
		RunAsNonRoot:   boolPtr(true),
		SeccompProfile: &corev1.SeccompProfile{Type: corev1.SeccompProfileTypeRuntimeDefault},
	}
	if fsGroup != nil {
		context.FSGroup = fsGroup
		policy := corev1.FSGroupChangeOnRootMismatch
		context.FSGroupChangePolicy = &policy
	}
	return context
}

func restrictedContainerSecurityContext() *corev1.SecurityContext {
	return &corev1.SecurityContext{
		AllowPrivilegeEscalation: boolPtr(false),
		ReadOnlyRootFilesystem:   boolPtr(true),
		Capabilities: &corev1.Capabilities{
			Drop: []corev1.Capability{"ALL"},
		},
	}
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

func (r *WorkspaceReconciler) setWorkspaceControllerReference(
	workspace *workspacev1alpha1.Workspace,
	obj client.Object,
) error {
	if workspace.Namespace != obj.GetNamespace() {
		return fmt.Errorf(
			"managed object namespace %q must match Workspace namespace %q",
			obj.GetNamespace(),
			workspace.Namespace,
		)
	}
	return controllerutil.SetControllerReference(workspace, obj, r.Scheme)
}
