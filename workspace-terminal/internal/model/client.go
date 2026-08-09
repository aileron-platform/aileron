package model

import (
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	ID          string
	WS          *websocket.Conn
	WorkspaceID string
	ConnectedAt time.Time
	WriteMutex  sync.Mutex // Protects WebSocket write operations
}
