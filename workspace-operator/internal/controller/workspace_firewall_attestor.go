package controller

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

const maxCiliumEndpointResponseBytes = 16 * 1024 * 1024

var errCiliumAgentUnavailable = errors.New("Cilium agent is unavailable")

type FirewallAttestor struct {
	Client       client.Client
	NodeName     string
	Namespace    string
	SocketPath   string
	PollInterval time.Duration
	MaxAge       time.Duration
	HTTPClient   *http.Client
	Now          func() time.Time
}

type ciliumAgentEndpoint struct {
	ID     int64
	Status map[string]interface{}
}

func (a *FirewallAttestor) Run(ctx context.Context) error {
	if err := a.validate(); err != nil {
		return err
	}
	logger := log.FromContext(ctx).WithValues("node", a.NodeName)
	for {
		if err := a.reconcile(ctx); err != nil {
			if ctx.Err() != nil {
				return nil
			}
			logger.Error(err, "firewall attestation reconciliation failed")
			if errors.Is(err, errCiliumAgentUnavailable) {
				return err
			}
		}
		timer := time.NewTimer(a.PollInterval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil
		case <-timer.C:
		}
	}
}

func (a *FirewallAttestor) validate() error {
	if a.Client == nil {
		return fmt.Errorf("Kubernetes client is required")
	}
	if strings.TrimSpace(a.NodeName) == "" {
		return fmt.Errorf("node name is required")
	}
	if strings.TrimSpace(a.Namespace) == "" {
		return fmt.Errorf("namespace is required")
	}
	if strings.TrimSpace(a.SocketPath) == "" {
		return fmt.Errorf("Cilium agent socket path is required")
	}
	if a.PollInterval <= 0 {
		return fmt.Errorf("poll interval must be positive")
	}
	if a.MaxAge <= a.PollInterval {
		return fmt.Errorf("attestation max age must be greater than poll interval")
	}
	return nil
}

func (a *FirewallAttestor) reconcile(ctx context.Context) error {
	policies := &unstructured.UnstructuredList{}
	policies.SetGroupVersionKind(ciliumNetworkPolicyListGVK)
	if err := a.Client.List(ctx, policies, client.InNamespace(a.Namespace)); err != nil {
		return fmt.Errorf("list CiliumNetworkPolicies: %w", err)
	}

	var pods corev1.PodList
	if err := a.Client.List(ctx, &pods, client.InNamespace(a.Namespace)); err != nil {
		return fmt.Errorf("list Pods: %w", err)
	}
	endpoints := &unstructured.UnstructuredList{}
	endpoints.SetGroupVersionKind(ciliumEndpointListGVK)
	if err := a.Client.List(ctx, endpoints, client.InNamespace(a.Namespace)); err != nil {
		return fmt.Errorf("list CiliumEndpoints: %w", err)
	}

	agentEndpoints, incarnation, agentErr := a.readAgentEndpoints(ctx)
	var reconcileErrors []error
	for index := range policies.Items {
		policy := &policies.Items[index]
		if policy.GetAnnotations()[workspaceResourceAnnotation] == "" {
			continue
		}
		value := ""
		if agentErr == nil {
			attestation, err := a.attestPolicy(
				policy,
				pods.Items,
				endpoints.Items,
				agentEndpoints,
				incarnation,
			)
			if err != nil {
				reconcileErrors = append(reconcileErrors, err)
			} else if attestation != nil {
				encoded, marshalErr := json.Marshal(attestation)
				if marshalErr != nil {
					reconcileErrors = append(reconcileErrors, fmt.Errorf(
						"marshal policy %s attestation: %w",
						policy.GetName(),
						marshalErr,
					))
				} else {
					value = string(encoded)
				}
			}
		}
		if err := a.patchAttestation(ctx, policy, value); err != nil {
			reconcileErrors = append(reconcileErrors, err)
		}
	}
	if agentErr != nil {
		reconcileErrors = append(
			reconcileErrors,
			fmt.Errorf("%w: %v", errCiliumAgentUnavailable, agentErr),
		)
	}
	return errors.Join(reconcileErrors...)
}

func (a *FirewallAttestor) attestPolicy(
	policy *unstructured.Unstructured,
	pods []corev1.Pod,
	ciliumEndpoints []unstructured.Unstructured,
	agentEndpoints []ciliumAgentEndpoint,
	incarnation string,
) (*firewallPolicyAttestation, error) {
	annotations := policy.GetAnnotations()
	deliveryID := annotations[firewallDeliveryIDAnnotation]
	if strings.TrimSpace(deliveryID) == "" {
		return nil, nil
	}
	revision, err := strconv.ParseInt(annotations[firewallRevisionAnnotation], 10, 64)
	if err != nil {
		return nil, fmt.Errorf("policy %s target revision is invalid", policy.GetName())
	}
	if policy.GetUID() == "" || policy.GetGeneration() <= 0 {
		return nil, fmt.Errorf("policy %s has no durable identity", policy.GetName())
	}
	markers, err := policyDeliveryMarkers(policy)
	if err != nil {
		return nil, err
	}
	selectors, err := ciliumPolicyEndpointSelectors(policy)
	if err != nil {
		return nil, err
	}
	selectedPods := selectActivePodsByAnySelector(pods, selectors)
	localPods := make([]corev1.Pod, 0, len(selectedPods))
	for index := range selectedPods {
		if selectedPods[index].Spec.NodeName == a.NodeName {
			localPods = append(localPods, selectedPods[index])
		}
	}
	if len(localPods) == 0 {
		return nil, nil
	}

	cepsByName := make(map[string]*unstructured.Unstructured, len(ciliumEndpoints))
	for index := range ciliumEndpoints {
		cep := &ciliumEndpoints[index]
		cepsByName[cep.GetName()] = cep
	}
	agentByPodAndID := make(map[string]ciliumAgentEndpoint, len(agentEndpoints))
	for _, endpoint := range agentEndpoints {
		namespace, _ := nestedString(endpoint.Status, "external-identifiers", "k8s-namespace")
		podName, _ := nestedString(endpoint.Status, "external-identifiers", "k8s-pod-name")
		if namespace == a.Namespace && podName != "" {
			agentByPodAndID[fmt.Sprintf("%s\x00%d", podName, endpoint.ID)] = endpoint
		}
	}

	endpointAttestations := make([]firewallEndpointAttestation, 0, len(localPods))
	for index := range localPods {
		pod := &localPods[index]
		if pod.UID == "" {
			return nil, fmt.Errorf("policy %s Pod %s has no UID", policy.GetName(), pod.Name)
		}
		cep := cepsByName[pod.Name]
		if cep == nil || cep.GetUID() == "" {
			return nil, fmt.Errorf("policy %s Pod %s has no durable CiliumEndpoint", policy.GetName(), pod.Name)
		}
		endpointID, err := ciliumEndpointID(cep)
		if err != nil {
			return nil, fmt.Errorf("policy %s Pod %s CiliumEndpoint: %w", policy.GetName(), pod.Name, err)
		}
		agentEndpoint, found := agentByPodAndID[fmt.Sprintf("%s\x00%d", pod.Name, endpointID)]
		if !found {
			return nil, fmt.Errorf(
				"policy %s Pod %s agent endpoint identity does not match CiliumEndpoint",
				policy.GetName(),
				pod.Name,
			)
		}
		realized, ok := nestedMap(agentEndpoint.Status, "policy", "realized")
		if !ok {
			return nil, fmt.Errorf("policy %s endpoint %d has no realized policy", policy.GetName(), endpointID)
		}
		state, _ := nestedString(agentEndpoint.Status, "state")
		if state != "ready" {
			return nil, fmt.Errorf("policy %s endpoint %d state is %q", policy.GetName(), endpointID, state)
		}
		realizedRevision, ok := nestedPositiveInt64(realized, "policy-revision")
		if !ok {
			return nil, fmt.Errorf("policy %s endpoint %d has no realized policy revision", policy.GetName(), endpointID)
		}
		policyEnabled, _ := nestedString(realized, "policy-enabled")
		if policyEnabled != "egress" && policyEnabled != "both" {
			return nil, fmt.Errorf(
				"policy %s endpoint %d is not isolated for egress",
				policy.GetName(),
				endpointID,
			)
		}
		if err := verifyRealizedDeliveryMarkers(realized, policy, markers); err != nil {
			return nil, fmt.Errorf("policy %s endpoint %d: %w", policy.GetName(), endpointID, err)
		}
		endpointAttestations = append(endpointAttestations, firewallEndpointAttestation{
			PodName:                pod.Name,
			PodUID:                 pod.UID,
			CiliumEndpointUID:      cep.GetUID(),
			EndpointID:             endpointID,
			RealizedPolicyRevision: realizedRevision,
		})
	}
	sort.Slice(endpointAttestations, func(left int, right int) bool {
		return endpointAttestations[left].PodName < endpointAttestations[right].PodName
	})
	now := a.now().UTC()
	return &firewallPolicyAttestation{
		Version:          firewallAttestationVersion,
		NodeName:         a.NodeName,
		AgentIncarnation: incarnation,
		ObservedAt:       metav1.NewTime(now),
		ExpiresAt:        metav1.NewTime(now.Add(a.MaxAge)),
		PolicyNamespace:  policy.GetNamespace(),
		PolicyName:       policy.GetName(),
		PolicyUID:        policy.GetUID(),
		PolicyGeneration: policy.GetGeneration(),
		TargetRevision:   revision,
		DeliveryID:       deliveryID,
		DeliveryMarkers:  markers,
		Endpoints:        endpointAttestations,
	}, nil
}

func (a *FirewallAttestor) patchAttestation(
	ctx context.Context,
	policy *unstructured.Unstructured,
	value string,
) error {
	key := firewallAttestationAnnotationKey(a.NodeName)
	current := policy.GetAnnotations()
	if current[key] == value || (value == "" && current[key] == "") {
		return nil
	}
	before := policy.DeepCopy()
	next := make(map[string]string, len(current)+1)
	for annotationKey, annotationValue := range current {
		next[annotationKey] = annotationValue
	}
	if value == "" {
		delete(next, key)
	} else {
		next[key] = value
	}
	policy.SetAnnotations(next)
	if err := a.Client.Patch(ctx, policy, client.MergeFrom(before)); err != nil {
		return fmt.Errorf("patch policy %s attestation: %w", policy.GetName(), err)
	}
	return nil
}

func (a *FirewallAttestor) readAgentEndpoints(
	ctx context.Context,
) ([]ciliumAgentEndpoint, string, error) {
	beforeInfo, before, err := socketIncarnation(a.SocketPath)
	if err != nil {
		return nil, "", fmt.Errorf("stat Cilium agent socket: %w", err)
	}
	httpClient := a.HTTPClient
	if httpClient == nil {
		transport := &http.Transport{
			DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
				return (&net.Dialer{}).DialContext(ctx, "unix", a.SocketPath)
			},
			DisableKeepAlives: true,
		}
		httpClient = &http.Client{Transport: transport, Timeout: a.PollInterval}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, "http://cilium/v1/endpoint", nil)
	if err != nil {
		return nil, "", fmt.Errorf("create Cilium endpoint request: %w", err)
	}
	response, err := httpClient.Do(request)
	if err != nil {
		return nil, "", fmt.Errorf("query Cilium endpoint API: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, "", fmt.Errorf("Cilium endpoint API returned %s", response.Status)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxCiliumEndpointResponseBytes+1))
	if err != nil {
		return nil, "", fmt.Errorf("read Cilium endpoint API: %w", err)
	}
	if len(body) > maxCiliumEndpointResponseBytes {
		return nil, "", fmt.Errorf("Cilium endpoint API response exceeds size limit")
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	var rawEndpoints []map[string]interface{}
	if err := decoder.Decode(&rawEndpoints); err != nil {
		return nil, "", fmt.Errorf("decode Cilium endpoint API: %w", err)
	}
	afterInfo, after, err := socketIncarnation(a.SocketPath)
	if err != nil {
		return nil, "", fmt.Errorf("restat Cilium agent socket: %w", err)
	}
	if !os.SameFile(beforeInfo, afterInfo) || before != after {
		return nil, "", fmt.Errorf("Cilium agent restarted during endpoint observation")
	}
	endpoints := make([]ciliumAgentEndpoint, 0, len(rawEndpoints))
	for index, raw := range rawEndpoints {
		id, ok := nestedPositiveInt64(raw, "id")
		if !ok {
			return nil, "", fmt.Errorf("Cilium endpoint %d has invalid id", index)
		}
		status, ok := nestedMap(raw, "status")
		if !ok {
			return nil, "", fmt.Errorf("Cilium endpoint %d has invalid status", id)
		}
		endpoints = append(endpoints, ciliumAgentEndpoint{ID: id, Status: status})
	}
	return endpoints, before, nil
}

func socketIncarnation(path string) (os.FileInfo, string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, "", err
	}
	if info.Mode()&os.ModeSocket == 0 {
		return nil, "", fmt.Errorf("%s is not a Unix socket", path)
	}
	statIdentity := stableFileStatIdentity(info.Sys())
	sum := sha256.Sum256([]byte(fmt.Sprintf(
		"%s\x00%d\x00%d\x00%s",
		path,
		info.Size(),
		info.ModTime().UnixNano(),
		statIdentity,
	)))
	return info, hex.EncodeToString(sum[:]), nil
}

func stableFileStatIdentity(stat interface{}) string {
	value := reflect.ValueOf(stat)
	if value.Kind() == reflect.Pointer {
		value = value.Elem()
	}
	if !value.IsValid() || value.Kind() != reflect.Struct {
		return fmt.Sprintf("%T", stat)
	}
	fieldValue := func(name string) string {
		field := value.FieldByName(name)
		if !field.IsValid() || !field.CanInterface() {
			return ""
		}
		return fmt.Sprint(field.Interface())
	}
	creationTime := fieldValue("Ctim")
	if creationTime == "" {
		creationTime = fieldValue("Ctimespec")
	}
	return strings.Join(
		[]string{fieldValue("Dev"), fieldValue("Ino"), creationTime},
		":",
	)
}

func ciliumPolicyEndpointSelectors(
	policy *unstructured.Unstructured,
) ([]map[string]string, error) {
	rules, err := ciliumPolicyRules(policy)
	if err != nil {
		return nil, err
	}
	selectors := make([]map[string]string, 0, len(rules))
	for index, rule := range rules {
		selector, found, err := unstructured.NestedStringMap(
			rule,
			"endpointSelector",
			"matchLabels",
		)
		if err != nil || !found || len(selector) == 0 {
			return nil, fmt.Errorf("policy %s rule %d endpoint selector is invalid", policy.GetName(), index)
		}
		selectors = append(selectors, selector)
	}
	return selectors, nil
}

func selectActivePodsByAnySelector(
	pods []corev1.Pod,
	selectors []map[string]string,
) []corev1.Pod {
	selectedByUID := make(map[string]corev1.Pod)
	for _, selector := range selectors {
		for _, pod := range selectActivePods(pods, selector) {
			key := string(pod.UID)
			if key == "" {
				key = pod.Namespace + "/" + pod.Name
			}
			selectedByUID[key] = pod
		}
	}
	selected := make([]corev1.Pod, 0, len(selectedByUID))
	for _, pod := range selectedByUID {
		selected = append(selected, pod)
	}
	sort.Slice(selected, func(left int, right int) bool {
		return selected[left].Name < selected[right].Name
	})
	return selected
}

func verifyRealizedDeliveryMarkers(
	realized map[string]interface{},
	policy *unstructured.Unstructured,
	markers []string,
) error {
	labelSets := collectDerivedRuleLabelSets(realized)
	requiredPolicyLabels := []string{
		"k8s:io.cilium.k8s.policy.name=" + policy.GetName(),
		"k8s:io.cilium.k8s.policy.namespace=" + policy.GetNamespace(),
		"k8s:io.cilium.k8s.policy.uid=" + string(policy.GetUID()),
	}
	for _, marker := range markers {
		found := false
		for _, labelSet := range labelSets {
			if containsAllStrings(labelSet, append(requiredPolicyLabels, marker)) {
				found = true
				break
			}
		}
		if !found {
			return fmt.Errorf("realized policy is missing exact delivery marker %s", marker)
		}
	}
	return nil
}

func collectDerivedRuleLabelSets(value interface{}) [][]string {
	var results [][]string
	switch typed := value.(type) {
	case map[string]interface{}:
		for key, child := range typed {
			if key == "derived-from-rules" {
				results = append(results, parseDerivedRuleLabelSets(child)...)
				continue
			}
			results = append(results, collectDerivedRuleLabelSets(child)...)
		}
	case []interface{}:
		for _, child := range typed {
			results = append(results, collectDerivedRuleLabelSets(child)...)
		}
	}
	return results
}

func parseDerivedRuleLabelSets(value interface{}) [][]string {
	rawSets, ok := value.([]interface{})
	if !ok {
		return nil
	}
	results := make([][]string, 0, len(rawSets))
	flat := make([]string, 0)
	for _, rawSet := range rawSets {
		switch typed := rawSet.(type) {
		case []interface{}:
			set := make([]string, 0, len(typed))
			for _, rawLabel := range typed {
				if label, ok := rawLabel.(string); ok {
					set = append(set, label)
				}
			}
			if len(set) > 0 {
				results = append(results, set)
			}
		case string:
			flat = append(flat, typed)
		}
	}
	if len(flat) > 0 {
		results = append(results, flat)
	}
	return results
}

func containsAllStrings(values []string, required []string) bool {
	available := make(map[string]struct{}, len(values))
	for _, value := range values {
		available[value] = struct{}{}
	}
	for _, value := range required {
		if _, found := available[value]; !found {
			return false
		}
	}
	return true
}

func nestedMap(value map[string]interface{}, path ...string) (map[string]interface{}, bool) {
	current := value
	for index, key := range path {
		child, found := current[key]
		if !found {
			return nil, false
		}
		if index == len(path)-1 {
			result, ok := child.(map[string]interface{})
			return result, ok
		}
		next, ok := child.(map[string]interface{})
		if !ok {
			return nil, false
		}
		current = next
	}
	return current, true
}

func nestedString(value map[string]interface{}, path ...string) (string, bool) {
	if len(path) == 0 {
		return "", false
	}
	current := value
	for index, key := range path {
		child, found := current[key]
		if !found {
			return "", false
		}
		if index == len(path)-1 {
			result, ok := child.(string)
			return result, ok
		}
		next, ok := child.(map[string]interface{})
		if !ok {
			return "", false
		}
		current = next
	}
	return "", false
}

func nestedPositiveInt64(value map[string]interface{}, path ...string) (int64, bool) {
	if len(path) == 0 {
		return 0, false
	}
	current := value
	for index, key := range path {
		child, found := current[key]
		if !found {
			return 0, false
		}
		if index == len(path)-1 {
			switch typed := child.(type) {
			case json.Number:
				number, err := typed.Int64()
				return number, err == nil && number > 0
			case int64:
				return typed, typed > 0
			case int:
				return int64(typed), typed > 0
			case float64:
				number := int64(typed)
				return number, typed == float64(number) && number > 0
			case string:
				number, err := strconv.ParseInt(typed, 10, 64)
				return number, err == nil && number > 0
			default:
				return 0, false
			}
		}
		next, ok := child.(map[string]interface{})
		if !ok {
			return 0, false
		}
		current = next
	}
	return 0, false
}

func (a *FirewallAttestor) now() time.Time {
	if a.Now != nil {
		return a.Now()
	}
	return time.Now()
}
