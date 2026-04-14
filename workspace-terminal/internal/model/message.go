package model

import "time"

type MessageType string

const (
	// 連線管理
	TypeConnect    MessageType = "connect"
	TypeConnected  MessageType = "connected"
	TypeDisconnect MessageType = "disconnect"

	// Tab 管理
	TypeCreateTab MessageType = "create_tab"
	TypeCloseTab  MessageType = "close_tab"
	TypeSwitchTab MessageType = "switch_tab"
	TypeListTabs  MessageType = "list_tabs"

	// 事件
	TypeTabCreated  MessageType = "tab_created"
	TypeTabClosed   MessageType = "tab_closed"
	TypeTabSwitched MessageType = "tab_switched"
	TypeTabList     MessageType = "tab_list"

	// 終端操作
	TypeInput   MessageType = "input"
	TypeOutput  MessageType = "output"
	TypeResize  MessageType = "resize"
	TypeResized MessageType = "resized"
	TypeClear   MessageType = "clear"

	// 錯誤
	TypeError MessageType = "error"
)

type Message struct {
	Type      MessageType            `json:"type"`
	TabID     string                 `json:"tab_id,omitempty"`
	Data      map[string]interface{} `json:"data,omitempty"`
	Timestamp int64                  `json:"timestamp,omitempty"`
}

// 特定訊息類型的輔助函數
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

func NewTabCreatedMessage(tabID string, sessionID string, name string, workspacePath string, cols int, rows int) *Message {
	return &Message{
		Type:  TypeTabCreated,
		TabID: tabID,
		Data: map[string]interface{}{
			"session_id":     sessionID,
			"name":           name,
			"workspace_path": workspacePath,
			"cols":           cols,
			"rows":           rows,
			"created_at":     time.Now().Unix(),
		},
		Timestamp: time.Now().Unix(),
	}
}

func NewTabClosedMessage(tabID string, exitCode int) *Message {
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

func NewOutputMessage(tabID string, data []byte) *Message {
	return &Message{
		Type:  TypeOutput,
		TabID: tabID,
		Data: map[string]interface{}{
			"data": string(data),
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

func NewTabListMessage(tabs []map[string]interface{}) *Message {
	return &Message{
		Type: TypeTabList,
		Data: map[string]interface{}{
			"tabs":  tabs,
			"count": len(tabs),
		},
		Timestamp: time.Now().Unix(),
	}
}
