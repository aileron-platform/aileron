package handler

import (
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

type WebSocketHandler struct {
	tokenManager *service.TokenManager
	terminalMgr  *service.TerminalManager
	logger       *zap.Logger
	upgrader     websocket.Upgrader
	mu           sync.RWMutex
}

func NewWebSocketHandler(
	tokenManager *service.TokenManager,
	terminalMgr *service.TerminalManager,
	logger *zap.Logger,
) *WebSocketHandler {
	return &WebSocketHandler{
		tokenManager: tokenManager,
		terminalMgr:  terminalMgr,
		logger:       logger,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // 實際部署時應該限制 origin
			},
		},
	}
}

// WebSocket 端點
func (h *WebSocketHandler) HandleTerminalWS(c *gin.Context) {
	token := c.Query("token")

	if token == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing token parameter"})
		return
	}

	// 認證
	tokenInfo, err := h.authenticateConnection(token)
	if err != nil {
		h.logger.Warn("Authentication failed", zap.Error(err))
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}

	// 升級連線
	ws, err := h.upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		h.logger.Error("WebSocket upgrade failed", zap.Error(err))
		return
	}

	clientID := uuid.New().String()
	client := &model.Client{
		ID:          clientID,
		WS:          ws,
		UserID:      tokenInfo.UserID,
		WorkspaceID: "", // Terminal Service 不綁定 workspace
		Token:       token,
		ConnectedAt: time.Now(),
	}

	// 註冊客戶端
	h.terminalMgr.RegisterClient(client)

	h.logger.Info("Client connected",
		zap.String("client_id", clientID),
		zap.String("user_id", tokenInfo.UserID))

	// 發送 connected 訊息
	h.sendMessage(client, model.NewConnectedMessage(clientID, tokenInfo.UserID))

	// 處理客戶端
	h.handleClient(client)

	// 斷開時清理
	h.terminalMgr.UnregisterClient(clientID)

	h.logger.Info("Client disconnected", zap.String("client_id", clientID))
}

// 認證連線
func (h *WebSocketHandler) authenticateConnection(token string) (*service.TokenInfo, error) {
	tokenInfo, err := h.tokenManager.VerifyToken(token)
	if err != nil {
		return nil, fmt.Errorf("token verification failed: %w", err)
	}

	return tokenInfo, nil
}

// 處理客戶端消息
func (h *WebSocketHandler) handleClient(client *model.Client) {
	defer client.WS.Close()

	for {
		var msg model.Message
		err := client.WS.ReadJSON(&msg)
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				h.logger.Error("WebSocket error", zap.Error(err))
			}
			return
		}

		h.routeMessage(client, &msg)
	}
}

// 路由消息
func (h *WebSocketHandler) routeMessage(client *model.Client, msg *model.Message) {
	switch msg.Type {
	case model.TypeCreateTab:
		h.handleCreateTab(client, msg)
	case model.TypeCloseTab:
		h.handleCloseTab(client, msg)
	case model.TypeSwitchTab:
		h.handleSwitchTab(client, msg)
	case model.TypeInput:
		h.handleInput(client, msg)
	case model.TypeResize:
		h.handleResize(client, msg)
	case model.TypeListTabs:
		h.handleListTabs(client, msg)
	case model.TypeClear:
		h.handleClear(client, msg)
	default:
		h.sendError(client, "INVALID_MESSAGE_TYPE", "Unknown message type")
	}
}

// 發送訊息
func (h *WebSocketHandler) sendMessage(client *model.Client, msg *model.Message) error {
	client.WriteMutex.Lock()
	defer client.WriteMutex.Unlock()
	return client.WS.WriteJSON(msg)
}

// 發送錯誤
func (h *WebSocketHandler) sendError(client *model.Client, code string, message string) {
	h.sendMessage(client, model.NewErrorMessage("", code, message))
}

// 廣播到 workspace 的所有客戶端
func (h *WebSocketHandler) broadcastToWorkspace(workspaceID string, msg *model.Message) {
	clients := h.terminalMgr.GetWorkspaceClients(workspaceID)
	for _, client := range clients {
		if err := h.sendMessage(client, msg); err != nil {
			h.logger.Error("Failed to send message to client",
				zap.String("client_id", client.ID),
				zap.Error(err))
		}
	}
}
