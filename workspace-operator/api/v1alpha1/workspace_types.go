package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

type WorkspaceResourceSpec struct {
	ImageKey  string                        `json:"imageKey,omitempty"`
	Image     string                        `json:"image,omitempty"`
	Resources *corev1.ResourceRequirements `json:"resources,omitempty"`
}

type WorkspaceOptionalComponentSpec struct {
	Enabled   bool                           `json:"enabled,omitempty"`
	Image     string                         `json:"image,omitempty"`
	Resources *corev1.ResourceRequirements  `json:"resources,omitempty"`
}

type WorkspaceGitSpec struct {
	URL    string `json:"url,omitempty"`
	Branch string `json:"branch,omitempty"`
}

type WorkspaceEnvVar struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

type WorkspacePortMapping struct {
	ContainerPort int32  `json:"containerPort"`
	HostPort      *int32 `json:"hostPort,omitempty"`
	Protocol      string `json:"protocol"`
	Description   string `json:"description,omitempty"`
}

type WorkspaceOperationsSpec struct {
	RestartWorkspaceAt *metav1.Time `json:"restartWorkspaceAt,omitempty"`
	RestartRuntimeAt   *metav1.Time `json:"restartRuntimeAt,omitempty"`
	RestartBrowserAt   *metav1.Time `json:"restartBrowserAt,omitempty"`
	RestartNextjsAt    *metav1.Time `json:"restartNextjsAt,omitempty"`
}

type WorkspaceFirewallGroupSpec struct {
	NetworkAccessEnabled bool     `json:"networkAccessEnabled"`
	DomainAccessMode     string   `json:"domainAccessMode"`
	AllowedDomains       []string `json:"allowedDomains"`
}

type WorkspaceFirewallSpec struct {
	Workspace WorkspaceFirewallGroupSpec `json:"workspace"`
	Browser   WorkspaceFirewallGroupSpec `json:"browser"`
}

type WorkspaceSpec struct {
	WorkspaceID     string                         `json:"workspaceId"`
	OwnerID         string                         `json:"ownerId"`
	Provisioner     string                         `json:"provisioner"`
	TargetNamespace string                         `json:"targetNamespace,omitempty"`
	Runtime         WorkspaceResourceSpec          `json:"runtime"`
	Browser         WorkspaceOptionalComponentSpec `json:"browser"`
	Nextjs          WorkspaceOptionalComponentSpec `json:"nextjs"`
	Git             WorkspaceGitSpec               `json:"git,omitempty"`
	WorkspacePath   string                         `json:"workspacePath"`
	EnvVars         []WorkspaceEnvVar              `json:"envVars,omitempty"`
	PortMappings    []WorkspacePortMapping         `json:"portMappings,omitempty"`
	Operations      WorkspaceOperationsSpec        `json:"operations,omitempty"`
	Firewall        WorkspaceFirewallSpec          `json:"firewall"`
}

type WorkspaceComponentStatus struct {
	Phase           string       `json:"phase,omitempty"`
	InternalURL     string       `json:"internalUrl,omitempty"`
	ExternalURL     string       `json:"externalUrl,omitempty"`
	LastRestartedAt *metav1.Time `json:"lastRestartedAt,omitempty"`
}

type WorkspaceComponentsStatus struct {
	Runtime WorkspaceComponentStatus `json:"runtime,omitempty"`
	Browser WorkspaceComponentStatus `json:"browser,omitempty"`
	Nextjs  WorkspaceComponentStatus `json:"nextjs,omitempty"`
}

type WorkspaceFirewallGroupStatus struct {
	EffectiveAllowedDomains []string `json:"effectiveAllowedDomains,omitempty"`
}

type WorkspaceFirewallStatus struct {
	Workspace WorkspaceFirewallGroupStatus `json:"workspace,omitempty"`
	Browser   WorkspaceFirewallGroupStatus `json:"browser,omitempty"`
}

type WorkspaceStatus struct {
	Phase              string                    `json:"phase,omitempty"`
	ObservedGeneration int64                     `json:"observedGeneration,omitempty"`
	TargetNamespace    string                    `json:"targetNamespace,omitempty"`
	Components         WorkspaceComponentsStatus `json:"components,omitempty"`
	Firewall           WorkspaceFirewallStatus   `json:"firewall,omitempty"`
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
		copy(out.Items, in.Items)
	}
	return out
}

func init() {
	SchemeBuilder.Register(&Workspace{}, &WorkspaceList{})
}
