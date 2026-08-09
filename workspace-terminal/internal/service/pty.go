package service

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf8"

	"github.com/creack/pty"
	"github.com/google/uuid"
)

// maxCoalescedBytes caps how much output the coalescer accumulates before
// forcing a flush, regardless of the flush window timer.
const maxCoalescedBytes = 32 * 1024

// Create PTY
func createPTY(
	workingDirectory string,
	cols int,
	rows int,
	replayBufferBytes int,
	outputFlushWindow time.Duration,
) (*TerminalTab, error) {
	// Create shell command (using both login and interactive)
	cmd := exec.Command("/bin/bash", "-l", "-i")
	cmd.Dir = workingDirectory
	// Set environment variables, including PS1 prompt to show username and container ID
	env := os.Environ()
	env = append(env,
		"TERM=xterm-256color",
		"COLORTERM=truecolor",
		"LANG=en_US.UTF-8",
		"LC_ALL=en_US.UTF-8",
		"BRACKETED_PASTE=1",
	)
	promptCommand := `( __aileron_osc7_path=$PWD; export LC_ALL=C; ` +
		`printf '\033]7;file://'; ` +
		`for ((__aileron_osc7_index=0; ` +
		`__aileron_osc7_index<${#__aileron_osc7_path}; ` +
		`__aileron_osc7_index++)); do ` +
		`__aileron_osc7_char=${__aileron_osc7_path:__aileron_osc7_index:1}; ` +
		`case "$__aileron_osc7_char" in ` +
		`[a-zA-Z0-9.~_/-]) printf '%s' "$__aileron_osc7_char" ;; ` +
		`*) printf '%%%02X' "'$__aileron_osc7_char" ;; esac; ` +
		`done; printf '\007' )`
	if existingPromptCommand := os.Getenv("PROMPT_COMMAND"); existingPromptCommand != "" {
		promptCommand = existingPromptCommand + "\n" + promptCommand
	}
	env = append(env, "PROMPT_COMMAND="+promptCommand)
	if os.Getenv("HOME") == "" {
		env = append(env, "HOME="+workingDirectory)
	}

	containerID := getContainerID()
	if containerID == "" {
		containerID = "container"
	}
	env = append(env, fmt.Sprintf("CONTAINER_ID=%s", containerID))
	ps1 := fmt.Sprintf(`\u@\h[%s]:\w$ `, containerID)
	env = append(env, fmt.Sprintf("PS1=%s", ps1))
	bashrcPath := filepath.Join(workingDirectory, ".bashrc")
	env = append(env, fmt.Sprintf("BASH_ENV=%s", bashrcPath))
	cmd.Env = env

	// Start PTY
	ptmx, err := pty.StartWithSize(cmd, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to start PTY: %w", err)
	}

	tab := &TerminalTab{
		TabID:            "tab_" + uuid.New().String(),
		SessionID:        fmt.Sprintf("shell_%s_%s", time.Now().Format("20060102150405"), uuid.New().String()[:8]),
		Cols:             cols,
		Rows:             rows,
		WorkingDirectory: workingDirectory,
		CreatedAt:        time.Now(),
		LastActiveAt:     time.Now(),
		Status:           "running",
		pty:              ptmx,
		cmd:              cmd,
		OutputChan:       make(chan OutputChunk, 256),
		replay:           newReplayRing(replayBufferBytes),
	}

	// Start output monitoring goroutine
	go monitorPTYOutput(tab, ptmx, outputFlushWindow)

	return tab, nil
}

// splitCompleteUTF8 splits data into a prefix of complete UTF-8 runes and a
// trailing remainder that may be an incomplete multi-byte rune. The remainder
// must be carried into the next PTY read so multi-byte characters are never
// split across output chunks (which would otherwise decode as U+FFFD).
// At most utf8.UTFMax-1 bytes are ever withheld, and invalid UTF-8 byte
// sequences are always passed through immediately rather than held back.
func splitCompleteUTF8(data []byte) (complete, rest []byte) {
	if len(data) == 0 {
		return data, nil
	}

	maxCarry := utf8.UTFMax - 1
	start := len(data) - maxCarry
	if start < 0 {
		start = 0
	}

	for i := len(data) - 1; i >= start; i-- {
		b := data[i]
		if b < 0x80 {
			return data, nil
		}
		if b >= 0xC0 {
			if utf8.FullRune(data[i:]) {
				return data, nil
			}
			return data[:i], data[i:]
		}
	}

	return data, nil
}

// ptyReader reads raw PTY output at the granularity the kernel hands it to
// us and forwards each chunk to raw, closing it once the PTY is gone (the
// shell exited or the fd was closed).
func ptyReader(ptyFile *os.File, raw chan<- []byte) {
	buf := make([]byte, 4096)
	for {
		n, err := ptyFile.Read(buf)
		if n > 0 {
			data := make([]byte, n)
			copy(data, buf[:n])
			raw <- data
		}
		if err != nil {
			close(raw)
			return
		}
	}
}

// monitorPTYOutput coalesces bursts of raw PTY reads that arrive within
// outputFlushWindow into a single replay-ring chunk / broadcast message,
// instead of emitting one WebSocket message per <=4KB PTY read. Coalescing
// happens before the replay ring append so live broadcast and replay always
// see identical chunking and seq numbers.
func monitorPTYOutput(tab *TerminalTab, ptyFile *os.File, flushWindow time.Duration) {
	raw := make(chan []byte)
	go ptyReader(ptyFile, raw)

	var pending []byte
	var carry []byte
	var timer *time.Timer
	var timerC <-chan time.Time

	flush := func() {
		if timer != nil {
			timer.Stop()
			timer = nil
			timerC = nil
		}
		if len(pending) == 0 {
			return
		}
		complete, rest := splitCompleteUTF8(append(carry, pending...))
		if len(complete) > 0 {
			data := make([]byte, len(complete))
			copy(data, complete)
			chunk := tab.replay.append(data)
			chunk.WorkingDirectoryChanged = tab.observeWorkingDirectory(data)
			tab.OutputChan <- chunk
		}
		carry = append([]byte(nil), rest...)
		pending = nil
	}

	for {
		select {
		case data, ok := <-raw:
			if !ok {
				flush()
				if len(carry) > 0 {
					tab.OutputChan <- tab.replay.append(carry)
				}
				tab.markExited()
				close(tab.OutputChan)
				return
			}
			pending = append(pending, data...)
			if len(pending) >= maxCoalescedBytes {
				flush()
			} else if timer == nil {
				timer = time.NewTimer(flushWindow)
				timerC = timer.C
			}
		case <-timerC:
			flush()
		}
	}
}

func (tab *TerminalTab) markExited() {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.Status == "exited" {
		return
	}

	exitCode := 0
	if tab.cmd != nil {
		err := tab.cmd.Wait()
		if err != nil && tab.cmd.ProcessState != nil {
			exitCode = tab.cmd.ProcessState.ExitCode()
		} else if err != nil {
			exitCode = -1
		} else if tab.cmd.ProcessState != nil {
			exitCode = tab.cmd.ProcessState.ExitCode()
		}
	}

	tab.Status = "exited"
	tab.ExitCode = &exitCode
	tab.LastActiveAt = time.Now()
}

func getContainerID() string {
	hostname, err := os.Hostname()
	if err != nil {
		return ""
	}
	id := strings.TrimSpace(hostname)
	if dot := strings.IndexByte(id, '.'); dot != -1 {
		id = id[:dot]
	}
	if len(id) > 8 {
		id = id[:8]
	}
	return id
}

// Send input to PTY
func (tab *TerminalTab) SendInput(data []byte) error {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.pty == nil {
		return fmt.Errorf("PTY not available")
	}

	tab.LastActiveAt = time.Now()
	_, err := tab.pty.Write(data)
	return err
}

// Resize PTY
func (tab *TerminalTab) Resize(cols int, rows int) error {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.pty == nil {
		return fmt.Errorf("PTY not available")
	}

	tab.Cols = cols
	tab.Rows = rows
	tab.LastActiveAt = time.Now()

	return pty.Setsize(tab.pty, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	})
}

// Close PTY
func (tab *TerminalTab) Close() error {
	tab.mu.Lock()
	command := tab.cmd
	ptyFile := tab.pty
	tab.pty = nil
	tab.LastActiveAt = time.Now()
	tab.mu.Unlock()

	if command != nil && command.Process != nil {
		terminateProcessTree(command.Process.Pid, 250*time.Millisecond)
	}
	if ptyFile == nil {
		return nil
	}
	return ptyFile.Close()
}

func (tab *TerminalTab) snapshotExitCode() *int {
	tab.mu.Lock()
	defer tab.mu.Unlock()
	if tab.ExitCode == nil {
		return nil
	}
	exitCode := *tab.ExitCode
	return &exitCode
}

func terminateProcessTree(rootPID int, gracePeriod time.Duration) {
	if rootPID <= 1 {
		return
	}

	descendants := descendantProcessIDs(rootPID)
	processGroupID, groupErr := syscall.Getpgid(rootPID)
	if groupErr == nil && processGroupID == rootPID {
		_ = syscall.Kill(-processGroupID, syscall.SIGTERM)
	} else {
		_ = syscall.Kill(rootPID, syscall.SIGTERM)
	}
	for _, processID := range descendants {
		_ = syscall.Kill(processID, syscall.SIGTERM)
	}

	deadline := time.Now().Add(gracePeriod)
	for time.Now().Before(deadline) && processExists(rootPID) {
		time.Sleep(10 * time.Millisecond)
	}

	if groupErr == nil && processGroupID == rootPID {
		_ = syscall.Kill(-processGroupID, syscall.SIGKILL)
	} else {
		_ = syscall.Kill(rootPID, syscall.SIGKILL)
	}
	for _, processID := range descendants {
		_ = syscall.Kill(processID, syscall.SIGKILL)
	}
}

func descendantProcessIDs(rootPID int) []int {
	childrenByParent := make(map[int][]int)
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		processID, err := strconv.Atoi(entry.Name())
		if err != nil || processID <= 1 {
			continue
		}
		parentID, err := processParentID(processID)
		if err == nil {
			childrenByParent[parentID] = append(childrenByParent[parentID], processID)
		}
	}

	result := make([]int, 0)
	queue := append([]int(nil), childrenByParent[rootPID]...)
	for len(queue) > 0 {
		processID := queue[0]
		queue = queue[1:]
		result = append(result, processID)
		queue = append(queue, childrenByParent[processID]...)
	}
	sort.Sort(sort.Reverse(sort.IntSlice(result)))
	return result
}

func processParentID(processID int) (int, error) {
	file, err := os.Open(fmt.Sprintf("/proc/%d/status", processID))
	if err != nil {
		return 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) == 2 && fields[0] == "PPid:" {
			return strconv.Atoi(fields[1])
		}
	}
	if err := scanner.Err(); err != nil {
		return 0, err
	}
	return 0, fmt.Errorf("parent process ID is unavailable")
}

func processExists(processID int) bool {
	err := syscall.Kill(processID, 0)
	return err == nil || err == syscall.EPERM
}
