import React from 'react';
import { FileDiff, History, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlWorkbenchMode } from '@/shared/components/version-control';

interface KnowledgeBaseVersionControlPresentationProps {
  mode: VersionControlWorkbenchMode;
  count: number;
  sidebar: React.ReactNode;
  navigatorActions?: React.ReactNode;
  main: React.ReactNode;
  renderRegions?: (regions: KnowledgeBaseVersionControlRegions) => React.ReactNode;
}

export interface KnowledgeBaseVersionControlRegions {
  navigator: React.ReactNode;
  navigatorTitle: string;
  navigatorIcon: LucideIcon;
  navigatorInfo: React.ReactNode;
  navigatorActions?: React.ReactNode;
  main: React.ReactNode;
}

export const KnowledgeBaseVersionControlPresentation: React.FC<
  KnowledgeBaseVersionControlPresentationProps
> = ({ mode, count, sidebar, navigatorActions, main, renderRegions }) => {
  const { t } = useI18n();
  const title = mode === 'changes'
    ? t('shared.versionControl.mode.fileChanges')
    : t('shared.versionControl.mode.commitHistory');
  const Icon = mode === 'changes' ? FileDiff : History;

  const regions: KnowledgeBaseVersionControlRegions = {
    navigator: (
      <div data-testid="knowledge-base-version-control-sidebar">
        {sidebar}
      </div>
    ),
    navigatorTitle: title,
    navigatorIcon: Icon,
    navigatorInfo: (
      <span className="ml-1 min-w-5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] leading-none text-muted-foreground">
        {count}
      </span>
    ),
    navigatorActions,
    main: (
      <div data-testid="knowledge-base-version-control-main">
        <div>{main}</div>
      </div>
    ),
  };

  return renderRegions ? (
    <>{renderRegions(regions)}</>
  ) : (
    <>
      <div data-testid="knowledge-base-version-control-sidebar">
        {sidebar}
        {regions.navigatorInfo}
      </div>
      {regions.main}
    </>
  );
};
