package handler

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"workspace-terminal/internal/service"
)

const runtimeDrainTimeoutErrorCode = "RUNTIME_DRAIN_TIMEOUT"

type DrainAssertionVerifier interface {
	Verify(assertion string) (*service.DrainClaims, error)
}

type InternalHandler struct {
	assertionVerifier DrainAssertionVerifier
	terminalManager   *service.TerminalManager
	logger            *zap.Logger
}

func NewInternalHandler(
	assertionVerifier DrainAssertionVerifier,
	terminalManager *service.TerminalManager,
	logger *zap.Logger,
) *InternalHandler {
	return &InternalHandler{
		assertionVerifier: assertionVerifier,
		terminalManager:   terminalManager,
		logger:            logger,
	}
}

func (h *InternalHandler) HandleDrain(c *gin.Context) {
	if c.Request.URL.RawQuery != "" {
		h.writeDrainError(c, http.StatusUnauthorized, service.DrainAssertionInvalidErrorCode)
		return
	}
	assertion := strictBearerAssertion(c.Request.Header.Values("Authorization"))
	if assertion == "" {
		h.writeDrainError(c, http.StatusUnauthorized, service.DrainAssertionInvalidErrorCode)
		return
	}

	claims, err := h.assertionVerifier.Verify(assertion)
	if err != nil {
		assertionError := service.AsDrainAssertionError(err)
		status := http.StatusUnauthorized
		if assertionError.ErrorCode == service.DrainContextMismatchErrorCode {
			status = http.StatusConflict
		}
		h.writeDrainError(c, status, assertionError.ErrorCode)
		return
	}

	drainContext, cancel := context.WithDeadline(c.Request.Context(), claims.Deadline)
	defer cancel()
	if err := h.terminalManager.Drain(drainContext, claims.DrainAttemptID); err != nil {
		switch {
		case errors.Is(err, service.ErrDrainAttemptMismatch):
			h.writeDrainError(c, http.StatusConflict, service.DrainContextMismatchErrorCode)
		case errors.Is(err, context.DeadlineExceeded), errors.Is(err, context.Canceled):
			h.writeDrainError(c, http.StatusGatewayTimeout, runtimeDrainTimeoutErrorCode)
		default:
			h.logger.Warn("Terminal drain did not finish", zap.String("error_code", runtimeDrainTimeoutErrorCode))
			h.writeDrainError(c, http.StatusGatewayTimeout, runtimeDrainTimeoutErrorCode)
		}
		return
	}
	c.Status(http.StatusNoContent)
}

func (h *InternalHandler) writeDrainError(c *gin.Context, status int, errorCode string) {
	h.logger.Warn("Terminal drain request rejected", zap.String("error_code", errorCode))
	c.JSON(status, gin.H{"errorCode": errorCode})
}

func strictBearerAssertion(authorizations []string) string {
	if len(authorizations) != 1 {
		return ""
	}
	authorization := authorizations[0]
	if !strings.HasPrefix(authorization, "Bearer ") {
		return ""
	}
	assertion := strings.TrimPrefix(authorization, "Bearer ")
	if !serviceTokenValue(assertion) {
		return ""
	}
	return assertion
}

func serviceTokenValue(value string) bool {
	return value != "" && value == strings.TrimSpace(value) &&
		!strings.ContainsAny(value, " \t\r\n\x00")
}
