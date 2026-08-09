package handler

import (
	"encoding/base64"
	"errors"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

const (
	terminalWebSocketProtocol    = "aileron-terminal-v1"
	terminalBearerProtocolPrefix = "bearer."

	// Keepalive defaults: ping more often than pongWait so a client that
	// misses one ping still has time to respond before the read deadline
	// expires. This is what keeps the connection alive through idle-timeout
	// proxies (e.g. ingress defaults around 60s) between PTY output bursts.
	// Kept as handler fields (not consts) below so tests can shorten them.
	defaultPongWait         = 60 * time.Second
	defaultPingPeriod       = 25 * time.Second
	defaultWriteControlWait = 10 * time.Second
)

type WebSocketHandler struct {
	accessVerifier service.WorkspaceAccessVerifier
	terminalMgr    *service.TerminalManager
	logger         *zap.Logger
	upgrader       websocket.Upgrader

	pongWait         time.Duration
	pingPeriod       time.Duration
	writeControlWait time.Duration
}

func NewWebSocketHandler(
	accessVerifier service.WorkspaceAccessVerifier,
	terminalMgr *service.TerminalManager,
	logger *zap.Logger,
	frontendOrigin string,
) *WebSocketHandler {
	return &WebSocketHandler{
		accessVerifier: accessVerifier,
		terminalMgr:    terminalMgr,
		logger:         logger,
		upgrader: websocket.Upgrader{
			Subprotocols: []string{terminalWebSocketProtocol},
			CheckOrigin: func(r *http.Request) bool {
				return frontendOrigin != "" && r.Header.Get("Origin") == frontendOrigin
			},
		},
		pongWait:         defaultPongWait,
		pingPeriod:       defaultPingPeriod,
		writeControlWait: defaultWriteControlWait,
	}
}

func (h *WebSocketHandler) HandleTerminalWS(c *gin.Context) {
	if c.Request.URL.Query().Has("token") || c.Request.URL.Query().Has("access_token") {
		c.JSON(http.StatusUnauthorized, gin.H{"errorCode": service.RuntimeActionForbiddenErrorCode})
		return
	}
	token := terminalBearerToken(c.Request)
	workspaceID := c.Query("workspace_id")

	if token == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"errorCode": service.RuntimeActionForbiddenErrorCode})
		return
	}
	if workspaceID == "" {
		c.JSON(http.StatusUnprocessableEntity, gin.H{"errorCode": service.RuntimeActionInvalidErrorCode})
		return
	}
	if h.terminalMgr.IsDraining() {
		c.JSON(http.StatusLocked, gin.H{"errorCode": "WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS"})
		return
	}
	if err := h.accessVerifier.VerifyTerminalAccess(c.Request.Context(), token, workspaceID); err != nil {
		accessError := service.AsWorkspaceAccessError(err)
		h.logger.Warn("Terminal access verification denied", zap.String("error_code", accessError.ErrorCode))
		c.JSON(accessError.HTTPStatus, gin.H{"errorCode": accessError.ErrorCode})
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
		WorkspaceID: workspaceID,
		ConnectedAt: time.Now(),
	}

	if err := h.terminalMgr.RegisterClient(client); err != nil {
		_ = ws.WriteControl(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseTryAgainLater, "runtime access recycling"),
			time.Now().Add(time.Second),
		)
		_ = ws.Close()
		return
	}

	h.logger.Info("Client connected",
		zap.String("client_id", clientID),
		zap.String("workspace_id", workspaceID))

	_ = ws.SetReadDeadline(time.Now().Add(h.pongWait))
	ws.SetPongHandler(func(string) error {
		return ws.SetReadDeadline(time.Now().Add(h.pongWait))
	})

	h.sendMessage(client, model.NewConnectedMessage(clientID))

	pingDone := make(chan struct{})
	go h.pingLoop(client, pingDone)

	h.handleClient(client)
	close(pingDone)

	// Logged before unregistering: tests observe disconnect completion by
	// polling GetWorkspaceClients, and that read is mutex-synchronized with
	// UnregisterClient below, so this ordering guarantees the log call has
	// already finished by the time such a poll observes the empty client
	// list (avoids racing a *testing.T-backed logger against test teardown).
	h.logger.Info("Client disconnected", zap.String("client_id", clientID))

	h.terminalMgr.UnregisterClient(clientID)
}

// pingLoop keeps the connection alive across idle-timeout proxies by
// sending periodic WebSocket pings. It exits when done is closed (client
// disconnected) or a ping write fails (connection is already dead).
func (h *WebSocketHandler) pingLoop(client *model.Client, done <-chan struct{}) {
	ticker := time.NewTicker(h.pingPeriod)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			return
		case <-ticker.C:
			client.WriteMutex.Lock()
			err := client.WS.WriteControl(websocket.PingMessage, nil, time.Now().Add(h.writeControlWait))
			client.WriteMutex.Unlock()
			if err != nil {
				return
			}
		}
	}
}

func terminalBearerToken(request *http.Request) string {
	if len(request.Header.Values("Authorization")) != 0 {
		return ""
	}

	protocols := strings.Split(request.Header.Get("Sec-WebSocket-Protocol"), ",")
	foundTerminalProtocol := false
	encodedBearer := ""
	for _, rawProtocol := range protocols {
		protocol := strings.TrimSpace(rawProtocol)
		switch {
		case protocol == terminalWebSocketProtocol:
			if foundTerminalProtocol {
				return ""
			}
			foundTerminalProtocol = true
		case strings.HasPrefix(protocol, terminalBearerProtocolPrefix):
			if encodedBearer != "" {
				return ""
			}
			encodedBearer = strings.TrimPrefix(protocol, terminalBearerProtocolPrefix)
		}
	}
	if !foundTerminalProtocol || encodedBearer == "" {
		return ""
	}
	decodedBearer, err := base64.RawURLEncoding.DecodeString(encodedBearer)
	if err != nil || !canonicalBearerToken(string(decodedBearer)) {
		return ""
	}
	return string(decodedBearer)
}

func canonicalBearerToken(value string) bool {
	return value != "" && value == strings.TrimSpace(value) &&
		!strings.ContainsAny(value, " \t\r\n\x00")
}

func (h *WebSocketHandler) handleClient(client *model.Client) {
	defer client.WS.Close()

	for {
		var msg model.Message
		err := client.WS.ReadJSON(&msg)
		if err != nil {
			if h.terminalMgr.IsDraining() || isExpectedWebSocketClose(err) {
				h.logger.Debug("WebSocket closed", zap.Error(err))
			} else {
				h.logger.Error("WebSocket read failed", zap.Error(err))
			}
			return
		}
		_ = client.WS.SetReadDeadline(time.Now().Add(h.pongWait))

		h.routeMessage(client, &msg)
	}
}

func isExpectedWebSocketClose(err error) bool {
	if errors.Is(err, net.ErrClosed) {
		return true
	}
	// A read deadline expiring means the client stopped responding to
	// pings (e.g. it vanished without a clean close); treat it the same as
	// an expected disconnect rather than logging it as an error.
	// gorilla/websocket re-wraps net timeout errors into its own private
	// type before returning them from Read*, discarding the original
	// os.ErrDeadlineExceeded sentinel, so net.Error.Timeout() is the only
	// way left to recognize it here.
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	var closeError *websocket.CloseError
	if !errors.As(err, &closeError) {
		return false
	}
	return closeError.Code == websocket.CloseNormalClosure ||
		closeError.Code == websocket.CloseGoingAway ||
		closeError.Code == websocket.CloseNoStatusReceived
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
	case model.TypeReplay:
		h.handleReplay(client, msg)
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
