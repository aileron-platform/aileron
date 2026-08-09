import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AgentSettingsMenu,
  defaultSettings,
  ModeSettingsMenu,
  ModelSettingsMenu,
  normalizeThreadSettings,
  type AgenticToolId,
  type ThreadSettings,
} from '@/features/ai-chat/public';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationWorkspaceApi } from '../../api/automationWorkspaceApi';

interface AutomationAgentSelection {
  agenticTool: string | null | undefined;
  model: string | null | undefined;
  mode: string | null | undefined;
}

interface AutomationAgentSelectorProps {
  workspaceId: string;
  value: AutomationAgentSelection;
  onChange(value: AutomationAgentSelection): void;
}

const toThreadSettings = (
  value: AutomationAgentSelection,
  fallback: ThreadSettings,
): ThreadSettings => {
  if (!value.agenticTool || !value.model) return fallback;
  return {
    agenticTool: value.agenticTool as AgenticToolId,
    model: value.model,
    claudeMode: value.mode as ThreadSettings['claudeMode'],
  };
};

export function AutomationAgentSelector({
  workspaceId,
  value,
  onChange,
}: AutomationAgentSelectorProps) {
  const { t } = useI18n();
  const capabilitiesQuery = useQuery({
    queryKey: ['automation', 'workspace-capabilities', workspaceId],
    queryFn: () => automationWorkspaceApi.getCapabilities(workspaceId),
    enabled: workspaceId.length > 0,
    retry: false,
  });
  const capabilities = capabilitiesQuery.data;
  const { agenticTool, model, mode } = value;

  useEffect(() => {
    if (!capabilities || capabilities.tools.length === 0) return;
    const fallback = defaultSettings(capabilities);
    const normalized = normalizeThreadSettings(
      capabilities,
      toThreadSettings({ agenticTool, model, mode }, fallback),
    );
    if (
      normalized.agenticTool === agenticTool
      && normalized.model === model
      && normalized.claudeMode === (mode ?? null)
    ) {
      return;
    }
    onChange({
      agenticTool: normalized.agenticTool,
      model: normalized.model,
      mode: normalized.claudeMode,
    });
  }, [agenticTool, capabilities, mode, model, onChange]);

  if (!workspaceId) return null;
  if (capabilitiesQuery.isLoading) {
    return <p className="text-xs text-muted-foreground">{t('automation.form.fields.agent.loading')}</p>;
  }
  if (capabilitiesQuery.isError || !capabilities || capabilities.tools.length === 0) {
    return <p className="text-xs text-destructive">{t('automation.form.fields.agent.error')}</p>;
  }

  const settings = normalizeThreadSettings(
    capabilities,
    toThreadSettings(value, defaultSettings(capabilities)),
  );
  const handleChange = (next: ThreadSettings) => onChange({
    agenticTool: next.agenticTool,
    model: next.model,
    mode: next.claudeMode,
  });

  return (
    <div className="space-y-2">
      <Label className="text-sm">{t('automation.form.fields.agent.label')}</Label>
      <div className="flex flex-wrap items-center gap-1 rounded-md border border-border/60 p-2">
        <AgentSettingsMenu
          capabilities={capabilities}
          settings={settings}
          locked={false}
          onChange={handleChange}
        />
        <ModelSettingsMenu
          capabilities={capabilities}
          settings={settings}
          locked={false}
          onChange={handleChange}
        />
        <ModeSettingsMenu
          capabilities={capabilities}
          settings={settings}
          locked={false}
          onChange={handleChange}
        />
      </div>
      <p className="text-xs text-muted-foreground">{t('automation.form.fields.agent.help')}</p>
    </div>
  );
}
