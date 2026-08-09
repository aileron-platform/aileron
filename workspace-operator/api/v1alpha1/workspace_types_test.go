package v1alpha1

import (
	"encoding/json"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func TestWorkspaceFirewallGroupSpecUsesEgressModeContract(t *testing.T) {
	payload, err := json.Marshal(WorkspaceFirewallGroupSpec{
		EgressMode:     WorkspaceFirewallEgressModeAllowlist,
		AllowedDomains: []string{"api.example.com"},
	})
	if err != nil {
		t.Fatalf("marshal firewall group: %v", err)
	}

	var group map[string]any
	if err := json.Unmarshal(payload, &group); err != nil {
		t.Fatalf("unmarshal firewall group: %v", err)
	}
	if group["egressMode"] != string(WorkspaceFirewallEgressModeAllowlist) {
		t.Fatalf("egressMode = %v, want %q", group["egressMode"], WorkspaceFirewallEgressModeAllowlist)
	}
	for _, legacyField := range []string{"networkAccessEnabled", "domainAccessMode"} {
		if _, found := group[legacyField]; found {
			t.Fatalf("legacy field %q must not be serialized", legacyField)
		}
	}
}

func TestWorkspaceComponentStatusSerializesZeroObservedRevisions(t *testing.T) {
	payload, err := json.Marshal(WorkspaceComponentStatus{})
	if err != nil {
		t.Fatalf("marshal component status: %v", err)
	}

	var status map[string]any
	if err := json.Unmarshal(payload, &status); err != nil {
		t.Fatalf("unmarshal component status: %v", err)
	}
	for _, field := range []string{
		"observedRevision",
		"mountObservedRevision",
		"accessObservedRevision",
		"credentialObservedRevision",
	} {
		value, ok := status[field]
		if !ok {
			t.Fatalf("%s must be serialized when its value is zero", field)
		}
		if value != float64(0) {
			t.Fatalf("%s = %v, want 0", field, value)
		}
	}
	for _, forbiddenField := range []string{"internalUrl", "externalUrl"} {
		if _, found := status[forbiddenField]; found {
			t.Fatalf("component status must not expose %s", forbiddenField)
		}
	}
}

func TestWorkspaceDeepCopyKeepsLifecycleStateIndependent(t *testing.T) {
	transition := metav1.NewTime(time.Unix(1_700_000_000, 0))
	workspace := &Workspace{
		Spec: WorkspaceSpec{
			Storage: WorkspaceStorageSpec{
				WorkspaceData: WorkspaceStorageCapacitySpec{CapacityBytes: 21_474_836_480, Revision: 1},
				RuntimeHome:   WorkspaceStorageCapacitySpec{CapacityBytes: 2_147_483_648, Revision: 1},
			},
			Runtime: WorkspaceResourceSpec{
				Resources: &corev1.ResourceRequirements{
					Requests: corev1.ResourceList{
						corev1.ResourceMemory: resource.MustParse("1Gi"),
					},
				},
			},
			Firewall: WorkspaceFirewallSpec{
				Workspace: WorkspaceFirewallGroupSpec{
					EgressMode:     WorkspaceFirewallEgressModeAllowlist,
					AllowedDomains: []string{"api.example.com"},
				},
			},
		},
		Status: WorkspaceStatus{
			Storage: WorkspaceStorageStatus{
				WorkspaceData: WorkspaceStorageCapacityStatus{ObservedAt: &transition},
				RuntimeHome:   WorkspaceStorageCapacityStatus{ObservedAt: &transition},
			},
			Bootstrap: WorkspaceBootstrapStatus{LastTransitionAt: &transition},
			Firewall: WorkspaceFirewallStatus{
				TargetDeliveryID: "delivery-1",
			},
			Components: WorkspaceComponentsStatus{
				Runtime: WorkspaceComponentStatus{LastTransitionAt: &transition},
			},
			Conditions: []metav1.Condition{{
				Type:   "RuntimeReady",
				Status: metav1.ConditionTrue,
				Reason: "RuntimeReady",
			}},
		},
	}

	copied := workspace.DeepCopyObject().(*Workspace)
	copied.Spec.Runtime.Resources.Requests[corev1.ResourceMemory] = resource.MustParse("2Gi")
	copied.Spec.Firewall.Workspace.AllowedDomains[0] = "changed.example.com"
	copied.Status.Bootstrap.LastTransitionAt.Time = time.Unix(1_800_000_000, 0)
	copied.Status.Storage.WorkspaceData.ObservedAt.Time = time.Unix(1_800_000_000, 0)
	copied.Status.Storage.RuntimeHome.ObservedAt.Time = time.Unix(1_900_000_000, 0)
	copied.Status.Firewall.TargetDeliveryID = "delivery-2"
	copied.Status.Components.Runtime.LastTransitionAt.Time = time.Unix(1_900_000_000, 0)
	copied.Status.Conditions[0].Reason = "Changed"

	if actual := workspace.Spec.Runtime.Resources.Requests.Memory().String(); actual != "1Gi" {
		t.Fatalf("source resources changed through deep copy: %s", actual)
	}
	if workspace.Spec.Firewall.Workspace.AllowedDomains[0] != "api.example.com" {
		t.Fatal("source firewall domains changed through deep copy")
	}
	if workspace.Status.Bootstrap.LastTransitionAt.Unix() != 1_700_000_000 {
		t.Fatal("source bootstrap transition time changed through deep copy")
	}
	if workspace.Status.Storage.WorkspaceData.ObservedAt.Unix() != 1_700_000_000 {
		t.Fatal("source workspace data observation time changed through deep copy")
	}
	if workspace.Status.Storage.RuntimeHome.ObservedAt.Unix() != 1_700_000_000 {
		t.Fatal("source runtime home observation time changed through deep copy")
	}
	if workspace.Status.Firewall.TargetDeliveryID != "delivery-1" {
		t.Fatal("source firewall delivery identity changed through deep copy")
	}
	if workspace.Status.Components.Runtime.LastTransitionAt.Unix() != 1_700_000_000 {
		t.Fatal("source component transition time changed through deep copy")
	}
	if workspace.Status.Conditions[0].Reason != "RuntimeReady" {
		t.Fatal("source condition changed through deep copy")
	}
}

func TestWorkspaceStorageContractUsesIntegerBytesAndStableFields(t *testing.T) {
	observedAt := metav1.NewTime(time.Unix(1_700_000_000, 0).UTC())
	workspace := Workspace{
		Spec: WorkspaceSpec{
			Storage: WorkspaceStorageSpec{
				WorkspaceData: WorkspaceStorageCapacitySpec{CapacityBytes: 21_474_836_480, Revision: 7},
				RuntimeHome:   WorkspaceStorageCapacitySpec{CapacityBytes: 2_147_483_648, Revision: 3},
			},
		},
		Status: WorkspaceStatus{
			Storage: WorkspaceStorageStatus{
				WorkspaceData: WorkspaceStorageCapacityStatus{
					AllocatedBytes:     17_179_869_184,
					ObservedRevision:   7,
					ExpansionSupported: true,
					ObservedAt:         &observedAt,
				},
				RuntimeHome: WorkspaceStorageCapacityStatus{
					AllocatedBytes:     2_147_483_648,
					ObservedRevision:   3,
					ExpansionSupported: false,
					ObservedAt:         &observedAt,
					ErrorCode:          WorkspaceStorageErrorExpansionUnsupported,
				},
			},
		},
	}

	payload, err := json.Marshal(workspace)
	if err != nil {
		t.Fatalf("marshal workspace storage contract: %v", err)
	}

	var wire map[string]any
	if err := json.Unmarshal(payload, &wire); err != nil {
		t.Fatalf("unmarshal workspace storage contract: %v", err)
	}
	spec := wire["spec"].(map[string]any)["storage"].(map[string]any)
	if spec["workspaceData"].(map[string]any)["capacityBytes"] != float64(21_474_836_480) {
		t.Fatalf("workspaceData.capacityBytes = %v", spec["workspaceData"])
	}
	if spec["workspaceData"].(map[string]any)["revision"] != float64(7) {
		t.Fatalf("workspaceData.revision = %v", spec["workspaceData"])
	}
	status := wire["status"].(map[string]any)["storage"].(map[string]any)
	workspaceData := status["workspaceData"].(map[string]any)
	for _, field := range []string{
		"allocatedBytes",
		"observedRevision",
		"expansionSupported",
		"observedAt",
	} {
		if _, ok := workspaceData[field]; !ok {
			t.Fatalf("workspaceData status does not serialize %q", field)
		}
	}
	for _, removed := range []string{"requestedBytes", "phase"} {
		if _, ok := workspaceData[removed]; ok {
			t.Fatalf("workspaceData status unexpectedly serializes %q", removed)
		}
	}
}

func TestWorkspaceListDeepCopyKeepsStorageObservationIndependent(t *testing.T) {
	observedAt := metav1.NewTime(time.Unix(1_700_000_000, 0).UTC())
	list := &WorkspaceList{Items: []Workspace{{
		Status: WorkspaceStatus{Storage: WorkspaceStorageStatus{
			WorkspaceData: WorkspaceStorageCapacityStatus{ObservedAt: &observedAt},
		}},
	}}}

	copied := list.DeepCopyObject().(*WorkspaceList)
	copied.Items[0].Status.Storage.WorkspaceData.ObservedAt.Time = time.Unix(1_800_000_000, 0)

	if list.Items[0].Status.Storage.WorkspaceData.ObservedAt.Unix() != 1_700_000_000 {
		t.Fatal("source list storage observation changed through deep copy")
	}
}
