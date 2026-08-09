package controller

import (
	"context"
	"fmt"
	"reflect"
	"strings"
	"testing"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

func TestFirewallEgressRulesModes(t *testing.T) {
	reconciler := &WorkspaceReconciler{}
	tests := []struct {
		name      string
		group     workspacev1alpha1.WorkspaceFirewallGroupSpec
		wantWorld bool
		wantFQDNs bool
	}{
		{
			name: "blocked",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
			},
		},
		{
			name: "unrestricted",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeUnrestricted,
			},
			wantWorld: true,
		},
		{
			name: "allowlist",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"example.com"},
			},
			wantFQDNs: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			rules := reconciler.firewallEgressRules(test.group)
			baseRules := reconciler.baseEgressRules(nil)
			if len(rules) < len(baseRules) ||
				!reflect.DeepEqual(rules[:len(baseRules)], baseRules) {
				t.Fatal("firewall rules do not preserve the complete base egress prefix")
			}
			wantRuleCount := len(baseRules)
			if test.wantWorld || test.wantFQDNs {
				wantRuleCount++
			}
			if len(rules) != wantRuleCount {
				t.Fatalf("rule count = %d, want %d", len(rules), wantRuleCount)
			}
			hasWorld := false
			hasFQDNs := false
			for _, rawRule := range rules {
				rule, ok := rawRule.(map[string]interface{})
				if !ok {
					continue
				}
				if _, found := rule["toEntities"]; found {
					hasWorld = true
				}
				if _, found := rule["toFQDNs"]; found {
					hasFQDNs = true
				}
			}
			if hasWorld != test.wantWorld {
				t.Fatalf("world rule = %v, want %v", hasWorld, test.wantWorld)
			}
			if hasFQDNs != test.wantFQDNs {
				t.Fatalf("FQDN rule = %v, want %v", hasFQDNs, test.wantFQDNs)
			}
			if !policyHasDNSRule(rules) {
				t.Fatal("DNS rule is missing TCP/UDP 53 or rules.dns.matchPattern wildcard")
			}
		})
	}
}

func TestRuntimeFirewallEgressRulesDoNotIncludeIdentityProviderDependencies(t *testing.T) {
	reconciler := &WorkspaceReconciler{
		ConfigNamespace: "workspace-system",
	}
	rules := reconciler.runtimeFirewallEgressRules(workspacev1alpha1.WorkspaceFirewallGroupSpec{
		EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
		AllowedDomains: []string{"example.com"},
	})

	if policyHasInternalServiceRule(rules, "workspace-system", "identity-provider") {
		t.Fatal("runtime firewall must not include identity provider egress")
	}
	if policyHasFQDNRule(rules, "identity.example.com") {
		t.Fatal("runtime firewall must not reach an external OIDC issuer")
	}
	if policyHasHostPortRule(rules, "443") {
		t.Fatal("runtime firewall must not add host HTTPS access for OIDC")
	}
	if !policyHasFQDNRule(rules, "example.com") {
		t.Fatal("runtime firewall did not preserve the workspace allowlist FQDN rule")
	}
}

func policyHasFQDNRule(egressEntries []interface{}, expectedDomain string) bool {
	for _, rawRule := range egressEntries {
		rule, ok := rawRule.(map[string]interface{})
		if !ok {
			continue
		}
		fqdnEntries, found, err := unstructured.NestedSlice(rule, "toFQDNs")
		if err != nil || !found {
			continue
		}
		for _, rawEntry := range fqdnEntries {
			entry, ok := rawEntry.(map[string]interface{})
			if ok && entry["matchName"] == expectedDomain {
				return true
			}
		}
	}
	return false
}

func policyHasHostPortRule(egressEntries []interface{}, expectedPort string) bool {
	for _, rawRule := range egressEntries {
		rule, ok := rawRule.(map[string]interface{})
		if !ok {
			continue
		}
		entities, found, err := unstructured.NestedStringSlice(rule, "toEntities")
		if err != nil || !found || len(entities) != 1 || entities[0] != "host" {
			continue
		}
		ports, found, err := unstructured.NestedSlice(rule, "toPorts")
		if err != nil || !found {
			continue
		}
		for _, rawPortRule := range ports {
			portRule, ok := rawPortRule.(map[string]interface{})
			if !ok {
				continue
			}
			portEntries, found, err := unstructured.NestedSlice(portRule, "ports")
			if err != nil || !found {
				continue
			}
			for _, rawPort := range portEntries {
				port, ok := rawPort.(map[string]interface{})
				if ok && port["port"] == expectedPort && port["protocol"] == "TCP" {
					return true
				}
			}
		}
	}
	return false
}

func TestValidateFirewallGroupRequiresCanonicalExactHostnames(t *testing.T) {
	validDomains := make([]string, 128)
	for index := range validDomains {
		validDomains[index] = "host-" + strings.Repeat("a", index%10) + "a.example.com"
	}
	oversizedDomains := make([]string, 128)
	for index := range oversizedDomains {
		oversizedDomains[index] = fmt.Sprintf(
			"host-%d.%s.%s.example.com",
			index,
			strings.Repeat("a", 60),
			strings.Repeat("b", 60),
		)
	}

	tests := []struct {
		name    string
		group   workspacev1alpha1.WorkspaceFirewallGroupSpec
		wantErr bool
	}{
		{
			name: "canonical exact hostnames",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"github.com", "api.github.com"},
			},
		},
		{
			name: "blocked mode",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
			},
		},
		{
			name: "unrestricted mode",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeUnrestricted,
			},
		},
		{
			name: "allowlist mode requires domains",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
			},
			wantErr: true,
		},
		{
			name: "wildcard",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"*.example.com"},
			},
			wantErr: true,
		},
		{
			name: "upper case",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"API.example.com"},
			},
			wantErr: true,
		},
		{
			name: "trailing dot",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"api.example.com."},
			},
			wantErr: true,
		},
		{
			name: "IP address",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"192.0.2.10"},
			},
			wantErr: true,
		},
		{
			name: "duplicate",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: []string{"api.example.com", "api.example.com"},
			},
			wantErr: true,
		},
		{
			name: "invalid mode",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode: "wildcard",
			},
			wantErr: true,
		},
		{
			name: "blocked mode rejects domains",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeBlocked,
				AllowedDomains: []string{"api.example.com"},
			},
			wantErr: true,
		},
		{
			name: "unrestricted mode rejects domains",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeUnrestricted,
				AllowedDomains: []string{"api.example.com"},
			},
			wantErr: true,
		},
		{
			name: "too many domains",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: append(validDomains, "overflow.example.com"),
			},
			wantErr: true,
		},
		{
			name: "total domain bytes too large",
			group: workspacev1alpha1.WorkspaceFirewallGroupSpec{
				EgressMode:     workspacev1alpha1.WorkspaceFirewallEgressModeAllowlist,
				AllowedDomains: oversizedDomains,
			},
			wantErr: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := validateFirewallGroup(test.group)
			if (err != nil) != test.wantErr {
				t.Fatalf("validateFirewallGroup() error = %v, wantErr %v", err, test.wantErr)
			}
		})
	}
}

func TestPersistFirewallErrorDoesNotAdvanceObservedRevision(t *testing.T) {
	scheme := runtime.NewScheme()
	mustAddSchemes(t, scheme)
	workspace := &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "platform.aileron.io/v1alpha1",
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-firewall-error",
			Namespace: "team-a",
			Annotations: map[string]string{
				firewallDeliveryIDAnnotation: testFirewallDeliveryID,
			},
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{Revision: 6},
		},
		Status: workspacev1alpha1.WorkspaceStatus{
			Firewall: workspacev1alpha1.WorkspaceFirewallStatus{
				TargetRevision:            5,
				TargetDeliveryID:          "delivery-7",
				ObservedRevision:          5,
				Phase:                     "Applied",
				WorkspacePolicyGeneration: 3,
			},
		},
	}
	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&workspacev1alpha1.Workspace{}).
		WithObjects(workspace).
		Build()
	reconciler := &WorkspaceReconciler{Client: cl, Scheme: scheme}

	reconciler.persistFirewallError(context.Background(), workspace)

	var updated workspacev1alpha1.Workspace
	if err := cl.Get(context.Background(), types.NamespacedName{
		Name:      workspace.Name,
		Namespace: workspace.Namespace,
	}, &updated); err != nil {
		t.Fatalf("get Workspace: %v", err)
	}
	if updated.Status.Firewall.TargetRevision != 6 ||
		updated.Status.Firewall.TargetDeliveryID != testFirewallDeliveryID ||
		updated.Status.Firewall.ObservedRevision != 5 ||
		updated.Status.Firewall.WorkspacePolicyGeneration != 0 ||
		updated.Status.Firewall.Phase != "Error" ||
		updated.Status.Firewall.ErrorCode != "FIREWALL_POLICY_APPLY_FAILED" {
		t.Fatalf("firewall status advanced failed revision: %+v", updated.Status.Firewall)
	}
}
