import React, { useState } from 'react';
import { Tabs, TabsContent } from '@/shared/components/ui/tabs';
import { TemplateFormValues } from './formTypes';
import { Info, File as FileIcon } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { CLAUDE_CODE_ICONS } from '@/features/workspace/components/navigation-constants';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';

import BasicInfoSection from './sections/BasicInfoSection';
import McpServersSection from './sections/McpServersSection';
import SlashCommandsSection from './sections/SlashCommandsSection';
import HooksSection from './sections/HooksSection';
import SubAgentsSection from './sections/SubAgentsSection';
import OutputStylesSection from './sections/OutputStylesSection';
import DocsSection from './sections/DocsSection';
import SkillsSection from './sections/SkillsSection';
import ScriptsSection from './sections/ScriptsSection';


export interface TemplateFormProps {
  values: TemplateFormValues;
  onChange: (next: TemplateFormValues) => void;
  onAddKeyword: (keyword: string) => void;
  onRemoveKeyword: (keyword: string) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
  activeTab?: string;
  setActiveTab?: (tab: string) => void;
  isEditMode?: boolean;
}



export const TemplateForm: React.FC<TemplateFormProps> = ({
  values,
  onChange,
  onAddKeyword,
  onRemoveKeyword,
  templateId,
  onReloadTemplate,
  activeTab: externalActiveTab,
  setActiveTab: externalSetActiveTab,
  isEditMode = false,
}) => {
  const { t } = useI18n();
  // 使用外部狀態（如果提供），否則使用內部狀態
  const [internalActiveTab, setInternalActiveTab] = useState('basic');
  const activeTab = externalActiveTab ?? internalActiveTab;
  const setActiveTab = externalSetActiveTab ?? setInternalActiveTab;

  const updateCollection = <K extends keyof TemplateFormValues>(key: K, items: TemplateFormValues[K]) => {
    onChange({ ...values, [key]: items });
  };

  const ClaudeMdIcon = CLAUDE_CODE_ICONS['claude-md'];
  const HooksIcon = CLAUDE_CODE_ICONS['hooks'];
  const McpIcon = CLAUDE_CODE_ICONS['mcp'];
  const SubagentsIcon = CLAUDE_CODE_ICONS['subagents'];
  const SlashCommandsIcon = CLAUDE_CODE_ICONS['slash-commands'];
  const OutputStylesIcon = CLAUDE_CODE_ICONS['output-styles'];
  const SkillsIcon = CLAUDE_CODE_ICONS['skills'];
  const templateTabs = [
    { value: 'basic', label: t('template.editor.tabs.basic'), icon: Info },
    { value: 'docs', label: t('template.editor.tabs.claudeMd'), icon: ClaudeMdIcon },
    { value: 'hooks', label: t('template.editor.tabs.hooks'), icon: HooksIcon, count: values.hooks.length },
    { value: 'mcp', label: t('template.editor.tabs.mcp'), icon: McpIcon, count: values.mcpServers.length },
    { value: 'subagent', label: t('template.editor.tabs.subAgents'), icon: SubagentsIcon, count: values.subAgents.length },
    { value: 'slash', label: t('template.editor.tabs.slashCommands'), icon: SlashCommandsIcon, count: values.slashCommands.length },
    { value: 'outputstyle', label: t('template.editor.tabs.outputStyles'), icon: OutputStylesIcon, count: values.outputStyles.length },
    { value: 'skills', label: t('template.editor.tabs.skills'), icon: SkillsIcon, count: values.skills.length },
    { value: 'scripts', label: t('template.editor.tabs.scripts'), icon: FileIcon, count: values.scripts.length },
  ] as const;

  return (
    <div className="h-full flex flex-col">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        <TopTabsBar>
          <TopTabsList>
            {templateTabs.map(tab => {
              const Icon = tab.icon;
              return (
                <TopTabsTrigger key={tab.value} value={tab.value}>
                  <Icon className="h-4 w-4" />
                  {tab.label}
                  <TopTabsCountBadge count={tab.count ?? 0} />
                </TopTabsTrigger>
              );
            })}
          </TopTabsList>
        </TopTabsBar>
          <TabsContent value="basic" className="flex-1 overflow-auto !p-0 !m-0">
            <div className="p-6">
              <BasicInfoSection
                values={values}
                onChange={onChange}
                onAddKeyword={onAddKeyword}
                onRemoveKeyword={onRemoveKeyword}
                isEditMode={isEditMode}
              />
            </div>
          </TabsContent>

          <TabsContent value="mcp" className="flex-1 overflow-auto !p-0 !m-0">
            <McpServersSection
              servers={values.mcpServers}
              onServersChange={items => updateCollection('mcpServers', items)}
            />
          </TabsContent>

          <TabsContent value="slash" className="flex-1 overflow-auto !p-0 !mt-0 !mb-0 !mx-0" style={{ marginTop: '1px' }}>
            <SlashCommandsSection
              slashCommands={values.slashCommands}
              onSlashCommandsChange={items => updateCollection('slashCommands', items)}
              templateId={templateId}
              onReloadTemplate={onReloadTemplate}
            />
          </TabsContent>

          <TabsContent value="hooks" className="flex-1 overflow-auto !p-0 !m-0">
            <HooksSection
              hooks={values.hooks}
              onHooksChange={items => updateCollection('hooks', items)}
            />
          </TabsContent>

          <TabsContent value="subagent" className="flex-1 overflow-auto !p-0 !m-0">
            <SubAgentsSection
              subAgents={values.subAgents}
              onSubAgentsChange={items => updateCollection('subAgents', items)}
              templateId={templateId}
              onReloadTemplate={onReloadTemplate}
            />
          </TabsContent>

          <TabsContent value="outputstyle" className="flex-1 overflow-auto !p-0 !m-0">
            <OutputStylesSection
              outputStyles={values.outputStyles}
              onOutputStylesChange={items => updateCollection('outputStyles', items)}
              templateId={templateId}
              onReloadTemplate={onReloadTemplate}
            />
          </TabsContent>

          <TabsContent value="skills" className="flex-1 overflow-auto !p-0 !m-0">
            <SkillsSection
              templateId={templateId}
              skills={values.skills}
              onSkillsChange={items => updateCollection('skills', items)}
            />
          </TabsContent>

          <TabsContent value="scripts" className="flex-1 overflow-auto !p-0 !m-0">
            <ScriptsSection
              templateId={templateId}
              scripts={values.scripts}
              onScriptsChange={items => updateCollection('scripts', items)}
            />
          </TabsContent>

          <TabsContent value="docs" className="flex-1 overflow-auto !p-0 !m-0">
            <DocsSection
              templateId={templateId}
              documentation={values.documentation}
              claudeMd={values.claudeMd}
              onChange={(partial) => onChange({ ...values, ...partial })}
            />
          </TabsContent>
      </Tabs>
    </div>
  );
};

export default TemplateForm;
