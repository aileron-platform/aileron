package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"workspace-terminal/internal/config"
	"workspace-terminal/internal/handler"
	"workspace-terminal/internal/service"
)

func main() {
	// 1. 加載配置
	cfg := config.Load()

	// 2. 初始化日誌
	logger := initLogger(cfg.LogLevel)
	defer logger.Sync()

	logger.Info("Starting terminal service",
		zap.String("port", cfg.Port),
		zap.String("log_level", cfg.LogLevel))

	// 3. 初始化服務
	tokenManager := service.NewTokenManager()
	terminalManager := service.NewTerminalManager()

	// 5. 初始化 Gin
	if cfg.LogLevel == "info" || cfg.LogLevel == "warn" || cfg.LogLevel == "error" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.Default()

	// 6. 註冊路由
	wsHandler := handler.NewWebSocketHandler(
		tokenManager,
		terminalManager,
		logger,
	)

	router.GET("/health", handler.HealthCheckHandler)
	router.GET("/ws/terminal", wsHandler.HandleTerminalWS)

	// 7. 啟動服務器
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%s", cfg.Port),
		Handler: router,
	}

	go func() {
		logger.Info("Server started", zap.String("port", cfg.Port))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Server error", zap.Error(err))
		}
	}()

	// 8. 優雅關閉
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	logger.Info("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Error("Server forced to shutdown", zap.Error(err))
	}

	terminalManager.Close()

	logger.Info("Server exited")
}

func initLogger(level string) *zap.Logger {
	var zapLevel zap.AtomicLevel

	switch level {
	case "debug":
		zapLevel = zap.NewAtomicLevelAt(zap.DebugLevel)
	case "info":
		zapLevel = zap.NewAtomicLevelAt(zap.InfoLevel)
	case "warn":
		zapLevel = zap.NewAtomicLevelAt(zap.WarnLevel)
	case "error":
		zapLevel = zap.NewAtomicLevelAt(zap.ErrorLevel)
	default:
		zapLevel = zap.NewAtomicLevelAt(zap.InfoLevel)
	}

	config := zap.Config{
		Level:            zapLevel,
		Development:      false,
		Encoding:         "json",
		EncoderConfig:    zap.NewProductionEncoderConfig(),
		OutputPaths:      []string{"stdout"},
		ErrorOutputPaths: []string{"stderr"},
	}

	logger, err := config.Build()
	if err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}

	return logger
}
