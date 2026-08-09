package handler

import (
	"context"
	"encoding/base64"
	"errors"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

type fakeWorkspaceAccessVerifier struct {
	err         error
	calls       int
	bearerToken string
	workspaceID string
}

const testFrontendOrigin = "http://frontend.test"

var testWebSocketHeaders = http.Header{"Origin": []string{testFrontendOrigin}}

func (v *fakeWorkspaceAccessVerifier) VerifyTerminalAccess(
	_ context.Context,
	bearerToken string,
	workspaceID string,
) error {
	v.calls++
	v.bearerToken = bearerToken
	v.workspaceID = workspaceID
	return v.err
}

// waitForClientUnregistered blocks until the server has finished tearing
// down every client for workspaceID. WebSocket connections are hijacked, so
// httptest.Server.Close() does not wait for their handler goroutines; tests
// that let one of those goroutines log via a *testing.T-backed logger must
// synchronize on this (rather than just closing the client connection and
// returning) or they race the goroutine's log call against test teardown.
func waitForClientUnregistered(t *testing.T, terminalManager *service.TerminalManager, workspaceID string) {
	t.Helper()
	assert.Eventually(t, func() bool {
		return len(terminalManager.GetWorkspaceClients(workspaceID)) == 0
	}, 2*time.Second, 10*time.Millisecond, "server did not finish disconnecting the client in time")
}

func TestHandleTerminalWSAcceptsProtocolBearerWithoutPuttingItInURL(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		terminalManager,
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connection, response, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)

	assert.Equal(t, http.StatusSwitchingProtocols, response.StatusCode)
	assert.Equal(t, terminalWebSocketProtocol, connection.Subprotocol())
	assert.Equal(t, 1, accessVerifier.calls)
	assert.Equal(t, "user-token", accessVerifier.bearerToken)
	assert.Equal(t, "workspace-123", accessVerifier.workspaceID)

	require.NoError(t, connection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestCreateTabRequiresExplicitModeAndConcurrentDefaultsCreateOneTab(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		terminalManager,
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	firstConnection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	defer firstConnection.Close()
	readMessageType(t, firstConnection, model.TypeConnected)

	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"cols":              80,
			"rows":              24,
			"working_directory": "/tmp",
		},
	}))
	invalidResponse := readMessageType(t, firstConnection, model.TypeError)
	assert.Equal(t, "INVALID_PARAMS", invalidResponse.Data["code"])
	assert.Empty(t, invalidResponse.Data["message"])

	secondConnection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	defer secondConnection.Close()
	readMessageType(t, secondConnection, model.TypeConnected)

	defaultRequest := map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"create_mode":       createModeDefaultIfEmpty,
			"cols":              80,
			"rows":              24,
			"working_directory": "/tmp",
		},
	}
	writeErrors := make(chan error, 2)
	var writeGroup sync.WaitGroup
	for _, connection := range []*websocket.Conn{firstConnection, secondConnection} {
		writeGroup.Add(1)
		go func(connection *websocket.Conn) {
			defer writeGroup.Done()
			writeErrors <- connection.WriteJSON(defaultRequest)
		}(connection)
	}
	writeGroup.Wait()
	close(writeErrors)
	for writeErr := range writeErrors {
		require.NoError(t, writeErr)
	}

	firstDefault := readMessageType(t, firstConnection, model.TypeTabCreated)
	secondDefault := readMessageType(t, secondConnection, model.TypeTabCreated)
	assert.Equal(t, firstDefault.TabID, secondDefault.TabID)
	tabs, err := terminalManager.ListTabs("workspace-123")
	require.NoError(t, err)
	assert.Len(t, tabs, 1)

	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"create_mode":       createModeAlways,
			"cols":              80,
			"rows":              24,
			"working_directory": "/tmp",
		},
	}))
	userCreated := readMessageType(t, firstConnection, model.TypeTabCreated)
	assert.NotEqual(t, firstDefault.TabID, userCreated.TabID)

	tabs, err = terminalManager.ListTabs("workspace-123")
	require.NoError(t, err)
	assert.Len(t, tabs, 2)

	require.NoError(t, firstConnection.Close())
	require.NoError(t, secondConnection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestWorkingDirectoryUpdatesAtPromptAndIsSharedAcrossConnections(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		terminalManager,
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connect := func() *websocket.Conn {
		connection, _, err := dialer.Dial(
			"ws"+strings.TrimPrefix(server.URL, "http")+
				"/ws/terminal?workspace_id=workspace-123",
			testWebSocketHeaders,
		)
		require.NoError(t, err)
		readMessageType(t, connection, model.TypeConnected)
		return connection
	}
	firstConnection := connect()
	secondConnection := connect()

	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"create_mode":       createModeAlways,
			"cols":              80,
			"rows":              24,
			"working_directory": "/tmp",
		},
	}))
	created := readMessageType(t, firstConnection, model.TypeTabCreated)
	readMessageType(t, secondConnection, model.TypeTabCreated)

	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type":   model.TypeInput,
		"tab_id": created.TabID,
		"data":   map[string]interface{}{"data": "cd /\n"},
	}))

	for _, connection := range []*websocket.Conn{firstConnection, secondConnection} {
		updated := readMessageType(t, connection, model.TypeTabUpdated)
		tabMetadata, ok := updated.Data["tab"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, "/", tabMetadata["working_directory"])
	}

	require.NoError(t, secondConnection.WriteJSON(map[string]interface{}{
		"type": model.TypeListTabs,
	}))
	listed := readMessageType(t, secondConnection, model.TypeTabList)
	tabs, ok := listed.Data["tabs"].([]interface{})
	require.True(t, ok)
	require.Len(t, tabs, 1)
	listedTab, ok := tabs[0].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, "/", listedTab["working_directory"])

	specialDirectory := t.TempDir() + "/cwd#?%"
	require.NoError(t, os.Mkdir(specialDirectory, 0o755))
	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type":   model.TypeInput,
		"tab_id": created.TabID,
		"data": map[string]interface{}{
			"data": "cd '" + specialDirectory + "'\n",
		},
	}))
	for _, connection := range []*websocket.Conn{firstConnection, secondConnection} {
		updated := readMessageType(t, connection, model.TypeTabUpdated)
		tabMetadata, ok := updated.Data["tab"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, specialDirectory, tabMetadata["working_directory"])
	}

	require.NoError(t, firstConnection.WriteJSON(map[string]interface{}{
		"type":   model.TypeInput,
		"tab_id": created.TabID,
		"data": map[string]interface{}{
			"data": "PROMPT_COMMAND=; printf '\\033]7;https://host/ignored\\a'\n",
		},
	}))
	require.NoError(t, secondConnection.WriteJSON(map[string]interface{}{
		"type": model.TypeListTabs,
	}))
	listed = readMessageType(t, secondConnection, model.TypeTabList)
	tabs, ok = listed.Data["tabs"].([]interface{})
	require.True(t, ok)
	require.Len(t, tabs, 1)
	listedTab, ok = tabs[0].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, specialDirectory, listedTab["working_directory"])

	require.NoError(t, firstConnection.Close())
	require.NoError(t, secondConnection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestCreateTabFallsBackWhenRequestedWorkingDirectoryIsUnavailable(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		terminalManager,
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	readMessageType(t, connection, model.TypeConnected)

	require.NoError(t, connection.WriteJSON(map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"create_mode":                createModeAlways,
			"cols":                       80,
			"rows":                       24,
			"working_directory":          "/path/that/does/not/exist",
			"fallback_working_directory": "/tmp",
		},
	}))
	created := readMessageType(t, connection, model.TypeTabCreated)
	tabMetadata, ok := created.Data["tab"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, "/tmp", tabMetadata["working_directory"])

	require.NoError(t, connection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestHandleClearBroadcastsTabClearedAndResetsReplayRing(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	handler := NewWebSocketHandler(accessVerifier, terminalManager, zaptest.NewLogger(t), testFrontendOrigin)
	router.GET("/ws/terminal", handler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	readMessageType(t, connection, model.TypeConnected)

	require.NoError(t, connection.WriteJSON(map[string]interface{}{
		"type": model.TypeCreateTab,
		"data": map[string]interface{}{
			"create_mode":       createModeAlways,
			"cols":              80,
			"rows":              24,
			"working_directory": "/tmp",
		},
	}))
	created := readMessageType(t, connection, model.TypeTabCreated)
	tabID := created.TabID
	require.NotEmpty(t, tabID)

	// Guarantee at least one chunk exists in the replay ring before
	// clearing, so the post-clear replay assertion below is deterministic
	// regardless of how much (if any) shell startup banner already arrived.
	require.NoError(t, connection.WriteJSON(map[string]interface{}{
		"type":   model.TypeInput,
		"tab_id": tabID,
		"data":   map[string]interface{}{"data": "echo clear-test\n"},
	}))
	readMessageType(t, connection, model.TypeOutput)

	require.NoError(t, connection.WriteJSON(map[string]interface{}{
		"type":   model.TypeClear,
		"tab_id": tabID,
	}))
	cleared := readMessageType(t, connection, model.TypeTabCleared)
	assert.Equal(t, tabID, cleared.TabID)
	floorSeq, ok := cleared.Data["floor_seq"].(float64)
	require.True(t, ok)
	assert.Greater(t, floorSeq, float64(1))

	// Replaying from before the clear must report the ring has moved past
	// it, not resurrect pre-clear scrollback.
	require.NoError(t, connection.WriteJSON(map[string]interface{}{
		"type":   model.TypeReplay,
		"tab_id": tabID,
		"data":   map[string]interface{}{"from_seq": 1},
	}))
	resetMsg := readMessageType(t, connection, model.TypeReplayReset)
	assert.Equal(t, tabID, resetMsg.TabID)
	assert.Equal(t, floorSeq, resetMsg.Data["floor_seq"])

	require.NoError(t, connection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestKeepalivePingsPreventIdleDisconnect(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	wsHandler := NewWebSocketHandler(accessVerifier, terminalManager, zaptest.NewLogger(t), testFrontendOrigin)
	wsHandler.pongWait = 200 * time.Millisecond
	wsHandler.pingPeriod = 40 * time.Millisecond
	wsHandler.writeControlWait = 50 * time.Millisecond
	router.GET("/ws/terminal", wsHandler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	defer connection.Close()
	readMessageType(t, connection, model.TypeConnected)

	// gorilla/websocket auto-responds to Ping control frames with a Pong
	// while a Read call is outstanding; keep one outstanding so the server
	// keeps seeing pongs and never lets its read deadline expire.
	go func() {
		for {
			if _, _, err := connection.ReadMessage(); err != nil {
				return
			}
		}
	}()

	// Outlive pongWait several times over while pings keep the connection alive.
	time.Sleep(500 * time.Millisecond)

	assert.Len(t, terminalManager.GetWorkspaceClients("workspace-123"), 1)

	require.NoError(t, connection.Close())
	waitForClientUnregistered(t, terminalManager, "workspace-123")
}

func TestKeepaliveClosesConnectionThatStopsRespondingToPings(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	terminalManager := service.NewTerminalManager(service.DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = terminalManager.Drain(context.Background(), "test-cleanup")
	})
	router := gin.New()
	wsHandler := NewWebSocketHandler(accessVerifier, terminalManager, zaptest.NewLogger(t), testFrontendOrigin)
	wsHandler.pongWait = 100 * time.Millisecond
	wsHandler.pingPeriod = 30 * time.Millisecond
	wsHandler.writeControlWait = 50 * time.Millisecond
	router.GET("/ws/terminal", wsHandler.HandleTerminalWS)
	server := httptest.NewServer(router)
	defer server.Close()

	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	dialer := websocket.Dialer{Subprotocols: []string{
		terminalWebSocketProtocol,
		terminalBearerProtocolPrefix + encodedBearer,
	}}
	connection, _, err := dialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http")+
			"/ws/terminal?workspace_id=workspace-123",
		testWebSocketHeaders,
	)
	require.NoError(t, err)
	defer connection.Close()
	readMessageType(t, connection, model.TypeConnected)
	// Deliberately stop reading after this: no more pongs are ever sent
	// back, so the server's read deadline should expire and it should
	// unregister the client on its own.

	assert.Eventually(t, func() bool {
		return len(terminalManager.GetWorkspaceClients("workspace-123")) == 0
	}, 2*time.Second, 10*time.Millisecond)
}

func readMessageType(
	t *testing.T,
	connection *websocket.Conn,
	wantedType model.MessageType,
) model.Message {
	t.Helper()
	require.NoError(t, connection.SetReadDeadline(time.Now().Add(3*time.Second)))
	for {
		var message model.Message
		require.NoError(t, connection.ReadJSON(&message))
		if message.Type == wantedType {
			return message
		}
	}
}

func TestHandleTerminalWSRejectsMissingWorkspaceID(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	handler := NewWebSocketHandler(
		accessVerifier,
		service.NewTerminalManager(service.DefaultTerminalManagerConfig()),
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)

	req := httptest.NewRequest(http.MethodGet, "/ws/terminal", nil)
	req.Header.Set(
		"Sec-WebSocket-Protocol",
		terminalWebSocketProtocol+", "+terminalBearerProtocolPrefix+
			base64.RawURLEncoding.EncodeToString([]byte("test-token")),
	)
	recorder := httptest.NewRecorder()

	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusUnprocessableEntity, recorder.Code)
	assert.JSONEq(t, `{"errorCode":"WORKSPACE_RUNTIME_ACTION_INVALID"}`, recorder.Body.String())
	assert.Zero(t, accessVerifier.calls)
}

func TestHandleTerminalWSFailsClosedWhenLocalVerifierDeniesAccess(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{err: &service.WorkspaceAccessError{
		HTTPStatus: http.StatusLocked,
		ErrorCode:  "WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS",
	}}
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		service.NewTerminalManager(service.DefaultTerminalManagerConfig()),
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)

	req := httptest.NewRequest(http.MethodGet, "/ws/terminal?workspace_id=workspace-123", nil)
	req.Header.Set(
		"Sec-WebSocket-Protocol",
		terminalWebSocketProtocol+", "+terminalBearerProtocolPrefix+
			base64.RawURLEncoding.EncodeToString([]byte("user-token")),
	)
	recorder := httptest.NewRecorder()

	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusLocked, recorder.Code)
	assert.JSONEq(
		t,
		`{"errorCode":"WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS"}`,
		recorder.Body.String(),
	)
	assert.Equal(t, 1, accessVerifier.calls)
}

func TestHandleTerminalWSRejectsBearerInQueryBeforeManagerCall(t *testing.T) {
	gin.SetMode(gin.TestMode)
	accessVerifier := &fakeWorkspaceAccessVerifier{}
	router := gin.New()
	handler := NewWebSocketHandler(
		accessVerifier,
		service.NewTerminalManager(service.DefaultTerminalManagerConfig()),
		zaptest.NewLogger(t),
		testFrontendOrigin,
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)

	req := httptest.NewRequest(
		http.MethodGet,
		"/ws/terminal?workspace_id=workspace-123&token=user-token",
		nil,
	)
	recorder := httptest.NewRecorder()

	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
	assert.JSONEq(
		t,
		`{"errorCode":"WORKSPACE_RUNTIME_ACTION_FORBIDDEN"}`,
		recorder.Body.String(),
	)
	assert.Zero(t, accessVerifier.calls)
}

func TestTerminalBearerTokenRejectsAmbiguousOrInvalidProtocols(t *testing.T) {
	validEncoded := base64.RawURLEncoding.EncodeToString([]byte("user-token"))
	testCases := []string{
		terminalBearerProtocolPrefix + validEncoded,
		terminalWebSocketProtocol + ", " + terminalBearerProtocolPrefix + "not*base64",
		terminalWebSocketProtocol + ", " + terminalBearerProtocolPrefix + validEncoded +
			", " + terminalBearerProtocolPrefix + validEncoded,
	}

	for _, protocols := range testCases {
		request := httptest.NewRequest(http.MethodGet, "/ws/terminal", nil)
		request.Header.Set("Sec-WebSocket-Protocol", protocols)

		assert.Empty(t, terminalBearerToken(request))
	}
}

func TestTerminalBearerTokenRejectsAmbiguousAuthorizationSources(t *testing.T) {
	encodedBearer := base64.RawURLEncoding.EncodeToString([]byte("protocol-token"))
	request := httptest.NewRequest(http.MethodGet, "/ws/terminal", nil)
	request.Header.Add("Authorization", "Bearer header-token")
	request.Header.Add("Authorization", "Bearer second-header-token")
	assert.Empty(t, terminalBearerToken(request))

	request = httptest.NewRequest(http.MethodGet, "/ws/terminal", nil)
	request.Header.Set("Authorization", "Bearer header-token")
	request.Header.Set(
		"Sec-WebSocket-Protocol",
		terminalWebSocketProtocol+", "+terminalBearerProtocolPrefix+encodedBearer,
	)
	assert.Empty(t, terminalBearerToken(request))
}

func TestExpectedWebSocketCloseClassification(t *testing.T) {
	testCases := []struct {
		name     string
		err      error
		expected bool
	}{
		{
			name:     "normal closure",
			err:      &websocket.CloseError{Code: websocket.CloseNormalClosure},
			expected: true,
		},
		{
			name:     "going away",
			err:      &websocket.CloseError{Code: websocket.CloseGoingAway},
			expected: true,
		},
		{
			name:     "no status received",
			err:      &websocket.CloseError{Code: websocket.CloseNoStatusReceived},
			expected: true,
		},
		{
			name:     "abnormal closure",
			err:      &websocket.CloseError{Code: websocket.CloseAbnormalClosure},
			expected: false,
		},
		{
			name:     "non close, non timeout error",
			err:      errors.New("boom"),
			expected: false,
		},
		{
			name: "read deadline expired (missed pings)",
			// gorilla/websocket re-wraps net timeout errors before
			// returning them from Read*, but always preserves
			// net.Error.Timeout() == true; a raw *net.OpError is a
			// reasonable stand-in for that wrapped shape.
			err:      &net.OpError{Op: "read", Err: os.ErrDeadlineExceeded},
			expected: true,
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			assert.Equal(t, testCase.expected, isExpectedWebSocketClose(testCase.err))
		})
	}
}
