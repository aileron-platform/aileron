package handler

import (
	"go.uber.org/zap"

	"workspace-terminal/internal/model"
	"workspace-terminal/internal/service"
)

const (
	createModeAlways         = "always"
	createModeDefaultIfEmpty = "default_if_empty"
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

	createMode, ok := msg.Data["create_mode"].(string)
	if !ok || (createMode != createModeAlways && createMode != createModeDefaultIfEmpty) {
		h.sendError(client, "INVALID_PARAMS", "")
		return
	}

	workingDirectory, ok := msg.Data["working_directory"].(string)
	if !ok || workingDirectory == "" {
		workingDirectory = "/workspace"
	}
	fallbackWorkingDirectory, _ := msg.Data["fallback_working_directory"].(string)

	createTab := func(directory string) (*service.TerminalTab, bool, error) {
		if createMode == createModeDefaultIfEmpty {
			return h.terminalMgr.GetOrCreateDefaultTab(
				client.WorkspaceID,
				int(cols),
				int(rows),
				directory,
			)
		}
		tab, err := h.terminalMgr.CreateTab(
			client.WorkspaceID,
			int(cols),
			int(rows),
			directory,
		)
		return tab, true, err
	}

	tab, created, err := createTab(workingDirectory)
	if err != nil &&
		fallbackWorkingDirectory != "" &&
		fallbackWorkingDirectory != workingDirectory {
		h.logger.Debug(
			"Requested terminal working directory is unavailable; using fallback",
			zap.String("working_directory", workingDirectory),
			zap.String("fallback_working_directory", fallbackWorkingDirectory),
		)
		tab, created, err = createTab(fallbackWorkingDirectory)
	}
	if err != nil {
		h.logger.Error("Failed to create tab", zap.Error(err))
		h.sendError(client, "TAB_CREATION_FAILED", err.Error())
		return
	}

	if !created {
		h.handleListTabs(client, msg)
		h.logger.Debug("Default tab already exists",
			zap.String("tab_id", tab.TabID),
			zap.String("workspace_id", client.WorkspaceID))
		return
	}

	metadata := service.TabMetadata(tab)
	response := model.NewTabCreatedMessage(metadata)
	h.broadcastToWorkspace(client.WorkspaceID, response)

	go h.monitorTabOutput(client.WorkspaceID, tab)

	h.logger.Info("Tab created",
		zap.String("tab_id", metadata.TabID),
		zap.String("working_directory", metadata.WorkingDirectory),
		zap.String("workspace_id", client.WorkspaceID))
}

func (h *WebSocketHandler) handleCloseTab(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	exitCode, err := h.terminalMgr.CloseTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.logger.Error("Failed to close tab", zap.Error(err))
		h.sendError(client, "TAB_CLOSE_FAILED", err.Error())
		return
	}

	response := model.NewTabClosedMessage(msg.TabID, exitCode)
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

	err := h.terminalMgr.ValidateTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.logger.Error("Failed to switch tab", zap.Error(err))
		h.sendError(client, "TAB_SWITCH_FAILED", err.Error())
		return
	}

	response := model.NewTabSwitchedMessage(msg.TabID)
	h.sendMessage(client, response)

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

	tabsList := make([]model.TerminalTabMetadata, 0, len(tabs))
	for _, tab := range tabs {
		tabsList = append(tabsList, service.TabMetadata(tab))
	}

	response := model.NewTabListMessage(tabsList)
	h.sendMessage(client, response)
}

func (h *WebSocketHandler) handleReplay(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	fromSeq, ok := msg.Data["from_seq"].(float64)
	if !ok {
		h.sendError(client, "INVALID_PARAMS", "from_seq is required and must be a number")
		return
	}

	chunks, floorSeq, replayable, err := h.terminalMgr.ReplayFrom(client.WorkspaceID, msg.TabID, uint64(fromSeq))
	if err != nil {
		h.sendError(client, "INVALID_TAB_ID", err.Error())
		return
	}
	if !replayable {
		h.sendMessage(client, model.NewReplayResetMessage(msg.TabID, uint64(fromSeq), floorSeq))
		return
	}

	for _, chunk := range chunks {
		if err := h.sendMessage(client, model.NewOutputMessage(msg.TabID, chunk.Seq, chunk.Data)); err != nil {
			h.logger.Error("Failed to replay output",
				zap.String("client_id", client.ID),
				zap.String("tab_id", msg.TabID),
				zap.Error(err))
			return
		}
	}
}

func (h *WebSocketHandler) handleClear(client *model.Client, msg *model.Message) {
	if msg.TabID == "" {
		h.sendError(client, "INVALID_PARAMS", "tab_id is required")
		return
	}

	floorSeq, err := h.terminalMgr.ClearTab(client.WorkspaceID, msg.TabID)
	if err != nil {
		h.sendError(client, "INVALID_TAB_ID", err.Error())
		return
	}

	h.broadcastToWorkspace(client.WorkspaceID, model.NewTabClearedMessage(msg.TabID, floorSeq))

	h.logger.Info("Terminal cleared",
		zap.String("tab_id", msg.TabID),
		zap.String("workspace_id", client.WorkspaceID))
}

func (h *WebSocketHandler) monitorTabOutput(workspaceID string, tab *service.TerminalTab) {
	for chunk := range tab.OutputChan {
		if chunk.Data == nil {
			continue
		}
		msg := model.NewOutputMessage(tab.TabID, chunk.Seq, chunk.Data)
		h.broadcastToWorkspace(workspaceID, msg)
		if chunk.WorkingDirectoryChanged {
			h.broadcastToWorkspace(
				workspaceID,
				model.NewTabUpdatedMessage(service.TabMetadata(tab)),
			)
		}
	}

	h.logger.Info("Tab output monitor stopped",
		zap.String("tab_id", tab.TabID),
		zap.String("workspace_id", workspaceID))
}
