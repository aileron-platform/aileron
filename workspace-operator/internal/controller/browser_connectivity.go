package controller

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
)

type BrowserConnectivityEvidenceReader interface {
	ReadBackend(context.Context, string) (TURNPathEvidenceSnapshot, error)
	ReadFrontend(context.Context, string, string, string) (TURNPathEvidenceSnapshot, error)
}

type HTTPBrowserConnectivityEvidenceReader struct {
	Client        *http.Client
	FrontendToken string
}

func NewHTTPBrowserConnectivityEvidenceReader() *HTTPBrowserConnectivityEvidenceReader {
	return &HTTPBrowserConnectivityEvidenceReader{Client: &http.Client{Timeout: 3 * time.Second}}
}

func (reader *HTTPBrowserConnectivityEvidenceReader) ReadBackend(ctx context.Context, endpoint string) (TURNPathEvidenceSnapshot, error) {
	return reader.readWithToken(ctx, endpoint, "")
}

func (reader *HTTPBrowserConnectivityEvidenceReader) ReadFrontend(
	ctx context.Context,
	gatewayURL string,
	profileRevision string,
	vantage string,
) (TURNPathEvidenceSnapshot, error) {
	endpoint := strings.TrimRight(gatewayURL, "/") + "/v1/evidence/" +
		url.PathEscape(profileRevision) + "/" + url.PathEscape(vantage)
	return reader.readWithToken(ctx, endpoint, reader.FrontendToken)
}

func (reader *HTTPBrowserConnectivityEvidenceReader) readWithToken(
	ctx context.Context,
	endpoint string,
	token string,
) (TURNPathEvidenceSnapshot, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return TURNPathEvidenceSnapshot{}, err
	}
	if strings.TrimSpace(token) != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response, err := reader.Client.Do(request)
	if err != nil {
		return TURNPathEvidenceSnapshot{}, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return TURNPathEvidenceSnapshot{}, fmt.Errorf("evidence endpoint returned HTTP %d", response.StatusCode)
	}
	var snapshot TURNPathEvidenceSnapshot
	decoder := json.NewDecoder(response.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&snapshot); err != nil {
		return TURNPathEvidenceSnapshot{}, err
	}
	return snapshot, nil
}

func (r *WorkspaceReconciler) evaluateBrowserConnectivity(
	ctx context.Context,
	workspace *workspacev1alpha1.Workspace,
	namespace string,
	browserStatus workspacev1alpha1.WorkspaceComponentStatus,
) workspacev1alpha1.WorkspaceBrowserConnectivityStatus {
	now := time.Now().UTC()
	if !workspace.Spec.Browser.Enabled || workspace.Spec.Browser.DesiredState != "Running" {
		return withBrowserConnectivityTransition(
			workspace.Status.BrowserConnectivity,
			baseBrowserConnectivityStatus(BrowserConnectivityPending, "BrowserNotRunning", ""),
			now,
		)
	}
	if r.TURNProfile == nil {
		return withBrowserConnectivityTransition(
			workspace.Status.BrowserConnectivity,
			unavailableBrowserConnectivityStatus("TURNProfileUnavailable", "TURN_PROFILE_UNAVAILABLE"),
			now,
		)
	}
	if !browserStatus.Ready {
		status := baseBrowserConnectivityStatus(BrowserConnectivityPending, "BrowserConnectivityPending", "")
		status.ProfileRevision = r.TURNProfile.Revision()
		status.CredentialRevision = r.TURNCredentialRevision
		status.ObservedBrowserGeneration = browserStatus.ObservedInstanceID
		return withBrowserConnectivityTransition(
			workspace.Status.BrowserConnectivity, status, now,
		)
	}
	if r.ConnectivityEvidenceReader == nil {
		return withBrowserConnectivityTransition(
			workspace.Status.BrowserConnectivity,
			unavailableBrowserConnectivityStatus("BackendEvidenceUnavailable", "BACKEND_EVIDENCE_UNAVAILABLE"),
			now,
		)
	}

	backendEndpoint := fmt.Sprintf(
		"http://%s.%s.svc:8082/v1/evidence",
		resourceName(browserComponent, workspace.Spec.WorkspaceID),
		namespace,
	)
	backend, backendErr := r.ConnectivityEvidenceReader.ReadBackend(ctx, backendEndpoint)
	frontend := make(map[string]*TURNPathEvidenceSnapshot, len(r.TURNProfile.Evidence.RequiredFrontendVantages))
	frontendErrors := make(map[string]error, len(r.TURNProfile.Evidence.RequiredFrontendVantages))
	for _, vantage := range r.TURNProfile.Evidence.RequiredFrontendVantages {
		evidence, err := r.ConnectivityEvidenceReader.ReadFrontend(
			ctx, r.ConnectivityEvidenceGatewayURL, r.TURNProfile.Revision(), vantage,
		)
		if err != nil {
			frontendErrors[vantage] = err
			continue
		}
		copy := evidence
		frontend[vantage] = &copy
	}
	var backendPointer *TURNPathEvidenceSnapshot
	if backendErr == nil {
		backendPointer = &backend
	}
	status := projectBrowserConnectivity(
		r.TURNProfile,
		r.TURNCredentialRevision,
		backendPointer,
		backendErr,
		frontend,
		frontendErrors,
		now,
	)
	status.ObservedBrowserGeneration = browserStatus.ObservedInstanceID
	return withBrowserConnectivityTransition(
		workspace.Status.BrowserConnectivity, status, now,
	)
}

func withBrowserConnectivityTransition(
	previous workspacev1alpha1.WorkspaceBrowserConnectivityStatus,
	status workspacev1alpha1.WorkspaceBrowserConnectivityStatus,
	now time.Time,
) workspacev1alpha1.WorkspaceBrowserConnectivityStatus {
	if previous.State == status.State && previous.Admission == status.Admission &&
		previous.ProfileRevision == status.ProfileRevision &&
		previous.CredentialRevision == status.CredentialRevision &&
		previous.LastTransitionAt != nil {
		status.LastTransitionAt = previous.LastTransitionAt.DeepCopy()
	} else {
		transition := metav1.NewTime(now)
		status.LastTransitionAt = &transition
	}
	return status
}

func projectBrowserConnectivity(
	profile *TURNReachabilityProfile,
	credentialRevision string,
	backend *TURNPathEvidenceSnapshot,
	backendErr error,
	frontend map[string]*TURNPathEvidenceSnapshot,
	frontendErrors map[string]error,
	now time.Time,
) workspacev1alpha1.WorkspaceBrowserConnectivityStatus {
	if profile == nil || strings.TrimSpace(credentialRevision) == "" {
		return unavailableBrowserConnectivityStatus("TURNProfileUnavailable", "TURN_PROFILE_UNAVAILABLE")
	}
	status := baseBrowserConnectivityStatus(BrowserConnectivityPending, "BrowserConnectivityPending", "")
	status.ProfileRevision = profile.Revision()
	status.CredentialRevision = strings.TrimSpace(credentialRevision)
	if backendErr != nil {
		status.State = BrowserConnectivityUnavailable
		status.BackendState = BrowserConnectivityUnavailable
		status.Reason = "BackendEvidenceUnavailable"
		status.ErrorCode = "BACKEND_EVIDENCE_UNAVAILABLE"
		status.BackendReason = status.Reason
		status.BackendErrorCode = status.ErrorCode
		return status
	}
	if backend == nil {
		return status
	}
	if !evidenceSnapshotIsValid(*backend, "") ||
		backend.LatestAttempt.Outcome != TURNProbeOutcomeSuccess || backend.LastSuccess == nil ||
		!evidenceIsFresh(*backend.LastSuccess, status.ProfileRevision, status.CredentialRevision, now) {
		status.State = BrowserConnectivityNotReady
		status.BackendState = BrowserConnectivityNotReady
		status.Reason = "BackendTURNPathNotReady"
		status.ErrorCode = "BACKEND_TURN_PATH_NOT_READY"
		status.BackendReason = status.Reason
		status.BackendErrorCode = status.ErrorCode
		status.BackendAcceptedAt = timeToMeta(&backend.LatestAttempt.AcceptedAt)
		status.BackendExpiresAt = timeToMeta(&backend.LatestAttempt.ExpiresAt)
		status.AcceptedAt = status.BackendAcceptedAt
		status.ExpiresAt = status.BackendExpiresAt
		return status
	}

	status.BackendState = BrowserConnectivityReady
	status.BackendReason = "BackendTURNPathReady"
	status.BackendAcceptedAt = timeToMeta(&backend.LastSuccess.AcceptedAt)
	status.BackendExpiresAt = timeToMeta(&backend.LastSuccess.ExpiresAt)
	var frontendAcceptedAt *time.Time
	var frontendExpiresAt *time.Time
	degraded := false
	for _, vantage := range profile.Evidence.RequiredFrontendVantages {
		snapshot := frontend[vantage]
		if snapshot != nil && evidenceSnapshotIsValid(*snapshot, vantage) && snapshot.LastSuccess != nil &&
			evidenceIsFresh(*snapshot.LastSuccess, status.ProfileRevision, status.CredentialRevision, now) {
			frontendAcceptedAt = earliestTime(frontendAcceptedAt, &snapshot.LastSuccess.AcceptedAt)
			frontendExpiresAt = earliestTime(frontendExpiresAt, &snapshot.LastSuccess.ExpiresAt)
			if snapshot.LatestAttempt.Outcome != TURNProbeOutcomeSuccess || frontendErrors[vantage] != nil {
				degraded = true
			}
			continue
		}
		status.State = BrowserConnectivityNotReady
		status.FrontendState = BrowserConnectivityNotReady
		status.Reason = "FrontendTURNPathNotReady"
		status.ErrorCode = "FRONTEND_TURN_PATH_NOT_READY"
		status.FrontendReason = status.Reason
		status.FrontendErrorCode = status.ErrorCode
		status.AcceptedAt = earliestTimeMeta(&backend.LastSuccess.AcceptedAt, frontendAcceptedAt)
		status.ExpiresAt = earliestTimeMeta(&backend.LastSuccess.ExpiresAt, frontendExpiresAt)
		return status
	}
	status.FrontendAcceptedAt = timeToMeta(frontendAcceptedAt)
	status.FrontendExpiresAt = timeToMeta(frontendExpiresAt)
	status.AcceptedAt = earliestTimeMeta(&backend.LastSuccess.AcceptedAt, frontendAcceptedAt)
	status.ExpiresAt = earliestTimeMeta(&backend.LastSuccess.ExpiresAt, frontendExpiresAt)
	if degraded {
		status.State = BrowserConnectivityDegraded
		status.Admission = BrowserConnectivityAllowed
		status.FrontendState = BrowserConnectivityDegraded
		status.Reason = "FrontendTURNPathNotReady"
		status.ErrorCode = "FRONTEND_TURN_PATH_NOT_READY"
		status.FrontendReason = status.Reason
		status.FrontendErrorCode = status.ErrorCode
		return status
	}
	status.State = BrowserConnectivityReady
	status.Admission = BrowserConnectivityAllowed
	status.FrontendState = BrowserConnectivityReady
	status.FrontendReason = "FrontendTURNPathReady"
	status.Reason = "BrowserConnectivityReady"
	return status
}

func baseBrowserConnectivityStatus(state string, reason string, errorCode string) workspacev1alpha1.WorkspaceBrowserConnectivityStatus {
	return workspacev1alpha1.WorkspaceBrowserConnectivityStatus{
		ContractVersion: BrowserConnectivityContractVersion,
		State:           state, Admission: BrowserConnectivityDenied,
		BackendState: BrowserConnectivityPending, FrontendState: BrowserConnectivityPending,
		Reason: reason, ErrorCode: errorCode,
	}
}

func unavailableBrowserConnectivityStatus(reason string, errorCode string) workspacev1alpha1.WorkspaceBrowserConnectivityStatus {
	status := baseBrowserConnectivityStatus(BrowserConnectivityUnavailable, reason, errorCode)
	status.BackendState = BrowserConnectivityUnavailable
	status.FrontendState = BrowserConnectivityUnavailable
	status.BackendReason, status.FrontendReason = reason, reason
	status.BackendErrorCode, status.FrontendErrorCode = errorCode, errorCode
	return status
}

func evidenceSnapshotIsValid(snapshot TURNPathEvidenceSnapshot, expectedVantage string) bool {
	latest := snapshot.LatestAttempt
	if snapshot.ContractVersion != BrowserConnectivityContractVersion ||
		!evidenceAttemptIsValid(latest) ||
		strings.TrimSpace(latest.Producer.InstallationID) == "" ||
		strings.TrimSpace(latest.Producer.VantageID) == "" ||
		(expectedVantage != "" && latest.Producer.VantageID != expectedVantage) ||
		!latest.ExpiresAt.After(latest.AcceptedAt) {
		return false
	}
	if snapshot.LastSuccess == nil {
		return true
	}
	lastSuccess := *snapshot.LastSuccess
	return evidenceAttemptIsValid(lastSuccess) &&
		lastSuccess.Outcome == TURNProbeOutcomeSuccess &&
		lastSuccess.Producer == latest.Producer &&
		lastSuccess.ProfileRevision == latest.ProfileRevision &&
		lastSuccess.CredentialRevision == latest.CredentialRevision &&
		lastSuccess.ExpiresAt.After(lastSuccess.AcceptedAt)
}

func evidenceAttemptIsValid(evidence TURNPathEvidence) bool {
	profileRevision := strings.TrimPrefix(evidence.ProfileRevision, "sha256:")
	_, digestError := hex.DecodeString(profileRevision)
	if evidence.ContractVersion != BrowserConnectivityContractVersion ||
		!strings.HasPrefix(evidence.ProfileRevision, "sha256:") ||
		len(profileRevision) != 64 || digestError != nil ||
		strings.TrimSpace(evidence.CredentialRevision) == "" {
		return false
	}
	if evidence.Outcome == TURNProbeOutcomeSuccess {
		return strings.TrimSpace(evidence.RelayAddress) != "" && evidence.ErrorCode == ""
	}
	return evidence.Outcome == TURNProbeOutcomeFailure &&
		strings.TrimSpace(evidence.ErrorCode) != "" && evidence.RelayAddress == ""
}

func evidenceIsFresh(evidence TURNPathEvidence, profileRevision string, credentialRevision string, now time.Time) bool {
	return evidence.ContractVersion == BrowserConnectivityContractVersion &&
		evidence.Outcome == TURNProbeOutcomeSuccess &&
		evidence.ProfileRevision == profileRevision &&
		evidence.CredentialRevision == credentialRevision &&
		!evidence.AcceptedAt.After(now) && evidence.ExpiresAt.After(now)
}

func earliestTime(current *time.Time, candidate *time.Time) *time.Time {
	if current == nil {
		return candidate
	}
	if candidate == nil || !candidate.Before(*current) {
		return current
	}
	return candidate
}

func earliestTimeMeta(values ...*time.Time) *metav1.Time {
	var earliest *time.Time
	for _, value := range values {
		earliest = earliestTime(earliest, value)
	}
	return timeToMeta(earliest)
}

func timeToMeta(value *time.Time) *metav1.Time {
	if value == nil {
		return nil
	}
	result := metav1.NewTime(*value)
	return &result
}
