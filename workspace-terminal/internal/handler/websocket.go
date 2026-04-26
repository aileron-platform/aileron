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
				return true // TODO: restrict origin in production
			},
		},
	}
}

func (h *WebSocketHandler) HandleTerminalWS(c *gin.Context) {
	token := c.Query("token")

	if token == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing token parameter"})
		return
	}

	tokenInfo, err := h.authenticateConnection(token)
	if err != nil {
		h.logger.Warn("Authentication failed", zap.Error(err))
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}

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
		WorkspaceID: "", // Terminal Service does not bind to workspace
		Token:       token,
		ConnectedAt: time.Now(),
	}

	h.terminalMgr.RegisterClient(client)

	h.logger.Info("Client connected",
		zap.String("client_id", clientID),
		zap.String("user_id", tokenInfo.UserID))

	h.sendMessage(client, model.NewConnectedMessage(clientID, tokenInfo.UserID))

	h.handleClient(client)

	h.terminalMgr.UnregisterClient(clientID)

	h.logger.Info("Client disconnected", zap.String("client_id", clientID))
}

func (h *WebSocketHandler) authenticateConnection(token string) (*service.TokenInfo, error) {
	tokenInfo, err := h.tokenManager.VerifyToken(token)
	if err != nil {
		return nil, fmt.Errorf("token verification failed: %w", err)
	}

	return tokenInfo, nil
}

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

func (h *WebSocketHandler) sendMessage(client *model.Client, msg *model.Message) error {
	client.WriteMutex.Lock()
	defer client.WriteMutex.Unlock()
	return client.WS.WriteJSON(msg)
}

func (h *WebSocketHandler) sendError(client *model.Client, code string, message string) {
	h.sendMessage(client, model.NewErrorMessage("", code, message))
}

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
