import React, { useEffect, useId, useState } from 'react';
import { Loader2, ShieldCheck } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  AgentMcpServer,
  CodexPluginMcpApprovalMode,
  CodexPluginMcpPolicy,
} from '../../model/mcp';

const APPROVAL_MODES: CodexPluginMcpApprovalMode[] = [
  'auto',
  'prompt',
  'writes',
  'approve',
];
const INHERIT_APPROVAL_MODE = 'inherit';

const parseToolList = (value: string): string[] | null => {
  const tools = value
    .split(',')
    .map((tool) => tool.trim())
    .filter(Boolean);
  return tools.length > 0 ? Array.from(new Set(tools)) : null;
};

export const parseCodexPluginToolPolicies = (
  value: string,
): CodexPluginMcpPolicy['tools'] => {
  const parsed = JSON.parse(value || '{}') as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('INVALID_TOOL_POLICY');
  }

  return Object.fromEntries(
    Object.entries(parsed).map(([toolName, toolPolicy]) => {
      if (
        !toolName.trim()
        || !toolPolicy
        || Array.isArray(toolPolicy)
        || typeof toolPolicy !== 'object'
      ) {
        throw new Error('INVALID_TOOL_POLICY');
      }
      const approvalMode = (toolPolicy as { approvalMode?: unknown }).approvalMode;
      if (
        approvalMode !== null
        && !APPROVAL_MODES.includes(approvalMode as CodexPluginMcpApprovalMode)
      ) {
        throw new Error('INVALID_TOOL_POLICY');
      }
      return [
        toolName.trim(),
        { approvalMode: approvalMode as CodexPluginMcpApprovalMode | null },
      ];
    }),
  );
};

interface CodexPluginMcpPolicyControlProps {
  server: AgentMcpServer & {
    pluginId: string;
    serverId: string;
    policy: CodexPluginMcpPolicy;
    policyRevision: string;
  };
  disabled?: boolean;
  i18nNamespace: string;
  onSave(
    server: AgentMcpServer,
    policy: CodexPluginMcpPolicy,
  ): Promise<void>;
}

const CodexPluginMcpPolicyControl: React.FC<CodexPluginMcpPolicyControlProps> = ({
  server,
  disabled = false,
  i18nNamespace,
  onSave,
}) => {
  const { t } = useI18n();
  const fieldId = useId();
  const [enabled, setEnabled] = useState(server.policy.enabled);
  const [defaultApprovalMode, setDefaultApprovalMode] = useState<
    CodexPluginMcpApprovalMode | null
  >(server.policy.defaultToolsApprovalMode);
  const [enabledTools, setEnabledTools] = useState(
    server.policy.enabledTools?.join(', ') ?? '',
  );
  const [disabledTools, setDisabledTools] = useState(
    server.policy.disabledTools?.join(', ') ?? '',
  );
  const [toolPolicies, setToolPolicies] = useState(
    JSON.stringify(server.policy.tools, null, 2),
  );
  const [validationError, setValidationError] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled(server.policy.enabled);
    setDefaultApprovalMode(server.policy.defaultToolsApprovalMode);
    setEnabledTools(server.policy.enabledTools?.join(', ') ?? '');
    setDisabledTools(server.policy.disabledTools?.join(', ') ?? '');
    setToolPolicies(JSON.stringify(server.policy.tools, null, 2));
    setValidationError(false);
  }, [server.policy, server.policyRevision]);

  const handleSave = async () => {
    let tools: CodexPluginMcpPolicy['tools'];
    try {
      tools = parseCodexPluginToolPolicies(toolPolicies);
      setValidationError(false);
    } catch {
      setValidationError(true);
      return;
    }

    setSaving(true);
    try {
      await onSave(server, {
        enabled,
        defaultToolsApprovalMode: defaultApprovalMode,
        enabledTools: parseToolList(enabledTools),
        disabledTools: parseToolList(disabledTools),
        tools,
      });
    } catch {
      // The page-level mutation handler reports the provider error.
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label={t(`${i18nNamespace}.mcp.pluginPolicy.title`)}
      className="space-y-4 rounded-md border border-primary/20 bg-primary/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            <h4 className="text-sm font-semibold">
              {t(`${i18nNamespace}.mcp.pluginPolicy.title`)}
            </h4>
            <Badge variant={server.effective ? 'default' : 'secondary'}>
              {t(`${i18nNamespace}.mcp.pluginPolicy.effective.${server.effective ? 'active' : 'inactive'}`)}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(`${i18nNamespace}.mcp.pluginPolicy.description`)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor={`${fieldId}-enabled`} className="text-xs">
            {t(`${i18nNamespace}.mcp.pluginPolicy.fields.enabled`)}
          </Label>
          <Switch
            id={`${fieldId}-enabled`}
            checked={enabled}
            onCheckedChange={setEnabled}
            disabled={disabled || saving}
            aria-label={t(`${i18nNamespace}.mcp.pluginPolicy.fields.enabled`)}
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-approval`} className="text-xs">
            {t(`${i18nNamespace}.mcp.pluginPolicy.fields.defaultApprovalMode`)}
          </Label>
          <Select
            value={defaultApprovalMode ?? INHERIT_APPROVAL_MODE}
            onValueChange={(value) => {
              setDefaultApprovalMode(
                value === INHERIT_APPROVAL_MODE
                  ? null
                  : value as CodexPluginMcpApprovalMode,
              );
            }}
            disabled={disabled || saving}
          >
            <SelectTrigger id={`${fieldId}-approval`} className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={INHERIT_APPROVAL_MODE}>
                {t(`${i18nNamespace}.mcp.pluginPolicy.approvalModes.inherit`)}
              </SelectItem>
              {APPROVAL_MODES.map((mode) => (
                <SelectItem key={mode} value={mode}>
                  {t(`${i18nNamespace}.mcp.pluginPolicy.approvalModes.${mode}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-enabled-tools`} className="text-xs">
            {t(`${i18nNamespace}.mcp.pluginPolicy.fields.enabledTools`)}
          </Label>
          <Input
            id={`${fieldId}-enabled-tools`}
            value={enabledTools}
            onChange={(event) => setEnabledTools(event.target.value)}
            placeholder={t(`${i18nNamespace}.mcp.pluginPolicy.placeholders.toolList`)}
            disabled={disabled || saving}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-disabled-tools`} className="text-xs">
            {t(`${i18nNamespace}.mcp.pluginPolicy.fields.disabledTools`)}
          </Label>
          <Input
            id={`${fieldId}-disabled-tools`}
            value={disabledTools}
            onChange={(event) => setDisabledTools(event.target.value)}
            placeholder={t(`${i18nNamespace}.mcp.pluginPolicy.placeholders.toolList`)}
            disabled={disabled || saving}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-tool-policies`} className="text-xs">
            {t(`${i18nNamespace}.mcp.pluginPolicy.fields.toolPolicies`)}
          </Label>
          <Textarea
            id={`${fieldId}-tool-policies`}
            value={toolPolicies}
            onChange={(event) => setToolPolicies(event.target.value)}
            className="min-h-24 font-mono text-xs"
            aria-invalid={validationError}
            disabled={disabled || saving}
          />
          {validationError ? (
            <p className="text-xs text-destructive">
              {t(`${i18nNamespace}.mcp.pluginPolicy.validation.invalidToolPolicies`)}
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {t(`${i18nNamespace}.mcp.pluginPolicy.newThreadRequired`)}
        </p>
        <Button
          type="button"
          size="sm"
          onClick={() => void handleSave()}
          disabled={disabled || saving}
        >
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {t(`${i18nNamespace}.mcp.pluginPolicy.actions.save`)}
        </Button>
      </div>
    </section>
  );
};

export default CodexPluginMcpPolicyControl;
