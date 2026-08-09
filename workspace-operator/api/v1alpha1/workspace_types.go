package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

type WorkspaceResourceSpec struct {
	Image             string                        `json:"image"`
	Resources         *corev1.ResourceRequirements  `json:"resources,omitempty"`
	Assertion         WorkspaceRuntimeAssertionSpec `json:"assertion"`
	RuntimeSecretName string                        `json:"runtimeSecretName"`
	DesiredState      string                        `json:"desiredState"`
	InstanceID        string                        `json:"instanceId"`
	Revision          int64                         `json:"revision"`
	MountRevision     int64                         `json:"mountRevision"`
	AccessRevision    int64                         `json:"accessRevision"`
}

type WorkspaceRuntimeAssertionSpec struct {
	Issuer                 string `json:"issuer"`
	PublicKeySetSecretName string `json:"publicKeySetSecretName"`
}

type WorkspaceOptionalComponentSpec struct {
	Enabled              bool                         `json:"enabled,omitempty"`
	DesiredState         string                       `json:"desiredState"`
	InstanceID           string                       `json:"instanceId"`
	Revision             int64                        `json:"revision"`
	Image                string                       `json:"image"`
	Resources            *corev1.ResourceRequirements `json:"resources,omitempty"`
	CredentialSecretName string                       `json:"credentialSecretName,omitempty"`
	CredentialRevision   int64                        `json:"credentialRevision,omitempty"`
	CredentialKeyID      string                       `json:"credentialKeyId,omitempty"`
	CredentialAlgorithm  string                       `json:"credentialAlgorithm,omitempty"`
}

type WorkspaceBootstrapSpec struct {
	Revision int64 `json:"revision"`
}

type WorkspaceGitSpec struct {
	URL    string `json:"url,omitempty"`
	Branch string `json:"branch,omitempty"`
}

type WorkspaceEnvVar struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

type WorkspaceKnowledgeBaseAttachment struct {
	KBID  string `json:"kbId"`
	Alias string `json:"alias"`
}

type WorkspaceFirewallEgressMode string

const (
	WorkspaceFirewallEgressModeBlocked      WorkspaceFirewallEgressMode = "blocked"
	WorkspaceFirewallEgressModeAllowlist    WorkspaceFirewallEgressMode = "allowlist"
	WorkspaceFirewallEgressModeUnrestricted WorkspaceFirewallEgressMode = "unrestricted"
)

// +kubebuilder:validation:XValidation:rule="self.egressMode == 'allowlist' || size(self.allowedDomains) == 0",message="allowedDomains must be empty unless egressMode is allowlist"
// +kubebuilder:validation:XValidation:rule="self.egressMode != 'allowlist' || size(self.allowedDomains) > 0",message="allowedDomains must contain at least one hostname when egressMode is allowlist"
type WorkspaceFirewallGroupSpec struct {
	// +kubebuilder:validation:Enum=blocked;allowlist;unrestricted
	EgressMode     WorkspaceFirewallEgressMode `json:"egressMode"`
	AllowedDomains []string                    `json:"allowedDomains"`
}

type WorkspaceFirewallSpec struct {
	Revision  int64                      `json:"revision"`
	Workspace WorkspaceFirewallGroupSpec `json:"workspace"`
	Browser   WorkspaceFirewallGroupSpec `json:"browser"`
}

type WorkspaceStorageCapacitySpec struct {
	// +kubebuilder:validation:Minimum=1
	CapacityBytes int64 `json:"capacityBytes"`
	// +kubebuilder:validation:Minimum=1
	Revision int64 `json:"revision"`
}

type WorkspaceStorageSpec struct {
	WorkspaceData WorkspaceStorageCapacitySpec `json:"workspaceData"`
	RuntimeHome   WorkspaceStorageCapacitySpec `json:"runtimeHome"`
}

type WorkspaceSpec struct {
	WorkspaceID string `json:"workspaceId"`
	OwnerID     string `json:"ownerId"`
	Provisioner string `json:"provisioner"`
	// TargetNamespace is deployment-derived. Empty means metadata.namespace; otherwise it must match metadata.namespace.
	TargetNamespace string                             `json:"targetNamespace,omitempty"`
	Bootstrap       WorkspaceBootstrapSpec             `json:"bootstrap"`
	Runtime         WorkspaceResourceSpec              `json:"runtime"`
	Browser         WorkspaceOptionalComponentSpec     `json:"browser"`
	Canvas          WorkspaceOptionalComponentSpec     `json:"canvas"`
	Git             WorkspaceGitSpec                   `json:"git,omitempty"`
	WorkspacePath   string                             `json:"workspacePath"`
	WorktreeSubdir  string                             `json:"worktreeSubdir"`
	EnvVars         []WorkspaceEnvVar                  `json:"envVars,omitempty"`
	KnowledgeBases  []WorkspaceKnowledgeBaseAttachment `json:"knowledgeBases,omitempty"`
	Firewall        WorkspaceFirewallSpec              `json:"firewall"`
	Storage         WorkspaceStorageSpec               `json:"storage"`
}

const (
	WorkspaceStorageErrorCapacityInvalid      = "STORAGE_CAPACITY_INVALID"
	WorkspaceStorageErrorShrinkUnsupported    = "STORAGE_CAPACITY_SHRINK_UNSUPPORTED"
	WorkspaceStorageErrorExpansionUnsupported = "STORAGE_CLASS_EXPANSION_UNSUPPORTED"
	WorkspaceStorageErrorClassNotFound        = "STORAGE_CLASS_NOT_FOUND"
)

type WorkspaceStorageCapacityStatus struct {
	AllocatedBytes     int64        `json:"allocatedBytes"`
	ObservedRevision   int64        `json:"observedRevision"`
	ExpansionSupported bool         `json:"expansionSupported"`
	ObservedAt         *metav1.Time `json:"observedAt,omitempty"`
	ErrorCode          string       `json:"errorCode,omitempty"`
}

type WorkspaceStorageStatus struct {
	WorkspaceData WorkspaceStorageCapacityStatus `json:"workspaceData,omitempty"`
	RuntimeHome   WorkspaceStorageCapacityStatus `json:"runtimeHome,omitempty"`
}

type WorkspaceComponentStatus struct {
	ObservedInstanceID          string       `json:"observedInstanceId,omitempty"`
	ObservedRevision            int64        `json:"observedRevision"`
	Phase                       string       `json:"phase,omitempty"`
	PodUID                      string       `json:"podUid,omitempty"`
	Ready                       bool         `json:"ready"`
	TerminalReady               bool         `json:"terminalReady,omitempty"`
	Reason                      string       `json:"reason,omitempty"`
	ErrorCode                   string       `json:"errorCode,omitempty"`
	LastTransitionAt            *metav1.Time `json:"lastTransitionTime,omitempty"`
	MountObservedRevision       int64        `json:"mountObservedRevision"`
	LastKnownGoodMountRevision  int64        `json:"lastKnownGoodMountRevision"`
	AccessObservedRevision      int64        `json:"accessObservedRevision"`
	CredentialObservedRevision  int64        `json:"credentialObservedRevision"`
	CredentialObservedKeyID     string       `json:"credentialObservedKeyId,omitempty"`
	CredentialObservedAlgorithm string       `json:"credentialObservedAlgorithm,omitempty"`
}

type WorkspaceComponentsStatus struct {
	Runtime WorkspaceComponentStatus `json:"runtime,omitempty"`
	Browser WorkspaceComponentStatus `json:"browser,omitempty"`
	Canvas  WorkspaceComponentStatus `json:"canvas,omitempty"`
}

type WorkspaceBootstrapStatus struct {
	ObservedRevision int64        `json:"observedRevision"`
	Phase            string       `json:"phase,omitempty"`
	Reason           string       `json:"reason,omitempty"`
	ErrorCode        string       `json:"errorCode,omitempty"`
	LastTransitionAt *metav1.Time `json:"lastTransitionTime,omitempty"`
}

type WorkspaceFirewallStatus struct {
	TargetRevision              int64        `json:"targetRevision"`
	TargetDeliveryID            string       `json:"targetDeliveryId,omitempty"`
	ObservedRevision            int64        `json:"observedRevision"`
	Phase                       string       `json:"phase,omitempty"`
	Reason                      string       `json:"reason,omitempty"`
	ErrorCode                   string       `json:"errorCode,omitempty"`
	WorkspacePolicyName         string       `json:"workspacePolicyName,omitempty"`
	WorkspacePolicyGeneration   int64        `json:"workspacePolicyGeneration,omitempty"`
	RuntimePeerPolicyName       string       `json:"runtimePeerPolicyName,omitempty"`
	RuntimePeerPolicyGeneration int64        `json:"runtimePeerPolicyGeneration,omitempty"`
	BrowserPolicyName           string       `json:"browserPolicyName,omitempty"`
	BrowserPolicyGeneration     int64        `json:"browserPolicyGeneration,omitempty"`
	LastTransitionAt            *metav1.Time `json:"lastTransitionTime,omitempty"`
}

type WorkspaceBrowserConnectivityStatus struct {
	ContractVersion           string       `json:"contractVersion"`
	State                     string       `json:"state,omitempty"`
	Admission                 string       `json:"admission"`
	ObservedBrowserGeneration string       `json:"observedBrowserGeneration,omitempty"`
	ProfileRevision           string       `json:"profileRevision,omitempty"`
	CredentialRevision        string       `json:"credentialRevision,omitempty"`
	BackendState              string       `json:"backendState,omitempty"`
	BackendAcceptedAt         *metav1.Time `json:"backendAcceptedAt,omitempty"`
	BackendExpiresAt          *metav1.Time `json:"backendExpiresAt,omitempty"`
	BackendReason             string       `json:"backendReason,omitempty"`
	BackendErrorCode          string       `json:"backendErrorCode,omitempty"`
	FrontendState             string       `json:"frontendState,omitempty"`
	FrontendAcceptedAt        *metav1.Time `json:"frontendAcceptedAt,omitempty"`
	FrontendExpiresAt         *metav1.Time `json:"frontendExpiresAt,omitempty"`
	FrontendReason            string       `json:"frontendReason,omitempty"`
	FrontendErrorCode         string       `json:"frontendErrorCode,omitempty"`
	AcceptedAt                *metav1.Time `json:"acceptedAt,omitempty"`
	ExpiresAt                 *metav1.Time `json:"expiresAt,omitempty"`
	Reason                    string       `json:"reason,omitempty"`
	ErrorCode                 string       `json:"errorCode,omitempty"`
	LastTransitionAt          *metav1.Time `json:"lastTransitionAt,omitempty"`
}

type WorkspaceStatus struct {
	Phase               string                             `json:"phase,omitempty"`
	ObservedGeneration  int64                              `json:"observedGeneration,omitempty"`
	TargetNamespace     string                             `json:"targetNamespace,omitempty"`
	Bootstrap           WorkspaceBootstrapStatus           `json:"bootstrap,omitempty"`
	Firewall            WorkspaceFirewallStatus            `json:"firewall,omitempty"`
	BrowserConnectivity WorkspaceBrowserConnectivityStatus `json:"browserConnectivity,omitempty"`
	Components          WorkspaceComponentsStatus          `json:"components,omitempty"`
	Storage             WorkspaceStorageStatus             `json:"storage,omitempty"`
	Conditions          []metav1.Condition                 `json:"conditions,omitempty"`
}

type Workspace struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   WorkspaceSpec   `json:"spec,omitempty"`
	Status WorkspaceStatus `json:"status,omitempty"`
}

type WorkspaceList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Workspace `json:"items"`
}

func (in *Workspace) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := new(Workspace)
	*out = *in
	out.TypeMeta = in.TypeMeta
	out.ObjectMeta = *in.ObjectMeta.DeepCopy()
	if in.Spec.EnvVars != nil {
		out.Spec.EnvVars = make([]WorkspaceEnvVar, len(in.Spec.EnvVars))
		copy(out.Spec.EnvVars, in.Spec.EnvVars)
	}
	if in.Spec.KnowledgeBases != nil {
		out.Spec.KnowledgeBases = make([]WorkspaceKnowledgeBaseAttachment, len(in.Spec.KnowledgeBases))
		copy(out.Spec.KnowledgeBases, in.Spec.KnowledgeBases)
	}
	if in.Spec.Runtime.Resources != nil {
		out.Spec.Runtime.Resources = in.Spec.Runtime.Resources.DeepCopy()
	}
	if in.Spec.Browser.Resources != nil {
		out.Spec.Browser.Resources = in.Spec.Browser.Resources.DeepCopy()
	}
	if in.Spec.Canvas.Resources != nil {
		out.Spec.Canvas.Resources = in.Spec.Canvas.Resources.DeepCopy()
	}
	if in.Spec.Firewall.Workspace.AllowedDomains != nil {
		out.Spec.Firewall.Workspace.AllowedDomains = make([]string, len(in.Spec.Firewall.Workspace.AllowedDomains))
		copy(out.Spec.Firewall.Workspace.AllowedDomains, in.Spec.Firewall.Workspace.AllowedDomains)
	}
	if in.Spec.Firewall.Browser.AllowedDomains != nil {
		out.Spec.Firewall.Browser.AllowedDomains = make([]string, len(in.Spec.Firewall.Browser.AllowedDomains))
		copy(out.Spec.Firewall.Browser.AllowedDomains, in.Spec.Firewall.Browser.AllowedDomains)
	}
	if in.Status.Bootstrap.LastTransitionAt != nil {
		out.Status.Bootstrap.LastTransitionAt = in.Status.Bootstrap.LastTransitionAt.DeepCopy()
	}
	if in.Status.Firewall.LastTransitionAt != nil {
		lastTransitionAt := in.Status.Firewall.LastTransitionAt.DeepCopy()
		out.Status.Firewall.LastTransitionAt = lastTransitionAt
	}
	if in.Status.BrowserConnectivity.AcceptedAt != nil {
		out.Status.BrowserConnectivity.AcceptedAt = in.Status.BrowserConnectivity.AcceptedAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.ExpiresAt != nil {
		out.Status.BrowserConnectivity.ExpiresAt = in.Status.BrowserConnectivity.ExpiresAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.BackendAcceptedAt != nil {
		out.Status.BrowserConnectivity.BackendAcceptedAt = in.Status.BrowserConnectivity.BackendAcceptedAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.BackendExpiresAt != nil {
		out.Status.BrowserConnectivity.BackendExpiresAt = in.Status.BrowserConnectivity.BackendExpiresAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.FrontendAcceptedAt != nil {
		out.Status.BrowserConnectivity.FrontendAcceptedAt = in.Status.BrowserConnectivity.FrontendAcceptedAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.FrontendExpiresAt != nil {
		out.Status.BrowserConnectivity.FrontendExpiresAt = in.Status.BrowserConnectivity.FrontendExpiresAt.DeepCopy()
	}
	if in.Status.BrowserConnectivity.LastTransitionAt != nil {
		out.Status.BrowserConnectivity.LastTransitionAt = in.Status.BrowserConnectivity.LastTransitionAt.DeepCopy()
	}
	if in.Status.Components.Runtime.LastTransitionAt != nil {
		out.Status.Components.Runtime.LastTransitionAt = in.Status.Components.Runtime.LastTransitionAt.DeepCopy()
	}
	if in.Status.Components.Browser.LastTransitionAt != nil {
		out.Status.Components.Browser.LastTransitionAt = in.Status.Components.Browser.LastTransitionAt.DeepCopy()
	}
	if in.Status.Components.Canvas.LastTransitionAt != nil {
		out.Status.Components.Canvas.LastTransitionAt = in.Status.Components.Canvas.LastTransitionAt.DeepCopy()
	}
	if in.Status.Storage.WorkspaceData.ObservedAt != nil {
		out.Status.Storage.WorkspaceData.ObservedAt = in.Status.Storage.WorkspaceData.ObservedAt.DeepCopy()
	}
	if in.Status.Storage.RuntimeHome.ObservedAt != nil {
		out.Status.Storage.RuntimeHome.ObservedAt = in.Status.Storage.RuntimeHome.ObservedAt.DeepCopy()
	}
	if in.Status.Conditions != nil {
		out.Status.Conditions = make([]metav1.Condition, len(in.Status.Conditions))
		copy(out.Status.Conditions, in.Status.Conditions)
	}
	return out
}

func (in *WorkspaceList) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := new(WorkspaceList)
	*out = *in
	out.TypeMeta = in.TypeMeta
	out.ListMeta = in.ListMeta
	if in.Items != nil {
		out.Items = make([]Workspace, len(in.Items))
		for index := range in.Items {
			out.Items[index] = *in.Items[index].DeepCopyObject().(*Workspace)
		}
	}
	return out
}

func init() {
	SchemeBuilder.Register(&Workspace{}, &WorkspaceList{})
}
