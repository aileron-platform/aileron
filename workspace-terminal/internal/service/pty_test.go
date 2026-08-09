package service

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
	"unicode/utf8"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTerminateProcessTreeStopsProcessGroupAndDescendant(t *testing.T) {
	childPIDFile := filepath.Join(t.TempDir(), "child.pid")
	command := exec.Command("/bin/sh", "-c", `sleep 30 & echo $! > "$CHILD_PID_FILE"; wait`)
	command.Env = append(os.Environ(), "CHILD_PID_FILE="+childPIDFile)
	command.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	require.NoError(t, command.Start())
	t.Cleanup(func() {
		if command.Process != nil {
			_ = command.Process.Kill()
		}
	})

	childPID := waitForChildPID(t, childPIDFile)
	require.True(t, processExists(command.Process.Pid))
	require.True(t, processExists(childPID))

	terminateProcessTree(command.Process.Pid, 50*time.Millisecond)
	_, _ = command.Process.Wait()

	assert.Eventually(t, func() bool {
		return !processExists(command.Process.Pid)
	}, time.Second, 10*time.Millisecond)
	assert.Eventually(t, func() bool {
		return !processExists(childPID) || processIsZombie(childPID)
	}, time.Second, 10*time.Millisecond)
}

func waitForChildPID(t *testing.T, path string) int {
	t.Helper()
	var processID int
	require.Eventually(t, func() bool {
		encoded, err := os.ReadFile(path)
		if err != nil {
			return false
		}
		parsed, err := strconv.Atoi(strings.TrimSpace(string(encoded)))
		if err != nil {
			return false
		}
		processID = parsed
		return processID > 1
	}, time.Second, 10*time.Millisecond)
	return processID
}

func processIsZombie(processID int) bool {
	encoded, err := os.ReadFile("/proc/" + strconv.Itoa(processID) + "/status")
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(encoded), "\n") {
		if strings.HasPrefix(line, "State:") {
			return strings.Contains(line, "Z")
		}
	}
	return false
}

func TestSplitCompleteUTF8(t *testing.T) {
	twoByteRune := "é"           // C3 A9
	threeByteRune := "€"         // E2 82 AC
	fourByteRune := "\U0001F4A9" // F0 9F 92 A9

	t.Run("empty input", func(t *testing.T) {
		complete, rest := splitCompleteUTF8(nil)
		assert.Empty(t, complete)
		assert.Empty(t, rest)
	})

	t.Run("ascii only is entirely complete", func(t *testing.T) {
		data := []byte("hello world")
		complete, rest := splitCompleteUTF8(data)
		assert.Equal(t, data, complete)
		assert.Empty(t, rest)
	})

	for _, sample := range []string{twoByteRune, threeByteRune, fourByteRune} {
		sample := sample
		t.Run("complete multi-byte rune at end: "+sample, func(t *testing.T) {
			data := []byte("prefix " + sample)
			complete, rest := splitCompleteUTF8(data)
			assert.Equal(t, data, complete)
			assert.Empty(t, rest)
		})

		encoded := []byte(sample)
		for split := 1; split < len(encoded); split++ {
			split := split
			t.Run("rune split at byte offset", func(t *testing.T) {
				data := append([]byte("prefix "), encoded[:split]...)
				complete, rest := splitCompleteUTF8(data)
				assert.Equal(t, []byte("prefix "), complete)
				assert.Equal(t, encoded[:split], rest)
			})
		}
	}

	t.Run("chunk boundary carry produces no replacement character", func(t *testing.T) {
		full := []byte("emoji " + fourByteRune + " done")
		splitAt := len("emoji ") + 2 // split inside the 4-byte rune

		firstComplete, carry := splitCompleteUTF8(full[:splitAt])
		assert.Equal(t, []byte("emoji "), firstComplete)
		assert.NotEmpty(t, carry)

		secondComplete, secondRest := splitCompleteUTF8(append(append([]byte{}, carry...), full[splitAt:]...))
		assert.Empty(t, secondRest)

		reassembled := append(append([]byte{}, firstComplete...), secondComplete...)
		assert.Equal(t, full, reassembled)
		assert.NotContains(t, string(reassembled), string(utf8.RuneError))
	})

	t.Run("invalid trailing bytes pass through instead of stalling", func(t *testing.T) {
		data := []byte("prefix \xff\xfe")
		complete, rest := splitCompleteUTF8(data)
		assert.Equal(t, data, complete)
		assert.Empty(t, rest)
	})

	t.Run("lone continuation bytes pass through", func(t *testing.T) {
		data := []byte("prefix \x80\x81\x82")
		complete, rest := splitCompleteUTF8(data)
		assert.Equal(t, data, complete)
		assert.Empty(t, rest)
	})
}

// requireChunk reads one chunk from ch, failing the test if none arrives
// within timeout.
func requireChunk(t *testing.T, ch <-chan OutputChunk, timeout time.Duration) OutputChunk {
	t.Helper()
	select {
	case chunk, ok := <-ch:
		require.True(t, ok, "channel closed before a chunk arrived")
		return chunk
	case <-time.After(timeout):
		t.Fatal("timed out waiting for output chunk")
		return OutputChunk{}
	}
}

// newPipeTab builds a bare TerminalTab backed by an os.Pipe instead of a
// real PTY, so tests can control exactly when bytes arrive and when the
// "PTY" closes. monitorPTYOutput only needs Read/Close from the *os.File it
// is given, which os.Pipe's read end satisfies.
func newPipeTab(t *testing.T) (tab *TerminalTab, read *os.File, write *os.File) {
	t.Helper()
	read, write, err := os.Pipe()
	require.NoError(t, err)
	t.Cleanup(func() {
		_ = read.Close()
		_ = write.Close()
	})
	tab = &TerminalTab{
		OutputChan: make(chan OutputChunk, 16),
		replay:     newReplayRing(defaultReplayBufferBytes),
	}
	return tab, read, write
}

func TestMonitorPTYOutputCoalescesWritesWithinFlushWindow(t *testing.T) {
	tab, read, write := newPipeTab(t)
	go monitorPTYOutput(tab, read, 100*time.Millisecond)

	_, err := write.Write([]byte("hello "))
	require.NoError(t, err)
	_, err = write.Write([]byte("world"))
	require.NoError(t, err)

	chunk := requireChunk(t, tab.OutputChan, time.Second)
	assert.Equal(t, "hello world", string(chunk.Data))
	assert.Equal(t, uint64(1), chunk.Seq)
}

func TestMonitorPTYOutputCarriesIncompleteRuneAcrossFlushBoundary(t *testing.T) {
	tab, read, write := newPipeTab(t)
	go monitorPTYOutput(tab, read, 30*time.Millisecond)

	euro := []byte("€") // E2 82 AC
	_, err := write.Write([]byte("value: "))
	require.NoError(t, err)
	_, err = write.Write(euro[:2]) // incomplete rune tail: E2 82
	require.NoError(t, err)

	first := requireChunk(t, tab.OutputChan, time.Second)
	assert.Equal(t, "value: ", string(first.Data), "incomplete rune must be withheld, not flushed as garbage")

	_, err = write.Write(euro[2:]) // remaining byte: AC
	require.NoError(t, err)

	second := requireChunk(t, tab.OutputChan, time.Second)

	combined := string(first.Data) + string(second.Data)
	assert.Equal(t, "value: €", combined)
	assert.NotContains(t, combined, string(utf8.RuneError))
}

func TestMonitorPTYOutputFlushesImmediatelyWhenSizeLimitReached(t *testing.T) {
	tab, read, write := newPipeTab(t)
	// A flush window long enough that only the size limit could explain an
	// early flush.
	go monitorPTYOutput(tab, read, 2*time.Second)

	payload := bytes.Repeat([]byte("a"), maxCoalescedBytes)
	_, err := write.Write(payload)
	require.NoError(t, err)

	select {
	case chunk, ok := <-tab.OutputChan:
		require.True(t, ok)
		assert.Equal(t, maxCoalescedBytes, len(chunk.Data))
	case <-time.After(500 * time.Millisecond):
		t.Fatal("expected a size-triggered flush well before the flush window elapsed")
	}
}

func TestMonitorPTYOutputFlushesPendingCarryOnExit(t *testing.T) {
	tab, read, write := newPipeTab(t)
	// Long enough that only PTY-exit cleanup, not the timer, could flush
	// the pending incomplete rune below.
	go monitorPTYOutput(tab, read, 2*time.Second)

	euro := []byte("€")
	_, err := write.Write(euro[:2]) // incomplete rune, held back as carry
	require.NoError(t, err)
	require.NoError(t, write.Close())

	chunk, ok := <-tab.OutputChan
	require.True(t, ok)
	assert.Equal(t, euro[:2], chunk.Data)

	_, ok = <-tab.OutputChan
	assert.False(t, ok, "OutputChan must close once the PTY is gone")

	assert.Eventually(t, func() bool {
		return tab.snapshotExitCode() != nil
	}, time.Second, 10*time.Millisecond)
}
