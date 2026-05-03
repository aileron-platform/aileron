import React from 'react';
import { Check, Shield } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import type {
  CodexApprovalPolicy,
  CodexPermissionConfig,
  CodexSandboxMode,
} from './agentSessionTypes';

interface CodexPermissionSelectorProps {
  value: CodexPermissionConfig;
  onChange: (config: CodexPermissionConfig) => void;
  t: (key: string) => string;
}

const SANDBOX_MODES: CodexSandboxMode[] = ['strict', 'relaxed', 'off'];
const APPROVAL_POLICIES: CodexApprovalPolicy[] = ['manual', 'suggest', 'auto'];

export const DEFAULT_CODEX_PERMISSION_CONFIG: CodexPermissionConfig = {
  sandboxMode: 'strict',
  approvalPolicy: 'manual',
};

export const isCodexPermissionConfig = (value: unknown): value is CodexPermissionConfig => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<CodexPermissionConfig>;
  return (
    SANDBOX_MODES.includes(candidate.sandboxMode as CodexSandboxMode) &&
    APPROVAL_POLICIES.includes(candidate.approvalPolicy as CodexApprovalPolicy)
  );
};

export const CodexPermissionSelector: React.FC<CodexPermissionSelectorProps> = ({
  value,
  onChange,
  t,
}) => {
  const setSandboxMode = (sandboxMode: CodexSandboxMode) => {
    onChange({ ...value, sandboxMode });
  };

  const setApprovalPolicy = (approvalPolicy: CodexApprovalPolicy) => {
    onChange({ ...value, approvalPolicy });
  };

  const sandboxLabel = t(`workspace.chat.input.codexPermission.sandbox.${value.sandboxMode}.label`);
  const approvalLabel = t(`workspace.chat.input.codexPermission.approval.${value.approvalPolicy}.label`);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-secondary/50 px-2.5 shadow-sm transition-all hover:border-primary/30 hover:bg-secondary"
          title={t('workspace.chat.input.codexPermission.label')}
        >
          <Shield className="h-3 w-3 flex-shrink-0 text-primary" />
          <span className="text-xs font-medium whitespace-nowrap">
            {sandboxLabel} · {approvalLabel}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-96">
        <div className="px-3 py-2">
          <div className="text-sm font-medium">{t('workspace.chat.input.codexPermission.sandbox.label')}</div>
          <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t('workspace.chat.input.codexPermission.sandbox.description')}
          </div>
        </div>
        {SANDBOX_MODES.map((mode) => (
          <DropdownMenuItem
            key={mode}
            onClick={() => setSandboxMode(mode)}
            className="flex cursor-pointer items-start gap-2 py-2.5"
          >
            <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
              {value.sandboxMode === mode && <Check className="h-4 w-4 text-primary" />}
            </div>
            <div className="flex flex-1 flex-col gap-0.5">
              <div className="text-sm font-medium">
                {t(`workspace.chat.input.codexPermission.sandbox.${mode}.label`)}
              </div>
              <div className="text-xs leading-relaxed text-muted-foreground">
                {t(`workspace.chat.input.codexPermission.sandbox.${mode}.description`)}
              </div>
            </div>
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />

        <div className="px-3 py-2">
          <div className="text-sm font-medium">{t('workspace.chat.input.codexPermission.approval.label')}</div>
          <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t('workspace.chat.input.codexPermission.approval.description')}
          </div>
        </div>
        {APPROVAL_POLICIES.map((policy) => (
          <DropdownMenuItem
            key={policy}
            onClick={() => setApprovalPolicy(policy)}
            className="flex cursor-pointer items-start gap-2 py-2.5"
          >
            <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
              {value.approvalPolicy === policy && <Check className="h-4 w-4 text-primary" />}
            </div>
            <div className="flex flex-1 flex-col gap-0.5">
              <div className="text-sm font-medium">
                {t(`workspace.chat.input.codexPermission.approval.${policy}.label`)}
              </div>
              <div className="text-xs leading-relaxed text-muted-foreground">
                {t(`workspace.chat.input.codexPermission.approval.${policy}.description`)}
              </div>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default CodexPermissionSelector;
