package config

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"workspace-terminal/internal/service"
)

type Config struct {
	Port            string
	LogLevel        string
	TerminalManager service.TerminalManagerConfig

	// Runtime access and signed drain configuration
	WorkspaceID               string
	RuntimeInstanceID         string
	RuntimeAccessRevision     int64
	PlatformPublicOrigin      string
	MountedRevision           int64
	AssertionPublicKeySetFile string
	AssertionIssuer           string
}

func Load() (*Config, error) {
	terminalManagerConfig := service.DefaultTerminalManagerConfig()
	var err error
	terminalManagerConfig.ReplayBufferBytes, err = getEnvPositiveInt(
		"TERMINAL_REPLAY_BUFFER_BYTES",
		terminalManagerConfig.ReplayBufferBytes,
	)
	if err != nil {
		return nil, err
	}
	outputFlushMilliseconds, err := getEnvPositiveInt(
		"TERMINAL_OUTPUT_FLUSH_MS",
		int(terminalManagerConfig.OutputFlushWindow/time.Millisecond),
	)
	if err != nil {
		return nil, err
	}
	terminalManagerConfig.OutputFlushWindow = time.Duration(outputFlushMilliseconds) * time.Millisecond
	if err := terminalManagerConfig.Validate(); err != nil {
		return nil, fmt.Errorf("invalid terminal manager configuration: %w", err)
	}

	return &Config{
		Port:            getEnv("TERMINAL_PORT", "8745"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
		TerminalManager: terminalManagerConfig,

		WorkspaceID:               getEnv("AILERON_WORKSPACE_ID", ""),
		RuntimeInstanceID:         getEnv("AILERON_RUNTIME_INSTANCE_ID", ""),
		RuntimeAccessRevision:     getEnvInt64("AILERON_RUNTIME_ACCESS_REVISION", -1),
		PlatformPublicOrigin:      getEnv("AILERON_PLATFORM_PUBLIC_ORIGIN", ""),
		MountedRevision:           getEnvInt64("AILERON_KB_MOUNT_REVISION", -1),
		AssertionPublicKeySetFile: getEnv("AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", ""),
		AssertionIssuer:           getEnv("AILERON_RUNTIME_ASSERTION_ISSUER", "workspace-manager"),
	}, nil
}

func getEnv(key, defaultVal string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return defaultVal
}

func getEnvInt64(key string, defaultVal int64) int64 {
	valStr := getEnv(key, "")
	if val, err := strconv.ParseInt(valStr, 10, 64); err == nil {
		return val
	}
	return defaultVal
}

func getEnvPositiveInt(key string, defaultVal int) (int, error) {
	value, exists := os.LookupEnv(key)
	if !exists {
		return defaultVal, nil
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return parsed, nil
}
