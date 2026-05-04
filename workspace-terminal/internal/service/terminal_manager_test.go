package service

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCreateTabStoresMetadata(t *testing.T) {
	tm := NewTerminalManager()

	tab, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")

	require.NoError(t, err)
	require.NotNil(t, tab)
	assert.Equal(t, "Terminal 1", tab.Name)
	assert.Equal(t, 80, tab.Cols)
	assert.Equal(t, 24, tab.Rows)
	assert.Equal(t, "/tmp", tab.WorkspacePath)
	assert.Equal(t, "running", tab.Status)
	assert.Nil(t, tab.ExitCode)
	assert.NotEmpty(t, tab.TabID)
	assert.NotEmpty(t, tab.SessionID)

	metadata := TabMetadata(tab)
	assert.Equal(t, tab.TabID, metadata.TabID)
	assert.Equal(t, tab.SessionID, metadata.SessionID)
	assert.Equal(t, "Terminal 1", metadata.Name)
	assert.Equal(t, "/tmp", metadata.WorkspacePath)
}

func TestCreateTabUsesProvidedName(t *testing.T) {
	tm := NewTerminalManager()

	tab, err := tm.CreateTab("ws_123", "Gemini", 100, 32, "/tmp")

	require.NoError(t, err)
	assert.Equal(t, "Gemini", tab.Name)
}

func TestDefaultNamesAreUnique(t *testing.T) {
	tm := NewTerminalManager()

	tab1, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)
	tab2, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)
	tab3, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)

	assert.Equal(t, "Terminal 1", tab1.Name)
	assert.Equal(t, "Terminal 2", tab2.Name)
	assert.Equal(t, "Terminal 3", tab3.Name)
}

func TestCloseTabRemovesTab(t *testing.T) {
	tm := NewTerminalManager()
	tab, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)

	exitCode, err := tm.CloseTab("ws_123", tab.TabID)

	assert.NoError(t, err)
	assert.Nil(t, exitCode)

	_, err = tm.GetTab("ws_123", tab.TabID)
	assert.Error(t, err)
}

func TestListTabsUsesCanonicalOrder(t *testing.T) {
	tm := NewTerminalManager()

	tab2, err := tm.CreateTab("ws_123", "Second", 80, 24, "/tmp")
	require.NoError(t, err)
	tab1, err := tm.CreateTab("ws_123", "First", 80, 24, "/tmp")
	require.NoError(t, err)
	tab3, err := tm.CreateTab("ws_123", "Third", 80, 24, "/tmp")
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
	tm := NewTerminalManager()

	ws1Tab, err := tm.CreateTab("ws_1", "", 80, 24, "/tmp")
	require.NoError(t, err)
	ws2Tab, err := tm.CreateTab("ws_2", "", 80, 24, "/tmp")
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
	tm := NewTerminalManager()
	tab, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)

	err = tm.ValidateTab("ws_123", tab.TabID)

	assert.NoError(t, err)
	workspace := tm.workspaces["ws_123"]
	assert.NotContains(t, workspace.Tabs, "missing")
}

func TestRenameTabUpdatesMetadata(t *testing.T) {
	tm := NewTerminalManager()
	tab, err := tm.CreateTab("ws_123", "", 80, 24, "/tmp")
	require.NoError(t, err)

	renamed, err := tm.RenameTab("ws_123", tab.TabID, "Codex")

	require.NoError(t, err)
	assert.Equal(t, "Codex", renamed.Name)
	assert.Equal(t, "Codex", TabMetadata(renamed).Name)
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
