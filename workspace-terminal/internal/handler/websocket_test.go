package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"go.uber.org/zap/zaptest"

	"workspace-terminal/internal/service"
)

func TestHandleTerminalWSRejectsMissingWorkspaceID(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	handler := NewWebSocketHandler(
		service.NewTokenManager(),
		service.NewTerminalManager(),
		zaptest.NewLogger(t),
	)
	router.GET("/ws/terminal", handler.HandleTerminalWS)

	req := httptest.NewRequest(http.MethodGet, "/ws/terminal?token=test-token", nil)
	recorder := httptest.NewRecorder()

	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusBadRequest, recorder.Code)
	assert.Contains(t, recorder.Body.String(), "missing workspace_id parameter")
}
