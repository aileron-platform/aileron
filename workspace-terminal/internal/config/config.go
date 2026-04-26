package config

import (
	"os"
	"strconv"
)

type Config struct {
	Port      string
	LogLevel  string
	RedisHost string
	RedisPort string
	RedisDB   int

	// Terminal configuration
	MaxTabsPerWorkspace int
	SessionTimeout      int // seconds
	PTYBufferSize       int
}

func Load() *Config {
	return &Config{
		Port:      getEnv("TERMINAL_PORT", "8745"),
		LogLevel:  getEnv("LOG_LEVEL", "info"),
		RedisHost: getEnv("REDIS_HOST", "localhost"),
		RedisPort: getEnv("REDIS_PORT", "6379"),
		RedisDB:   getEnvInt("REDIS_DB", 0),

		MaxTabsPerWorkspace: getEnvInt("MAX_TABS_PER_WORKSPACE", 10),
		SessionTimeout:      getEnvInt("SESSION_TIMEOUT", 300),
		PTYBufferSize:       getEnvInt("PTY_BUFFER_SIZE", 1024),
	}
}

func getEnv(key, defaultVal string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	valStr := getEnv(key, "")
	if val, err := strconv.Atoi(valStr); err == nil {
		return val
	}
	return defaultVal
}

