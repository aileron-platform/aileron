import React, { useEffect, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AutomationDashboardJobEditDialog');
import { AutomationJobEditDialog } from './AutomationJobEditDialog';
import { useAutomation } from '../../providers/AutomationProvider';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { automationWorkspaceApi } from '../../api/automationWorkspaceApi';
import type { AutomationWorkspaceSummary } from '../../model/automationTypes';

export const AutomationDashboardJobEditDialog: React.FC = () => {
  const { state, closeEditDialog, updateTask } = useAutomation();
  const [workspaces, setWorkspaces] = useState<AutomationWorkspaceSummary[]>([]);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);

  useEffect(() => {
    if (!state.isEditDialogOpen) {
      setWorkspaces([]);
      return;
    }

    const controller = new AbortController();
    const selectedId = state.editingTask?.workspaceId ?? null;

    void (async () => {
      try {
        const items = await automationWorkspaceApi.list(controller.signal);
        if (controller.signal.aborted) return;

        let resolvedItems = items;
        if (selectedId && !items.some(item => item.id === selectedId)) {
          resolvedItems = [...items, { id: selectedId, name: selectedId }];
        }
        setWorkspaces(resolvedItems);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load automation workspaces', { error });
        setWorkspaces([]);
      }
    })();

    return () => controller.abort();
  }, [state.editingTask?.workspaceId, state.isEditDialogOpen]);

  useEffect(() => {
    if (!state.isEditDialogOpen || !state.editingTask?.workspaceId) {
      setCommands([]);
      setCommandsLoading(false);
      return;
    }

    const controller = new AbortController();
    setCommandsLoading(true);

    void (async () => {
      try {
        const items = await automationWorkspaceApi.listSlashCommands(
          state.editingTask.workspaceId,
          controller.signal
        );
        if (controller.signal.aborted) return;
        setCommands(items);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load automation slash commands', { error });
        setCommands([]);
      } finally {
        if (!controller.signal.aborted) {
          setCommandsLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [state.editingTask?.workspaceId, state.isEditDialogOpen]);

  return (
    <AutomationJobEditDialog
      isOpen={state.isEditDialogOpen}
      task={state.editingTask}
      loading={state.editLoading}
      saving={state.editing}
      onClose={closeEditDialog}
      onSave={updateTask}
      workspaces={workspaces}
      commands={commands}
      commandsLoading={commandsLoading}
    />
  );
};
