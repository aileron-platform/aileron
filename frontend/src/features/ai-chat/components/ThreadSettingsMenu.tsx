import { useState, type ReactNode } from 'react';
import { Check, ClipboardList, Cpu, Play } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { AgenticToolId, ToolCapability, WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { agentIconSrcByTool } from './agentIcons';
import { selectMode, selectModel, selectTool, type ThreadSettings } from '../model/threadSettingsModel';

interface ThreadSettingsMenuProps {
  capabilities: WorkspaceCapabilities;
  settings: ThreadSettings;
  locked: boolean;
  onChange: (settings: ThreadSettings) => void;
}

const findSelectedTool = (
  capabilities: WorkspaceCapabilities,
  toolId: AgenticToolId,
): ToolCapability | null => capabilities.tools.find((tool) => tool.id === toolId) ?? null;

const menuTriggerClass =
  'inline-flex h-8 min-w-0 items-center gap-2 rounded-md px-2 text-sm text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50';

const AgentIcon = ({ toolId }: { toolId: AgenticToolId }) => {
  return <img src={agentIconSrcByTool[toolId]} alt="" className="h-4 w-4 shrink-0 rounded-sm" aria-hidden="true" />;
};

const ModeIcon = ({ mode }: { mode: NonNullable<ThreadSettings['claudeMode']> }) => {
  if (mode === 'plan') {
    return <ClipboardList className="h-4 w-4 shrink-0" aria-hidden="true" />;
  }

  return <Play className="h-4 w-4 shrink-0" aria-hidden="true" />;
};

interface OptionButtonProps {
  ariaLabel?: string;
  selected: boolean;
  icon?: ReactNode;
  children: ReactNode;
  onClick: () => void;
}

const OptionButton = ({ ariaLabel, selected, icon, children, onClick }: OptionButtonProps) => (
  <button
    type="button"
    aria-label={ariaLabel}
    onClick={onClick}
    className={cn(
      'flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent',
      selected && 'bg-accent text-accent-foreground',
    )}
  >
    <span className="flex min-w-0 items-center gap-2">
      {icon}
      <span className="truncate">{children}</span>
    </span>
    {selected && <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
  </button>
);

export const AgentSettingsMenu = ({ capabilities, settings, locked, onChange }: ThreadSettingsMenuProps) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label={t('aiChat.settings.tool')} className={menuTriggerClass} disabled={locked}>
          <AgentIcon toolId={settings.agenticTool} />
          <span className="truncate">{settings.agenticTool}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-2">
        <section className="space-y-1">
          <div className="px-2 text-xs font-medium text-muted-foreground">{t('aiChat.settings.tool')}</div>
          {capabilities.tools.map((tool) => (
            <OptionButton
              key={tool.id}
              ariaLabel={tool.id}
              selected={settings.agenticTool === tool.id}
              icon={<AgentIcon toolId={tool.id} />}
              onClick={() => {
                onChange(selectTool(capabilities, settings, tool.id));
                setOpen(false);
              }}
            >
              {tool.id}
            </OptionButton>
          ))}
        </section>
      </PopoverContent>
    </Popover>
  );
};

export const ModelSettingsMenu = ({ capabilities, settings, locked, onChange }: ThreadSettingsMenuProps) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const selectedTool = findSelectedTool(capabilities, settings.agenticTool);

  if (locked || !selectedTool) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label={t('aiChat.settings.model')} className={menuTriggerClass}>
          <Cpu className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="max-w-48 truncate">{settings.model}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 space-y-1 p-2">
        <div className="px-2 pb-1 text-xs font-medium text-muted-foreground">{t('aiChat.settings.model')}</div>
        {selectedTool.models.map((model) => (
          <OptionButton
            key={model}
            ariaLabel={model}
            selected={settings.model === model}
            onClick={() => {
              onChange(selectModel(settings, model));
              setOpen(false);
            }}
          >
            {model}
          </OptionButton>
        ))}
      </PopoverContent>
    </Popover>
  );
};

export const ModeSettingsMenu = ({ capabilities, settings, locked, onChange }: ThreadSettingsMenuProps) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const selectedTool = findSelectedTool(capabilities, settings.agenticTool);

  if (locked || !selectedTool?.modes || !settings.claudeMode) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label={t('aiChat.settings.mode')} className={menuTriggerClass}>
          <ModeIcon mode={settings.claudeMode} />
          <span>{t(`aiChat.settings.${settings.claudeMode}`)}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-44 space-y-1 p-2">
        {selectedTool.modes.map((mode) => (
          <OptionButton
            key={mode}
            ariaLabel={t(`aiChat.settings.${mode}`)}
            selected={settings.claudeMode === mode}
            icon={<ModeIcon mode={mode} />}
            onClick={() => {
              onChange(selectMode(settings, mode));
              setOpen(false);
            }}
          >
            {t(`aiChat.settings.${mode}`)}
          </OptionButton>
        ))}
      </PopoverContent>
    </Popover>
  );
};
