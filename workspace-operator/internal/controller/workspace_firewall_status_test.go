package controller

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const (
	testFirewallDeliveryID    = "delivery-7"
	testAttestationDeliveryID = "delivery-8"
	testAttestationRevision   = int64(8)
)

func TestFirewallDeliveryMarkersAreUniquePerTopLevelRule(t *testing.T) {
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	firstRule, _, err := unstructured.NestedMap(policy.Object, "spec")
	if err != nil {
		t.Fatal(err)
	}
	secondRule := runtime.DeepCopyJSONValue(firstRule).(map[string]interface{})
	delete(policy.Object, "spec")
	if err := unstructured.SetNestedSlice(
		policy.Object,
		[]interface{}{firstRule, secondRule},
		"specs",
	); err != nil {
		t.Fatal(err)
	}
	if err := setFirewallPolicyDeliveryMarkers(
		policy,
		types.UID("workspace-uid"),
		testAttestationRevision,
		testAttestationDeliveryID,
	); err != nil {
		t.Fatalf("set delivery markers: %v", err)
	}

	markers, err := policyDeliveryMarkers(policy)
	if err != nil {
		t.Fatalf("read delivery markers: %v", err)
	}
	if len(markers) != 2 || markers[0] == markers[1] {
		t.Fatalf("delivery markers = %v", markers)
	}
	policyLabels := []interface{}{
		"k8s:io.cilium.k8s.policy.name=" + policy.GetName(),
		"k8s:io.cilium.k8s.policy.namespace=" + policy.GetNamespace(),
		"k8s:io.cilium.k8s.policy.uid=" + string(policy.GetUID()),
	}
	realized := map[string]interface{}{
		"l4": map[string]interface{}{
			"egress": []interface{}{
				map[string]interface{}{
					"derived-from-rules": []interface{}{
						append(append([]interface{}{}, policyLabels...), markers[0]),
					},
				},
				map[string]interface{}{
					"derived-from-rules": []interface{}{
						append(append([]interface{}{}, policyLabels...), markers[1]),
					},
				},
			},
		},
	}
	if err := verifyRealizedDeliveryMarkers(realized, policy, markers); err != nil {
		t.Fatalf("all top-level Rule markers were rejected: %v", err)
	}
	realized["l4"].(map[string]interface{})["egress"] =
		realized["l4"].(map[string]interface{})["egress"].([]interface{})[:1]
	if err := verifyRealizedDeliveryMarkers(realized, policy, markers); err == nil {
		t.Fatal("missing top-level Rule marker was accepted")
	}
}

func TestPolicyDeliveryMarkersRejectAnnotationOnlyOrTamperedEvidence(t *testing.T) {
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	if _, err := policyDeliveryMarkers(policy); err != nil {
		t.Fatalf("valid marker rejected: %v", err)
	}

	spec, _, _ := unstructured.NestedMap(policy.Object, "spec")
	delete(spec, "labels")
	_ = unstructured.SetNestedMap(policy.Object, spec, "spec")
	if _, err := policyDeliveryMarkers(policy); err == nil {
		t.Fatal("annotation-only delivery identity was accepted")
	}
}

func TestEvaluateFirewallPolicyAttestationRequiresExactFreshEndpointEvidence(t *testing.T) {
	now := time.Date(2026, 7, 24, 8, 0, 0, 0, time.UTC)
	workspace := testAttestationWorkspace()
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	pod := testAttestationPod()
	endpoint := testAttestationCiliumEndpoint()
	attestation := testValidFirewallAttestation(t, policy, pod, endpoint, now)
	setPolicyAttestation(t, policy, attestation)

	reconciler := testAttestationReconciler(t, pod, endpoint)
	evaluation := reconciler.evaluateFirewallPolicyAttestations(
		context.Background(),
		workspace,
		"team-a",
		now,
		policy,
	)
	if evaluation.Phase != "Applied" {
		t.Fatalf("evaluation = %+v", evaluation)
	}

	t.Run("status nodes and CEP enforcing are never fallback truth", func(t *testing.T) {
		withoutEvidence := policy.DeepCopy()
		withoutEvidence.SetAnnotations(map[string]string{
			firewallRevisionAnnotation:   "8",
			firewallDeliveryIDAnnotation: testAttestationDeliveryID,
			workspaceResourceAnnotation:  "workspace-a",
		})
		_ = unstructured.SetNestedMap(
			withoutEvidence.Object,
			map[string]interface{}{
				"node-a": map[string]interface{}{
					"ok":                  true,
					"enforcing":           true,
					"localPolicyRevision": int64(8),
				},
			},
			"status",
			"nodes",
		)
		_ = unstructured.SetNestedField(
			endpoint.Object,
			true,
			"status",
			"policy",
			"egress",
			"enforcing",
		)
		evaluation := reconciler.evaluateFirewallPolicyAttestations(
			context.Background(),
			workspace,
			"team-a",
			now,
			withoutEvidence,
		)
		if evaluation.Phase != "Applying" {
			t.Fatalf("legacy fallback produced %+v", evaluation)
		}
	})

	t.Run("expired evidence revokes Applied", func(t *testing.T) {
		evaluation := reconciler.evaluateFirewallPolicyAttestations(
			context.Background(),
			workspace,
			"team-a",
			now.Add(defaultFirewallAttestationMaxAge+time.Second),
			policy,
		)
		if evaluation.Phase != "Applying" || !strings.Contains(evaluation.Detail, "stale") {
			t.Fatalf("expired evaluation = %+v", evaluation)
		}
	})

	t.Run("new Pod UID cannot reuse old evidence", func(t *testing.T) {
		replacement := pod.DeepCopy()
		replacement.UID = types.UID("pod-uid-new")
		replacementReconciler := testAttestationReconciler(t, replacement, endpoint)
		evaluation := replacementReconciler.evaluateFirewallPolicyAttestations(
			context.Background(),
			workspace,
			"team-a",
			now,
			policy,
		)
		if evaluation.Phase != "Applying" {
			t.Fatalf("replacement Pod reused evidence: %+v", evaluation)
		}
	})

	t.Run("empty delivery never applies", func(t *testing.T) {
		emptyDelivery := workspace.DeepCopyObject().(*workspacev1alpha1.Workspace)
		delete(emptyDelivery.Annotations, firewallDeliveryIDAnnotation)
		emptyDelivery.Status.Firewall.TargetDeliveryID = ""
		evaluation := reconciler.evaluateFirewallPolicyAttestations(
			context.Background(),
			emptyDelivery,
			"team-a",
			now,
			policy,
		)
		if evaluation.Phase != "Applying" {
			t.Fatalf("empty delivery evaluation = %+v", evaluation)
		}
	})
}

func TestAttestorUsesOnlyRealizedPolicyAndRequiresAllExactMarkers(t *testing.T) {
	now := time.Date(2026, 7, 24, 8, 0, 0, 0, time.UTC)
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	pod := testAttestationPod()
	endpoint := testAttestationCiliumEndpoint()
	markers, err := policyDeliveryMarkers(policy)
	if err != nil {
		t.Fatal(err)
	}
	realizedLabels := []interface{}{
		"k8s:io.cilium.k8s.policy.name=" + policy.GetName(),
		"k8s:io.cilium.k8s.policy.namespace=" + policy.GetNamespace(),
		"k8s:io.cilium.k8s.policy.uid=" + string(policy.GetUID()),
		markers[0],
	}
	agentEndpoint := ciliumAgentEndpoint{
		ID: 101,
		Status: map[string]interface{}{
			"state": "ready",
			"external-identifiers": map[string]interface{}{
				"k8s-namespace": "team-a",
				"k8s-pod-name":  pod.Name,
			},
			"policy": map[string]interface{}{
				"spec": map[string]interface{}{
					"policy-revision": int64(999),
				},
				"realized": map[string]interface{}{
					"policy-revision": int64(42),
					"policy-enabled":  "egress",
					"l4": map[string]interface{}{
						"egress": []interface{}{
							map[string]interface{}{
								"derived-from-rules": []interface{}{realizedLabels},
							},
						},
					},
				},
			},
		},
	}
	attestor := &FirewallAttestor{
		NodeName:  "node-a",
		Namespace: "team-a",
		MaxAge:    30 * time.Second,
		Now: func() time.Time {
			return now
		},
	}
	attestation, err := attestor.attestPolicy(
		policy,
		[]corev1.Pod{*pod},
		[]unstructured.Unstructured{*endpoint},
		[]ciliumAgentEndpoint{agentEndpoint},
		"agent-incarnation-a",
	)
	if err != nil {
		t.Fatalf("attest realized policy: %v", err)
	}
	if len(attestation.Endpoints) != 1 ||
		attestation.Endpoints[0].RealizedPolicyRevision != 42 {
		t.Fatalf("attestation = %+v", attestation)
	}

	realized, _ := nestedMap(agentEndpoint.Status, "policy", "realized")
	realizedL4, _ := nestedMap(realized, "l4")
	realizedL4["egress"] = []interface{}{}
	if _, err := attestor.attestPolicy(
		policy,
		[]corev1.Pod{*pod},
		[]unstructured.Unstructured{*endpoint},
		[]ciliumAgentEndpoint{agentEndpoint},
		"agent-incarnation-a",
	); err == nil {
		t.Fatal("policy.spec marker was incorrectly accepted without realized marker")
	}
}

func TestAttestorReadsOnlyTheLocalCiliumAgentEndpointAPI(t *testing.T) {
	socketFile, err := os.CreateTemp("/tmp", "cilium-*.sock")
	if err != nil {
		t.Fatalf("reserve test Unix socket path: %v", err)
	}
	socketPath := socketFile.Name()
	_ = socketFile.Close()
	_ = os.Remove(socketPath)
	t.Cleanup(func() {
		_ = os.Remove(socketPath)
	})
	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		t.Fatalf("listen on test Unix socket: %v", err)
	}
	server := &http.Server{
		Handler: http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			if request.Method != http.MethodGet || request.URL.Path != "/v1/endpoint" {
				http.Error(writer, "unexpected request", http.StatusBadRequest)
				return
			}
			writer.Header().Set("Content-Type", "application/json")
			_, _ = writer.Write([]byte(
				`[{"id":101,"status":{"state":"ready","policy":{"realized":{"policy-revision":42}}}}]`,
			))
		}),
	}
	go func() {
		_ = server.Serve(listener)
	}()
	t.Cleanup(func() {
		_ = server.Shutdown(context.Background())
	})

	attestor := &FirewallAttestor{
		SocketPath:   socketPath,
		PollInterval: time.Second,
	}
	endpoints, incarnation, err := attestor.readAgentEndpoints(context.Background())
	if err != nil {
		t.Fatalf("read local agent endpoints: %v", err)
	}
	if incarnation == "" || len(endpoints) != 1 || endpoints[0].ID != 101 {
		t.Fatalf("agent observation = %+v, incarnation=%q", endpoints, incarnation)
	}
}

func TestAttestorRevokesEvidenceAndRestartsWhenAgentUnavailable(t *testing.T) {
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	attestation := testValidFirewallAttestation(
		t,
		policy,
		testAttestationPod(),
		testAttestationCiliumEndpoint(),
		time.Now(),
	)
	setPolicyAttestation(t, policy, attestation)
	scheme := testControllerScheme(t)
	kubernetesClient := fake.NewClientBuilder().
		WithScheme(scheme).
		WithRuntimeObjects(policy).
		Build()
	attestor := &FirewallAttestor{
		Client:       kubernetesClient,
		NodeName:     "node-a",
		Namespace:    "team-a",
		SocketPath:   t.TempDir() + "/missing.sock",
		PollInterval: time.Second,
		MaxAge:       30 * time.Second,
	}

	err := attestor.reconcile(context.Background())
	if !errors.Is(err, errCiliumAgentUnavailable) {
		t.Fatalf("reconcile error = %v", err)
	}
	updated := newCiliumNetworkPolicy("team-a", policy.GetName())
	if err := kubernetesClient.Get(
		context.Background(),
		client.ObjectKeyFromObject(updated),
		updated,
	); err != nil {
		t.Fatalf("get updated policy: %v", err)
	}
	if updated.GetAnnotations()[firewallAttestationAnnotationKey("node-a")] != "" {
		t.Fatal("unavailable agent evidence was not revoked")
	}
}

func TestSetFirewallPolicyMetadataPreservesOnlyCurrentTargetAttestations(t *testing.T) {
	workspace := testAttestationWorkspace()
	policy := testAttestationPolicy(t, "policy-a", map[string]string{"app": "runtime"})
	key := firewallAttestationAnnotationKey("node-a")
	annotations := policy.GetAnnotations()
	annotations[key] = `{"version":"v1"}`
	policy.SetAnnotations(annotations)
	reconciler := &WorkspaceReconciler{Scheme: testControllerScheme(t)}

	if err := reconciler.setFirewallPolicyMetadata(workspace, policy); err != nil {
		t.Fatalf("preserve current target: %v", err)
	}
	if policy.GetAnnotations()[key] == "" {
		t.Fatal("current target attestation was deleted")
	}

	workspace.Annotations[firewallDeliveryIDAnnotation] = "delivery-9"
	if err := reconciler.setFirewallPolicyMetadata(workspace, policy); err != nil {
		t.Fatalf("replace target: %v", err)
	}
	if policy.GetAnnotations()[key] != "" {
		t.Fatal("stale target attestation was preserved")
	}
}

func TestExpiredApplyingEvidenceTimesOut(t *testing.T) {
	startedAt := metav1.NewTime(time.Now().Add(-firewallPolicyEnforcementTimeout))
	previous := workspacev1alpha1.WorkspaceFirewallStatus{
		TargetRevision:   testAttestationRevision,
		TargetDeliveryID: testAttestationDeliveryID,
		Phase:            "Applying",
		LastTransitionAt: &startedAt,
	}
	evaluation := expireFirewallPolicyApplying(
		previous,
		firewallPolicyApplying("attestation is stale"),
		testAttestationRevision,
		testAttestationDeliveryID,
		time.Now(),
	)
	if evaluation.Phase != "Degraded" ||
		evaluation.ErrorCode != firewallPolicyEnforcementTimeoutCode {
		t.Fatalf("evaluation = %+v", evaluation)
	}
}

func TestAppliedFirewallAlwaysRequeuesBeforeAttestationExpiry(t *testing.T) {
	requeueAfter := firewallEvaluationRequeueAfter(
		true,
		firewallPolicyApplied("FirewallPolicyApplied"),
		30*time.Second,
	)
	if requeueAfter != 15*time.Second {
		t.Fatalf("Applied requeueAfter = %s, want 15s", requeueAfter)
	}
	if disabled := firewallEvaluationRequeueAfter(
		false,
		firewallPolicyApplied("FirewallPolicyDisabled"),
		30*time.Second,
	); disabled != 0 {
		t.Fatalf("disabled firewall requeueAfter = %s, want zero", disabled)
	}
}

func testAttestationWorkspace() *workspacev1alpha1.Workspace {
	return &workspacev1alpha1.Workspace{
		TypeMeta: metav1.TypeMeta{
			APIVersion: workspacev1alpha1.GroupVersion.String(),
			Kind:       "Workspace",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "workspace-a",
			Namespace: "team-a",
			UID:       types.UID("workspace-uid"),
			Annotations: map[string]string{
				firewallDeliveryIDAnnotation: testAttestationDeliveryID,
			},
		},
		Spec: workspacev1alpha1.WorkspaceSpec{
			Runtime: workspacev1alpha1.WorkspaceResourceSpec{DesiredState: "Running"},
			Firewall: workspacev1alpha1.WorkspaceFirewallSpec{
				Revision: testAttestationRevision,
			},
		},
		Status: workspacev1alpha1.WorkspaceStatus{
			Firewall: workspacev1alpha1.WorkspaceFirewallStatus{
				TargetRevision:   testAttestationRevision,
				TargetDeliveryID: testAttestationDeliveryID,
			},
		},
	}
}

func testAttestationPolicy(
	t *testing.T,
	name string,
	selector map[string]string,
) *unstructured.Unstructured {
	t.Helper()
	policy := newCiliumNetworkPolicy("team-a", name)
	policy.SetUID(types.UID("policy-uid"))
	policy.SetGeneration(4)
	policy.SetAnnotations(map[string]string{
		firewallRevisionAnnotation:   "8",
		firewallDeliveryIDAnnotation: testAttestationDeliveryID,
		workspaceResourceAnnotation:  "workspace-a",
	})
	controller := true
	policy.SetOwnerReferences([]metav1.OwnerReference{{
		APIVersion: workspacev1alpha1.GroupVersion.String(),
		Kind:       "Workspace",
		Name:       "workspace-a",
		UID:        types.UID("workspace-uid"),
		Controller: &controller,
	}})
	selectorValues := make(map[string]interface{}, len(selector))
	for key, value := range selector {
		selectorValues[key] = value
	}
	if err := unstructured.SetNestedMap(policy.Object, map[string]interface{}{
		"endpointSelector": map[string]interface{}{
			"matchLabels": selectorValues,
		},
		"egress": []interface{}{
			map[string]interface{}{"toEntities": []interface{}{"world"}},
		},
	}, "spec"); err != nil {
		t.Fatal(err)
	}
	if err := setFirewallPolicyDeliveryMarkers(
		policy,
		types.UID("workspace-uid"),
		testAttestationRevision,
		testAttestationDeliveryID,
	); err != nil {
		t.Fatal(err)
	}
	return policy
}

func testAttestationPod() *corev1.Pod {
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "runtime-a",
			Namespace: "team-a",
			UID:       types.UID("pod-uid"),
			Labels:    map[string]string{"app": "runtime"},
		},
		Spec: corev1.PodSpec{NodeName: "node-a"},
		Status: corev1.PodStatus{
			Phase: corev1.PodRunning,
		},
	}
}

func testAttestationCiliumEndpoint() *unstructured.Unstructured {
	endpoint := &unstructured.Unstructured{}
	endpoint.SetGroupVersionKind(ciliumEndpointGVK)
	endpoint.SetName("runtime-a")
	endpoint.SetNamespace("team-a")
	endpoint.SetUID(types.UID("cep-uid"))
	_ = unstructured.SetNestedField(endpoint.Object, int64(101), "status", "id")
	return endpoint
}

func testValidFirewallAttestation(
	t *testing.T,
	policy *unstructured.Unstructured,
	pod *corev1.Pod,
	endpoint *unstructured.Unstructured,
	now time.Time,
) firewallPolicyAttestation {
	t.Helper()
	markers, err := policyDeliveryMarkers(policy)
	if err != nil {
		t.Fatal(err)
	}
	return firewallPolicyAttestation{
		Version:          firewallAttestationVersion,
		NodeName:         "node-a",
		AgentIncarnation: "agent-incarnation-a",
		ObservedAt:       metav1.NewTime(now),
		ExpiresAt:        metav1.NewTime(now.Add(defaultFirewallAttestationMaxAge)),
		PolicyNamespace:  policy.GetNamespace(),
		PolicyName:       policy.GetName(),
		PolicyUID:        policy.GetUID(),
		PolicyGeneration: policy.GetGeneration(),
		TargetRevision:   testAttestationRevision,
		DeliveryID:       testAttestationDeliveryID,
		DeliveryMarkers:  markers,
		Endpoints: []firewallEndpointAttestation{{
			PodName:                pod.Name,
			PodUID:                 pod.UID,
			CiliumEndpointUID:      endpoint.GetUID(),
			EndpointID:             101,
			RealizedPolicyRevision: 42,
		}},
	}
}

func setPolicyAttestation(
	t *testing.T,
	policy *unstructured.Unstructured,
	attestation firewallPolicyAttestation,
) {
	t.Helper()
	encoded, err := json.Marshal(attestation)
	if err != nil {
		t.Fatal(err)
	}
	annotations := policy.GetAnnotations()
	annotations[firewallAttestationAnnotationKey(attestation.NodeName)] = string(encoded)
	policy.SetAnnotations(annotations)
}

func testAttestationReconciler(
	t *testing.T,
	objects ...runtime.Object,
) *WorkspaceReconciler {
	t.Helper()
	scheme := testControllerScheme(t)
	return &WorkspaceReconciler{
		Client: fake.NewClientBuilder().
			WithScheme(scheme).
			WithRuntimeObjects(objects...).
			Build(),
		Scheme: scheme,
	}
}

func testControllerScheme(t *testing.T) *runtime.Scheme {
	t.Helper()
	scheme := runtime.NewScheme()
	if err := corev1.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	if err := workspacev1alpha1.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	return scheme
}

func testFirewallNode(
	name string,
	ready bool,
	unschedulable bool,
	taints []corev1.Taint,
) *corev1.Node {
	conditionStatus := corev1.ConditionFalse
	if ready {
		conditionStatus = corev1.ConditionTrue
	}
	return &corev1.Node{
		ObjectMeta: metav1.ObjectMeta{Name: name},
		Spec: corev1.NodeSpec{
			Unschedulable: unschedulable,
			Taints:        taints,
		},
		Status: corev1.NodeStatus{
			Conditions: []corev1.NodeCondition{{
				Type:   corev1.NodeReady,
				Status: conditionStatus,
			}},
		},
	}
}

func markFirewallPoliciesEnforced(
	t *testing.T,
	kubernetesClient client.Client,
	namespace string,
	revision int64,
	policyNames ...string,
) {
	t.Helper()
	now := time.Now().UTC()
	for index, policyName := range policyNames {
		policy := newCiliumNetworkPolicy(namespace, policyName)
		if err := kubernetesClient.Get(
			context.Background(),
			client.ObjectKeyFromObject(policy),
			policy,
		); err != nil {
			t.Fatalf("get policy %s: %v", policyName, err)
		}
		if policy.GetUID() == "" {
			policy.SetUID(types.UID("policy-uid-" + policyName))
		}
		if policy.GetGeneration() <= 0 {
			policy.SetGeneration(1)
		}
		selectors, err := ciliumPolicyEndpointSelectors(policy)
		if err != nil {
			t.Fatalf("read policy %s selectors: %v", policyName, err)
		}
		podName := "firewall-endpoint-" + strconv.Itoa(index)
		pod := &corev1.Pod{
			ObjectMeta: metav1.ObjectMeta{
				Name:      podName,
				Namespace: namespace,
				UID:       types.UID("pod-uid-" + strconv.Itoa(index)),
				Labels:    selectors[0],
			},
			Spec: corev1.PodSpec{NodeName: "node-a"},
			Status: corev1.PodStatus{
				Phase: corev1.PodRunning,
			},
		}
		if err := kubernetesClient.Create(context.Background(), pod); err != nil {
			t.Fatalf("create policy %s Pod: %v", policyName, err)
		}
		endpointID := int64(100 + index)
		endpoint := &unstructured.Unstructured{}
		endpoint.SetGroupVersionKind(ciliumEndpointGVK)
		endpoint.SetName(podName)
		endpoint.SetNamespace(namespace)
		endpoint.SetUID(types.UID("cep-uid-" + strconv.Itoa(index)))
		_ = unstructured.SetNestedField(endpoint.Object, endpointID, "status", "id")
		if err := kubernetesClient.Create(context.Background(), endpoint); err != nil {
			t.Fatalf("create policy %s CiliumEndpoint: %v", policyName, err)
		}
		markers, err := policyDeliveryMarkers(policy)
		if err != nil {
			t.Fatalf("read policy %s markers: %v", policyName, err)
		}
		attestation := firewallPolicyAttestation{
			Version:          firewallAttestationVersion,
			NodeName:         "node-a",
			AgentIncarnation: "agent-incarnation-a",
			ObservedAt:       metav1.NewTime(now),
			ExpiresAt:        metav1.NewTime(now.Add(defaultFirewallAttestationMaxAge)),
			PolicyNamespace:  namespace,
			PolicyName:       policyName,
			PolicyUID:        policy.GetUID(),
			PolicyGeneration: policy.GetGeneration(),
			TargetRevision:   revision,
			DeliveryID:       testFirewallDeliveryID,
			DeliveryMarkers:  markers,
			Endpoints: []firewallEndpointAttestation{{
				PodName:                podName,
				PodUID:                 pod.UID,
				CiliumEndpointUID:      endpoint.GetUID(),
				EndpointID:             endpointID,
				RealizedPolicyRevision: int64(200 + index),
			}},
		}
		setPolicyAttestation(t, policy, attestation)
		if err := kubernetesClient.Update(context.Background(), policy); err != nil {
			t.Fatalf("update policy %s attestation: %v", policyName, err)
		}
	}
}
