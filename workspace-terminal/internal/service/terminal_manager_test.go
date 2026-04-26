package service

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCreateTab(t *testing.T) {
	tm := NewTerminalManager()

	tab, err := tm.CreateTab("ws_123", 80, 24, "/tmp")

	assert.NoError(t, err)
	assert.NotNil(t, tab)
	assert.Equal(t, 80, tab.Cols)
	assert.Equal(t, 24, tab.Rows)
	assert.NotEmpty(t, tab.TabID)
	assert.NotEmpty(t, tab.SessionID)
}

func TestCloseTab(t *testing.T) {
	tm := NewTerminalManager()

	// Create tab
	tab, _ := tm.CreateTab("ws_123", 80, 24, "/tmp")

	// Close tab
	err := tm.CloseTab("ws_123", tab.TabID)

	assert.NoError(t, err)

	// Verify tab is deleted
	_, err = tm.GetTab("ws_123", tab.TabID)
	assert.Error(t, err)
}

func TestListTabs(t *testing.T) {
	tm := NewTerminalManager()

	// Create multiple tabs
	tm.CreateTab("ws_123", 80, 24, "/tmp")
	tm.CreateTab("ws_123", 80, 24, "/tmp")
	tm.CreateTab("ws_123", 80, 24, "/tmp")

	tabs, err := tm.ListTabs("ws_123")

	assert.NoError(t, err)
	assert.Len(t, tabs, 3)
}

func TestSwitchTab(t *testing.T) {
	tm := NewTerminalManager()

	// Create two tabs
	tab1, _ := tm.CreateTab("ws_123", 80, 24, "/tmp")
	tab2, _ := tm.CreateTab("ws_123", 80, 24, "/tmp")

	// Switch to tab2
	err := tm.SwitchTab("ws_123", tab2.TabID)

	assert.NoError(t, err)

	// Verify activeTabID
	workspace := tm.workspaces["ws_123"]
	assert.Equal(t, tab2.TabID, workspace.ActiveTabID)

	// Switch back to tab1
	err = tm.SwitchTab("ws_123", tab1.TabID)
	assert.NoError(t, err)
	assert.Equal(t, tab1.TabID, workspace.ActiveTabID)
}

