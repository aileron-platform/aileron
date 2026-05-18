/**
 * AcpToolWidget - ACP tool-specific widget container.
 */

import React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Terminal,
  PenTool,
  HelpCircle,
} from 'lucide-react';
import type { AcpToolWidgetProps, AcpToolWidgetType, ToolStatus } from './AcpToolWidget/types';
import { AcpReadWidget } from './AcpToolWidget/AcpReadWidget';
import { AcpWriteWidget } from './AcpToolWidget/AcpWriteWidget';
import { AcpBashWidget } from './AcpToolWidget/AcpBashWidget';
import { AcpGenericWidget } from './AcpToolWidget/AcpGenericWidget';
import {
  extractAcpCommand,
  extractAcpKind,
  extractAcpPath,
  extractAcpTitle,
} from './AcpToolWidget/acpRawPayload';

const widgetMap: Record<AcpToolWidgetType, React.FC<any>> = {
  read: AcpReadWidget,
  write: AcpWriteWidget,
  terminal: AcpBashWidget,
  generic: AcpGenericWidget,
};

const widgetIconMap: Record<AcpToolWidgetType, React.ComponentType<{ className?: string }>> = {
  read: FileText,
  write: PenTool,
  terminal: Terminal,
  generic: HelpCircle,
};

const getStatusDotClass = (status: ToolStatus): string => {
  switch (status) {
    case 'in_progress':
      return 'bg-blue-500 animate-pulse';
    case 'completed':
      return 'bg-green-500';
    case 'error':
      return 'bg-red-500';
    default:
      return 'bg-gray-400';
  }
};

export const AcpToolWidget: React.FC<AcpToolWidgetProps> = ({
  toolName,
  widgetType,
  status,
  input,
  output,
  error,
  collapsible = true,
  defaultExpanded = false,
}) => {
  const { t } = useI18n();
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
  const [isHovered, setIsHovered] = React.useState(false);
  const WidgetComponent = widgetMap[widgetType] || AcpGenericWidget;
  const Icon = widgetIconMap[widgetType] || HelpCircle;

  const acpInput = (input ?? {}) as Record<string, unknown>;
  const acpKind = extractAcpKind(acpInput);

  const headerInfo = React.useMemo(() => {
    const title = extractAcpTitle(acpInput, toolName || t('workspace.chat.widgets.labels.acpTool'));
    switch (widgetType) {
      case 'read':
        return {
          label: t('workspace.chat.widgets.labels.fileContent'),
          detail: extractAcpPath(acpInput, output, toolName || '') || title,
        };
      case 'write':
        return {
          label: acpKind === 'edit' ? t('workspace.chat.widgets.labels.editingFile') : t('workspace.chat.widgets.labels.writingFile'),
          detail: extractAcpPath(acpInput, output, toolName || '') || title,
        };
      case 'terminal':
        return {
          label: t('workspace.chat.widgets.labels.terminal'),
          detail: extractAcpCommand(acpInput, toolName || '') || title,
        };
      default:
        return {
          label: t('workspace.chat.widgets.labels.acpTool'),
          detail: title || toolName,
        };
    }
  }, [acpInput, acpKind, output, toolName, widgetType, t]);

  return (
    <div
      className={cn(
        'border overflow-hidden font-mono text-sm',
        'bg-white dark:bg-zinc-900 border-gray-200 dark:border-zinc-700 text-gray-900 dark:text-zinc-100'
      )}
    >
      <div
        className={cn(
          'flex items-center gap-2 px-2 py-1 border-b',
          'bg-gray-50/80 dark:bg-zinc-800/50 border-gray-200 dark:border-zinc-700',
          collapsible && 'cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors'
        )}
        onClick={collapsible ? () => setIsExpanded((prev) => !prev) : undefined}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {isHovered && collapsible ? (
          isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
          )
        ) : (
          <Icon className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
        )}

        <span className="text-xs text-gray-700 dark:text-zinc-300">
          {headerInfo.label}:
        </span>
        {headerInfo.detail && (
          <code className="text-xs font-mono bg-white dark:bg-zinc-800 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-600 flex-1 truncate">
            {headerInfo.detail}
          </code>
        )}
        <div className="flex items-center ml-auto">
          <div className={cn('h-2 w-2 rounded-full', getStatusDotClass(status))} />
        </div>
      </div>

      {(!collapsible || isExpanded) && (
        <WidgetComponent
          input={input}
          output={output}
          error={error}
          status={status}
          isExpanded={isExpanded}
          toolType={toolName}
        />
      )}
    </div>
  );
};

export default AcpToolWidget;
