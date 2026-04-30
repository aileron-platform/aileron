/**
 * PermissionRequestWidget - permission request widget.
 *
 * Inspired by agor-main/apps/agor-ui/src/components/PermissionRequestBlock/PermissionRequestBlock.tsx
 * and agor-main/apps/agor-ui/src/components/PermissionModeSelector/PermissionModeSelector.tsx.
 *
 * Supports permission options for different agent SDKs:
 * - Claude Code: PermissionScope (ONCE, PROJECT, USER, LOCAL)
 * - Codex: SandboxMode + ApprovalPolicy
 * - Gemini: ApprovalMode (default, autoEdit, yolo)
 * - OpenCode: ApprovalMode (default, acceptEdits, bypassPermissions)
 */

import React, { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Check,
  X,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Clock,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Lock,
  Unlock,
  FileEdit,
  FlaskConical,
  FolderLock,
  HardDrive,
  Globe
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { ToolStatus } from './ClaudeToolWidget/types';
import {
  PermissionScope as PermissionScopeType,
  PermissionStatus as PermissionStatusType
} from '@/features/workspace/components/ChatPanel/agentSessionTypes';

export type AgentToolType = 'claude-code' | 'codex' | 'gemini' | 'opencode';

export type PermissionScope = PermissionScopeType;

export enum PermissionScopeEnum {
  ONCE = 'once',
  SESSION = 'session',
  PROJECT = 'project',
  USER = 'user',
  LOCAL = 'local',
}

export const PermissionScopeValues = {
  ONCE: 'once' as const,
  SESSION: 'session' as const,
  PROJECT: 'project' as const,
  USER: 'user' as const,
  LOCAL: 'local' as const,
};

export type CodexSandboxMode = 'read-only' | 'workspace-write' | 'danger-full-access';
export type CodexApprovalPolicy = 'untrusted' | 'on-request' | 'on-failure' | 'never';

export type GeminiPermissionMode = 'default' | 'autoEdit' | 'yolo';
export type OpenCodePermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions';

export type PermissionStatus = PermissionStatusType;

export const PermissionStatusValues = {
  PENDING: 'pending' as const,
  APPROVED: 'approved' as const,
  DENIED: 'denied' as const,
};

const claudeCodeScopeOptions = [
  {
    value: PermissionScopeValues.ONCE,
    labelKey: 'workspace.chat.widgets.permission.scope.once.label',
    descriptionKey: 'workspace.chat.widgets.permission.scope.once.description',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: PermissionScopeValues.SESSION,
    labelKey: 'workspace.chat.widgets.permission.scope.session.label',
    descriptionKey: 'workspace.chat.widgets.permission.scope.session.description',
    icon: Clock,
    color: 'text-blue-500'
  },
  {
    value: PermissionScopeValues.PROJECT,
    labelKey: 'workspace.chat.widgets.permission.scope.project.label',
    descriptionKey: 'workspace.chat.widgets.permission.scope.project.description',
    icon: FolderLock,
    color: 'text-green-500'
  },
  {
    value: PermissionScopeValues.USER,
    labelKey: 'workspace.chat.widgets.permission.scope.user.label',
    descriptionKey: 'workspace.chat.widgets.permission.scope.user.description',
    icon: Globe,
    color: 'text-purple-500'
  },
  {
    value: PermissionScopeValues.LOCAL,
    labelKey: 'workspace.chat.widgets.permission.scope.local.label',
    descriptionKey: 'workspace.chat.widgets.permission.scope.local.description',
    icon: HardDrive,
    color: 'text-orange-500'
  },
];

const codexSandboxOptions = [
  {
    value: 'read-only' as CodexSandboxMode,
    label: 'read-only',
    descriptionKey: 'workspace.chat.widgets.permission.codex.sandbox.readOnly',
  },
  {
    value: 'workspace-write' as CodexSandboxMode,
    label: 'workspace-write',
    descriptionKey: 'workspace.chat.widgets.permission.codex.sandbox.workspaceWrite',
  },
  {
    value: 'danger-full-access' as CodexSandboxMode,
    label: 'full-access',
    descriptionKey: 'workspace.chat.widgets.permission.codex.sandbox.fullAccess',
  },
];

const codexApprovalOptions = [
  {
    value: 'untrusted' as CodexApprovalPolicy,
    label: 'untrusted',
    descriptionKey: 'workspace.chat.widgets.permission.codex.approval.untrusted',
  },
  {
    value: 'on-request' as CodexApprovalPolicy,
    label: 'on-request',
    descriptionKey: 'workspace.chat.widgets.permission.codex.approval.onRequest',
  },
  {
    value: 'on-failure' as CodexApprovalPolicy,
    label: 'on-failure',
    descriptionKey: 'workspace.chat.widgets.permission.codex.approval.onFailure',
  },
  {
    value: 'never' as CodexApprovalPolicy,
    label: 'never',
    descriptionKey: 'workspace.chat.widgets.permission.codex.approval.never',
  },
];

const geminiModeOptions = [
  {
    value: 'default' as GeminiPermissionMode,
    label: 'default',
    descriptionKey: 'workspace.chat.widgets.permission.gemini.default',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: 'autoEdit' as GeminiPermissionMode,
    label: 'autoEdit',
    descriptionKey: 'workspace.chat.widgets.permission.gemini.autoEdit',
    icon: FileEdit,
    color: 'text-green-500'
  },
  {
    value: 'yolo' as GeminiPermissionMode,
    label: 'yolo',
    descriptionKey: 'workspace.chat.widgets.permission.gemini.yolo',
    icon: Unlock,
    color: 'text-orange-500'
  },
];

const opencodeModeOptions = [
  {
    value: 'default' as OpenCodePermissionMode,
    label: 'default',
    descriptionKey: 'workspace.chat.widgets.permission.opencode.default',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: 'acceptEdits' as OpenCodePermissionMode,
    label: 'acceptEdits',
    descriptionKey: 'workspace.chat.widgets.permission.opencode.acceptEdits',
    icon: FileEdit,
    color: 'text-green-500'
  },
  {
    value: 'bypassPermissions' as OpenCodePermissionMode,
    label: 'bypassPermissions',
    descriptionKey: 'workspace.chat.widgets.permission.opencode.bypassPermissions',
    icon: Unlock,
    color: 'text-orange-500'
  },
];

interface WidgetProps {
  input?: Record<string, any>;
  output?: string | Record<string, any>;
  error?: string;
  status: ToolStatus;
  isExpanded: boolean;
}

export interface PermissionRequestWidgetProps extends WidgetProps {
  agentTool?: AgentToolType;
  isWaiting?: boolean;
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onCodexApprove?: (messageId: string, sandbox: CodexSandboxMode, approval: CodexApprovalPolicy) => void;
  onGeminiApprove?: (messageId: string, mode: GeminiPermissionMode) => void;
  onOpenCodeApprove?: (messageId: string, mode: OpenCodePermissionMode) => void;
  onDeny?: (messageId: string) => void;
  requested_at?: string;
}

export const PermissionRequestWidget: React.FC<PermissionRequestWidgetProps> = ({
  input,
  agentTool = 'claude-code',
  isWaiting = false,
  onApprove,
  onCodexApprove,
  onGeminiApprove,
  onOpenCodeApprove,
  onDeny,
  requested_at,
}) => {
  const { t } = useI18n();
  const [rememberChoice, setRememberChoice] = useState<boolean>(false);
  const [selectedScope, setSelectedScope] = useState<PermissionScope>(PermissionScopeValues.ONCE);
  const [codexSandbox, setCodexSandbox] = useState<CodexSandboxMode>('workspace-write');
  const [codexApproval, setCodexApproval] = useState<CodexApprovalPolicy>('on-request');
  const [geminiMode, setGeminiMode] = useState<GeminiPermissionMode>('autoEdit');
  const [opencodeMode, setOpencodeMode] = useState<OpenCodePermissionMode>('acceptEdits');
  const [showDetails, setShowDetails] = useState<boolean>(true);

  const tool_name = input?.tool_name || 'Unknown Tool';
  const tool_input = input?.tool_input || {};
  const permissionStatus = input?.permission_status || PermissionStatusValues.PENDING;
  const approved_at = input?.approved_at;
  const denied_at = input?.denied_at;
  const message_id = input?.message_id || '';
  const reason = input?.reason || '';

  const isApproved = permissionStatus === PermissionStatusValues.APPROVED;
  const isDenied = permissionStatus === PermissionStatusValues.DENIED;
  const isPending = permissionStatus === PermissionStatusValues.PENDING;
  const isActive = isPending && !isWaiting;

  const getStateStyles = () => {
    if (isWaiting) {
      return {
        container: 'bg-muted/50 border-border opacity-70',
        iconBg: 'bg-muted',
        iconColor: 'text-muted-foreground',
      };
    }
    if (isActive) {
      return {
        container: 'bg-amber-50/50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800',
        iconBg: 'bg-amber-100 dark:bg-amber-900/50',
        iconColor: 'text-amber-600 dark:text-amber-400',
      };
    }
    if (isApproved) {
      return {
        container: 'bg-green-50/50 dark:bg-green-950/30 border-green-200 dark:border-green-800',
        iconBg: 'bg-green-100 dark:bg-green-900/50',
        iconColor: 'text-green-600 dark:text-green-400',
      };
    }
    if (isDenied) {
      return {
        container: 'bg-red-50/50 dark:bg-red-950/30 border-red-200 dark:border-red-800',
        iconBg: 'bg-red-100 dark:bg-red-900/50',
        iconColor: 'text-red-600 dark:text-red-400',
      };
    }
    return {
      container: 'bg-muted/50 border-border',
      iconBg: 'bg-muted',
      iconColor: 'text-muted-foreground',
    };
  };

  const getIcon = () => {
    if (isWaiting) return <Clock className="h-5 w-5" />;
    if (isActive) return <ShieldAlert className="h-5 w-5" />;
    if (isApproved) return <ShieldCheck className="h-5 w-5" />;
    if (isDenied) return <ShieldX className="h-5 w-5" />;
    return <ShieldAlert className="h-5 w-5" />;
  };

  const getTitle = () => {
    if (isWaiting) return t('workspace.chat.widgets.permission.title.waiting');
    if (isActive) return t('workspace.chat.widgets.permission.title.active');
    if (isApproved) return t('workspace.chat.widgets.permission.title.approved');
    if (isDenied) return t('workspace.chat.widgets.permission.title.denied');
    return t('workspace.chat.widgets.permission.title.default');
  };

  const getSubtitle = () => {
    if (isWaiting) return t('workspace.chat.widgets.permission.subtitle.waiting');
    if (isActive) return t('workspace.chat.widgets.permission.subtitle.active');
    if (isApproved && approved_at) {
      return t('workspace.chat.widgets.permission.subtitle.approvedAt', {
        date: new Date(approved_at).toLocaleString(),
      });
    }
    if (isDenied && denied_at) {
      return t('workspace.chat.widgets.permission.subtitle.deniedAt', {
        date: new Date(denied_at).toLocaleString(),
      });
    }
    return '';
  };

  const getAgentLabel = () => {
    switch (agentTool) {
      case 'claude-code': return 'Claude Code';
      case 'codex': return 'Codex';
      case 'gemini': return 'Gemini';
      case 'opencode': return 'OpenCode';
      default: return 'Agent';
    }
  };

  const styles = getStateStyles();
  const hasToolInput = Object.keys(tool_input).length > 0;

  const handleApprove = () => {
    switch (agentTool) {
      case 'claude-code':
        if (onApprove) {
          const scope = rememberChoice ? selectedScope : PermissionScopeValues.ONCE;
          onApprove(message_id, scope);
        }
        break;
      case 'codex':
        if (onCodexApprove) {
          onCodexApprove(message_id, codexSandbox, codexApproval);
        }
        break;
      case 'gemini':
        if (onGeminiApprove) {
          onGeminiApprove(message_id, geminiMode);
        }
        break;
      case 'opencode':
        if (onOpenCodeApprove) {
          onOpenCodeApprove(message_id, opencodeMode);
        }
        break;
    }
  };

  const handleDeny = () => {
    if (onDeny) {
      onDeny(message_id);
    }
  };

  const renderClaudeCodeOptions = () => (
    <div className="space-y-2">
      <RadioGroup
        value={rememberChoice ? 'remember' : 'once'}
        onValueChange={(value) => setRememberChoice(value === 'remember')}
        className="space-y-1.5"
      >
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="once" id="once" className="h-3.5 w-3.5" />
          <Label htmlFor="once" className="text-xs text-muted-foreground cursor-pointer">
            {t('workspace.chat.widgets.permission.onceOnly')}
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="remember" id="remember" className="h-3.5 w-3.5" />
          <Label htmlFor="remember" className="text-xs text-muted-foreground cursor-pointer">
            {t('workspace.chat.widgets.permission.rememberChoice')}
          </Label>
          <Select
            value={selectedScope}
            onValueChange={(value: PermissionScope) => {
              setSelectedScope(value);
              setRememberChoice(true);
            }}
            disabled={!rememberChoice}
          >
            <SelectTrigger
              className={cn(
                "h-6 text-[11px] w-[180px]",
                !rememberChoice && "opacity-50"
              )}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {claudeCodeScopeOptions.slice(1).map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs">
                  <div className="flex items-center gap-1.5">
                    <option.icon className={cn("h-3 w-3", option.color)} />
                    {t(option.labelKey)}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </RadioGroup>

      {rememberChoice && (
        <p className="text-[11px] text-muted-foreground pl-5">
          {t(claudeCodeScopeOptions.find(o => o.value === selectedScope)?.descriptionKey ?? '')}
        </p>
      )}
    </div>
  );

  const renderCodexOptions = () => (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {/* Sandbox Mode */}
        <div className="flex-1">
          <Label className="text-[11px] text-muted-foreground mb-1 block">
            {t('workspace.chat.widgets.permission.codex.sandbox.label')}
          </Label>
          <Select value={codexSandbox} onValueChange={(v: CodexSandboxMode) => setCodexSandbox(v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {codexSandboxOptions.map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs">
                  <div>
                    <div className="font-medium">{option.label}</div>
                    <div className="text-[10px] text-muted-foreground">{t(option.descriptionKey)}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Approval Policy */}
        <div className="flex-1">
          <Label className="text-[11px] text-muted-foreground mb-1 block">
            {t('workspace.chat.widgets.permission.codex.approval.label')}
          </Label>
          <Select value={codexApproval} onValueChange={(v: CodexApprovalPolicy) => setCodexApproval(v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {codexApprovalOptions.map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs">
                  <div>
                    <div className="font-medium">{option.label}</div>
                    <div className="text-[10px] text-muted-foreground">{t(option.descriptionKey)}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );

  const renderGeminiOptions = () => (
    <div className="space-y-2">
      <Label className="text-[11px] text-muted-foreground">
        {t('workspace.chat.widgets.permission.approvalMode')}
      </Label>
      <RadioGroup
        value={geminiMode}
        onValueChange={(v: GeminiPermissionMode) => setGeminiMode(v)}
        className="space-y-1"
      >
        {geminiModeOptions.map((option) => (
          <div key={option.value} className="flex items-start space-x-2">
            <RadioGroupItem value={option.value} id={`gemini-${option.value}`} className="h-3.5 w-3.5 mt-0.5" />
            <Label htmlFor={`gemini-${option.value}`} className="cursor-pointer">
              <div className="flex items-center gap-1.5">
                <option.icon className={cn("h-3.5 w-3.5", option.color)} />
                <span className="text-xs font-medium">{option.label}</span>
              </div>
              <p className="text-[10px] text-muted-foreground">{t(option.descriptionKey)}</p>
            </Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  );

  const renderOpenCodeOptions = () => (
    <div className="space-y-2">
      <Label className="text-[11px] text-muted-foreground">
        {t('workspace.chat.widgets.permission.approvalMode')}
      </Label>
      <RadioGroup
        value={opencodeMode}
        onValueChange={(v: OpenCodePermissionMode) => setOpencodeMode(v)}
        className="space-y-1"
      >
        {opencodeModeOptions.map((option) => (
          <div key={option.value} className="flex items-start space-x-2">
            <RadioGroupItem value={option.value} id={`opencode-${option.value}`} className="h-3.5 w-3.5 mt-0.5" />
            <Label htmlFor={`opencode-${option.value}`} className="cursor-pointer">
              <div className="flex items-center gap-1.5">
                <option.icon className={cn("h-3.5 w-3.5", option.color)} />
                <span className="text-xs font-medium">{option.label}</span>
              </div>
              <p className="text-[10px] text-muted-foreground">{t(option.descriptionKey)}</p>
            </Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  );

  const renderPermissionOptions = () => {
    switch (agentTool) {
      case 'claude-code':
        return renderClaudeCodeOptions();
      case 'codex':
        return renderCodexOptions();
      case 'gemini':
        return renderGeminiOptions();
      case 'opencode':
        return renderOpenCodeOptions();
      default:
        return renderClaudeCodeOptions();
    }
  };

  return (
    <div className={cn('border rounded-lg overflow-hidden', styles.container)}>
      <div className="p-3 flex items-start gap-3">
        <div className={cn('p-2 rounded-lg flex-shrink-0', styles.iconBg)}>
          <div className={styles.iconColor}>
            {getIcon()}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-foreground">{getTitle()}</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
              {getAgentLabel()}
            </span>
          </div>
          {getSubtitle() && (
            <p className="text-xs text-muted-foreground mt-0.5">{getSubtitle()}</p>
          )}
        </div>
      </div>

      <div className="px-3 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {t('workspace.chat.widgets.permission.toolLabel')}
          </span>
          <code className="text-xs font-mono bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded">
            {tool_name}
          </code>
        </div>

        {reason && isActive && (
          <div className="mt-2 flex items-start gap-2 text-xs text-muted-foreground bg-muted p-2 rounded">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-muted-foreground" />
            <span>{reason}</span>
          </div>
        )}
      </div>

      {hasToolInput && (isActive || showDetails) && (
        <div className="px-3 pb-2">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-1"
          >
            {showDetails ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            <span>{t('workspace.chat.widgets.permission.parameterDetails')}</span>
          </button>

          {showDetails && (
            <div className="bg-muted rounded border border-border overflow-hidden">
              <table className="w-full text-xs">
                <tbody>
                  {Object.entries(tool_input).map(([key, value], index) => (
                    <tr
                      key={key}
                      className={cn(
                        index !== 0 && 'border-t border-border'
                      )}
                    >
                      <td className="px-2 py-1.5 bg-muted/50 text-muted-foreground font-mono align-top whitespace-nowrap">
                        {key}
                      </td>
                      <td className="px-2 py-1.5 text-foreground font-mono break-all">
                        <pre className="whitespace-pre-wrap text-[11px]">
                          {typeof value === 'string'
                            ? value
                            : JSON.stringify(value, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {requested_at && isActive && (
        <div className="px-3 pb-2">
          <p className="text-[11px] text-muted-foreground">
            {t('workspace.chat.widgets.permission.requestedAt', {
              date: new Date(requested_at).toLocaleString(),
            })}
          </p>
        </div>
      )}

      {isActive && (onApprove || onCodexApprove || onGeminiApprove || onOpenCodeApprove) && onDeny && (
        <div className="border-t border-border bg-muted/30 p-3 space-y-3">
          {renderPermissionOptions()}

          <div className="flex items-center gap-2 pt-1">
            <Button
              onClick={handleApprove}
              className="h-8 px-4 text-xs bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              <Check className="mr-1.5 h-3.5 w-3.5" />
              {t('workspace.chat.widgets.permission.approve')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeny}
              className="h-8 px-4 text-xs"
            >
              <X className="mr-1.5 h-3.5 w-3.5" />
              {t('workspace.chat.widgets.permission.deny')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PermissionRequestWidget;
