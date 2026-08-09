import React from 'react';
import {
  Bot,
  Maximize2,
  Minimize2,
  SquareTerminal,
} from 'lucide-react';
import { CompanionChatPanel } from '@/features/ai-chat/public';
import { TerminalPanel } from '@/features/workspace/features/container-management/components/TerminalPanel';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type {
  WorkspaceCompanionActiveTab,
  WorkspaceCompanionTerminalPlacement,
} from '../providers/workspaceStateTypes';
import { resolveWorkspaceCompanionTab } from './workspaceShellSurfaceModel';

export interface WorkspaceCompanionColumnProps {
  workspaceId: string;
  userId: string;
  activeTab: WorkspaceCompanionActiveTab;
  canUseAgentChat: boolean;
  canUseTerminal: boolean;
  isExpanded?: boolean;
  terminalPlacement?: WorkspaceCompanionTerminalPlacement;
  onActiveTabChange: (tab: WorkspaceCompanionActiveTab) => void;
  onTerminalPlacementChange?: (placement: WorkspaceCompanionTerminalPlacement) => void;
  onToggleExpand?: () => void;
}

export interface WorkspaceCompanionHeaderProps {
  activeTab: WorkspaceCompanionActiveTab;
  canUseAgentChat: boolean;
  canUseTerminal: boolean;
  isExpanded: boolean;
  onActiveTabChange: (tab: WorkspaceCompanionActiveTab) => void;
  onToggleExpand: () => void;
}

const headerIconButtonClass =
  'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40';
const headerIconClass = 'h-3.5 w-3.5';

export const WorkspaceCompanionHeader: React.FC<WorkspaceCompanionHeaderProps> = ({
  activeTab,
  canUseAgentChat,
  canUseTerminal,
  isExpanded,
  onActiveTabChange,
  onToggleExpand,
}) => {
  const { t } = useI18n();
  const effectiveActiveTab = resolveWorkspaceCompanionTab(activeTab, canUseAgentChat, canUseTerminal);
  const FeatureIcon = effectiveActiveTab === 'terminal' ? SquareTerminal : Bot;
  const allowedTabs = [
    ...(canUseAgentChat ? ['ai-chat' as const] : []),
    ...(canUseTerminal ? ['terminal' as const] : []),
  ];

  if (!effectiveActiveTab) {
    return null;
  }

  return (
    <div data-testid="workspace-companion-header" className="relative flex min-w-0 flex-1 items-center gap-2">
      <div
        data-testid="workspace-companion-feature-icon"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
      >
        <FeatureIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
      </div>
      <div
        role="tablist"
        aria-label={t('aiChat.companion.tabs.label')}
        className="absolute inset-x-0 flex items-center justify-center gap-1"
      >
        {allowedTabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={effectiveActiveTab === tab}
            className={cn(
              'h-7 rounded-md px-2 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground',
              effectiveActiveTab === tab && 'bg-muted text-foreground',
            )}
            onClick={() => onActiveTabChange(tab)}
          >
            {tab === 'ai-chat'
              ? t('aiChat.companion.tabs.aiChat')
              : t('aiChat.companion.tabs.terminal')}
          </button>
        ))}
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <button
          type="button"
          aria-label={t(isExpanded ? 'aiChat.companion.restore' : 'aiChat.companion.expand')}
          className={headerIconButtonClass}
          onClick={onToggleExpand}
        >
          {isExpanded ? (
            <Minimize2 className={headerIconClass} aria-hidden="true" />
          ) : (
            <Maximize2 className={headerIconClass} aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
};

export const WorkspaceCompanionCollapsedContent: React.FC = () => (
  <div className="flex w-full flex-1 flex-col items-center pt-3">
    <Bot data-testid="workspace-companion-collapsed-icon" className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
  </div>
);

export const WorkspaceCompanionContent: React.FC<WorkspaceCompanionColumnProps> = ({
  workspaceId,
  userId,
  activeTab,
  canUseAgentChat,
  canUseTerminal,
  terminalPlacement,
  onTerminalPlacementChange,
}) => {
  const effectiveActiveTab = resolveWorkspaceCompanionTab(activeTab, canUseAgentChat, canUseTerminal);
  if (!effectiveActiveTab) {
    return null;
  }

  return effectiveActiveTab === 'terminal' ? (
    <TerminalPanel
      variant="compact"
      terminalPlacement={terminalPlacement}
      onTerminalPlacementChange={onTerminalPlacementChange}
    />
  ) : (
    <CompanionChatPanel workspaceId={workspaceId} userId={userId} />
  );
};

/**
 * Content-only companion renderer used by ProductShell. Geometry, collapse,
 * resize handles, and the collapsed rail belong to ProductShell.
 */
export const WorkspaceCompanionColumn: React.FC<WorkspaceCompanionColumnProps> = (props) => (
  <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden" data-testid="workspace-companion-column">
    <WorkspaceCompanionContent {...props} />
  </div>
);
