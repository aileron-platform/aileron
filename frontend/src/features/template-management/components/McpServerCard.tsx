import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Copy, Database, Edit, Trash2, Eye, EyeOff } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useState } from 'react';

// 通用 MCP 伺服器資料介面
export interface BaseMcpServerData {
  name: string;
  description?: string;
  transport?: string;
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
}

// 檢視頁專用資料類型
export type ClaudeMcpServer = BaseMcpServerData;

// 編輯頁專用資料類型
export interface McpServerFormValue extends BaseMcpServerData {
  localId: string;
  type?: string;
  argsText?: string;
  envText?: string;
  headersText?: string;
}

export interface McpServerCardProps<T extends BaseMcpServerData> {
  server: T;
  mode: 'view' | 'edit';
  onCopyConfig: (server: T) => void;
  onEdit?: (server: T) => void;
  onDelete?: (serverId: string) => void;
}

export default function McpServerCard<T extends BaseMcpServerData>({
  server,
  mode,
  onCopyConfig,
  onEdit,
  onDelete
}: McpServerCardProps<T>) {
  const { t } = useI18n();
  const [showEnvValues, setShowEnvValues] = useState(false);

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'command': return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'http': return 'bg-primary/10 text-primary border-primary/20';
      case 'sse': return 'bg-orange-50 text-orange-700 border-orange-200';
      default: return 'bg-gray-50 text-gray-600 border-gray-200';
    }
  };

  const handleCopyConfig = () => {
    onCopyConfig(server);
  };

  // 取得要顯示的 args
  const getDisplayArgs = () => {
    if ('args' in server && server.args) {
      return server.args.join(' ');
    } else if ('argsText' in server && server.argsText) {
      const formServer = server as McpServerFormValue;
      return formServer.argsText
        .split('\n')
        .filter(arg => arg.trim())
        .join(' ');
    }
    return '';
  };

  // 取得要顯示的 env
  const getDisplayEnv = () => {
    if ('env' in server && server.env) {
      return Object.entries(server.env);
    } else if ('envText' in server && server.envText) {
      const formServer = server as McpServerFormValue;
      return formServer.envText
        .split('\n')
        .filter(line => line.trim() && line.includes('='))
        .map(line => {
          const [key, ...valueParts] = line.split('=').map(part => part.trim());
          const value = valueParts.join('=');
          return [key, value] as [string, string];
        });
    }
    return [];
  };

  // 取得要顯示的 headers（僅編輯模式）
  const getDisplayHeaders = () => {
    if (mode === 'edit' && 'headersText' in server && server.headersText) {
      const formServer = server as McpServerFormValue;
      return formServer.headersText
        .split('\n')
        .filter(line => line.trim() && line.includes(':'))
        .map(line => {
          const [key, ...valueParts] = line.split(':').map(part => part.trim());
          const value = valueParts.join(':');
          return [key, value] as [string, string];
        });
    }
    return [];
  };

  const serverType = (server as any).type || server.transport || 'stdio';
  const displayArgs = getDisplayArgs();
  const displayEnv = getDisplayEnv();
  const displayHeaders = getDisplayHeaders();

  return (
    <div className="bg-background border border-border rounded-lg p-4 hover:shadow-sm transition-shadow">
      {/* Server Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
            <Database className="h-5 w-5 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-foreground">
                {server.name || (mode === 'edit' ? t('template.editor.mcp.card.nameFallback') : '')}
              </h3>
              <Badge variant="outline" className={`text-xs ${getTypeColor(serverType)}`}>
                {serverType.toUpperCase()}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {mode === 'edit' && onEdit && (
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onEdit(server);
              }}
            >
              <Edit className="h-4 w-4" />
            </Button>
          )}
          {mode === 'edit' && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete((server as McpServerFormValue).localId);
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleCopyConfig();
            }}
            title={mode === 'view'
              ? t('template.detail.mcp.card.copyTooltip')
              : t('template.editor.mcp.card.actions.copyTooltip')
            }
          >
            <Copy className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Description */}
      {server.description && (
        <p className="text-sm text-muted-foreground mb-4">
          {server.description}
        </p>
      )}

      {/* Configuration Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Command or URL */}
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            {serverType === 'http' || serverType === 'sse'
              ? (mode === 'view'
                  ? t('template.detail.mcp.card.sections.url')
                  : t('template.editor.mcp.card.sections.command.urlLabel'))
              : (mode === 'view'
                  ? t('template.detail.mcp.card.sections.command')
                  : t('template.editor.mcp.card.sections.command.commandLabel'))
            }
          </h4>
          <div className="bg-muted/50 rounded-md p-3">
            {serverType === 'http' || serverType === 'sse' ? (
              <code className="text-sm font-mono text-foreground break-all">{server.url}</code>
            ) : (
              <>
                <code className="text-sm font-mono text-foreground break-all">{server.command}</code>
                {displayArgs && (
                  <div className="mt-2 text-xs text-muted-foreground break-all">
                    {mode === 'view' ? displayArgs : t('template.editor.mcp.card.sections.command.args', { args: displayArgs })}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Environment Variables */}
        {displayEnv.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {mode === 'view'
                  ? t('template.detail.mcp.card.sections.env')
                  : t('template.editor.mcp.card.sections.environment.title')
                }
              </h4>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowEnvValues(!showEnvValues);
                }}
                className="h-6 px-2"
                title={showEnvValues
                  ? t('template.editor.mcp.card.actions.hideEnvValues')
                  : t('template.editor.mcp.card.actions.showEnvValues')
                }
              >
                {showEnvValues ? (
                  <EyeOff className="h-3 w-3" />
                ) : (
                  <Eye className="h-3 w-3" />
                )}
              </Button>
            </div>
            <div className="bg-muted/50 rounded-md p-3 space-y-1">
              {displayEnv.map(([key, value], index) => (
                <div key={index} className="bg-muted/30 rounded px-2 py-1">
                  <span className="font-mono text-xs break-all">
                    <span className="text-primary font-semibold">{key}</span>
                    <span className="text-muted-foreground mx-1">=</span>
                    <span className="text-foreground">
                      {showEnvValues ? value : '***'}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* HTTP Headers - 僅編輯模式且有資料時顯示 */}
      {mode === 'edit' && displayHeaders.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            {t('template.editor.mcp.card.sections.headers')}
          </h4>
          <div className="bg-muted/50 rounded-md p-3 space-y-1">
            {displayHeaders.map(([key, value], index) => (
              <div key={index} className="bg-muted/30 rounded px-2 py-1">
                <span className="font-mono text-xs break-all">
                  <span className="text-primary font-semibold">{key}</span>
                  <span className="text-muted-foreground mx-1">:</span>
                  <span className="text-foreground">{value}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
