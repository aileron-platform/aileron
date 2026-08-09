package service

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"sync"
	"time"

	"workspace-terminal/internal/model"
)

const (
	defaultReplayBufferBytes = 1024 * 1024

	// defaultOutputFlushWindow coalesces PTY reads that arrive within this
	// window into a single replay chunk / broadcast message, instead of one
	// WebSocket message per <=4KB read.
	defaultOutputFlushWindow = 12 * time.Millisecond
)

type TerminalManagerConfig struct {
	ReplayBufferBytes int
	OutputFlushWindow time.Duration
}

func DefaultTerminalManagerConfig() TerminalManagerConfig {
	return TerminalManagerConfig{
		ReplayBufferBytes: defaultReplayBufferBytes,
		OutputFlushWindow: defaultOutputFlushWindow,
	}
}

func (config TerminalManagerConfig) Validate() error {
	if config.ReplayBufferBytes <= 0 {
		return errors.New("terminal replay buffer bytes must be greater than zero")
	}
	if config.OutputFlushWindow <= 0 {
		return errors.New("terminal output flush window must be greater than zero")
	}
	return nil
}

var (
	ErrTerminalDraining     = errors.New("terminal is draining")
	ErrDrainAttemptMismatch = errors.New("drain attempt does not match active attempt")
)

type OutputChunk struct {
	Seq                     uint64
	Data                    []byte
	WorkingDirectoryChanged bool
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

// reset discards all retained output and moves the floor past every chunk
// seen so far, so a client that replays from the returned seq gets a clean
// screen instead of pre-clear scrollback.
func (r *replayRing) reset() uint64 {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.chunks = nil
	r.totalBytes = 0
	r.floorSeq = r.nextSeq
	return r.floorSeq
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
	TabID            string
	SessionID        string
	Cols             int
	Rows             int
	WorkingDirectory string
	CreatedAt        time.Time
	LastActiveAt     time.Time
	Status           string
	ExitCode         *int

	// PTY-related fields
	pty        *os.File
	cmd        *exec.Cmd
	OutputChan chan OutputChunk
	replay     *replayRing
	osc7       osc7Observer

	mu sync.Mutex
}

func (t *TerminalTab) observeWorkingDirectory(data []byte) bool {
	workingDirectory, ok := t.osc7.Observe(data)
	if !ok {
		return false
	}

	t.mu.Lock()
	defer t.mu.Unlock()
	if workingDirectory == t.WorkingDirectory {
		return false
	}
	t.WorkingDirectory = workingDirectory
	t.LastActiveAt = time.Now()
	return true
}

type WorkspaceTerminals struct {
	WorkspaceID string
	Tabs        map[string]*TerminalTab
	createMu    sync.Mutex
	mu          sync.RWMutex
}

type TerminalManager struct {
	workspaces        map[string]*WorkspaceTerminals
	clients           map[string]*model.Client
	replayBufferBytes int
	outputFlushWindow time.Duration
	draining          bool
	drainAttemptID    string
	mu                sync.RWMutex
}

func NewTerminalManager(config TerminalManagerConfig) *TerminalManager {
	return &TerminalManager{
		workspaces:        make(map[string]*WorkspaceTerminals),
		clients:           make(map[string]*model.Client),
		replayBufferBytes: config.ReplayBufferBytes,
		outputFlushWindow: config.OutputFlushWindow,
	}
}

func (tm *TerminalManager) ensureWorkspace(workspaceID string) *WorkspaceTerminals {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	workspace, exists := tm.workspaces[workspaceID]
	if !exists {
		workspace = &WorkspaceTerminals{
			WorkspaceID: workspaceID,
			Tabs:        make(map[string]*TerminalTab),
		}
		tm.workspaces[workspaceID] = workspace
	}
	return workspace
}

// Create new tab
func (tm *TerminalManager) CreateTab(
	workspaceID string,
	cols int,
	rows int,
	workingDirectory string,
) (*TerminalTab, error) {
	if tm.IsDraining() {
		return nil, ErrTerminalDraining
	}
	workspace := tm.ensureWorkspace(workspaceID)
	workspace.createMu.Lock()
	defer workspace.createMu.Unlock()

	return tm.createTabLocked(workspace, cols, rows, workingDirectory)
}

// GetOrCreateDefaultTab returns the existing workspace tab or creates the first tab atomically.
func (tm *TerminalManager) GetOrCreateDefaultTab(
	workspaceID string,
	cols int,
	rows int,
	workingDirectory string,
) (*TerminalTab, bool, error) {
	if tm.IsDraining() {
		return nil, false, ErrTerminalDraining
	}
	workspace := tm.ensureWorkspace(workspaceID)
	workspace.createMu.Lock()
	defer workspace.createMu.Unlock()

	if tm.IsDraining() {
		return nil, false, ErrTerminalDraining
	}
	workspace.mu.RLock()
	for _, tab := range workspace.Tabs {
		workspace.mu.RUnlock()
		return tab, false, nil
	}
	workspace.mu.RUnlock()

	tab, err := tm.createTabLocked(workspace, cols, rows, workingDirectory)
	if err != nil {
		return nil, false, err
	}
	return tab, true, nil
}

func (tm *TerminalManager) createTabLocked(
	workspace *WorkspaceTerminals,
	cols int,
	rows int,
	workingDirectory string,
) (*TerminalTab, error) {
	if tm.IsDraining() {
		return nil, ErrTerminalDraining
	}

	// Create PTY
	tab, err := createPTY(
		workingDirectory,
		cols,
		rows,
		tm.replayBufferBytes,
		tm.outputFlushWindow,
	)
	if err != nil {
		return nil, err
	}

	tm.mu.RLock()
	if tm.draining {
		tm.mu.RUnlock()
		_ = tab.Close()
		return nil, ErrTerminalDraining
	}
	workspace.mu.Lock()
	workspace.Tabs[tab.TabID] = tab
	workspace.mu.Unlock()
	tm.mu.RUnlock()

	return tab, nil
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
	return tab.snapshotExitCode(), err
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

func (tm *TerminalManager) ReplayFrom(workspaceID string, tabID string, seq uint64) ([]OutputChunk, uint64, bool, error) {
	tab, err := tm.GetTab(workspaceID, tabID)
	if err != nil {
		return nil, 0, false, err
	}
	chunks, floorSeq, ok := tab.replay.replayFrom(seq)
	return chunks, floorSeq, ok, nil
}

// ClearTab discards a tab's retained output so viewers reconnecting or
// replaying afterward start from a clean screen. It does not touch the PTY
// itself; the terminal's actual screen contents are cleared client-side.
func (tm *TerminalManager) ClearTab(workspaceID string, tabID string) (uint64, error) {
	tab, err := tm.GetTab(workspaceID, tabID)
	if err != nil {
		return 0, err
	}
	return tab.replay.reset(), nil
}

func TabMetadata(tab *TerminalTab) model.TerminalTabMetadata {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	return model.TerminalTabMetadata{
		TabID:            tab.TabID,
		SessionID:        tab.SessionID,
		WorkingDirectory: tab.WorkingDirectory,
		Cols:             tab.Cols,
		Rows:             tab.Rows,
		CreatedAt:        tab.CreatedAt.Unix(),
		LastActiveAt:     tab.LastActiveAt.Unix(),
		Status:           tab.Status,
		ExitCode:         tab.ExitCode,
	}
}

// RegisterClient adds a client only while the generation accepts new sessions.
func (tm *TerminalManager) RegisterClient(client *model.Client) error {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	if tm.draining {
		return ErrTerminalDraining
	}
	tm.clients[client.ID] = client
	return nil
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

func (tm *TerminalManager) IsDraining() bool {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.draining
}

// Drain rejects new sessions and closes every client and PTY in this workload.
func (tm *TerminalManager) Drain(ctx context.Context, drainAttemptID string) error {
	if !isCanonicalContextValue(drainAttemptID) {
		return ErrDrainAttemptMismatch
	}

	clients, tabs, err := tm.beginDrain(drainAttemptID)
	if err != nil {
		return err
	}
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	for _, client := range clients {
		if client.WS != nil {
			_ = client.WS.Close()
		}
	}
	for _, tab := range tabs {
		_ = tab.Close()
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return nil
	}
}

func (tm *TerminalManager) beginDrain(
	drainAttemptID string,
) ([]*model.Client, []*TerminalTab, error) {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	if tm.draining && tm.drainAttemptID != drainAttemptID {
		return nil, nil, ErrDrainAttemptMismatch
	}
	if !tm.draining {
		tm.draining = true
		tm.drainAttemptID = drainAttemptID
	}

	clients := make([]*model.Client, 0, len(tm.clients))
	for _, client := range tm.clients {
		clients = append(clients, client)
	}
	tm.clients = make(map[string]*model.Client)

	tabs := make([]*TerminalTab, 0)
	for _, workspace := range tm.workspaces {
		workspace.mu.Lock()
		for _, tab := range workspace.Tabs {
			tabs = append(tabs, tab)
		}
		workspace.Tabs = make(map[string]*TerminalTab)
		workspace.mu.Unlock()
	}
	return clients, tabs, nil
}

// Close all resources
func (tm *TerminalManager) Close() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = tm.Drain(ctx, "server-shutdown")
}
