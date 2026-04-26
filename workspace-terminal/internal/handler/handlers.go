package handler

import (
	"go.uber.org/zap"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

func (h *WebSocketHandler) handleCreateTab(client *model.Client, msg *model.Message) {
	cols, ok := msg.Data["cols"].(float64)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "cols is required and must be a number")
		return
	}

	rows, ok := msg.Data["rows"].(float64)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "rows is required and must be a number")
		return
	}

	name, ok := msg.Data["name"].(string)
	if !ok || name == "" {
		name = "Terminal" // Default name
	}

	workspacePath, ok := msg.Data["workspace_path"].(string)
	if !ok || workspacePath == "" {
		workspacePath = "/workspace" // Default working directory
	}

	tab, err := h.terminalMgr.CreateTab(client.WorkspaceID, int(cols), int(rows), workspacePath)
	if err != nil {
		h.logger.Error("Failed to create tab", zap.Error(err))
		h.sendError(client, "TAB_CREATION_FAILED", err.Error())
		return
	}

	response := model.NewTabCreatedMessage(tab.TabID, tab.SessionID, name, tab.WorkspacePath, tab.Cols, tab.Rows)
	h.broadcastToWorkspace(client.WorkspaceID, response)

	go h.monitorTabOutput(client.WorkspaceID, tab)

	h.logger.Info("Tab created",
		zap.String("tab_id", tab.TabID),
		zap.String("name", name),
		zap.String("workspace_id", client.WorkspaceID))
}

func (h *WebSocketHandler) handleCloseTab(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	err := h.terminalMgr.CloseTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.logger.Error("Failed to close tab", zap.Error(err))
		h.sendError(client, "TAB_CLOSE_FAILED", err.Error())
		return
	}

	response := model.NewTabClosedMessage(msg.TabID, 0)
	h.broadcastToWorkspace(client.WorkspaceID, response)

	h.logger.Info("Tab closed",
		zap.String("tab_id", msg.TabID),
		zap.String("workspace_id", client.WorkspaceID))
}

func (h *WebSocketHandler) handleSwitchTab(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	err := h.terminalMgr.SwitchTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.logger.Error("Failed to switch tab", zap.Error(err))
		h.sendError(client, "TAB_SWITCH_FAILED", err.Error())
		return
	}

	response := model.NewTabSwitchedMessage(msg.TabID)
	h.broadcastToWorkspace(client.WorkspaceID, response)

	h.logger.Info("Tab switched",
		zap.String("tab_id", msg.TabID),
		zap.String("workspace_id", client.WorkspaceID))
}

func (h *WebSocketHandler) handleInput(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	data, ok := msg.Data["data"].(string)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "data is required and must be a string")
		return
	}

	tab, err := h.terminalMgr.GetTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.sendError(client, "INVALID_TAB_ID", err.Error())
		return
	}

	err = tab.SendInput([]byte(data))
	if err != nil {
		h.logger.Error("Failed to send input", zap.Error(err))
		h.sendError(client, "INPUT_FAILED", err.Error())
		return
	}
}

func (h *WebSocketHandler) handleResize(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	cols, ok := msg.Data["cols"].(float64)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "cols is required and must be a number")
		return
	}

	rows, ok := msg.Data["rows"].(float64)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "rows is required and must be a number")
		return
	}

	tab, err := h.terminalMgr.GetTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.sendError(client, "INVALID_TAB_ID", err.Error())
		return
	}

	err = tab.Resize(int(cols), int(rows))
	if err != nil {
		h.logger.Error("Failed to resize terminal", zap.Error(err))
		h.sendError(client, "RESIZE_FAILED", err.Error())
		return
	}

	response := model.NewResizedMessage(msg.TabID, int(cols), int(rows))
	h.broadcastToWorkspace(client.WorkspaceID, response)

	h.logger.Info("Terminal resized",
		zap.String("tab_id", msg.TabID),
		zap.Int("cols", int(cols)),
		zap.Int("rows", int(rows)))
}

func (h *WebSocketHandler) handleListTabs(client *model.Client, msg *model.Message) {
	tabs, err := h.terminalMgr.ListTabs(client.WorkspaceID)
	if err != nil {
		h.logger.Error("Failed to list tabs", zap.Error(err))
		h.sendError(client, "LIST_TABS_FAILED", err.Error())
		return
	}

	tabsList := make([]map[string]interface{}, 0, len(tabs))
	for _, tab := range tabs {
		tabsList = append(tabsList, map[string]interface{}{
			"tab_id":         tab.TabID,
			"session_id":     tab.SessionID,
			"cols":           tab.Cols,
			"rows":           tab.Rows,
			"cwd":            tab.WorkspacePath,
			"created_at":     tab.CreatedAt.Unix(),
			"last_active_at": tab.LastActiveAt.Unix(),
		})
	}

	response := model.NewTabListMessage(tabsList)
	h.sendMessage(client, response)
}

func (h *WebSocketHandler) handleClear(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	tab, err := h.terminalMgr.GetTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.sendError(client, "INVALID_TAB_ID", err.Error())
		return
	}

	err = tab.SendInput([]byte("clear\n"))
	if err != nil {
		h.logger.Error("Failed to clear terminal", zap.Error(err))
		h.sendError(client, "CLEAR_FAILED", err.Error())
		return
	}
}

func (h *WebSocketHandler) monitorTabOutput(workspaceID string, tab *service.TerminalTab) {
	for data := range tab.OutputChan {
		if data == nil {
			continue
		}
		msg := model.NewOutputMessage(tab.TabID, data)
		h.broadcastToWorkspace(workspaceID, msg)
	}

	h.logger.Info("Tab output monitor stopped",
		zap.String("tab_id", tab.TabID),
		zap.String("workspace_id", workspaceID))
}
