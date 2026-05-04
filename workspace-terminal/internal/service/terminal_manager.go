package service

import (
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strconv"
	"sync"
	"time"

	"workspace-terminal/internal/model"
)

const (
	defaultReplayBufferBytes = 1024 * 1024
	defaultTerminalBaseName  = "Terminal"
)

type OutputChunk struct {
	Seq  uint64
	Data []byte
}

type replayRing struct {
	chunks     []OutputChunk
	totalBytes int
	capacity   int
	nextSeq    uint64
	floorSeq   uint64
	mu         sync.RWMutex
}

func newReplayRing(capacity int) *replayRing {
	if capacity <= 0 {
		capacity = defaultReplayBufferBytes
	}
	return &replayRing{
		capacity: capacity,
		nextSeq:  1,
		floorSeq: 1,
	}
}

func (r *replayRing) append(data []byte) OutputChunk {
	r.mu.Lock()
	defer r.mu.Unlock()

	chunkData := make([]byte, len(data))
	copy(chunkData, data)
	chunk := OutputChunk{
		Seq:  r.nextSeq,
		Data: chunkData,
	}
	r.nextSeq++
	r.chunks = append(r.chunks, chunk)
	r.totalBytes += len(chunkData)

	for r.totalBytes > r.capacity && len(r.chunks) > 0 {
		removed := r.chunks[0]
		r.chunks = r.chunks[1:]
		r.totalBytes -= len(removed.Data)
		r.floorSeq = removed.Seq + 1
	}

	return chunk
}

func (r *replayRing) replayFrom(seq uint64) ([]OutputChunk, uint64, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if seq < r.floorSeq {
		return nil, r.floorSeq, false
	}

	chunks := make([]OutputChunk, 0)
	for _, chunk := range r.chunks {
		if chunk.Seq >= seq {
			chunkData := make([]byte, len(chunk.Data))
			copy(chunkData, chunk.Data)
			chunks = append(chunks, OutputChunk{Seq: chunk.Seq, Data: chunkData})
		}
	}

	return chunks, r.floorSeq, true
}

type TerminalTab struct {
	TabID         string
	SessionID     string
	Name          string
	Cols          int
	Rows          int
	WorkspacePath string
	CreatedAt     time.Time
	LastActiveAt  time.Time
	Status        string
	ExitCode      *int

	// PTY-related fields
	pty        *os.File
	cmd        *exec.Cmd
	OutputChan chan OutputChunk
	replay     *replayRing

	mu sync.Mutex
}

type WorkspaceTerminals struct {
	WorkspaceID       string
	Tabs              map[string]*TerminalTab
	NextDefaultNumber int
	mu                sync.RWMutex
}

type TerminalManager struct {
	workspaces        map[string]*WorkspaceTerminals
	clients           map[string]*model.Client
	replayBufferBytes int
	mu                sync.RWMutex
}

func NewTerminalManager() *TerminalManager {
	replayBufferBytes := defaultReplayBufferBytes
	if configured := os.Getenv("TERMINAL_REPLAY_BUFFER_BYTES"); configured != "" {
		if parsed, err := strconv.Atoi(configured); err == nil && parsed > 0 {
			replayBufferBytes = parsed
		}
	}

	return &TerminalManager{
		workspaces:        make(map[string]*WorkspaceTerminals),
		clients:           make(map[string]*model.Client),
		replayBufferBytes: replayBufferBytes,
	}
}

func (tm *TerminalManager) ensureWorkspace(workspaceID string) *WorkspaceTerminals {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	workspace, exists := tm.workspaces[workspaceID]
	if !exists {
		workspace = &WorkspaceTerminals{
			WorkspaceID:       workspaceID,
			Tabs:              make(map[string]*TerminalTab),
			NextDefaultNumber: 1,
		}
		tm.workspaces[workspaceID] = workspace
	}
	return workspace
}

// Create new tab
func (tm *TerminalManager) CreateTab(
	workspaceID string,
	name string,
	cols int,
	rows int,
	cwd string,
) (*TerminalTab, error) {
	workspace := tm.ensureWorkspace(workspaceID)

	workspace.mu.Lock()
	if name == "" {
		name = workspace.nextDefaultNameLocked()
	}
	workspace.mu.Unlock()

	// Create PTY
	tab, err := createPTY(cwd, cols, rows, tm.replayBufferBytes)
	if err != nil {
		return nil, err
	}
	tab.Name = name

	workspace.mu.Lock()
	workspace.Tabs[tab.TabID] = tab
	workspace.mu.Unlock()

	return tab, nil
}

func (w *WorkspaceTerminals) nextDefaultNameLocked() string {
	for {
		name := fmt.Sprintf("%s %d", defaultTerminalBaseName, w.NextDefaultNumber)
		w.NextDefaultNumber++
		exists := false
		for _, tab := range w.Tabs {
			if tab.Name == name {
				exists = true
				break
			}
		}
		if !exists {
			return name
		}
	}
}

// Close tab
func (tm *TerminalManager) CloseTab(workspaceID string, tabID string) (*int, error) {
	tm.mu.RLock()
	workspace, exists := tm.workspaces[workspaceID]
	tm.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("workspace not found")
	}

	workspace.mu.Lock()
	tab, exists := workspace.Tabs[tabID]
	if !exists {
		workspace.mu.Unlock()
		return nil, fmt.Errorf("tab not found")
	}

	delete(workspace.Tabs, tabID)

	workspace.mu.Unlock()

	// Clean up resources
	err := tab.Close()
	return tab.ExitCode, err
}

// ValidateTab confirms a tab exists in a workspace.
func (tm *TerminalManager) ValidateTab(workspaceID string, tabID string) error {
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

	sort.Slice(tabs, func(i, j int) bool {
		if tabs[i].CreatedAt.Equal(tabs[j].CreatedAt) {
			return tabs[i].TabID < tabs[j].TabID
		}
		return tabs[i].CreatedAt.Before(tabs[j].CreatedAt)
	})

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

func (tm *TerminalManager) RenameTab(workspaceID string, tabID string, name string) (*TerminalTab, error) {
	if name == "" {
		return nil, fmt.Errorf("name is required")
	}

	tab, err := tm.GetTab(workspaceID, tabID)
	if err != nil {
		return nil, err
	}

	tab.mu.Lock()
	tab.Name = name
	tab.LastActiveAt = time.Now()
	tab.mu.Unlock()

	return tab, nil
}

func (tm *TerminalManager) ReplayFrom(workspaceID string, tabID string, seq uint64) ([]OutputChunk, uint64, bool, error) {
	tab, err := tm.GetTab(workspaceID, tabID)
	if err != nil {
		return nil, 0, false, err
	}
	chunks, floorSeq, ok := tab.replay.replayFrom(seq)
	return chunks, floorSeq, ok, nil
}

func TabMetadata(tab *TerminalTab) model.TerminalTabMetadata {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	return model.TerminalTabMetadata{
		TabID:         tab.TabID,
		SessionID:     tab.SessionID,
		Name:          tab.Name,
		WorkspacePath: tab.WorkspacePath,
		Cols:          tab.Cols,
		Rows:          tab.Rows,
		CreatedAt:     tab.CreatedAt.Unix(),
		LastActiveAt:  tab.LastActiveAt.Unix(),
		Status:        tab.Status,
		ExitCode:      tab.ExitCode,
	}
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
