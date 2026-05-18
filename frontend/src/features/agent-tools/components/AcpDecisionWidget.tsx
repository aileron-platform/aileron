/**
 * AcpDecisionWidget - ACP tool-decision UI
 */

import React, { useMemo, useState } from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { ShieldAlert, ShieldCheck, ShieldX, Clock } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { cn } from '@/shared/utils/cn';
import type {
  ToolDecisionOption,
  ToolDecisionOutcome,
  ToolDecisionToolCall,
  ToolDecisionType,
  PermissionScope,
} from '@/features/workspace/components/ChatPanel/agentSessionTypes';
import { extractToolDecisionInput } from '@/features/workspace/components/ChatPanel/agentSessionTypes';

export interface AcpDecisionWidgetProps {
  requestId: string;
  status: 'pending' | 'approved' | 'denied' | 'timeout';
  decisionType: ToolDecisionType;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolCall?: ToolDecisionToolCall;
  options?: ToolDecisionOption[];
  reason?: string;
  content?: string;
  isWaiting?: boolean;
  onDecision?: (payload: {
    requestId: string;
    outcome: ToolDecisionOutcome;
    optionId?: string;
    scope?: PermissionScope;
    content?: string;
  }) => void;
}

const normalizeOptionId = (option: ToolDecisionOption): string | undefined =>
  option.option_id || option.optionId;

const findOptionByKind = (options: ToolDecisionOption[], kindPrefix: string) =>
  options.find((option) => option.kind?.startsWith(kindPrefix));

export const AcpDecisionWidget: React.FC<AcpDecisionWidgetProps> = ({
  requestId,
  status,
  decisionType,
  toolName,
  toolInput,
  toolCall,
  options,
  reason,
  content,
  isWaiting = false,
  onDecision,
}) => {
  const { t } = useI18n();
  const [userInput, setUserInput] = useState('');

  const fallbackOptions: ToolDecisionOption[] = useMemo(() => [
    { option_id: 'allow', name: t('workspace.chat.widgets.decision.allow'), kind: 'allow_once', scope: 'once' },
    { option_id: 'reject', name: t('workspace.chat.widgets.decision.reject'), kind: 'reject_once', scope: 'once' },
  ], [t]);

  const isPending = status === 'pending';
  const isActive = isPending && !isWaiting;
  const isApproved = status === 'approved';
  const isDenied = status === 'denied' || status === 'timeout';

  const hasOptions = !!(options && options.length > 0);
  const normalizedOptions = useMemo(() => {
    if (options && options.length > 0) return options;
    return fallbackOptions;
  }, [options]);

  const headerIcon = () => {
    if (isWaiting) return <Clock className="h-5 w-5" />;
    if (isApproved) return <ShieldCheck className="h-5 w-5" />;
    if (isDenied) return <ShieldX className="h-5 w-5" />;
    return <ShieldAlert className="h-5 w-5" />;
  };

  const headerStyle = () => {
    if (isWaiting) return 'bg-muted/50 border-border opacity-70';
    if (isPending) return 'bg-amber-50/50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800';
    if (isApproved) return 'bg-emerald-50/50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800';
    return 'bg-rose-50/50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-800';
  };

  const handleDecision = (payload: { outcome: ToolDecisionOutcome; optionId?: string; scope?: PermissionScope; content?: string }) => {
    if (!onDecision || !isActive) return;
    onDecision({ requestId, ...payload });
  };

  const handleOptionClick = (option: ToolDecisionOption) => {
    const optionId = normalizeOptionId(option);
    handleDecision({
      outcome: 'selected',
      optionId,
      scope: option.scope,
    });
  };

  const handleFallbackAllow = () => {
    handleDecision({ outcome: 'selected' });
  };

  const handleFallbackReject = () => {
    handleDecision({ outcome: 'cancelled' });
  };

  const handleUserInputSubmit = () => {
    const allowOption = hasOptions ? findOptionByKind(normalizedOptions, 'allow') : undefined;
    handleDecision({
      outcome: 'selected',
      optionId: allowOption ? normalizeOptionId(allowOption) : undefined,
      scope: allowOption?.scope,
      content: userInput,
    });
  };

  const handleUserInputCancel = () => {
    const rejectOption = hasOptions ? findOptionByKind(normalizedOptions, 'reject') : undefined;
    handleDecision({
      outcome: 'cancelled',
      optionId: rejectOption ? normalizeOptionId(rejectOption) : undefined,
      scope: rejectOption?.scope,
    });
  };

  const displayToolName = toolCall?.title || toolName || t('workspace.chat.widgets.labels.acpTool');
  const displayToolInput = useMemo(
    () => extractToolDecisionInput(toolCall, toolInput),
    [toolCall, toolInput],
  );
  const hasDisplayToolInput = Object.keys(displayToolInput).length > 0;

  return (
    <div className={cn('border p-4 space-y-3', headerStyle())}>
      <div className="flex items-center gap-3">
        <div className="rounded-full bg-background/70 p-2 text-foreground">
          {headerIcon()}
        </div>
        <div>
          <div className="text-sm font-semibold">
            {decisionType === 'user_input' ? t('workspace.chat.widgets.decision.needInput') : t('workspace.chat.widgets.decision.needPermission')}
          </div>
          <div className="text-xs text-muted-foreground">{displayToolName}</div>
        </div>
      </div>

      <div className="rounded-md bg-background/60 p-3 text-xs text-muted-foreground">
        <div className="font-medium text-foreground mb-2">{t('workspace.chat.widgets.decision.toolInput')}</div>
        {hasDisplayToolInput ? (
          <pre className="whitespace-pre-wrap break-words">{JSON.stringify(displayToolInput, null, 2)}</pre>
        ) : (
          <div className="text-muted-foreground">{t('workspace.chat.widgets.decision.noParameters')}</div>
        )}
      </div>

      {decisionType === 'user_input' && (
        <div className="space-y-2">
          {isPending ? (
            <>
              <Textarea
                value={userInput}
                onChange={(event) => setUserInput(event.target.value)}
                placeholder={t('workspace.chat.widgets.decision.replyPlaceholder')}
                disabled={!isActive}
                className="text-sm"
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleUserInputSubmit} disabled={!isActive}>
                  {t('workspace.chat.widgets.decision.submit')}
                </Button>
                <Button size="sm" variant="outline" onClick={handleUserInputCancel} disabled={!isActive}>
                  {t('common.cancel')}
                </Button>
              </div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground">
              {content || reason || t('workspace.chat.widgets.decision.completed')}
            </div>
          )}
        </div>
      )}

      {decisionType === 'permission' && (
        <div className="space-y-2">
          {hasOptions ? (
            <div className="flex flex-wrap gap-2">
              {normalizedOptions.map((option) => {
                const optionId = normalizeOptionId(option);
                return (
                  <Button
                    key={optionId || option.name}
                    size="sm"
                    variant={option.kind.startsWith('reject') ? 'outline' : 'default'}
                    onClick={() => handleOptionClick(option)}
                    disabled={!isActive}
                  >
                    {option.name}
                  </Button>
                );
              })}
            </div>
          ) : (
            <div className="flex gap-2">
              <Button size="sm" onClick={handleFallbackAllow} disabled={!isActive}>
                {t('workspace.chat.widgets.decision.allow')}
              </Button>
              <Button size="sm" variant="outline" onClick={handleFallbackReject} disabled={!isActive}>
                {t('workspace.chat.widgets.decision.reject')}
              </Button>
            </div>
          )}

          {!isPending && (reason || content) && (
            <div className="text-sm text-muted-foreground">{reason || content}</div>
          )}
        </div>
      )}

      {isWaiting && (
        <div className="text-xs text-muted-foreground">
          {t('workspace.chat.widgets.decision.waitingPrevious')}
        </div>
      )}
    </div>
  );
};

export default AcpDecisionWidget;
