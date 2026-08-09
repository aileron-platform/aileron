import React, { useMemo } from 'react';
import {
  MCPServerDialog,
  type MCPServerDialogData,
  type MCPServerDialogLabels,
  type MCPServerScopeOption,
  type MCPServerTransportOption,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentScope } from '@/features/workspace/features/agent-settings/model/documents';
import type { AgentMcpServer } from '@/features/workspace/features/agent-settings/model/mcp';

export type EditableMCPServerScope = Exclude<AgentScope, 'plugin'>;
export type WorkspaceMCPServerData = AgentMcpServer & {
  scope: EditableMCPServerScope;
  transport?: MCPTransport;
};

const EDITABLE_SCOPES: EditableMCPServerScope[] = ['project', 'user', 'local'];

export interface WorkspaceMCPServerDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  server: AgentMcpServer | null;
  availableScopes?: AgentScope[];
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (server: WorkspaceMCPServerData) => Promise<void>;
}

export const WorkspaceMCPServerDialog: React.FC<WorkspaceMCPServerDialogProps> = ({
  open,
  mode,
  server,
  availableScopes,
  i18nNamespace = 'workspace.agentSettings.common',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();

  const scopeOptions = useMemo<Array<MCPServerScopeOption<EditableMCPServerScope>>>(() => {
    const allowedScopes = availableScopes
      ? EDITABLE_SCOPES.filter((scope) => availableScopes.includes(scope))
      : EDITABLE_SCOPES;

    return allowedScopes.map((scope) => ({
      value: scope,
      title: t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${scope}.title`),
      description: t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${scope}.description`),
    }));
  }, [availableScopes, i18nNamespace, t]);

  const normalizedServer = useMemo(() => {
    if (!server) return null;
    return {
      ...server,
      scope: server.scope === 'plugin' ? 'project' : server.scope,
    };
  }, [server]);

  const transportOptions = useMemo<MCPServerTransportOption[]>(
    () => (['stdio', 'sse', 'http'] as MCPTransport[]).map((transport) => ({
      value: transport,
      title: t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.options.${transport}.title`),
      description: t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.options.${transport}.description`),
    })),
    [i18nNamespace, t],
  );

  const dialogLabels: MCPServerDialogLabels = {
    titleCreate: t(`${i18nNamespace}.mcp.dialogs.server.title.create`),
    titleEdit: t(`${i18nNamespace}.mcp.dialogs.server.title.edit`),
    description: t(`${i18nNamespace}.mcp.dialogs.server.description`),
    nameLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.name.label`),
    namePlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.name.placeholder`),
    nameHint: t(`${i18nNamespace}.mcp.dialogs.server.fields.name.hint`),
    scopeLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.label`),
    transportLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.label`),
    cancel: t('common.cancel'),
    create: t(`${i18nNamespace}.mcp.dialogs.server.actions.create`),
    save: t(`${i18nNamespace}.mcp.dialogs.server.actions.save`),
    nameRequired: t(`${i18nNamespace}.mcp.dialogs.server.errors.nameRequired`),
    commandRequired: t(`${i18nNamespace}.mcp.dialogs.server.errors.commandRequired`),
    urlRequired: t(`${i18nNamespace}.mcp.dialogs.server.errors.urlRequired`),
    saveFailed: t(`${i18nNamespace}.mcp.dialogs.server.errors.saveFailed`),
  };

  const transportFieldLabels: MCPTransportFieldsLabels = {
    commandLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.command.label`),
    commandPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.command.placeholder`),
    argsLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.label`),
    argsAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.add`),
    argsEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.empty`),
    argsPlaceholder: (index) =>
      t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.placeholder`, { index }),
    urlLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.label`),
    urlPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.placeholder.http`),
    urlHint: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.hint.http`),
    headersLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.label`),
    headersAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.add`),
    headersKeyPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.keyPlaceholder`),
    headersValuePlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.valuePlaceholder`),
    headersEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.empty`),
    envLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.label`),
    envAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.add`),
    envKeyPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.keyPlaceholder`),
    envValuePlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.valuePlaceholder`),
    envEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.empty`),
  };

  return (
    <MCPServerDialog<EditableMCPServerScope>
      open={open}
      mode={mode}
      server={normalizedServer}
      scopeOptions={scopeOptions}
      transportOptions={transportOptions}
      labels={dialogLabels}
      transportFieldLabels={transportFieldLabels}
      onClose={onClose}
      onSubmit={(payload: MCPServerDialogData<EditableMCPServerScope>) => onSubmit(payload as WorkspaceMCPServerData)}
    />
  );
};
