import React from 'react';
import { ArrowRight, BookOpen, Clock, UsersRound } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserGroup } from '../api/userManagementTypes';

interface GroupDetailPanelProps {
  group: UserGroup;
  onManageMembers: () => void;
}

export const GroupDetailPanel: React.FC<GroupDetailPanelProps> = ({
  group,
  onManageMembers,
}) => {
  const { state: i18nState, t } = useI18n();
  const updatedAt = React.useMemo(() => new Intl.DateTimeFormat(
    i18nState.currentLanguage,
    { dateStyle: 'medium', timeStyle: 'short' },
  ).format(new Date(group.updatedAt)), [group.updatedAt, i18nState.currentLanguage]);

  return (
    <section className="flex h-full min-h-0 flex-col overflow-y-auto">
      <div className="border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{t('userManagement.groups.summary.title')}</h2>
        {group.description ? (
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{group.description}</p>
        ) : null}
      </div>

      <div className="space-y-3 p-4">
        <div className="grid grid-cols-1 gap-2">
          <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <UsersRound className="h-4 w-4 text-muted-foreground" />
              <span className="truncate text-xs text-muted-foreground">
                {t('userManagement.groups.summary.memberCount')}
              </span>
            </div>
            <Badge variant="secondary">{group.memberCount}</Badge>
          </div>

          <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span className="truncate text-xs text-muted-foreground">
                {t('userManagement.groups.summary.sharedKnowledgeBases')}
              </span>
            </div>
            <Badge variant="outline">{group.knowledgeBaseShareCount}</Badge>
          </div>

          <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="truncate text-xs text-muted-foreground">
                {t('userManagement.groups.summary.updatedAt')}
              </span>
            </div>
            <span className="truncate text-xs text-foreground">{updatedAt}</span>
          </div>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
          {t('userManagement.groups.summary.permissionImpact')}
        </div>

        <Button type="button" className="h-8 w-full gap-1.5" onClick={onManageMembers}>
          {t('userManagement.groups.actions.manageMembers')}
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </section>
  );
};
