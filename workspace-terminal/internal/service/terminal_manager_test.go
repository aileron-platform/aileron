package service

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"workspace-terminal/internal/model"
)

func TestCreateTabStoresMetadata(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())

	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")

	require.NoError(t, err)
	require.NotNil(t, tab)
	assert.Equal(t, 80, tab.Cols)
	assert.Equal(t, 24, tab.Rows)
	assert.Equal(t, "/tmp", tab.WorkingDirectory)
	assert.Equal(t, "running", tab.Status)
	assert.Nil(t, tab.ExitCode)
	assert.NotEmpty(t, tab.TabID)
	assert.NotEmpty(t, tab.SessionID)

	metadata := TabMetadata(tab)
	assert.Equal(t, tab.TabID, metadata.TabID)
	assert.Equal(t, tab.SessionID, metadata.SessionID)
	assert.Equal(t, "/tmp", metadata.WorkingDirectory)

	encodedMetadata, err := json.Marshal(metadata)
	require.NoError(t, err)
	var metadataFields map[string]interface{}
	require.NoError(t, json.Unmarshal(encodedMetadata, &metadataFields))
	assert.NotContains(t, metadataFields, "name")
	assert.NotContains(t, metadataFields, "workspace_path")
}

func TestNewTerminalManagerUsesInjectedConfig(t *testing.T) {
	t.Setenv("TERMINAL_REPLAY_BUFFER_BYTES", "9999")
	t.Setenv("TERMINAL_OUTPUT_FLUSH_MS", "9999")
	managerConfig := TerminalManagerConfig{
		ReplayBufferBytes: 4096,
		OutputFlushWindow: 20 * time.Millisecond,
	}

	tm := NewTerminalManager(managerConfig)

	assert.Equal(t, managerConfig.ReplayBufferBytes, tm.replayBufferBytes)
	assert.Equal(t, managerConfig.OutputFlushWindow, tm.outputFlushWindow)
}

func TestDrainRejectsNewClientsAndTabsAndClosesAllState(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)
	require.NoError(t, tm.RegisterClient(&model.Client{ID: "client-a", WorkspaceID: "ws_123"}))
	require.NoError(t, tm.RegisterClient(&model.Client{ID: "client-b", WorkspaceID: "ws_123"}))

	err = tm.Drain(context.Background(), "attempt-123")

	require.NoError(t, err)
	assert.True(t, tm.IsDraining())
	assert.Empty(t, tm.GetWorkspaceClients("ws_123"))
	tabs, listErr := tm.ListTabs("ws_123")
	require.NoError(t, listErr)
	assert.Empty(t, tabs)
	assert.ErrorIs(t, tm.RegisterClient(&model.Client{ID: "client-c", WorkspaceID: "ws_123"}), ErrTerminalDraining)
	_, createErr := tm.CreateTab("ws_123", 80, 24, "/tmp")
	assert.ErrorIs(t, createErr, ErrTerminalDraining)
	assert.NotNil(t, tab)
}

func TestDrainIsIdempotentOnlyForSameAttempt(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())

	firstErr := tm.Drain(context.Background(), "attempt-123")
	retryErr := tm.Drain(context.Background(), "attempt-123")
	otherErr := tm.Drain(context.Background(), "attempt-other")

	require.NoError(t, firstErr)
	require.NoError(t, retryErr)
	assert.ErrorIs(t, otherErr, ErrDrainAttemptMismatch)
}

func TestDrainClosesRegisteredWebSocket(t *testing.T) {
	serverConnections := make(chan *websocket.Conn, 1)
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		connection, err := (&websocket.Upgrader{CheckOrigin: func(_ *http.Request) bool { return true }}).
			Upgrade(response, request, nil)
		if err == nil {
			serverConnections <- connection
		}
	}))
	defer server.Close()
	clientConnection, _, err := websocket.DefaultDialer.Dial(
		"ws"+strings.TrimPrefix(server.URL, "http"),
		nil,
	)
	require.NoError(t, err)
	defer clientConnection.Close()
	serverConnection := <-serverConnections

	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	require.NoError(t, tm.RegisterClient(&model.Client{
		ID:          "client-a",
		WorkspaceID: "workspace-123",
		WS:          serverConnection,
	}))

	require.NoError(t, tm.Drain(context.Background(), "attempt-123"))
	require.NoError(t, clientConnection.SetReadDeadline(time.Now().Add(time.Second)))
	_, _, readErr := clientConnection.ReadMessage()

	require.Error(t, readErr)
}

func TestGetOrCreateDefaultTabIsAtomicAcrossClients(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	t.Cleanup(func() {
		_ = tm.Drain(context.Background(), "test-cleanup")
	})

	type result struct {
		tab     *TerminalTab
		created bool
		err     error
	}
	const clientCount = 8
	start := make(chan struct{})
	results := make(chan result, clientCount)
	var waitGroup sync.WaitGroup
	for index := 0; index < clientCount; index++ {
		waitGroup.Add(1)
		go func() {
			defer waitGroup.Done()
			<-start
			tab, created, err := tm.GetOrCreateDefaultTab("ws_123", 80, 24, "/tmp")
			results <- result{tab: tab, created: created, err: err}
		}()
	}

	close(start)
	waitGroup.Wait()
	close(results)

	createdCount := 0
	defaultTabID := ""
	for result := range results {
		require.NoError(t, result.err)
		require.NotNil(t, result.tab)
		if result.created {
			createdCount++
		}
		if defaultTabID == "" {
			defaultTabID = result.tab.TabID
		}
		assert.Equal(t, defaultTabID, result.tab.TabID)
	}
	assert.Equal(t, 1, createdCount)

	userTab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)
	assert.NotEqual(t, defaultTabID, userTab.TabID)
	tabs, err := tm.ListTabs("ws_123")
	require.NoError(t, err)
	assert.Len(t, tabs, 2)
}

func TestCloseTabRemovesTab(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)

	_, err = tm.CloseTab("ws_123", tab.TabID)

	assert.NoError(t, err)

	_, err = tm.GetTab("ws_123", tab.TabID)
	assert.Error(t, err)
}

func TestListTabsUsesCanonicalOrder(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())

	tab2, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)
	tab1, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)
	tab3, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)

	tab1.CreatedAt = time.Unix(100, 0)
	tab1.TabID = "tab_b"
	tab2.CreatedAt = time.Unix(100, 0)
	tab2.TabID = "tab_a"
	tab3.CreatedAt = time.Unix(200, 0)
	tab3.TabID = "tab_c"

	tabs, err := tm.ListTabs("ws_123")

	require.NoError(t, err)
	require.Len(t, tabs, 3)
	assert.Equal(t, "tab_a", tabs[0].TabID)
	assert.Equal(t, "tab_b", tabs[1].TabID)
	assert.Equal(t, "tab_c", tabs[2].TabID)
}

func TestWorkspaceScopesTabs(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())

	ws1Tab, err := tm.CreateTab("ws_1", 80, 24, "/tmp")
	require.NoError(t, err)
	ws2Tab, err := tm.CreateTab("ws_2", 80, 24, "/tmp")
	require.NoError(t, err)

	ws1Tabs, err := tm.ListTabs("ws_1")
	require.NoError(t, err)
	ws2Tabs, err := tm.ListTabs("ws_2")
	require.NoError(t, err)

	require.Len(t, ws1Tabs, 1)
	require.Len(t, ws2Tabs, 1)
	assert.Equal(t, ws1Tab.TabID, ws1Tabs[0].TabID)
	assert.Equal(t, ws2Tab.TabID, ws2Tabs[0].TabID)
	assert.NotEqual(t, ws1Tab.TabID, ws2Tab.TabID)
}

func TestValidateTabDoesNotStoreWorkspaceGlobalActiveTab(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)

	err = tm.ValidateTab("ws_123", tab.TabID)

	assert.NoError(t, err)
	workspace := tm.workspaces["ws_123"]
	assert.NotContains(t, workspace.Tabs, "missing")
}

func TestReplayRingReturnsRetainedChunks(t *testing.T) {
	ring := newReplayRing(1024)
	ring.append([]byte("one"))
	ring.append([]byte("two"))

	chunks, floorSeq, ok := ring.replayFrom(1)

	assert.True(t, ok)
	assert.Equal(t, uint64(1), floorSeq)
	require.Len(t, chunks, 2)
	assert.Equal(t, uint64(1), chunks[0].Seq)
	assert.Equal(t, "one", string(chunks[0].Data))
	assert.Equal(t, uint64(2), chunks[1].Seq)
	assert.Equal(t, "two", string(chunks[1].Data))
}

func TestReplayRingReportsExpiredSequence(t *testing.T) {
	ring := newReplayRing(6)
	ring.append([]byte("first"))
	ring.append([]byte("second"))

	chunks, floorSeq, ok := ring.replayFrom(1)

	assert.False(t, ok)
	assert.Nil(t, chunks)
	assert.Equal(t, uint64(2), floorSeq)
}

func TestReplayRingResetDiscardsRetainedChunksAndAdvancesFloor(t *testing.T) {
	ring := newReplayRing(1024)
	ring.append([]byte("one"))
	ring.append([]byte("two"))

	floorSeq := ring.reset()

	assert.Equal(t, uint64(3), floorSeq)

	chunks, replayFloor, ok := ring.replayFrom(1)
	assert.False(t, ok, "chunks written before reset must not be replayable")
	assert.Nil(t, chunks)
	assert.Equal(t, floorSeq, replayFloor)

	chunk := ring.append([]byte("after reset"))
	assert.Equal(t, uint64(3), chunk.Seq, "seq numbering continues past reset instead of restarting")

	chunks, _, ok = ring.replayFrom(floorSeq)
	require.True(t, ok)
	require.Len(t, chunks, 1)
	assert.Equal(t, "after reset", string(chunks[0].Data))
}

func TestClearTabResetsReplayRingWithoutTypingIntoThePTY(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())
	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")
	require.NoError(t, err)

	tab.replay.append([]byte("pre-clear output"))

	floorSeq, err := tm.ClearTab("ws_123", tab.TabID)
	require.NoError(t, err)

	_, _, ok := tab.replay.replayFrom(1)
	assert.False(t, ok, "output retained before clear must not be replayable afterward")

	chunk := tab.replay.append([]byte("post-clear output"))
	assert.GreaterOrEqual(t, chunk.Seq, floorSeq)
}

func TestClearTabRejectsUnknownTab(t *testing.T) {
	tm := NewTerminalManager(DefaultTerminalManagerConfig())

	_, err := tm.ClearTab("ws_123", "missing-tab")

	require.Error(t, err)
}
