import React from 'react';
import {
  AlertCircle,
  Database,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useI18n } from '@/shared/hooks/useI18n';
import type { WorkspaceKnowledgeBaseMountSync } from '../../../api/workspaceApiTypes';

const ERROR_TRANSLATION_KEYS: Record<string, string> = {
  KB_MOUNT_ALIAS_INVALID: 'workspace.workspaceSettings.knowledgeBases.errors.KB_MOUNT_ALIAS_INVALID',
  KB_MOUNT_SOURCE_INVALID: 'workspace.workspaceSettings.knowledgeBases.errors.KB_MOUNT_SOURCE_INVALID',
  WORKSPACE_ACCESS_DENIED: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_ACCESS_DENIED',
  KB_ACCESS_DENIED: 'workspace.workspaceSettings.knowledgeBases.errors.KB_ACCESS_DENIED',
  KB_PERMISSION_DENIED: 'workspace.workspaceSettings.knowledgeBases.errors.KB_PERMISSION_DENIED',
  WORKSPACE_RUNTIME_ACTION_FORBIDDEN: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_RUNTIME_ACTION_FORBIDDEN',
  WORKSPACE_NOT_FOUND: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_NOT_FOUND',
  KB_NOT_FOUND: 'workspace.workspaceSettings.knowledgeBases.errors.KB_NOT_FOUND',
  KB_ATTACHMENT_NOT_FOUND: 'workspace.workspaceSettings.knowledgeBases.errors.KB_ATTACHMENT_NOT_FOUND',
  KB_ALREADY_ATTACHED: 'workspace.workspaceSettings.knowledgeBases.errors.KB_ALREADY_ATTACHED',
  KB_MOUNT_ALIAS_CONFLICT: 'workspace.workspaceSettings.knowledgeBases.errors.KB_MOUNT_ALIAS_CONFLICT',
  WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS',
  WORKSPACE_KB_MOUNT_SYNC_NOT_RETRYABLE: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_SYNC_NOT_RETRYABLE',
  WORKSPACE_KB_MOUNT_RECONCILE_FAILED: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_RECONCILE_FAILED',
  WORKSPACE_KB_MOUNT_JOB_INVALID: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_JOB_INVALID',
  WORKSPACE_KB_MOUNT_SNAPSHOT_INVALID: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_SNAPSHOT_INVALID',
  WORKSPACE_KB_MOUNT_STATE_INVALID: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_STATE_INVALID',
  WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED',
  WORKSPACE_LIFECYCLE_FAILED: 'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_LIFECYCLE_FAILED',
};

export const getWorkspaceKnowledgeBaseErrorTranslationKey = (errorCode?: string | null): string => (
  errorCode && ERROR_TRANSLATION_KEYS[errorCode]
    ? ERROR_TRANSLATION_KEYS[errorCode]
    : 'workspace.workspaceSettings.knowledgeBases.errors.unknown'
);

interface MountedKnowledgeBasesPanelProps {
  mountSync: WorkspaceKnowledgeBaseMountSync | null;
  runtimeAccessRevision?: number;
  runtimeAccessObservedRevision?: number;
  canRetry: boolean;
  isRetrying: boolean;
  onRetry: () => Promise<void> | void;
}

export const MountedKnowledgeBasesPanel: React.FC<MountedKnowledgeBasesPanelProps> = ({
  mountSync,
  runtimeAccessRevision,
  runtimeAccessObservedRevision,
  canRetry,
  isRetrying,
  onRetry,
}) => {
  const { t } = useI18n();
  const hasAccessRevisions = runtimeAccessRevision !== undefined
    && runtimeAccessObservedRevision !== undefined;
  const accessStatus = hasAccessRevisions
    ? (runtimeAccessRevision === runtimeAccessObservedRevision ? 'ready' : 'recycling')
    : null;
  const retryAllowed = canRetry
    && mountSync?.status === 'degraded'
    && !mountSync.compensating;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="h-4 w-4 text-sky-600" />
          {t('workspace.workspaceSettings.knowledgeBases.mounted.title')}
        </CardTitle>
        <CardDescription>
          {t('workspace.workspaceSettings.knowledgeBases.mounted.description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-3 rounded-lg border border-border/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-foreground">
                {t('workspace.workspaceSettings.knowledgeBases.mounted.mount.title')}
              </span>
              {mountSync ? (
                <Badge
                  variant={
                    mountSync.status === 'degraded'
                      ? 'destructive'
                      : mountSync.status === 'ready'
                        ? 'secondary'
                        : 'outline'
                  }
                >
                  {t(`workspace.workspaceSettings.knowledgeBases.mounted.mount.status.${mountSync.status}`)}
                </Badge>
              ) : null}
            </div>
            {mountSync ? (
              <div className="grid grid-cols-2 gap-3 text-sm text-muted-foreground sm:grid-cols-3">
                <div>
                  <div className="text-xs">{t('workspace.workspaceSettings.knowledgeBases.mounted.desiredRevision')}</div>
                  <div className="font-mono text-foreground">{mountSync.desiredRevision}</div>
                </div>
                <div>
                  <div className="text-xs">{t('workspace.workspaceSettings.knowledgeBases.mounted.observedRevision')}</div>
                  <div className="font-mono text-foreground">{mountSync.observedRevision}</div>
                </div>
                <div>
                  <div className="text-xs">
                    {t('workspace.workspaceSettings.knowledgeBases.mounted.lastKnownGoodRevision')}
                  </div>
                  <div className="font-mono text-foreground">
                    {mountSync.lastKnownGoodRevision}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                {t('workspace.workspaceSettings.knowledgeBases.status.loading')}
              </div>
            )}
          </div>

          <div className="space-y-3 rounded-lg border border-border/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2 font-medium text-foreground">
                <ShieldCheck className="h-4 w-4 text-sky-600" />
                {t('workspace.workspaceSettings.knowledgeBases.mounted.access.title')}
              </span>
              {accessStatus ? (
                <Badge variant={accessStatus === 'ready' ? 'secondary' : 'outline'}>
                  {t(`workspace.workspaceSettings.knowledgeBases.mounted.access.status.${accessStatus}`)}
                </Badge>
              ) : null}
            </div>
            {hasAccessRevisions ? (
              <div className="grid grid-cols-2 gap-3 text-sm text-muted-foreground">
                <div>
                  <div className="text-xs">{t('workspace.workspaceSettings.knowledgeBases.mounted.desiredRevision')}</div>
                  <div className="font-mono text-foreground">{runtimeAccessRevision}</div>
                </div>
                <div>
                  <div className="text-xs">{t('workspace.workspaceSettings.knowledgeBases.mounted.observedRevision')}</div>
                  <div className="font-mono text-foreground">{runtimeAccessObservedRevision}</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                {t('workspace.workspaceSettings.knowledgeBases.status.loading')}
              </div>
            )}
          </div>
        </div>

        {mountSync?.compensating ? (
          <div
            role="status"
            className="flex items-start gap-3 rounded-lg border border-border/70 bg-muted/40 p-4 text-sm text-muted-foreground"
          >
            <LoaderCircle className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-sky-600" />
            <div className="space-y-1">
              <p className="font-medium text-foreground">
                {t('workspace.workspaceSettings.knowledgeBases.mounted.compensating.title')}
              </p>
              <p>
                {t('workspace.workspaceSettings.knowledgeBases.mounted.compensating.description')}
              </p>
            </div>
          </div>
        ) : null}

        {mountSync?.status === 'degraded' ? (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-medium">
                {t('workspace.workspaceSettings.knowledgeBases.mounted.degradedTitle')}
              </p>
              <p>{t(getWorkspaceKnowledgeBaseErrorTranslationKey(mountSync.errorCode))}</p>
              {retryAllowed ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void onRetry();
                  }}
                  disabled={isRetrying}
                >
                  <RefreshCw className={`mr-2 h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
                  {isRetrying
                    ? t('workspace.workspaceSettings.knowledgeBases.mounted.retrying')
                    : t('workspace.workspaceSettings.knowledgeBases.mounted.retry')}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};
