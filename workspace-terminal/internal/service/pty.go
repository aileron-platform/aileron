package service

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/creack/pty"
	"github.com/google/uuid"
)

// 建立 PTY
func createPTY(workspacePath string, cols int, rows int) (*TerminalTab, error) {
	// 建立 shell 命令（同時使用 login + interactive）
	cmd := exec.Command("/bin/bash", "-l", "-i")
	cmd.Dir = workspacePath
	// 設置環境變量，包括 PS1 提示符以顯示用戶名和容器ID
	env := os.Environ()
	env = append(env,
		"TERM=xterm-256color",
		"COLORTERM=truecolor",
		"LANG=en_US.UTF-8",
		"LC_ALL=en_US.UTF-8",
		"BRACKETED_PASTE=1",
	)
	if os.Getenv("HOME") == "" {
		env = append(env, "HOME="+workspacePath)
	}

	containerID := getContainerID()
	if containerID == "" {
		containerID = "container"
	}
	env = append(env, fmt.Sprintf("CONTAINER_ID=%s", containerID))
	ps1 := fmt.Sprintf(`\u@\h[%s]:\w$ `, containerID)
	env = append(env, fmt.Sprintf("PS1=%s", ps1))
	bashrcPath := filepath.Join(workspacePath, ".bashrc")
	env = append(env, fmt.Sprintf("BASH_ENV=%s", bashrcPath))
	cmd.Env = env

	// 啟動 PTY
	ptmx, err := pty.StartWithSize(cmd, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to start PTY: %w", err)
	}

	tab := &TerminalTab{
		TabID:         "tab_" + uuid.New().String(),
		SessionID:     fmt.Sprintf("shell_%s_%s", time.Now().Format("20060102150405"), uuid.New().String()[:8]),
		Cols:          cols,
		Rows:          rows,
		WorkspacePath: workspacePath,
		CreatedAt:     time.Now(),
		LastActiveAt:  time.Now(),
		pty:           ptmx,
		cmd:           cmd,
		OutputChan:    make(chan []byte, 256),
	}

	// 啟動輸出監控 goroutine
	go monitorPTYOutput(tab)

	return tab, nil
}

// 監控 PTY 輸出
func monitorPTYOutput(tab *TerminalTab) {
	buf := make([]byte, 4096)
	for {
		n, err := tab.pty.Read(buf)
		if err != nil {
			close(tab.OutputChan)
			return
		}
		if n > 0 {
			// 複製數據以避免競態條件
			data := make([]byte, n)
			copy(data, buf[:n])
			select {
			case tab.OutputChan <- data:
			default:
				// channel 滿時丟棄舊資料
			}
		}
	}
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

// 發送輸入到 PTY
func (tab *TerminalTab) SendInput(data []byte) error {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.pty == nil {
		return fmt.Errorf("PTY not available")
	}

	_, err := tab.pty.Write(data)
	return err
}

// 調整 PTY 大小
func (tab *TerminalTab) Resize(cols int, rows int) error {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.pty == nil {
		return fmt.Errorf("PTY not available")
	}

	tab.Cols = cols
	tab.Rows = rows

	return pty.Setsize(tab.pty, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	})
}

// 關閉 PTY
func (tab *TerminalTab) Close() error {
	tab.mu.Lock()
	defer tab.mu.Unlock()

	if tab.cmd != nil && tab.cmd.Process != nil {
		tab.cmd.Process.Kill()
	}
	if tab.pty != nil {
		return tab.pty.Close()
	}
	return nil
}
