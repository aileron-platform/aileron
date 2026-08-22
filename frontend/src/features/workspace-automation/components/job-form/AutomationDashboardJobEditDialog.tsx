import React, { useEffect, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AutomationDashboardJobEditDialog');
import { AutomationJobEditDialog } from './AutomationJobEditDialog';
import { useAutomation } from '../../providers/AutomationProvider';
import { automationWorkspaceApi } from '../../api/automationWorkspaceApi';
import type { AutomationWorkspaceSummary } from '../../model/automationTypes';

export const AutomationDashboardJobEditDialog: React.FC = () => {
  const { state, closeEditDialog, updateTask } = useAutomation();
  const [workspaces, setWorkspaces] = useState<AutomationWorkspaceSummary[]>([]);

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

  return (
    <AutomationJobEditDialog
      isOpen={state.isEditDialogOpen}
      task={state.editingTask}
      loading={state.editLoading}
      saving={state.editing}
      onClose={closeEditDialog}
      onSave={updateTask}
      workspaces={workspaces}
    />
  );
};
