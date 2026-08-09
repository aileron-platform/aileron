package controller

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

const (
	firewallEndpointDiscoveryFailedCode  = "FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED"
	firewallPolicyEnforcementTimeoutCode = "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT"
	firewallPolicyRejectedCode           = "FIREWALL_POLICY_REJECTED"
	firewallPolicyStatusInvalidCode      = "FIREWALL_POLICY_STATUS_INVALID"
)

const (
	firewallPolicyEnforcementTimeout    = 2 * time.Minute
	defaultFirewallAttestationMaxAge    = 30 * time.Second
	firewallDeliveryMarkerKey           = "platform.aileron.io/firewall-delivery-marker"
	firewallAttestationAnnotationPrefix = "platform.aileron.io/firewall-attestation-"
	firewallAttestationVersion          = "v1"
)

type firewallPolicyEvaluation struct {
	Phase     string
	Reason    string
	ErrorCode string
	Detail    string
}

type firewallPolicyAttestation struct {
	Version          string                        `json:"version"`
	NodeName         string                        `json:"nodeName"`
	AgentIncarnation string                        `json:"agentIncarnation"`
	ObservedAt       metav1.Time                   `json:"observedAt"`
	ExpiresAt        metav1.Time                   `json:"expiresAt"`
	PolicyNamespace  string                        `json:"policyNamespace"`
	PolicyName       string                        `json:"policyName"`
	PolicyUID        types.UID                     `json:"policyUID"`
	PolicyGeneration int64                         `json:"policyGeneration"`
	TargetRevision   int64                         `json:"targetRevision"`
	DeliveryID       string                        `json:"deliveryID"`
	DeliveryMarkers  []string                      `json:"deliveryMarkers"`
	Endpoints        []firewallEndpointAttestation `json:"endpoints"`
}

type firewallEndpointAttestation struct {
	PodName                string    `json:"podName"`
	PodUID                 types.UID `json:"podUID"`
	CiliumEndpointUID      types.UID `json:"ciliumEndpointUID"`
	EndpointID             int64     `json:"endpointID"`
	RealizedPolicyRevision int64     `json:"realizedPolicyRevision"`
}

type expectedFirewallEndpoint struct {
	PodName           string
	PodUID            types.UID
	NodeName          string
	CiliumEndpointUID types.UID
	EndpointID        int64
}

func firewallPolicyApplied(reason string) firewallPolicyEvaluation {
	return firewallPolicyEvaluation{Phase: "Applied", Reason: reason}
}

func firewallPolicyApplying(detail string) firewallPolicyEvaluation {
	return firewallPolicyEvaluation{
		Phase:  "Applying",
		Reason: "FirewallPolicyAwaitingEnforcement",
		Detail: detail,
	}
}

func firewallPolicyDegraded(reason string, errorCode string, detail string) firewallPolicyEvaluation {
	return firewallPolicyEvaluation{
		Phase:     "Degraded",
		Reason:    reason,
		ErrorCode: errorCode,
		Detail:    detail,
	}
}

func (evaluation firewallPolicyEvaluation) RequiresRequeue() bool {
	return evaluation.Phase != "Applied"
}

func firewallAttestationAnnotationKey(nodeName string) string {
	sum := sha256.Sum256([]byte(nodeName))
	return firewallAttestationAnnotationPrefix + hex.EncodeToString(sum[:16])
}

func firewallDeliveryMarkerValue(
	workspaceUID types.UID,
	policyName string,
	revision int64,
	deliveryID string,
	ruleIndex int,
) string {
	sum := sha256.Sum256([]byte(fmt.Sprintf(
		"%s\x00%s\x00%d\x00%s\x00%d",
		workspaceUID,
		policyName,
		revision,
		deliveryID,
		ruleIndex,
	)))
	return fmt.Sprintf(
		"v1-r%d-i%d-%s",
		revision,
		ruleIndex,
		hex.EncodeToString(sum[:12]),
	)
}

func firewallDeliveryMarkerLabel(value string) string {
	return "k8s:" + firewallDeliveryMarkerKey + "=" + value
}

func setFirewallPolicyDeliveryMarkers(
	policy *unstructured.Unstructured,
	workspaceUID types.UID,
	revision int64,
	deliveryID string,
) error {
	rules, err := ciliumPolicyRules(policy)
	if err != nil {
		return err
	}
	for index := range rules {
		value := firewallDeliveryMarkerValue(
			workspaceUID,
			policy.GetName(),
			revision,
			deliveryID,
			index,
		)
		rules[index]["labels"] = []interface{}{
			map[string]interface{}{
				"key":    firewallDeliveryMarkerKey,
				"value":  value,
				"source": "k8s",
			},
		}
	}
	if len(rules) == 1 {
		if _, found, _ := unstructured.NestedFieldNoCopy(policy.Object, "spec"); found {
			if err := unstructured.SetNestedMap(policy.Object, rules[0], "spec"); err != nil {
				return fmt.Errorf("set delivery marker on policy %s: %w", policy.GetName(), err)
			}
			return nil
		}
	}
	rawRules := make([]interface{}, 0, len(rules))
	for _, rule := range rules {
		rawRules = append(rawRules, rule)
	}
	if err := unstructured.SetNestedSlice(policy.Object, rawRules, "specs"); err != nil {
		return fmt.Errorf("set delivery markers on policy %s: %w", policy.GetName(), err)
	}
	return nil
}

func ciliumPolicyRules(
	policy *unstructured.Unstructured,
) ([]map[string]interface{}, error) {
	specs, found, err := unstructured.NestedSlice(policy.Object, "specs")
	if err != nil {
		return nil, fmt.Errorf("policy %s specs is invalid: %w", policy.GetName(), err)
	}
	if found {
		if len(specs) == 0 {
			return nil, fmt.Errorf("policy %s specs is empty", policy.GetName())
		}
		rules := make([]map[string]interface{}, 0, len(specs))
		for index, rawRule := range specs {
			rule, ok := rawRule.(map[string]interface{})
			if !ok {
				return nil, fmt.Errorf("policy %s specs[%d] is not an object", policy.GetName(), index)
			}
			rules = append(rules, rule)
		}
		return rules, nil
	}

	spec, found, err := unstructured.NestedMap(policy.Object, "spec")
	if err != nil {
		return nil, fmt.Errorf("policy %s spec is invalid: %w", policy.GetName(), err)
	}
	if !found {
		return nil, fmt.Errorf("policy %s has no top-level Rule", policy.GetName())
	}
	return []map[string]interface{}{spec}, nil
}

func policyDeliveryMarkers(policy *unstructured.Unstructured) ([]string, error) {
	annotations := policy.GetAnnotations()
	revision, err := strconv.ParseInt(annotations[firewallRevisionAnnotation], 10, 64)
	if err != nil {
		return nil, fmt.Errorf("policy %s firewall revision is invalid", policy.GetName())
	}
	deliveryID := annotations[firewallDeliveryIDAnnotation]
	workspaceUID, err := policyWorkspaceUID(policy)
	if err != nil {
		return nil, err
	}
	rules, err := ciliumPolicyRules(policy)
	if err != nil {
		return nil, err
	}

	markers := make([]string, 0, len(rules))
	seen := make(map[string]struct{}, len(rules))
	for index, rule := range rules {
		labels, found, err := unstructured.NestedSlice(rule, "labels")
		if err != nil || !found {
			return nil, fmt.Errorf("policy %s rule %d has no valid delivery labels", policy.GetName(), index)
		}
		values := make([]string, 0, 1)
		for _, rawLabel := range labels {
			label, ok := rawLabel.(map[string]interface{})
			if !ok {
				return nil, fmt.Errorf("policy %s rule %d label is not an object", policy.GetName(), index)
			}
			key, _ := label["key"].(string)
			if key != firewallDeliveryMarkerKey {
				continue
			}
			source, _ := label["source"].(string)
			value, _ := label["value"].(string)
			if source != "k8s" || value == "" {
				return nil, fmt.Errorf("policy %s rule %d delivery marker is invalid", policy.GetName(), index)
			}
			values = append(values, value)
		}
		if len(values) != 1 {
			return nil, fmt.Errorf(
				"policy %s rule %d must contain exactly one delivery marker",
				policy.GetName(),
				index,
			)
		}
		expected := firewallDeliveryMarkerValue(
			workspaceUID,
			policy.GetName(),
			revision,
			deliveryID,
			index,
		)
		if values[0] != expected {
			return nil, fmt.Errorf("policy %s rule %d delivery marker does not match its target", policy.GetName(), index)
		}
		marker := firewallDeliveryMarkerLabel(values[0])
		if _, duplicate := seen[marker]; duplicate {
			return nil, fmt.Errorf("policy %s delivery markers are not unique", policy.GetName())
		}
		seen[marker] = struct{}{}
		markers = append(markers, marker)
	}
	return markers, nil
}

func policyWorkspaceUID(policy *unstructured.Unstructured) (types.UID, error) {
	for _, owner := range policy.GetOwnerReferences() {
		if owner.APIVersion == workspacev1alpha1.GroupVersion.String() &&
			owner.Kind == "Workspace" &&
			owner.UID != "" {
			return owner.UID, nil
		}
	}
	return "", fmt.Errorf("policy %s has no Workspace owner UID", policy.GetName())
}

func (r *WorkspaceReconciler) evaluateFirewallPolicyAttestations(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	now time.Time,
	policies ...*unstructured.Unstructured,
) firewallPolicyEvaluation {
	deliveryID := workspaceFirewallDeliveryID(workspace)
	if strings.TrimSpace(deliveryID) == "" {
		return firewallPolicyApplying("firewall delivery identity is empty")
	}
	if firewallDeliveryObservationPending(workspace) {
		return firewallPolicyApplying("firewall delivery identity has not completed an observation cycle")
	}

	var pods corev1.PodList
	if err := r.List(ctx, &pods, client.InNamespace(namespace)); err != nil {
		return firewallPolicyDegraded(
			"FirewallCiliumEndpointDiscoveryFailed",
			firewallEndpointDiscoveryFailedCode,
			fmt.Sprintf("list Workspace Pods for firewall attestation: %v", err),
		)
	}
	endpoints := &unstructured.UnstructuredList{}
	endpoints.SetGroupVersionKind(ciliumEndpointListGVK)
	if err := r.List(ctx, endpoints, client.InNamespace(namespace)); err != nil {
		return firewallPolicyDegraded(
			"FirewallCiliumEndpointDiscoveryFailed",
			firewallEndpointDiscoveryFailedCode,
			fmt.Sprintf("list CiliumEndpoints for firewall attestation: %v", err),
		)
	}
	endpointsByName := make(map[string]*unstructured.Unstructured, len(endpoints.Items))
	for index := range endpoints.Items {
		endpoint := &endpoints.Items[index]
		endpointsByName[endpoint.GetName()] = endpoint
	}

	for policyIndex, policy := range policies {
		evaluation := validatePolicyTarget(
			workspace.Spec.Firewall.Revision,
			deliveryID,
			policy,
		)
		if evaluation.Phase != "" {
			return evaluation
		}
		markers, err := policyDeliveryMarkers(policy)
		if err != nil {
			return firewallPolicyDegraded(
				"FirewallPolicyStatusInvalid",
				firewallPolicyStatusInvalidCode,
				err.Error(),
			)
		}
		selectors, err := ciliumPolicyEndpointSelectors(policy)
		if err != nil {
			return firewallPolicyDegraded(
				"FirewallPolicyStatusInvalid",
				firewallPolicyStatusInvalidCode,
				err.Error(),
			)
		}
		selectedPods := selectActivePodsByAnySelector(pods.Items, selectors)
		if len(selectedPods) == 0 {
			if firewallPolicyRequiresEndpoint(workspace, policyIndex) {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s has no active selected Pod",
					policy.GetName(),
				))
			}
			continue
		}
		expectedByNode := make(map[string][]expectedFirewallEndpoint)
		for index := range selectedPods {
			pod := &selectedPods[index]
			if pod.UID == "" || pod.Spec.NodeName == "" {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s selected Pod %s has no durable node identity",
					policy.GetName(),
					pod.Name,
				))
			}
			endpoint := endpointsByName[pod.Name]
			if endpoint == nil || endpoint.GetUID() == "" {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s selected Pod %s has no durable CiliumEndpoint identity",
					policy.GetName(),
					pod.Name,
				))
			}
			endpointID, err := ciliumEndpointID(endpoint)
			if err != nil {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s selected Pod %s has no Cilium agent endpoint ID: %v",
					policy.GetName(),
					pod.Name,
					err,
				))
			}
			expectedByNode[pod.Spec.NodeName] = append(
				expectedByNode[pod.Spec.NodeName],
				expectedFirewallEndpoint{
					PodName:           pod.Name,
					PodUID:            pod.UID,
					NodeName:          pod.Spec.NodeName,
					CiliumEndpointUID: endpoint.GetUID(),
					EndpointID:        endpointID,
				},
			)
		}
		for nodeName, expected := range expectedByNode {
			rawAttestation := policy.GetAnnotations()[firewallAttestationAnnotationKey(nodeName)]
			if rawAttestation == "" {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s has no attestation from node %s",
					policy.GetName(),
					nodeName,
				))
			}
			var attestation firewallPolicyAttestation
			if err := json.Unmarshal([]byte(rawAttestation), &attestation); err != nil {
				return firewallPolicyApplying(fmt.Sprintf(
					"policy %s node %s attestation is invalid",
					policy.GetName(),
					nodeName,
				))
			}
			if detail := validateFirewallAttestation(
				attestation,
				policy,
				workspace.Spec.Firewall.Revision,
				deliveryID,
				markers,
				expected,
				now,
				r.firewallAttestationMaxAge(),
			); detail != "" {
				return firewallPolicyApplying(detail)
			}
		}
	}
	return firewallPolicyApplied("FirewallPolicyApplied")
}

func validatePolicyTarget(
	desiredRevision int64,
	desiredDeliveryID string,
	policy *unstructured.Unstructured,
) firewallPolicyEvaluation {
	if policy == nil {
		return firewallPolicyDegraded(
			"FirewallPolicyStatusInvalid",
			firewallPolicyStatusInvalidCode,
			"CiliumNetworkPolicy resource is nil",
		)
	}
	annotations := policy.GetAnnotations()
	if annotations[firewallRevisionAnnotation] != strconv.FormatInt(desiredRevision, 10) ||
		annotations[firewallDeliveryIDAnnotation] != desiredDeliveryID {
		return firewallPolicyApplying(fmt.Sprintf(
			"policy %s target metadata has not converged",
			policy.GetName(),
		))
	}
	validity, detail, err := ciliumPolicyValidity(policy)
	if err != nil {
		return firewallPolicyDegraded(
			"FirewallPolicyStatusInvalid",
			firewallPolicyStatusInvalidCode,
			err.Error(),
		)
	}
	if validity == "False" {
		return firewallPolicyDegraded(
			"FirewallPolicyRejected",
			firewallPolicyRejectedCode,
			detail,
		)
	}
	if policy.GetUID() == "" || policy.GetGeneration() <= 0 {
		return firewallPolicyApplying(fmt.Sprintf(
			"policy %s has no durable Kubernetes identity",
			policy.GetName(),
		))
	}
	return firewallPolicyEvaluation{}
}

func validateFirewallAttestation(
	attestation firewallPolicyAttestation,
	policy *unstructured.Unstructured,
	revision int64,
	deliveryID string,
	markers []string,
	expected []expectedFirewallEndpoint,
	now time.Time,
	maxAge time.Duration,
) string {
	if attestation.Version != firewallAttestationVersion ||
		attestation.NodeName == "" ||
		attestation.AgentIncarnation == "" ||
		attestation.PolicyNamespace != policy.GetNamespace() ||
		attestation.PolicyName != policy.GetName() ||
		attestation.PolicyUID != policy.GetUID() ||
		attestation.PolicyGeneration != policy.GetGeneration() ||
		attestation.TargetRevision != revision ||
		attestation.DeliveryID != deliveryID ||
		!equalStrings(attestation.DeliveryMarkers, markers) {
		return fmt.Sprintf("policy %s attestation target does not match", policy.GetName())
	}
	if attestation.ObservedAt.IsZero() ||
		attestation.ExpiresAt.IsZero() ||
		attestation.ObservedAt.Time.After(now.Add(time.Second)) ||
		now.Sub(attestation.ObservedAt.Time) > maxAge ||
		!now.Before(attestation.ExpiresAt.Time) ||
		attestation.ExpiresAt.Time.Sub(attestation.ObservedAt.Time) > maxAge {
		return fmt.Sprintf("policy %s node %s attestation is stale", policy.GetName(), attestation.NodeName)
	}
	if len(expected) != len(attestation.Endpoints) {
		return fmt.Sprintf(
			"policy %s node %s endpoint attestation set has changed",
			policy.GetName(),
			attestation.NodeName,
		)
	}
	expectedByName := make(map[string]expectedFirewallEndpoint, len(expected))
	for _, endpoint := range expected {
		if endpoint.NodeName != attestation.NodeName {
			return fmt.Sprintf("policy %s attestation node does not match selected Pod", policy.GetName())
		}
		expectedByName[endpoint.PodName] = endpoint
	}
	seen := make(map[string]struct{}, len(attestation.Endpoints))
	for _, endpoint := range attestation.Endpoints {
		expectedEndpoint, found := expectedByName[endpoint.PodName]
		if !found {
			return fmt.Sprintf("policy %s attestation contains an unexpected endpoint", policy.GetName())
		}
		if _, duplicate := seen[endpoint.PodName]; duplicate ||
			endpoint.PodUID != expectedEndpoint.PodUID ||
			endpoint.CiliumEndpointUID != expectedEndpoint.CiliumEndpointUID ||
			endpoint.EndpointID != expectedEndpoint.EndpointID ||
			endpoint.RealizedPolicyRevision <= 0 {
			return fmt.Sprintf("policy %s endpoint attestation identity does not match", policy.GetName())
		}
		seen[endpoint.PodName] = struct{}{}
	}
	return ""
}

func (r *WorkspaceReconciler) firewallAttestationMaxAge() time.Duration {
	if r.FirewallAttestationMaxAge > 0 {
		return r.FirewallAttestationMaxAge
	}
	return defaultFirewallAttestationMaxAge
}

func ciliumEndpointID(endpoint *unstructured.Unstructured) (int64, error) {
	id, found, err := unstructured.NestedInt64(endpoint.Object, "status", "id")
	if err == nil && found && id > 0 {
		return id, nil
	}
	rawID, found, stringErr := unstructured.NestedString(endpoint.Object, "status", "id")
	if stringErr == nil && found {
		parsed, parseErr := strconv.ParseInt(rawID, 10, 64)
		if parseErr == nil && parsed > 0 {
			return parsed, nil
		}
	}
	return 0, fmt.Errorf("status.id must be a positive integer")
}

func equalStrings(left []string, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func selectActivePods(pods []corev1.Pod, matchLabels map[string]string) []corev1.Pod {
	selected := make([]corev1.Pod, 0)
	for index := range pods {
		pod := &pods[index]
		if !pod.DeletionTimestamp.IsZero() ||
			pod.Status.Phase == corev1.PodSucceeded ||
			pod.Status.Phase == corev1.PodFailed ||
			!labelsContain(pod.Labels, matchLabels) {
			continue
		}
		selected = append(selected, *pod)
	}
	sort.Slice(selected, func(left int, right int) bool {
		return selected[left].Name < selected[right].Name
	})
	return selected
}

func labelsContain(labels map[string]string, required map[string]string) bool {
	for key, value := range required {
		if labels[key] != value {
			return false
		}
	}
	return true
}

func firewallPolicyRequiresEndpoint(
	workspace *workspacev1alpha1.Workspace,
	policyIndex int,
) bool {
	switch policyIndex {
	case 0:
		return workspace.Spec.Runtime.DesiredState == "Running" ||
			(workspace.Spec.Canvas.Enabled && workspace.Spec.Canvas.DesiredState == "Running")
	case 1:
		return workspace.Spec.Runtime.DesiredState == "Running"
	case 2:
		return workspace.Spec.Browser.Enabled && workspace.Spec.Browser.DesiredState == "Running"
	default:
		return false
	}
}

func expireFirewallPolicyApplying(
	previous workspacev1alpha1.WorkspaceFirewallStatus,
	evaluation firewallPolicyEvaluation,
	desiredRevision int64,
	desiredDeliveryID string,
	now time.Time,
) firewallPolicyEvaluation {
	if evaluation.Phase != "Applying" {
		return evaluation
	}
	if previous.TargetRevision != desiredRevision || previous.TargetDeliveryID != desiredDeliveryID {
		return evaluation
	}
	if previous.Phase == "Degraded" &&
		previous.ErrorCode == firewallPolicyEnforcementTimeoutCode {
		return firewallPolicyDegraded(
			"FirewallPolicyEnforcementTimedOut",
			firewallPolicyEnforcementTimeoutCode,
			evaluation.Detail,
		)
	}
	if previous.Phase != "Applying" ||
		previous.LastTransitionAt == nil ||
		now.Sub(previous.LastTransitionAt.Time) < firewallPolicyEnforcementTimeout {
		return evaluation
	}
	return firewallPolicyDegraded(
		"FirewallPolicyEnforcementTimedOut",
		firewallPolicyEnforcementTimeoutCode,
		evaluation.Detail,
	)
}

func ciliumPolicyValidity(policy *unstructured.Unstructured) (string, string, error) {
	conditions, found, err := unstructured.NestedSlice(policy.Object, "status", "conditions")
	if err != nil {
		return "", "", fmt.Errorf("policy %s has invalid status.conditions: %w", policy.GetName(), err)
	}
	if !found {
		return "", "", nil
	}
	for _, rawCondition := range conditions {
		condition, ok := rawCondition.(map[string]interface{})
		if !ok {
			return "", "", fmt.Errorf("policy %s condition is not an object", policy.GetName())
		}
		conditionType, ok := condition["type"].(string)
		if !ok {
			return "", "", fmt.Errorf("policy %s condition type is invalid", policy.GetName())
		}
		if conditionType != "Valid" {
			continue
		}
		status, ok := condition["status"].(string)
		if !ok {
			return "", "", fmt.Errorf("policy %s Valid condition status is invalid", policy.GetName())
		}
		if status != "True" && status != "False" && status != "Unknown" {
			return "", "", fmt.Errorf("policy %s Valid condition status %q is invalid", policy.GetName(), status)
		}
		message, _ := condition["message"].(string)
		return status, fmt.Sprintf("policy %s validation: %s", policy.GetName(), message), nil
	}
	return "", "", nil
}

func (r *WorkspaceReconciler) setFirewallStatus(
	workspace *workspacev1alpha1.Workspace,
	evaluation firewallPolicyEvaluation,
	workspacePolicy *unstructured.Unstructured,
	runtimePeerPolicy *unstructured.Unstructured,
	browserPolicy *unstructured.Unstructured,
) {
	next := workspacev1alpha1.WorkspaceFirewallStatus{
		TargetRevision:   workspace.Spec.Firewall.Revision,
		TargetDeliveryID: workspaceFirewallDeliveryID(workspace),
		ObservedRevision: workspace.Status.Firewall.ObservedRevision,
		Phase:            evaluation.Phase,
		Reason:           evaluation.Reason,
		ErrorCode:        evaluation.ErrorCode,
	}
	if evaluation.Phase == "Applied" {
		next.ObservedRevision = workspace.Spec.Firewall.Revision
	}
	if workspacePolicy != nil {
		next.WorkspacePolicyName = workspacePolicy.GetName()
		next.WorkspacePolicyGeneration = workspacePolicy.GetGeneration()
	}
	if runtimePeerPolicy != nil {
		next.RuntimePeerPolicyName = runtimePeerPolicy.GetName()
		next.RuntimePeerPolicyGeneration = runtimePeerPolicy.GetGeneration()
	}
	if browserPolicy != nil {
		next.BrowserPolicyName = browserPolicy.GetName()
		next.BrowserPolicyGeneration = browserPolicy.GetGeneration()
	}
	next.LastTransitionAt = workspace.Status.Firewall.LastTransitionAt
	if !equality.Semantic.DeepEqual(workspace.Status.Firewall, next) {
		now := metav1.Now()
		next.LastTransitionAt = &now
	}
	workspace.Status.Firewall = next
}

func workspaceFirewallDeliveryID(workspace *workspacev1alpha1.Workspace) string {
	return workspace.GetAnnotations()[firewallDeliveryIDAnnotation]
}

func firewallDeliveryObservationPending(workspace *workspacev1alpha1.Workspace) bool {
	return workspace.Status.Firewall.TargetRevision != workspace.Spec.Firewall.Revision ||
		workspace.Status.Firewall.TargetDeliveryID != workspaceFirewallDeliveryID(workspace)
}
