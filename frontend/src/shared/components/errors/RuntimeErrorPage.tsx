import React from 'react';
import { Button } from '../ui/button';
import { RefreshCw, AlertCircle, Trash2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

interface RuntimeErrorPageProps {
  error: string;
  isLoading?: boolean;
  onRetry?: () => void;
  onCreateWorkspace?: () => void;
  onDeleteWorkspace?: () => void;
  workspaceId?: string | null;
}

export const RuntimeErrorPage: React.FC<RuntimeErrorPageProps> = ({
  error,
  isLoading = false,
  onRetry,
  onCreateWorkspace,
  onDeleteWorkspace,
  workspaceId,
}) => {
  const { t } = useI18n();

  const isNoWorkspaceError =
    error.includes(t('common.error.workspaceRuntime.noWorkspaceErrorMessage')) ||
    error.includes(t('common.error.workspaceRuntime.invalidWorkspaceErrorMessage'));

  const canShowDeleteButton = workspaceId && !isNoWorkspaceError && onDeleteWorkspace;

  return (
    <div className="flex-1 flex items-center justify-center bg-background/50">
      <div className="max-w-md w-full mx-auto text-center space-y-6 px-6">
        <div className="flex justify-center">
          <div className="relative">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center">
              <AlertCircle className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="absolute inset-0 border-2 border-transparent border-t-primary rounded-full animate-spin opacity-60" />
          </div>
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-foreground">
            {isNoWorkspaceError
              ? t('common.error.workspaceRuntime.noWorkspace')
              : t('common.error.workspaceRuntime.title')
            }
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {isNoWorkspaceError
              ? t('common.error.workspaceRuntime.noWorkspaceHint')
              : t('common.error.workspaceRuntime.connectionFailed')
            }
          </p>
        </div>

        <div className="bg-muted/50 rounded-lg p-4 border border-border/50">
          <p className="text-xs text-muted-foreground font-mono break-words">
            {error}
          </p>
        </div>

        <div className="space-y-3">
          {isNoWorkspaceError ? (
            <>
              {onCreateWorkspace && (
                <Button
                  onClick={onCreateWorkspace}
                  className="w-full"
                  disabled={isLoading}
                >
                  {t('common.error.workspaceRuntime.createWorkspace')}
                </Button>
              )}
              {onRetry && (
                <Button
                  variant="outline"
                  onClick={onRetry}
                  className="w-full"
                  disabled={isLoading}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                  {t('common.refresh')}
                </Button>
              )}
            </>
          ) : (
            <>
              {onRetry && (
                <Button
                  onClick={onRetry}
                  className="w-full"
                  disabled={isLoading}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                  {isLoading ? t('common.reconnecting') : t('common.reconnect')}
                </Button>
              )}
              {canShowDeleteButton && (
                <Button
                  variant="destructive"
                  onClick={onDeleteWorkspace}
                  className="w-full"
                  disabled={isLoading}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  {t('common.error.workspaceRuntime.deleteWorkspace')}
                </Button>
              )}
            </>
          )}
        </div>

        <div className="text-xs text-muted-foreground">
          <p>{t('common.error.workspaceRuntime.troubleshoot')}</p>
        </div>
      </div>
    </div>
  );
};

export default RuntimeErrorPage;
