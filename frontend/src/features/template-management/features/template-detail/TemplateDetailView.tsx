/**
 * TemplateDetailView - 範本詳細檢視
 * 參考 TemplateHub 設計，為每個功能項提供獨立的 tab
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import {
  FileText,
  ArrowLeft,
  PenSquare,
  Play,
  FolderOpen,
  Bot,
  Network,
  Zap,
  Command,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { CLAUDE_CODE_ICONS } from '@/features/workspace/components/navigation-constants';

import { useTemplateManagementContext } from '../../providers/TemplateManagementProvider';
import { apiClient } from '@/shared/api/apiClient';

import { SlashCommandsTabContent } from './components/SlashCommandsTabContent';
import { McpTabContent as McpTabContentView } from './components/McpTabContent';
import { HooksTabContent as HooksTabContentView } from './components/HooksTabContent';
import { ClaudeMdTabContent } from './components/ClaudeMdTabContent';
import { SubAgentsTabContent } from './components/SubAgentsTabContent';
import { OutputStylesTabContent } from './components/OutputStylesTabContent';
import { BasicInfoTabContent } from './components/BasicInfoTabContent';

import TemplateDetailFileViewer from './components/TemplateDetailFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TemplateDetailView');

export const TemplateDetailView: React.FC = () => {
  const navigate = useNavigate();
  const { templateId } = useParams<{ templateId: string }>();
  const { templates, isLoading } = useTemplateManagementContext();
  const [activeTab, setActiveTab] = useState('basic-info');
  const [scriptsCount, setScriptsCount] = useState(0);
  const [skillsCount, setSkillsCount] = useState(0);
  const { t } = useI18n();

  // 左側導航：固定寬度，不可收折
  const LEFT_WIDTH = 280;

  const template = useMemo(
    () => templates.find(item => item.id === templateId),
    [templates, templateId],
  );

  useEffect(() => {
    if (!templateId) return;

    setScriptsCount(0);
    setSkillsCount(0);

    const countFiles = (nodes: Array<{ type: 'file' | 'directory'; children?: any[] }>): number => {
      return nodes.reduce((total, node) => {
        if (node.type === 'file') {
          return total + 1;
        }
        if (node.children) {
          return total + countFiles(node.children);
        }
        return total;
      }, 0);
    };

    const fetchCount = async (
      scope: string,
      setter: (value: number) => void,
    ) => {
      try {
        const response = await apiClient.get<{ path: string; scope: string; nodes: Array<{ type: 'file' | 'directory'; children?: any[] }>; total: number }>(
          `/templates/${templateId}/files/tree?scope=${scope}&path=/&max_depth=10`,
        );
        setter(countFiles(response.nodes || []));
      } catch (error) {
        logger.error('Failed to fetch file count', { scope, error });
        setter(0);
      }
    };

    fetchCount('scripts', setScriptsCount);
    fetchCount('skills', setSkillsCount);
  }, [templateId]);

  const tabs = useMemo(
    () => [
      { id: 'basic-info', name: t('template.detail.tabs.basicInfo'), icon: FileText, count: 0 },
      { id: 'claude-md', name: t('template.detail.tabs.claudeMd'), icon: CLAUDE_CODE_ICONS['claude-md'], count: 0 },
      { id: 'hooks', name: t('template.detail.tabs.hooks'), icon: CLAUDE_CODE_ICONS['hooks'], count: template?.hooks.length || 0 },
      { id: 'mcp', name: t('template.detail.tabs.mcp'), icon: CLAUDE_CODE_ICONS['mcp'], count: template?.mcpServers.length || 0 },
      { id: 'subagent', name: t('template.detail.tabs.subAgents'), icon: CLAUDE_CODE_ICONS['subagents'], count: template?.subAgents.length || 0 },
      {
        id: 'slash-commands',
        name: t('template.detail.tabs.slashCommands'),
        icon: CLAUDE_CODE_ICONS['slash-commands'],
        count: template?.slashCommands.length || 0,
      },
      { id: 'output-styles', name: t('template.detail.tabs.outputStyles'), icon: CLAUDE_CODE_ICONS['output-styles'], count: template?.outputStyles.length || 0 },
      { id: 'skills', name: t('template.detail.tabs.skills'), icon: CLAUDE_CODE_ICONS['skills'], count: skillsCount },
      { id: 'scripts', name: t('template.detail.tabs.scripts'), icon: FolderOpen, count: scriptsCount },
    ],
    [
      scriptsCount,
      skillsCount,
      t,
      template?.hooks.length,
      template?.mcpServers.length,
      template?.slashCommands.length,
      template?.subAgents.length,
      template?.outputStyles.length,
    ],
  );

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {t('template.detail.loading')}
      </div>
    );
  }

  if (!template) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-sm text-muted-foreground">
        <p>{t('template.detail.notFound')}</p>
        <Button onClick={() => navigate('../..')}>{t('template.detail.actions.backToCenter')}</Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={template.name}
        icon={FileText}
        info={
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{t('template.detail.header.version', { version: template.version })}</span>
            <span>{t('template.detail.header.author', { author: template.author.name })}</span>
            <span>{t('template.detail.header.category', { category: template.categoryName || t('template.common.uncategorized') })}</span>
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate('../..')}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> {t('template.detail.actions.back')}
            </Button>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(ROUTES.TEMPLATE_EDIT(templateId!))}>
              <PenSquare className="mr-1.5 h-3.5 w-3.5" /> {t('template.detail.actions.edit')}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={() => navigate('../..')}>
              <Play className="mr-1.5 h-3.5 w-3.5" /> {t('template.detail.actions.goToInstall')}
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-hidden">
        <div className="h-full flex">
          {/* 左側 Tab 導航（固定寬度） */}
          <div
            className="h-full border-r border-border bg-background"
            style={{ width: LEFT_WIDTH }}
          >
            <div className="h-full flex flex-col">
              {/* 內容 */}
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-foreground mb-3">
                      {t('template.detail.sidebar.info.title')}
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          {t('template.detail.sidebar.info.categoryLabel')}
                        </span>
                        <Badge variant="secondary">{template.categoryName || t('template.common.uncategorized')}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          {t('template.detail.sidebar.info.versionLabel')}
                        </span>
                        <span className="font-medium">{template.version}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-medium text-foreground mb-3">
                      {t('template.detail.sidebar.features.title')}
                    </h4>
                    <div className="space-y-1">
                      {tabs.map(tab => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        return (
                          <Button
                            key={tab.id}
                            variant={isActive ? 'default' : 'ghost'}
                            className="w-full justify-start h-8 px-2 text-xs"
                            onClick={() => setActiveTab(tab.id)}
                          >
                            <Icon className="h-4 w-4 mr-2" />
                            <span className="flex-1 text-left">{tab.name}</span>
                            {tab.count > 0 && (
                              <Badge
                                variant="outline"
                                className={`ml-auto text-xs ${isActive ? 'bg-background text-foreground border-transparent' : ''}`}
                              >
                                {tab.count}
                              </Badge>
                            )}
                          </Button>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-medium text-foreground mb-3">
                      {t('template.detail.sidebar.keywords.title')}
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {template.keywords.map(keyword => (
                        <Badge key={keyword} variant="outline" className="text-xs">
                          #{keyword}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 右側內容區 */}
          <div className="flex-1 bg-background overflow-hidden">
            <div className="h-full">
              {/* Basic Info Tab */}
              {activeTab === 'basic-info' && <BasicInfoTabContent template={template} />}

              {/* Slash Commands Tab */}
              {activeTab === 'slash-commands' && <SlashCommandsTabContent commands={template.slashCommands} />}

              {/* MCP Tab */}
              {activeTab === 'mcp' && <McpTabContentView mcpServers={template.mcpServers} />}

              {/* Hooks Tab */}
              {activeTab === 'hooks' && <HooksTabContentView hooks={template.hooks} />}

              {/* Claude.md Tab */}
              {activeTab === 'claude-md' && <ClaudeMdTabContent templateId={templateId} claudeMd={template.claudeMd} />}

              {/* SubAgent Tab */}
              {activeTab === 'subagent' && <SubAgentsTabContent agents={template.subAgents} />}

              {/* Output Styles Tab */}
              {activeTab === 'output-styles' && <OutputStylesTabContent />}

              {/* Skills Tab */}
              {activeTab === 'skills' && templateId && (
                <TemplateDetailFileViewer
                  templateId={templateId}
                  basePath="skills"
                  title={t('template.detail.tabs.skills')}
                  onTreeUpdate={(_, count) => setSkillsCount(count)}
                />
              )}

              {/* Files Tab */}
              {activeTab === 'scripts' && templateId && (
                <TemplateDetailFileViewer
                  templateId={templateId}
                  basePath="scripts"
                  title={t('template.detail.tabs.scripts')}
                  onTreeUpdate={(_, count) => setScriptsCount(count)}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TemplateDetailView;
