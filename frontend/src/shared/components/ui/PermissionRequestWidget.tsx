// frontend/src/shared/components/ui/PermissionRequestWidget.tsx
/**
 * PermissionRequestWidget - 權限請求 Widget
 *
 * 參考 agor-main/apps/agor-ui/src/components/PermissionRequestBlock/PermissionRequestBlock.tsx
 * 和 agor-main/apps/agor-ui/src/components/PermissionModeSelector/PermissionModeSelector.tsx
 *
 * 支援不同 Agent SDK 的權限選項：
 * - Claude Code: PermissionScope (ONCE, PROJECT, USER, LOCAL)
 * - Codex: SandboxMode + ApprovalPolicy
 * - Gemini: ApprovalMode (default, autoEdit, yolo)
 * - OpenCode: ApprovalMode (default, acceptEdits, bypassPermissions)
 */

import React, { useState } from 'react';
import { Button } from './button';
import { RadioGroup, RadioGroupItem } from './radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { Label } from './label';
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

// ============================================================================
// Agent SDK 類型
// ============================================================================

export type AgentToolType = 'claude-code' | 'codex' | 'gemini' | 'opencode';

// ============================================================================
// Claude Code 權限範圍 (Claude Agent SDK)
// 重導出以保持向後相容
// ============================================================================

export type PermissionScope = PermissionScopeType;

// Enum for backward compatibility (used as values, not types)
export enum PermissionScopeEnum {
  ONCE = 'once',
  SESSION = 'session',
  PROJECT = 'project',
  USER = 'user',
  LOCAL = 'local',
}

// 提供常量供內部使用
export const PermissionScopeValues = {
  ONCE: 'once' as const,
  SESSION: 'session' as const,
  PROJECT: 'project' as const,
  USER: 'user' as const,
  LOCAL: 'local' as const,
};

// ============================================================================
// Codex 權限設定 (OpenAI Codex SDK)
// ============================================================================

export type CodexSandboxMode = 'read-only' | 'workspace-write' | 'danger-full-access';
export type CodexApprovalPolicy = 'untrusted' | 'on-request' | 'on-failure' | 'never';

// ============================================================================
// Gemini/OpenCode 權限模式
// ============================================================================

export type GeminiPermissionMode = 'default' | 'autoEdit' | 'yolo';
export type OpenCodePermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions';

// ============================================================================
// 權限狀態
// ============================================================================

export type PermissionStatus = PermissionStatusType;

// 提供常量供內部使用
export const PermissionStatusValues = {
  PENDING: 'pending' as const,
  APPROVED: 'approved' as const,
  DENIED: 'denied' as const,
};

// ============================================================================
// 權限選項配置
// ============================================================================

// Claude Code 權限範圍選項
const claudeCodeScopeOptions = [
  {
    value: PermissionScopeValues.ONCE,
    label: '僅本次允許',
    description: '只允許這一次請求',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: PermissionScopeValues.SESSION,
    label: '本次會話允許',
    description: '本次會話期間都允許此操作',
    icon: Clock,
    color: 'text-blue-500'
  },
  {
    value: PermissionScopeValues.PROJECT,
    label: '專案允許 (.claude/)',
    description: '儲存到專案設定，團隊成員可共享',
    icon: FolderLock,
    color: 'text-green-500'
  },
  {
    value: PermissionScopeValues.USER,
    label: '使用者允許 (~/.claude/)',
    description: '儲存到使用者設定，跨專案生效',
    icon: Globe,
    color: 'text-purple-500'
  },
  {
    value: PermissionScopeValues.LOCAL,
    label: '本地允許 (gitignored)',
    description: '儲存到本地，不會被版本控制追蹤',
    icon: HardDrive,
    color: 'text-orange-500'
  },
];

// Codex Sandbox 模式選項
const codexSandboxOptions = [
  {
    value: 'read-only' as CodexSandboxMode,
    label: 'read-only',
    description: '不允許寫入檔案系統',
  },
  {
    value: 'workspace-write' as CodexSandboxMode,
    label: 'workspace-write',
    description: '僅允許寫入工作區檔案（封鎖 .git/）',
  },
  {
    value: 'danger-full-access' as CodexSandboxMode,
    label: 'full-access',
    description: '完整檔案系統存取（包含 .git/）',
  },
];

// Codex Approval Policy 選項
const codexApprovalOptions = [
  {
    value: 'untrusted' as CodexApprovalPolicy,
    label: 'untrusted',
    description: '每次操作都詢問',
  },
  {
    value: 'on-request' as CodexApprovalPolicy,
    label: 'on-request',
    description: '模型決定何時詢問（推薦）',
  },
  {
    value: 'on-failure' as CodexApprovalPolicy,
    label: 'on-failure',
    description: '只在失敗時詢問',
  },
  {
    value: 'never' as CodexApprovalPolicy,
    label: 'never',
    description: '自動批准所有操作',
  },
];

// Gemini 權限模式選項
const geminiModeOptions = [
  {
    value: 'default' as GeminiPermissionMode,
    label: 'default',
    description: '每次工具使用都提示（最嚴格）',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: 'autoEdit' as GeminiPermissionMode,
    label: 'autoEdit',
    description: '自動批准檔案編輯，shell/web 工具詢問',
    icon: FileEdit,
    color: 'text-green-500'
  },
  {
    value: 'yolo' as GeminiPermissionMode,
    label: 'yolo',
    description: '允許所有操作不提示',
    icon: Unlock,
    color: 'text-orange-500'
  },
];

// OpenCode 權限模式選項
const opencodeModeOptions = [
  {
    value: 'default' as OpenCodePermissionMode,
    label: 'default',
    description: '每次操作前提示批准',
    icon: Lock,
    color: 'text-red-500'
  },
  {
    value: 'acceptEdits' as OpenCodePermissionMode,
    label: 'acceptEdits',
    description: '自動批准所有操作（推薦）',
    icon: FileEdit,
    color: 'text-green-500'
  },
  {
    value: 'bypassPermissions' as OpenCodePermissionMode,
    label: 'bypassPermissions',
    description: '完全繞過所有權限檢查',
    icon: Unlock,
    color: 'text-orange-500'
  },
];

// ============================================================================
// Widget Props
// ============================================================================

interface WidgetProps {
  input?: Record<string, any>;
  output?: string | Record<string, any>;
  error?: string;
  status: ToolStatus;
  isExpanded: boolean;
}

export interface PermissionRequestWidgetProps extends WidgetProps {
  /** Agent SDK 類型 */
  agentTool?: AgentToolType;
  /** 是否正在等待前一個權限請求 */
  isWaiting?: boolean;
  /** Claude Code: 批准回調 */
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  /** Codex: 批准回調（含 sandbox 和 approval policy） */
  onCodexApprove?: (messageId: string, sandbox: CodexSandboxMode, approval: CodexApprovalPolicy) => void;
  /** Gemini: 批准回調 */
  onGeminiApprove?: (messageId: string, mode: GeminiPermissionMode) => void;
  /** OpenCode: 批准回調 */
  onOpenCodeApprove?: (messageId: string, mode: OpenCodePermissionMode) => void;
  /** 拒絕回調 */
  onDeny?: (messageId: string) => void;
  /** 請求時間戳 */
  requested_at?: string;
}

// ============================================================================
// Widget 組件
// ============================================================================

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
  // Claude Code 狀態
  const [rememberChoice, setRememberChoice] = useState<boolean>(false);
  const [selectedScope, setSelectedScope] = useState<PermissionScope>(PermissionScopeValues.ONCE);

  // Codex 狀態
  const [codexSandbox, setCodexSandbox] = useState<CodexSandboxMode>('workspace-write');
  const [codexApproval, setCodexApproval] = useState<CodexApprovalPolicy>('on-request');

  // Gemini 狀態
  const [geminiMode, setGeminiMode] = useState<GeminiPermissionMode>('autoEdit');

  // OpenCode 狀態
  const [opencodeMode, setOpencodeMode] = useState<OpenCodePermissionMode>('acceptEdits');

  // 通用狀態
  const [showDetails, setShowDetails] = useState<boolean>(true);

  // 從 input 提取資料
  const tool_name = input?.tool_name || 'Unknown Tool';
  const tool_input = input?.tool_input || {};
  const permissionStatus = input?.permission_status || PermissionStatusValues.PENDING;
  const approved_at = input?.approved_at;
  const denied_at = input?.denied_at;
  const message_id = input?.message_id || '';
  const reason = input?.reason || '';

  // 狀態判斷
  const isApproved = permissionStatus === PermissionStatusValues.APPROVED;
  const isDenied = permissionStatus === PermissionStatusValues.DENIED;
  const isPending = permissionStatus === PermissionStatusValues.PENDING;
  const isActive = isPending && !isWaiting;

  // 獲取狀態樣式（支援深色模式）
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

  // 獲取圖示
  const getIcon = () => {
    if (isWaiting) return <Clock className="h-5 w-5" />;
    if (isActive) return <ShieldAlert className="h-5 w-5" />;
    if (isApproved) return <ShieldCheck className="h-5 w-5" />;
    if (isDenied) return <ShieldX className="h-5 w-5" />;
    return <ShieldAlert className="h-5 w-5" />;
  };

  // 獲取標題
  const getTitle = () => {
    if (isWaiting) return '等待前一個權限請求';
    if (isActive) return '需要權限';
    if (isApproved) return '權限已批准';
    if (isDenied) return '權限已拒絕';
    return '權限請求';
  };

  // 獲取副標題
  const getSubtitle = () => {
    if (isWaiting) return '請先處理前面的權限請求';
    if (isActive) return '代理需要您的批准才能繼續執行';
    if (isApproved && approved_at) {
      return `已於 ${new Date(approved_at).toLocaleString()} 批准`;
    }
    if (isDenied && denied_at) {
      return `已於 ${new Date(denied_at).toLocaleString()} 拒絕`;
    }
    return '';
  };

  // 獲取 Agent SDK 標籤
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

  // 處理批准
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

  // 處理拒絕
  const handleDeny = () => {
    if (onDeny) {
      onDeny(message_id);
    }
  };

  // 渲染 Claude Code 權限選項
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
            僅允許這一次
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="remember" id="remember" className="h-3.5 w-3.5" />
          <Label htmlFor="remember" className="text-xs text-muted-foreground cursor-pointer">
            記住這個選擇，儲存到
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
                    {option.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </RadioGroup>

      {rememberChoice && (
        <p className="text-[11px] text-muted-foreground pl-5">
          {claudeCodeScopeOptions.find(o => o.value === selectedScope)?.description}
        </p>
      )}
    </div>
  );

  // 渲染 Codex 權限選項（雙選擇器）
  const renderCodexOptions = () => (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {/* Sandbox Mode */}
        <div className="flex-1">
          <Label className="text-[11px] text-muted-foreground mb-1 block">Sandbox 模式</Label>
          <Select value={codexSandbox} onValueChange={(v: CodexSandboxMode) => setCodexSandbox(v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {codexSandboxOptions.map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs">
                  <div>
                    <div className="font-medium">{option.label}</div>
                    <div className="text-[10px] text-muted-foreground">{option.description}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Approval Policy */}
        <div className="flex-1">
          <Label className="text-[11px] text-muted-foreground mb-1 block">批准政策</Label>
          <Select value={codexApproval} onValueChange={(v: CodexApprovalPolicy) => setCodexApproval(v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {codexApprovalOptions.map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs">
                  <div>
                    <div className="font-medium">{option.label}</div>
                    <div className="text-[10px] text-muted-foreground">{option.description}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );

  // 渲染 Gemini 權限選項
  const renderGeminiOptions = () => (
    <div className="space-y-2">
      <Label className="text-[11px] text-muted-foreground">批准模式</Label>
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
              <p className="text-[10px] text-muted-foreground">{option.description}</p>
            </Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  );

  // 渲染 OpenCode 權限選項
  const renderOpenCodeOptions = () => (
    <div className="space-y-2">
      <Label className="text-[11px] text-muted-foreground">批准模式</Label>
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
              <p className="text-[10px] text-muted-foreground">{option.description}</p>
            </Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  );

  // 根據 Agent SDK 渲染對應的權限選項
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
      {/* 標題區域 */}
      <div className="p-3 flex items-start gap-3">
        {/* 圖示 */}
        <div className={cn('p-2 rounded-lg flex-shrink-0', styles.iconBg)}>
          <div className={styles.iconColor}>
            {getIcon()}
          </div>
        </div>

        {/* 標題和副標題 */}
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

      {/* 工具資訊 */}
      <div className="px-3 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">工具：</span>
          <code className="text-xs font-mono bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded">
            {tool_name}
          </code>
        </div>

        {/* 原因說明 */}
        {reason && isActive && (
          <div className="mt-2 flex items-start gap-2 text-xs text-muted-foreground bg-muted p-2 rounded">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-muted-foreground" />
            <span>{reason}</span>
          </div>
        )}
      </div>

      {/* 工具參數 - 可折疊 */}
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
            <span>參數詳情</span>
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

      {/* 請求時間 */}
      {requested_at && isActive && (
        <div className="px-3 pb-2">
          <p className="text-[11px] text-muted-foreground">
            請求時間：{new Date(requested_at).toLocaleString()}
          </p>
        </div>
      )}

      {/* 操作區域 - 僅在 active 狀態顯示 */}
      {isActive && (onApprove || onCodexApprove || onGeminiApprove || onOpenCodeApprove) && onDeny && (
        <div className="border-t border-border bg-muted/30 p-3 space-y-3">
          {/* 根據 Agent SDK 渲染權限選項 */}
          {renderPermissionOptions()}

          {/* 操作按鈕 */}
          <div className="flex items-center gap-2 pt-1">
            <Button
              onClick={handleApprove}
              className="h-8 px-4 text-xs bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              <Check className="mr-1.5 h-3.5 w-3.5" />
              批准
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeny}
              className="h-8 px-4 text-xs"
            >
              <X className="mr-1.5 h-3.5 w-3.5" />
              拒絕
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PermissionRequestWidget;
