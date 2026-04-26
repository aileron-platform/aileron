package service

import (
	"fmt"
	"os"
	"os/exec"
	"sync"
	"time"

	"workspace-terminal/internal/model"
)

type TerminalTab struct {
	TabID         string
	SessionID     string
	Cols          int
	Rows          int
	WorkspacePath string
	CreatedAt     time.Time
	LastActiveAt  time.Time

	// PTY-related fields
	pty        *os.File
	cmd        *exec.Cmd
	OutputChan chan []byte

	mu sync.Mutex
}

type WorkspaceTerminals struct {
	WorkspaceID string
	Tabs        map[string]*TerminalTab
	ActiveTabID string
	mu          sync.RWMutex
}

type TerminalManager struct {
	workspaces map[string]*WorkspaceTerminals
	clients    map[string]*model.Client
	mu         sync.RWMutex
}

func NewTerminalManager() *TerminalManager {
	return &TerminalManager{
		workspaces: make(map[string]*WorkspaceTerminals),
		clients:    make(map[string]*model.Client),
	}
}

// Create new tab
func (tm *TerminalManager) CreateTab(
	workspaceID string,
	cols int,
	rows int,
	cwd string,
) (*TerminalTab, error) {
	tm.mu.Lock()
	workspace, exists := tm.workspaces[workspaceID]
	if !exists {
		workspace = &WorkspaceTerminals{
			WorkspaceID: workspaceID,
			Tabs:        make(map[string]*TerminalTab),
		}
		tm.workspaces[workspaceID] = workspace
	}
	tm.mu.Unlock()

	// Create PTY
	tab, err := createPTY(cwd, cols, rows)
	if err != nil {
		return nil, err
	}

	workspace.mu.Lock()
	workspace.Tabs[tab.TabID] = tab
	if workspace.ActiveTabID == "" {
		workspace.ActiveTabID = tab.TabID
	}
	workspace.mu.Unlock()

	return tab, nil
}

// Close tab
func (tm *TerminalManager) CloseTab(workspaceID string, tabID string) error {
	tm.mu.RLock()
	workspace, exists := tm.workspaces[workspaceID]
	tm.mu.RUnlock()

	if !exists {
		return fmt.Errorf("workspace not found")
	}

	workspace.mu.Lock()
	tab, exists := workspace.Tabs[tabID]
	if !exists {
		workspace.mu.Unlock()
		return fmt.Errorf("tab not found")
	}

	delete(workspace.Tabs, tabID)

	if workspace.ActiveTabID == tabID {
		workspace.ActiveTabID = ""
		// If other tabs exist, set first one as active
		for id := range workspace.Tabs {
			workspace.ActiveTabID = id
			break
		}
	}

	workspace.mu.Unlock()

	// Clean up resources
	return tab.Close()
}

// Switch tab
func (tm *TerminalManager) SwitchTab(workspaceID string, tabID string) error {
	tm.mu.RLock()
	workspace, exists := tm.workspaces[workspaceID]
	tm.mu.RUnlock()

	if !exists {
		return fmt.Errorf("workspace not found")
	}

	workspace.mu.Lock()
	defer workspace.mu.Unlock()

	if _, exists := workspace.Tabs[tabID]; !exists {
		return fmt.Errorf("tab not found")
	}

	workspace.ActiveTabID = tabID
	return nil
}

// List all tabs
func (tm *TerminalManager) ListTabs(workspaceID string) ([]*TerminalTab, error) {
	tm.mu.RLock()
	workspace, exists := tm.workspaces[workspaceID]
	tm.mu.RUnlock()

	if !exists {
		return []*TerminalTab{}, nil
	}

	workspace.mu.RLock()
	tabs := make([]*TerminalTab, 0, len(workspace.Tabs))
	for _, tab := range workspace.Tabs {
		tabs = append(tabs, tab)
	}
	workspace.mu.RUnlock()

	return tabs, nil
}

// Get tab
func (tm *TerminalManager) GetTab(workspaceID string, tabID string) (*TerminalTab, error) {
	tm.mu.RLock()
	workspace, exists := tm.workspaces[workspaceID]
	tm.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("workspace not found")
	}

	workspace.mu.RLock()
	tab, exists := workspace.Tabs[tabID]
	workspace.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("tab not found")
	}

	return tab, nil
}

// Register client
func (tm *TerminalManager) RegisterClient(client *model.Client) {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	tm.clients[client.ID] = client
}

// Unregister client
func (tm *TerminalManager) UnregisterClient(clientID string) {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	delete(tm.clients, clientID)
}

// Get all clients for workspace
func (tm *TerminalManager) GetWorkspaceClients(workspaceID string) []*model.Client {
	tm.mu.RLock()
	defer tm.mu.RUnlock()

	clients := make([]*model.Client, 0)
	for _, client := range tm.clients {
		if client.WorkspaceID == workspaceID {
			clients = append(clients, client)
		}
	}
	return clients
}

// Close all resources
func (tm *TerminalManager) Close() {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	for _, workspace := range tm.workspaces {
		workspace.mu.Lock()
		for _, tab := range workspace.Tabs {
			tab.Close()
		}
		workspace.mu.Unlock()
	}
}
