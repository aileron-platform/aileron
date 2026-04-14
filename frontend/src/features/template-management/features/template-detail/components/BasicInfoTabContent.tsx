/**
 * BasicInfoTabContent - 模板基本資訊 Tab 內容
 * 顯示模板的基本資訊，包括名稱、版本、作者、描述等
 */

import React from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import { useI18n } from '@/shared/hooks/useI18n';
import type { Template } from '@/shared/types/templates';
import {
  FileText,
  User,
  Tag,
  FolderTree,
  Code2,
  Info
} from 'lucide-react';

interface BasicInfoTabContentProps {
  template: Template;
}

export const BasicInfoTabContent: React.FC<BasicInfoTabContentProps> = ({ template }) => {
  const { t } = useI18n();

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* 標題區 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Info className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold text-foreground">{t('template.detail.basicInfo.title')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            {t('template.detail.basicInfo.description')}
          </p>
        </div>

        <Separator />

        {/* 基本資訊卡片 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t('template.detail.basicInfo.sections.general.title')}
            </CardTitle>
            <CardDescription>
              {t('template.detail.basicInfo.sections.general.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 模板名稱 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.name')}
              </div>
              <div className="col-span-2 text-sm font-semibold text-foreground">
                {template.name}
              </div>
            </div>

            {/* 模板 ID */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.templateId')}
              </div>
              <div className="col-span-2 text-sm font-mono text-foreground">
                {template.id}
              </div>
            </div>

            {/* 版本 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.version')}
              </div>
              <div className="col-span-2">
                <Badge variant="secondary">{template.version}</Badge>
              </div>
            </div>

            {/* CLI 類型 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.cliType')}
              </div>
              <div className="col-span-2">
                <Badge variant="outline" className="font-mono">
                  {template.cliType || 'claude-code'}
                </Badge>
              </div>
            </div>

            {/* 分類 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                <FolderTree className="h-4 w-4" />
                {t('template.detail.basicInfo.fields.category')}
              </div>
              <div className="col-span-2">
                <Badge variant="secondary">{template.categoryName || t('template.common.uncategorized')}</Badge>
              </div>
            </div>

            {/* 描述 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.description')}
              </div>
              <div className="col-span-2 text-sm text-foreground">
                {template.description || t('template.detail.basicInfo.fields.noDescription')}
              </div>
            </div>

            {/* 初始化指令 */}
            {template.initCommands && (
              <div className="grid grid-cols-3 gap-4">
                <div className="text-sm font-medium text-muted-foreground">
                  {t('template.detail.basicInfo.fields.initCommands')}
                </div>
                <div className="col-span-2">
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto">
                    <code>{template.initCommands}</code>
                  </pre>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 作者資訊卡片 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              {t('template.detail.basicInfo.sections.author.title')}
            </CardTitle>
            <CardDescription>
              {t('template.detail.basicInfo.sections.author.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 作者名稱 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.authorName')}
              </div>
              <div className="col-span-2 text-sm text-foreground">
                {template.author.name}
              </div>
            </div>

            {/* 作者郵箱 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('template.detail.basicInfo.fields.authorEmail')}
              </div>
              <div className="col-span-2 text-sm text-foreground">
                {template.author.email}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 關鍵字卡片 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Tag className="h-5 w-5" />
              {t('template.detail.basicInfo.sections.keywords.title')}
            </CardTitle>
            <CardDescription>
              {t('template.detail.basicInfo.sections.keywords.description')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {template.keywords.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {template.keywords.map((keyword) => (
                  <Badge key={keyword} variant="outline" className="text-xs">
                    #{keyword}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('template.detail.basicInfo.fields.noKeywords')}
              </p>
            )}
          </CardContent>
        </Card>

        {/* 功能統計卡片 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Code2 className="h-5 w-5" />
              {t('template.detail.basicInfo.sections.features.title')}
            </CardTitle>
            <CardDescription>
              {t('template.detail.basicInfo.sections.features.description')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {/* MCP 伺服器 */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.mcpServers.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.mcpServers')}
                </div>
              </div>

              {/* Slash Commands */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.slashCommands.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.slashCommands')}
                </div>
              </div>

              {/* Hooks */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.hooks.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.hooks')}
                </div>
              </div>

              {/* SubAgents */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.subAgents.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.subAgents')}
                </div>
              </div>

              {/* Claude.md */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.claudeMd ? '1' : '0'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.claudeMd')}
                </div>
              </div>

              {/* Scripts */}
              <div className="flex flex-col items-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-primary">
                  {template.scripts.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('template.detail.basicInfo.stats.scripts')}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
};

export default BasicInfoTabContent;
