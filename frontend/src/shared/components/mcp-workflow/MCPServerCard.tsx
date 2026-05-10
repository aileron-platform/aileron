import React from 'react';
import { Edit, Eye, EyeOff, Info, Trash2 } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Switch } from '@/shared/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { cn } from '@/shared/utils/cn';
import type { MCPTransport } from './MCPTransportFieldsEditor';

export interface MCPServerCardData {
  id: string;
  name: string;
  scope: string;
  description?: string;
  transport?: MCPTransport;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
}

export interface MCPServerCardLabels {
  enabled: string;
  disabled: string;
  transportType: string;
  serverUrl: string;
  headers: string;
  command: string;
  commandArgs: string;
  env: string;
  showEnvValues: string;
  hideEnvValues: string;
  edit?: string;
  delete?: string;
  readOnlyTooltip?: string;
}

export interface MCPServerCardProps<TServer extends MCPServerCardData = MCPServerCardData> {
  server: TServer;
  scopeBadge: React.ReactNode;
  labels: MCPServerCardLabels;
  supportsToggle?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  disabled?: boolean;
  envVisible?: boolean;
  readOnlyIndicator?: React.ReactNode;
  className?: string;
  onEdit?: (server: TServer) => void;
  onDelete?: (server: TServer) => void;
  onToggleStatus?: (server: TServer, enabled: boolean) => void;
  onToggleEnvVisibility?: (server: TServer) => void;
}

export const MCPServerCard = <TServer extends MCPServerCardData = MCPServerCardData>({
  server,
  scopeBadge,
  labels,
  supportsToggle = true,
  canEdit = true,
  canDelete = true,
  disabled = false,
  envVisible = false,
  readOnlyIndicator,
  className,
  onEdit,
  onDelete,
  onToggleStatus,
  onToggleEnvVisibility,
}: MCPServerCardProps<TServer>) => {
  const transport = server.transport ?? 'stdio';
  const hasHeaders = Boolean(server.headers && Object.keys(server.headers).length > 0);
  const hasEnv = Boolean(server.env && Object.keys(server.env).length > 0);
  const readOnlyContent = readOnlyIndicator ?? (
    labels.readOnlyTooltip ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="cursor-help rounded-md p-2 text-muted-foreground"
            disabled
          >
            <Info className="h-4 w-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="text-sm">{labels.readOnlyTooltip}</p>
        </TooltipContent>
      </Tooltip>
    ) : null
  );

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-background p-6 transition-all',
        supportsToggle && server.enabled === false && 'bg-muted/30 opacity-60',
        className,
      )}
    >
      <div className="mb-4 flex items-start justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-lg font-semibold text-foreground">{server.name}</h3>
            {scopeBadge}
          </div>
        </div>

        <div className="ml-4 flex items-center gap-3">
          {supportsToggle ? (
            <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-1.5">
              <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">
                {server.enabled !== false ? labels.enabled : labels.disabled}
              </span>
              <Switch
                checked={server.enabled !== false}
                onCheckedChange={(checked) => onToggleStatus?.(server, checked)}
                disabled={disabled}
              />
            </div>
          ) : null}

          {canEdit ? (
            <button
              type="button"
              className="rounded-md p-2 transition-colors hover:bg-muted"
              onClick={() => onEdit?.(server)}
              disabled={disabled}
              title={labels.edit}
              aria-label={labels.edit}
            >
              <Edit className="h-4 w-4 text-muted-foreground" />
            </button>
          ) : null}
          {canDelete ? (
            <button
              type="button"
              className="rounded-md p-2 transition-colors hover:bg-muted"
              onClick={() => onDelete?.(server)}
              disabled={disabled}
              title={labels.delete}
              aria-label={labels.delete}
            >
              <Trash2 className="h-4 w-4 text-muted-foreground" />
            </button>
          ) : null}
          {!canEdit && !canDelete ? readOnlyContent : null}
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <MCPServerDetailRow label={labels.transportType}>
          <Badge variant="secondary" className="font-mono text-xs">
            {transport.toUpperCase()}
          </Badge>
        </MCPServerDetailRow>

        {(transport === 'http' || transport === 'sse') && server.url ? (
          <MCPServerDetailRow label={labels.serverUrl}>
            <span className="break-all font-mono text-xs">{server.url}</span>
          </MCPServerDetailRow>
        ) : null}

        {(transport === 'http' || transport === 'sse') && hasHeaders ? (
          <MCPServerRecordRows
            label={labels.headers}
            entries={Object.entries(server.headers ?? {})}
            separator=":"
          />
        ) : null}

        {transport === 'stdio' ? (
          <>
            <MCPServerDetailRow label={labels.command}>
              <span className="font-mono text-xs">{server.command ?? '-'}</span>
            </MCPServerDetailRow>
            {server.args && server.args.length > 0 ? (
              <MCPServerDetailRow label={labels.commandArgs}>
                <span className="break-all font-mono text-xs">{server.args.join(' ')}</span>
              </MCPServerDetailRow>
            ) : null}
          </>
        ) : null}

        {hasEnv ? (
          <MCPServerRecordRows
            label={labels.env}
            entries={Object.entries(server.env ?? {})}
            separator="="
            maskValues={!envVisible}
            headerAction={(
              <button
                type="button"
                onClick={() => onToggleEnvVisibility?.(server)}
                className="rounded p-0.5 transition-colors hover:bg-muted"
                title={envVisible ? labels.hideEnvValues : labels.showEnvValues}
              >
                {envVisible ? (
                  <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </button>
            )}
          />
        ) : null}
      </div>
    </div>
  );
};

const MCPServerDetailRow: React.FC<{
  label: string;
  children: React.ReactNode;
}> = ({ label, children }) => (
  <div className="flex items-center gap-2">
    <span className="min-w-[80px] font-medium text-muted-foreground">
      {label}:
    </span>
    {children}
  </div>
);

const MCPServerRecordRows: React.FC<{
  label: string;
  entries: Array<[string, string]>;
  separator: ':' | '=';
  maskValues?: boolean;
  headerAction?: React.ReactNode;
}> = ({ label, entries, separator, maskValues = false, headerAction }) => (
  <div className="flex items-start gap-2">
    <div className="flex min-w-[80px] items-center gap-2">
      <span className="font-medium text-muted-foreground">
        {label}:
      </span>
      {headerAction}
    </div>
    <div className="flex-1 space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded bg-muted/30 px-2 py-1">
          <span className="break-all font-mono text-xs">
            <span className="font-semibold text-primary">{key}</span>
            <span className="mx-1 text-muted-foreground">{separator}</span>
            <span className="text-foreground">{maskValues ? '***' : value}</span>
          </span>
        </div>
      ))}
    </div>
  </div>
);

MCPServerCard.displayName = 'MCPServerCard';

export default MCPServerCard;
