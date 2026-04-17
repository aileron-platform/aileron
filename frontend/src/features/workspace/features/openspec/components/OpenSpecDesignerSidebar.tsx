import React from 'react';
import { BookOpen, CheckCircle2, ChevronLeft, FileCog, RefreshCw, Sparkles, Wrench } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { useOpenSpecWorkspace } from '../OpenSpecWorkspaceContext';
import { getOpenSpecDesignerSection } from '../utils/designerRouting';
import type { OpenSpecDesignerSection } from '../../../components/ChatPanel/openSpecApi';

const sections: Array<{
  id: OpenSpecDesignerSection;
  icon: React.ComponentType<{ className?: string }>;
  labelKey: string;
  descriptionKey: string;
}> = [
  { id: 'overview', icon: Sparkles, labelKey: 'workspace.openspec.designer.sections.overview', descriptionKey: 'workspace.openspec.designer.sectionDescriptions.overview' },
  { id: 'project-config', icon: FileCog, labelKey: 'workspace.openspec.designer.sections.projectConfig', descriptionKey: 'workspace.openspec.designer.sectionDescriptions.projectConfig' },
  { id: 'schemas', icon: Wrench, labelKey: 'workspace.openspec.designer.sections.schemas', descriptionKey: 'workspace.openspec.designer.sectionDescriptions.schemas' },
  { id: 'validation', icon: CheckCircle2, labelKey: 'workspace.openspec.designer.sections.validation', descriptionKey: 'workspace.openspec.designer.sectionDescriptions.validation' },
];

export const OpenSpecDesignerSidebar: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const { layout, toggleSecondColumn } = useWorkspace();
  const { designer, isLoading, refresh } = useOpenSpecWorkspace();
  const currentSection = getOpenSpecDesignerSection(location.pathname);
  const isCollapsed = layout.secondColumnCollapsed;

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div className={`flex h-10 items-center border-b border-border bg-card px-3 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!isCollapsed ? (
          <div className="flex min-w-0 items-center gap-2">
            <BookOpen className="h-3.5 w-3.5 text-primary" />
            <span className="truncate text-sm font-medium">{t('workspace.openspec.designer.title')}</span>
          </div>
        ) : null}
        <div className="flex items-center gap-1">
          {!isCollapsed ? (
            <button
              type="button"
              className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent disabled:opacity-50"
              onClick={() => void refresh({ reloadActiveDocument: false })}
              title={isLoading ? t('workspace.openspec.sidebar.refreshing') : t('workspace.openspec.sidebar.refresh')}
              aria-label={isLoading ? t('workspace.openspec.sidebar.refreshing') : t('workspace.openspec.sidebar.refresh')}
              disabled={isLoading}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={toggleSecondColumn}
            className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
            aria-label={isCollapsed ? t('workspace.layout.expandSidebar') : t('workspace.layout.collapseSidebar')}
            title={isCollapsed ? t('workspace.layout.expandSidebar') : t('workspace.layout.collapseSidebar')}
          >
            <ChevronLeft className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder
          icon={BookOpen}
          className="text-primary"
          iconClassName="text-primary"
        />
      ) : (
        <div className="flex-1 space-y-4 overflow-y-auto p-3">
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">{t('workspace.openspec.designer.summaryTitle')}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t('workspace.openspec.designer.summaryDescription')}
                </p>
              </div>
              <Badge variant="outline">
                {designer?.overview.defaultSchema ?? t('workspace.openspec.designer.noDefaultSchema')}
              </Badge>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
              <div className="rounded-md bg-muted/50 px-2 py-1.5">
                {t('workspace.openspec.designer.metrics.config', { state: designer?.overview.configPresent ? t('workspace.openspec.designer.present') : t('workspace.openspec.designer.missing') })}
              </div>
              <div className="rounded-md bg-muted/50 px-2 py-1.5">
                {t('workspace.openspec.designer.metrics.schemas', { count: designer?.overview.projectSchemaCount ?? 0 })}
              </div>
            </div>
          </div>

          <div className="space-y-1">
            {sections.map((section) => {
              const Icon = section.icon;
              const active = currentSection === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => navigate(`/workspaces/openspec/designer/${section.id}`)}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-lg border px-3 py-2 text-left transition-colors',
                    active ? 'border-primary/40 bg-primary/10 text-primary' : 'border-border hover:bg-muted/50',
                  )}
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{t(section.labelKey)}</div>
                    <div className="text-xs text-muted-foreground">{t(section.descriptionKey)}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default OpenSpecDesignerSidebar;
