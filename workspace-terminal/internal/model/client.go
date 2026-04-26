package model

import (
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	ID          string
	WS          *websocket.Conn
	UserID      string
	WorkspaceID string
	Token       string
	ConnectedAt time.Time
	WriteMutex  sync.Mutex // Protects WebSocket write operations
}
