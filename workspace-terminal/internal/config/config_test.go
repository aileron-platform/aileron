package config

import (
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"workspace-terminal/internal/service"
)

func TestLoadReadsOnlyCanonicalPlatformEnvironment(t *testing.T) {
	t.Setenv("TERMINAL_PORT", "9876")
	t.Setenv("LOG_LEVEL", "debug")
	t.Setenv("TERMINAL_REPLAY_BUFFER_BYTES", "2048")
	t.Setenv("TERMINAL_OUTPUT_FLUSH_MS", "25")

	t.Setenv("AILERON_WORKSPACE_ID", "workspace-canonical")
	t.Setenv("AILERON_RUNTIME_INSTANCE_ID", "runtime-canonical")
	t.Setenv("AILERON_RUNTIME_ACCESS_REVISION", "41")
	t.Setenv("AILERON_KB_MOUNT_REVISION", "17")
	t.Setenv("AILERON_PLATFORM_PUBLIC_ORIGIN", "https://platform.example.test")
	t.Setenv("AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", "/run/secrets/runtime-assertion-jwks.json")
	t.Setenv("AILERON_RUNTIME_ASSERTION_ISSUER", "workspace-manager-canonical")

	t.Setenv("WORKSPACE_ID", "workspace-legacy")
	t.Setenv("FRONTEND_ORIGIN", "https://legacy.example.test")
	t.Setenv("RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", "/run/secrets/legacy-jwks.json")
	t.Setenv("RUNTIME_ASSERTION_ISSUER", "workspace-manager-legacy")

	want := &Config{
		Port:     "9876",
		LogLevel: "debug",
		TerminalManager: service.TerminalManagerConfig{
			ReplayBufferBytes: 2048,
			OutputFlushWindow: 25 * time.Millisecond,
		},
		WorkspaceID:               "workspace-canonical",
		RuntimeInstanceID:         "runtime-canonical",
		RuntimeAccessRevision:     41,
		PlatformPublicOrigin:      "https://platform.example.test",
		MountedRevision:           17,
		AssertionPublicKeySetFile: "/run/secrets/runtime-assertion-jwks.json",
		AssertionIssuer:           "workspace-manager-canonical",
	}

	got, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Load() = %#v, want %#v", got, want)
	}
}

func TestLoadUsesTerminalManagerDefaults(t *testing.T) {
	t.Setenv("TERMINAL_REPLAY_BUFFER_BYTES", "temporary")
	t.Setenv("TERMINAL_OUTPUT_FLUSH_MS", "temporary")
	if err := os.Unsetenv("TERMINAL_REPLAY_BUFFER_BYTES"); err != nil {
		t.Fatalf("Unsetenv() error = %v", err)
	}
	if err := os.Unsetenv("TERMINAL_OUTPUT_FLUSH_MS"); err != nil {
		t.Fatalf("Unsetenv() error = %v", err)
	}

	got, err := Load()

	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if got.TerminalManager != service.DefaultTerminalManagerConfig() {
		t.Fatalf(
			"TerminalManager = %#v, want %#v",
			got.TerminalManager,
			service.DefaultTerminalManagerConfig(),
		)
	}
}

func TestLoadRejectsInvalidTerminalManagerEnvironment(t *testing.T) {
	testCases := []struct {
		name  string
		key   string
		value string
	}{
		{name: "non-integer replay buffer", key: "TERMINAL_REPLAY_BUFFER_BYTES", value: "invalid"},
		{name: "zero replay buffer", key: "TERMINAL_REPLAY_BUFFER_BYTES", value: "0"},
		{name: "negative replay buffer", key: "TERMINAL_REPLAY_BUFFER_BYTES", value: "-1"},
		{name: "non-integer flush window", key: "TERMINAL_OUTPUT_FLUSH_MS", value: "invalid"},
		{name: "zero flush window", key: "TERMINAL_OUTPUT_FLUSH_MS", value: "0"},
		{name: "negative flush window", key: "TERMINAL_OUTPUT_FLUSH_MS", value: "-1"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Setenv("TERMINAL_REPLAY_BUFFER_BYTES", "1048576")
			t.Setenv("TERMINAL_OUTPUT_FLUSH_MS", "12")
			t.Setenv(testCase.key, testCase.value)

			got, err := Load()

			if got != nil {
				t.Fatalf("Load() = %#v, want nil", got)
			}
			if err == nil || !strings.Contains(err.Error(), testCase.key) {
				t.Fatalf("Load() error = %v, want error containing %q", err, testCase.key)
			}
		})
	}
}
