package controller

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

type profileDigestVectorContract struct {
	Vectors []struct {
		Name             string                  `json:"name"`
		Profile          TURNReachabilityProfile `json:"profile"`
		ExpectedRevision string                  `json:"expectedRevision"`
	} `json:"vectors"`
}

func validTURNProfile() TURNReachabilityProfile {
	return TURNReachabilityProfile{
		ContractVersion: BrowserConnectivityContractVersion,
		PolicyBackend:   TURNPolicyBackendCilium,
		Backend: TURNBackendProfile{
			URLs:               []string{"turn:turn.internal.example:3478"},
			ControlDestination: TURNPolicyDestination{Kind: TURNDestinationCiliumEntities, Values: []string{"host", "remote-node"}},
			RelayDestination:   TURNPolicyDestination{Kind: TURNDestinationCIDRs, Values: []string{"192.0.2.0/24"}},
			RelayPortRange:     TURNRelayPortRange{Min: 49160, Max: 49259},
		},
		Frontend:         TURNFrontendProfile{URLs: []string{"turns:turn.example.com:5349"}},
		CredentialIssuer: TURNCredentialIssuerProfile{Kind: "turnRest", SecretRef: "turn-rest", TTLSeconds: 300},
		Evidence:         TURNEvidencePolicy{IntervalSeconds: 30, TTLSeconds: 90, RequiredFrontendVantages: []string{"public-ap-east"}},
	}
}

func turnProfileForTest(serverURL string) *TURNReachabilityProfile {
	profile := validTURNProfile()
	profile.Backend.URLs = []string{serverURL}
	profile.Backend.ControlDestination = TURNPolicyDestination{
		Kind:   TURNDestinationCiliumEntities,
		Values: []string{"host", "remote-node", "kube-apiserver"},
	}
	profile.Backend.RelayDestination = profile.Backend.ControlDestination
	return &profile
}

func TestTURNReachabilityProfileRevisionIsContentAddressed(t *testing.T) {
	first := validTURNProfile()
	second := validTURNProfile()
	if first.Revision() != second.Revision() {
		t.Fatal("equal profiles produced different revisions")
	}
	second.Backend.RelayPortRange.Max++
	if first.Revision() == second.Revision() {
		t.Fatal("data-path change did not change profile revision")
	}
}

func TestTURNReachabilityProfileRevisionMatchesSharedFixture(t *testing.T) {
	raw, err := os.ReadFile("/contracts/browser-connectivity/turn-reachability-profile.json")
	if err != nil {
		t.Fatalf("read shared TURN profile fixture: %v", err)
	}
	profile, err := ParseTURNReachabilityProfile(string(raw))
	if err != nil {
		t.Fatalf("parse shared TURN profile fixture: %v", err)
	}
	if profile.Revision() != "sha256:dec4c3e486c36aa2fb937400a10e28c924f5737b0a7af4e7a94ce94de29c6aaa" {
		t.Fatalf("fixture revision = %s", profile.Revision())
	}
}

func TestTURNReachabilityProfileMatchesSharedDigestVectors(t *testing.T) {
	raw, err := os.ReadFile("/contracts/browser-connectivity/profile-digest-vectors.json")
	if err != nil {
		t.Fatalf("read digest vectors: %v", err)
	}
	var contract profileDigestVectorContract
	if err := json.Unmarshal(raw, &contract); err != nil {
		t.Fatalf("decode digest vectors: %v", err)
	}
	for _, vector := range contract.Vectors {
		t.Run(vector.Name, func(t *testing.T) {
			if err := vector.Profile.Validate(); err != nil {
				t.Fatalf("validate profile: %v", err)
			}
			if revision := vector.Profile.Revision(); revision != vector.ExpectedRevision {
				t.Fatalf("revision = %s, want %s", revision, vector.ExpectedRevision)
			}
		})
	}
}

func TestTURNReachabilityProfileRejectsUnknownContractVersion(t *testing.T) {
	profile := validTURNProfile()
	profile.ContractVersion = "browser-connectivity/v2"
	if err := profile.Validate(); err == nil {
		t.Fatal("unknown contractVersion was accepted")
	}
}

func TestTURNReachabilityProfileRevisionNormalizesSetFields(t *testing.T) {
	first := validTURNProfile()
	first.Backend.ControlDestination.Values = []string{"remote-node", "host", "host"}
	first.Evidence.RequiredFrontendVantages = []string{"z-vantage", "a-vantage", "z-vantage"}
	second := validTURNProfile()
	second.Backend.ControlDestination.Values = []string{"host", "remote-node"}
	second.Evidence.RequiredFrontendVantages = []string{"a-vantage", "z-vantage"}
	if first.Revision() != second.Revision() {
		t.Fatalf("semantic set normalization drifted: %s != %s", first.Revision(), second.Revision())
	}
}

func TestTURNReachabilityProfileRejectsUnsupportedCombinations(t *testing.T) {
	profile := validTURNProfile()
	profile.PolicyBackend = TURNPolicyBackendKubernetes
	if err := profile.Validate(); err == nil {
		t.Fatal("Kubernetes policy accepted Cilium entities")
	}
	profile = validTURNProfile()
	profile.Backend.RelayDestination = TURNPolicyDestination{Kind: TURNDestinationFQDNs, Values: []string{"relay.example.com"}}
	if err := profile.Validate(); err == nil {
		t.Fatal("relay FQDN destination was accepted")
	}
}

func TestBrowserTURNEgressRulesUseExplicitDestinations(t *testing.T) {
	profile := validTURNProfile()
	rules := browserTURNEgressRules(&profile)
	if len(rules) != 2 {
		t.Fatalf("rules = %d, want control and relay rules", len(rules))
	}
	control := rules[0].(map[string]interface{})
	if !reflect.DeepEqual(control["toEntities"], []interface{}{"host", "remote-node"}) {
		t.Fatalf("control destination = %#v", control)
	}
	relay := rules[1].(map[string]interface{})
	if !reflect.DeepEqual(relay["toCIDR"], []interface{}{"192.0.2.0/24"}) {
		t.Fatalf("relay destination = %#v", relay)
	}
}
