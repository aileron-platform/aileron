package model

import "time"

type MessageType string

const (
	// Connection management
	TypeConnected MessageType = "connected"

	// Tab management
	TypeCreateTab MessageType = "create_tab"
	TypeCloseTab  MessageType = "close_tab"
	TypeSwitchTab MessageType = "switch_tab"
	TypeListTabs  MessageType = "list_tabs"
	TypeRenameTab MessageType = "rename_tab"
	TypeReplay    MessageType = "replay"

	// Events
	TypeTabCreated  MessageType = "tab_created"
	TypeTabClosed   MessageType = "tab_closed"
	TypeTabSwitched MessageType = "tab_switched"
	TypeTabList     MessageType = "tab_list"
	TypeTabUpdated  MessageType = "tab_updated"
	TypeReplayReset MessageType = "tab_replay_reset"

	// Terminal operations
	TypeInput   MessageType = "input"
	TypeOutput  MessageType = "output"
	TypeResize  MessageType = "resize"
	TypeResized MessageType = "resized"
	TypeClear   MessageType = "clear"

	// Errors
	TypeError MessageType = "error"
)

type Message struct {
	Type      MessageType            `json:"type"`
	TabID     string                 `json:"tab_id,omitempty"`
	Data      map[string]interface{} `json:"data,omitempty"`
	Timestamp int64                  `json:"timestamp,omitempty"`
}

type TerminalTabMetadata struct {
	TabID         string `json:"tab_id"`
	SessionID     string `json:"session_id"`
	Name          string `json:"name"`
	WorkspacePath string `json:"workspace_path"`
	Cols          int    `json:"cols"`
	Rows          int    `json:"rows"`
	CreatedAt     int64  `json:"created_at"`
	LastActiveAt  int64  `json:"last_active_at"`
	Status        string `json:"status"`
	ExitCode      *int   `json:"exit_code,omitempty"`
}

// Helper functions for specific message types
func NewConnectedMessage(clientID string, userID string) *Message {
	return &Message{
		Type: TypeConnected,
		Data: map[string]interface{}{
			"client_id": clientID,
			"user_id":   userID,
			"message":   "Connected to terminal service",
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabCreatedMessage(tab TerminalTabMetadata) *Message {
	return &Message{
		Type:  TypeTabCreated,
		TabID: tab.TabID,
		Data: map[string]interface{}{
			"tab": tab,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabUpdatedMessage(tab TerminalTabMetadata) *Message {
	return &Message{
		Type:  TypeTabUpdated,
		TabID: tab.TabID,
		Data: map[string]interface{}{
			"tab": tab,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabClosedMessage(tabID string, exitCode *int) *Message {
	return &Message{
		Type:  TypeTabClosed,
		TabID: tabID,
		Data: map[string]interface{}{
			"exit_code": exitCode,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabSwitchedMessage(tabID string) *Message {
	return &Message{
		Type:  TypeTabSwitched,
		TabID: tabID,
		Data: map[string]interface{}{
			"active": true,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewOutputMessage(tabID string, seq uint64, data []byte) *Message {
	return &Message{
		Type:  TypeOutput,
		TabID: tabID,
		Data: map[string]interface{}{
			"data": string(data),
			"seq":  seq,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewResizedMessage(tabID string, cols int, rows int) *Message {
	return &Message{
		Type:  TypeResized,
		TabID: tabID,
		Data: map[string]interface{}{
			"cols": cols,
			"rows": rows,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewErrorMessage(tabID string, code string, message string) *Message {
	return &Message{
		Type:  TypeError,
		TabID: tabID,
		Data: map[string]interface{}{
			"code":    code,
			"message": message,
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabListMessage(tabs []TerminalTabMetadata) *Message {
	return &Message{
		Type: TypeTabList,
		Data: map[string]interface{}{
			"tabs":  tabs,
			"count": len(tabs),
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewReplayResetMessage(tabID string, requestedSeq uint64, floorSeq uint64) *Message {
	return &Message{
		Type:  TypeReplayReset,
		TabID: tabID,
		Data: map[string]interface{}{
			"requested_seq": requestedSeq,
			"floor_seq":     floorSeq,
		},
		Timestamp: time.Now().Unix(),
	}
}
