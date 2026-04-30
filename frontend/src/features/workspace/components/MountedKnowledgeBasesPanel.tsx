import React from 'react';
import { AlertCircle, Database, RefreshCw } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type { WorkspaceKnowledgeBaseAttachmentSummary } from '@/shared/types/knowledgeBase';
import { workspaceLifecycleApi } from '../services/workspaceLifecycleApi';
import { useWorkspace } from '../providers/WorkspaceProvider';

interface MountedKnowledgeBasesPanelProps {
  workspaceId?: string;
  attachments: WorkspaceKnowledgeBaseAttachmentSummary[];
  mountedKbSignature?: string | null;
  hasPendingKbChanges?: boolean;
  onRefresh?: () => Promise<void> | void;
}

export const MountedKnowledgeBasesPanel: React.FC<MountedKnowledgeBasesPanelProps> = ({
  workspaceId,
  attachments,
  mountedKbSignature,
  hasPendingKbChanges = false,
  onRefresh,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const [isRestarting, setIsRestarting] = React.useState(false);
  const mountedItems = React.useMemo(
    () => (hasPendingKbChanges ? [] : attachments),
    [attachments, hasPendingKbChanges],
  );

  const handleRestartRuntime = React.useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsRestarting(true);
    try {
      await workspaceLifecycleApi.restartRuntime(workspaceId);
      await workspaceRuntime.reload();
      await onRefresh?.();
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.mounted.restart.successTitle'),
        description: t('workspace.workspaceSettings.knowledgeBases.mounted.restart.successDescription'),
      });
    } catch (error) {
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.mounted.restart.errorTitle'),
        description:
          error instanceof Error && error.message
            ? error.message
            : t('workspace.workspaceSettings.knowledgeBases.mounted.restart.errorDescription'),
        variant: 'destructive',
      });
    } finally {
      setIsRestarting(false);
    }
  }, [onRefresh, t, toast, workspaceId, workspaceRuntime]);

  return (
    <Card>
      <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4 text-sky-600" />
            {t('workspace.workspaceSettings.knowledgeBases.mounted.title')}
            {hasPendingKbChanges ? (
              <Badge variant="secondary" className="ml-1">
                {t('workspace.workspaceSettings.knowledgeBases.mounted.pendingBadge')}
              </Badge>
            ) : null}
          </CardTitle>
          <CardDescription>
            {t('workspace.workspaceSettings.knowledgeBases.mounted.description')}
          </CardDescription>
        </div>
        {hasPendingKbChanges ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              void handleRestartRuntime();
            }}
            disabled={!workspaceId || isRestarting}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isRestarting ? 'animate-spin' : ''}`} />
            {isRestarting
              ? t('workspace.workspaceSettings.knowledgeBases.mounted.restart.loading')
              : t('workspace.workspaceSettings.knowledgeBases.mounted.restart.label')}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">
            {mountedKbSignature
              ? `${t('workspace.workspaceSettings.knowledgeBases.mounted.signatureLabel')}: ${mountedKbSignature.slice(0, 12)}`
              : t('workspace.workspaceSettings.knowledgeBases.mounted.signatureMissing')}
          </Badge>
          <span>
            {hasPendingKbChanges
              ? t('workspace.workspaceSettings.knowledgeBases.mounted.pendingHint')
              : t('workspace.workspaceSettings.knowledgeBases.mounted.syncedHint')}
          </span>
        </div>

        {hasPendingKbChanges ? (
          <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-800">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1">
                <p className="font-medium">
                  {t('workspace.workspaceSettings.knowledgeBases.mounted.pendingTitle')}
                </p>
                <p>{t('workspace.workspaceSettings.knowledgeBases.mounted.pendingDescription')}</p>
              </div>
            </div>
          </div>
        ) : null}

        {mountedItems.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-muted/40 p-5 text-sm text-muted-foreground">
            {hasPendingKbChanges
              ? t('workspace.workspaceSettings.knowledgeBases.mounted.pendingEmpty')
              : t('workspace.workspaceSettings.knowledgeBases.mounted.empty')}
          </div>
        ) : (
          <div className="space-y-3">
            {mountedItems.map((attachment) => (
              <div
                key={attachment.id}
                className="rounded-xl border border-border/60 bg-card/60 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Database className="h-4 w-4 shrink-0 text-primary" />
                  <span className="font-medium text-foreground">{attachment.name}</span>
                  <Badge variant="outline">{attachment.slug}</Badge>
                  <Badge variant={attachment.mode === 'rw' ? 'secondary' : 'outline'}>
                    {attachment.mode.toUpperCase()}
                  </Badge>
                  {attachment.role ? (
                    <Badge variant="outline">{attachment.role}</Badge>
                  ) : null}
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  /knowledge/{attachment.mountAlias}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MountedKnowledgeBasesPanel;
