package handler

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

type fakeDrainAssertionVerifier struct {
	claimsByAssertion map[string]*service.DrainClaims
	errorByAssertion  map[string]error
	calls             int
}

func (v *fakeDrainAssertionVerifier) Verify(assertion string) (*service.DrainClaims, error) {
	v.calls++
	if err := v.errorByAssertion[assertion]; err != nil {
		return nil, err
	}
	claims := v.claimsByAssertion[assertion]
	if claims == nil {
		return nil, errors.New("invalid assertion")
	}
	return claims, nil
}

func TestInternalDrainClosesAllClientsAndTabsAndIsIdempotentForAttempt(t *testing.T) {
	gin.SetMode(gin.TestMode)
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	_, err := terminalManager.CreateTab("workspace-123", 80, 24, "/tmp")
	require.NoError(t, err)
	require.NoError(t, terminalManager.RegisterClient(&model.Client{ID: "client-a", WorkspaceID: "workspace-123"}))
	require.NoError(t, terminalManager.RegisterClient(&model.Client{ID: "client-b", WorkspaceID: "workspace-123"}))
	deadline := time.Now().Add(5 * time.Second)
	verifier := &fakeDrainAssertionVerifier{
		claimsByAssertion: map[string]*service.DrainClaims{
			"assertion-one": {DrainAttemptID: "attempt-123", Deadline: deadline},
			"assertion-two": {DrainAttemptID: "attempt-123", Deadline: deadline},
		},
		errorByAssertion: make(map[string]error),
	}
	router := gin.New()
	router.POST(
		"/internal/drain",
		NewInternalHandler(verifier, terminalManager, zaptest.NewLogger(t)).HandleDrain,
	)

	first := performDrainRequest(router, "assertion-one", "")
	retry := performDrainRequest(router, "assertion-two", "")

	assert.Equal(t, http.StatusNoContent, first.Code)
	assert.Equal(t, http.StatusNoContent, retry.Code)
	assert.Empty(t, terminalManager.GetWorkspaceClients("workspace-123"))
	tabs, listErr := terminalManager.ListTabs("workspace-123")
	require.NoError(t, listErr)
	assert.Empty(t, tabs)
}

func TestInternalDrainRejectsDifferentAttemptAfterDrainingStarted(t *testing.T) {
	gin.SetMode(gin.TestMode)
	deadline := time.Now().Add(5 * time.Second)
	verifier := &fakeDrainAssertionVerifier{
		claimsByAssertion: map[string]*service.DrainClaims{
			"first":  {DrainAttemptID: "attempt-123", Deadline: deadline},
			"second": {DrainAttemptID: "attempt-other", Deadline: deadline},
		},
		errorByAssertion: make(map[string]error),
	}
	router := gin.New()
	router.POST(
		"/internal/drain",
		NewInternalHandler(verifier, service.NewTerminalManager(service.DefaultTerminalManagerConfig()), zaptest.NewLogger(t)).HandleDrain,
	)
	require.Equal(t, http.StatusNoContent, performDrainRequest(router, "first", "").Code)

	response := performDrainRequest(router, "second", "")

	assert.Equal(t, http.StatusConflict, response.Code)
	assert.JSONEq(t, `{"errorCode":"RUNTIME_DRAIN_CONTEXT_MISMATCH"}`, response.Body.String())
}

func TestInternalDrainMapsInvalidAssertionToCodeOnlyUnauthorized(t *testing.T) {
	gin.SetMode(gin.TestMode)
	verifier := &fakeDrainAssertionVerifier{
		claimsByAssertion: make(map[string]*service.DrainClaims),
		errorByAssertion: map[string]error{
			"invalid": &service.DrainAssertionError{ErrorCode: service.DrainAssertionInvalidErrorCode},
		},
	}
	router := gin.New()
	router.POST(
		"/internal/drain",
		NewInternalHandler(verifier, service.NewTerminalManager(service.DefaultTerminalManagerConfig()), zaptest.NewLogger(t)).HandleDrain,
	)

	response := performDrainRequest(router, "invalid", "")

	assert.Equal(t, http.StatusUnauthorized, response.Code)
	assert.JSONEq(t, `{"errorCode":"RUNTIME_DRAIN_ASSERTION_INVALID"}`, response.Body.String())
	assert.NotContains(t, response.Body.String(), "message")
}

func TestInternalDrainRejectsAnyQueryBeforeVerification(t *testing.T) {
	gin.SetMode(gin.TestMode)
	verifier := &fakeDrainAssertionVerifier{
		claimsByAssertion: make(map[string]*service.DrainClaims),
		errorByAssertion:  make(map[string]error),
	}
	router := gin.New()
	router.POST(
		"/internal/drain",
		NewInternalHandler(verifier, service.NewTerminalManager(service.DefaultTerminalManagerConfig()), zaptest.NewLogger(t)).HandleDrain,
	)

	response := performDrainRequest(router, "header-assertion", "?unexpected=value")

	assert.Equal(t, http.StatusUnauthorized, response.Code)
	assert.Zero(t, verifier.calls)
}

func TestInternalDrainRejectsAmbiguousAuthorizationHeaders(t *testing.T) {
	gin.SetMode(gin.TestMode)
	verifier := &fakeDrainAssertionVerifier{
		claimsByAssertion: make(map[string]*service.DrainClaims),
		errorByAssertion:  make(map[string]error),
	}
	router := gin.New()
	router.POST(
		"/internal/drain",
		NewInternalHandler(verifier, service.NewTerminalManager(service.DefaultTerminalManagerConfig()), zaptest.NewLogger(t)).HandleDrain,
	)
	request := httptest.NewRequest(http.MethodPost, "/internal/drain", nil)
	request.Header.Add("Authorization", "Bearer assertion-one")
	request.Header.Add("Authorization", "Bearer assertion-two")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	assert.Equal(t, http.StatusUnauthorized, response.Code)
	assert.Zero(t, verifier.calls)
}

func performDrainRequest(
	router http.Handler,
	assertion string,
	query string,
) *httptest.ResponseRecorder {
	request := httptest.NewRequest(http.MethodPost, "/internal/drain"+query, nil)
	request.Header.Set("Authorization", "Bearer "+assertion)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}
