/**
 * JobEditDialog - Edit automation job dialog (使用共用組件)
 */

import React, { useEffect, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('JobEditDialog');
import { AutomationJobEditDialog, type SchedulerWorkspaceSummary } from '@/shared/components/composite';
import { useAutomation } from '../providers/AutomationProvider';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { workspaceApi } from '../services/workspaceApi';

export const JobEditDialog: React.FC = () => {
  const { state, closeEditDialog, updateTask } = useAutomation();
  const [workspaces, setWorkspaces] = useState<SchedulerWorkspaceSummary[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);

  // 載入工作區列表
  useEffect(() => {
    if (!state.isEditDialogOpen) {
      setWorkspaces([]);
      setWorkspacesLoading(false);
      return;
    }

    const controller = new AbortController();
    setWorkspacesLoading(true);

    const selectedId = state.editingTask?.workspaceId ?? null;

    void (async () => {
      try {
        const items = await workspaceApi.list(controller.signal);
        if (controller.signal.aborted) return;

        let resolvedItems = items;
        if (selectedId && !items.some(item => item.id === selectedId)) {
          resolvedItems = [...items, { id: selectedId, name: selectedId }];
        }
        setWorkspaces(resolvedItems);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load scheduler workspaces', { error });
        setWorkspaces([]);
      } finally {
        if (!controller.signal.aborted) {
          setWorkspacesLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [state.editingTask?.workspaceId, state.isEditDialogOpen]);

  // 載入 Slash Commands
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
        const items = await workspaceApi.listSlashCommands(
          state.editingTask.workspaceId,
          controller.signal
        );
        if (controller.signal.aborted) return;
        setCommands(items);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load scheduler slash commands', { error });
        setCommands([]);
      } finally {
        if (!controller.signal.aborted) {
          setCommandsLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [state.editingTask?.workspaceId, state.isEditDialogOpen]);

  // 收集現有的標籤建議
  const existingTags = React.useMemo(() => {
    const tags = new Set<string>();
    state.automationJobs.forEach(task => task.tags.forEach(tag => tags.add(tag)));
    return Array.from(tags);
  }, [state.automationJobs]);

  return (
    <AutomationJobEditDialog
      isOpen={state.isEditDialogOpen}
      task={state.editingTask}
      loading={state.editLoading}
      saving={state.editing}
      onClose={closeEditDialog}
      onSave={updateTask}
      workspaces={workspaces}
      workspacesLoading={workspacesLoading}
      commands={commands}
      commandsLoading={commandsLoading}
      existingTags={existingTags}
    />
  );
};

export default JobEditDialog;
