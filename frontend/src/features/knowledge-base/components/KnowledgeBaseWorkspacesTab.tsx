import React from 'react';
import { Box, EyeOff, FolderTree, Link2 } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

interface KnowledgeBaseWorkspacesTabProps {
  knowledgeBaseId: string;
}

export const KnowledgeBaseWorkspacesTab: React.FC<KnowledgeBaseWorkspacesTabProps> = ({
  knowledgeBaseId,
}) => {
  const { t } = useI18n();
  const { workspaceUsageById, loadKnowledgeBaseWorkspaceUsage } = useKnowledgeBase();
  const [loadFailed, setLoadFailed] = React.useState(false);
  const usage = workspaceUsageById[knowledgeBaseId];

  React.useEffect(() => {
    if (usage !== undefined) {
      return;
    }

    let active = true;
    void loadKnowledgeBaseWorkspaceUsage(knowledgeBaseId).catch(() => {
      if (active) {
        setLoadFailed(true);
      }
    });
    return () => {
      active = false;
    };
  }, [knowledgeBaseId, loadKnowledgeBaseWorkspaceUsage, usage]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <FeatureHeader
        title={t('knowledgeBase.navigation.workspaces')}
        icon={Link2}
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-6 bg-background p-6">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('knowledgeBase.attachments.description')}
          </p>

          {loadFailed ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {t('knowledgeBase.attachments.loadFailed')}
            </div>
          ) : usage === undefined ? (
            <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-sm text-muted-foreground">
              {t('knowledgeBase.attachments.loading')}
            </div>
          ) : (
            <>
              {usage.visibleItems.length === 0 ? (
                <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-sm text-muted-foreground">
                  {t('knowledgeBase.attachments.empty')}
                </div>
              ) : (
                <div className="grid gap-3 lg:grid-cols-2">
                  {usage.visibleItems.map((attachment) => (
                    <div
                      key={attachment.attachmentId}
                      className="space-y-3 rounded-md border border-border/60 bg-background/70 p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Box className="h-4 w-4 shrink-0 text-sky-600" />
                        <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                          {attachment.workspaceName}
                        </span>
                        <Badge variant="outline">{attachment.workspaceId}</Badge>
                        <Badge variant={attachment.attachmentStatus === 'active' ? 'secondary' : 'outline'}>
                          {t(`knowledgeBase.attachments.status.${attachment.attachmentStatus}`)}
                        </Badge>
                      </div>
                      <div className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground">
                        <FolderTree className="h-3.5 w-3.5" />
                        /knowledge/{attachment.mountAlias}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {usage.hiddenWorkspaceCount > 0 ? (
                <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
                  <EyeOff className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {t('knowledgeBase.attachments.hiddenWorkspaces', {
                      count: usage.hiddenWorkspaceCount,
                    })}
                  </span>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
