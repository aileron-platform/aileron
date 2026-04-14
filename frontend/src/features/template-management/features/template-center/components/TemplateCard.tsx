import React, { useMemo } from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '@/shared/components/ui/dropdown-menu';
import { MoreVertical, Play, Edit, Trash2, Download } from 'lucide-react';
import type { Template } from '@/shared/types/templates';
import { buildFeatureFlags } from '@/features/template-management/utils/templateSelectors';
import { useI18n } from '@/shared/hooks/useI18n';

export interface TemplateCardProps {
  template: Template;
  onOpenDetail: (template: Template) => void;
  onInstall: (template: Template) => void;
  onEdit: (template: Template) => void;
  onDelete: (template: Template) => void;
  onExport: (template: Template) => void;
  isExporting?: boolean;
}

export const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  onOpenDetail,
  onInstall,
  onEdit,
  onDelete,
  onExport,
  isExporting = false,
}) => {
  const featureFlags = useMemo(() => buildFeatureFlags(template), [template]);
  const { t } = useI18n();
  const featureLabels: Array<{ key: keyof ReturnType<typeof buildFeatureFlags>; label: string }> = useMemo(
    () => [
      { key: 'hasMcp', label: t('template.center.card.features.mcp') },
      { key: 'hasSlashCommands', label: t('template.center.card.features.slashCommands') },
      { key: 'hasHooks', label: t('template.center.card.features.hooks') },
      { key: 'hasClaudeMd', label: t('template.center.card.features.claudeMd') },
      { key: 'hasSubAgents', label: t('template.center.card.features.subAgents') },
      { key: 'hasOutputStyles', label: t('template.center.card.features.outputStyles') },
      { key: 'hasScripts', label: t('template.center.card.features.scripts') },
      { key: 'hasSkills', label: t('template.center.card.features.skills') },
    ],
    [t],
  );

  return (
    <Card className="p-5 h-full flex flex-col border-border/80 hover:border-primary/60 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1" onClick={() => onOpenDetail(template)}>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {template.categoryName || t('template.common.uncategorized')}
          </p>
          <h3 className="text-lg font-semibold text-foreground cursor-pointer hover:text-primary">
            {template.name}
          </h3>
          <p className="text-xs font-mono text-muted-foreground">ID: {template.id}</p>
          <p className="text-sm text-muted-foreground line-clamp-2">{template.description}</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEdit(template)}>
              <Edit className="h-4 w-4 mr-2" />
              {t('template.center.card.actions.edit')}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport(template)}>
              <Download className="h-4 w-4 mr-2" />
              {t('template.center.card.actions.export')}
            </DropdownMenuItem>
            <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onDelete(template)}>
              <Trash2 className="h-4 w-4 mr-2" />
              {t('template.center.card.actions.delete')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="mt-4 mb-5 flex flex-wrap gap-2">
        <Badge variant="secondary" className="text-xs">{template.version}</Badge>
        <Badge variant="outline" className="text-xs">{template.author.name}</Badge>
        {template.keywords.slice(0, 3).map(keyword => (
          <Badge key={keyword} variant="outline" className="text-xs">
            #{keyword}
          </Badge>
        ))}
        {template.keywords.length > 3 && (
          <Badge variant="outline" className="text-xs">+{template.keywords.length - 3}</Badge>
        )}
      </div>

      <div className="space-y-2 text-xs text-muted-foreground flex-1">
        <div className="grid grid-cols-2 gap-2">
          {featureLabels.map(({ key, label }) =>
            featureFlags[key] ? (
              <div key={key} className="flex items-center gap-2 text-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                <span>{label}</span>
              </div>
            ) : null,
          )}
        </div>
      </div>

      <div className="mt-6 flex items-center gap-2">
        <Button className="flex-1" onClick={() => onInstall(template)}>
          <Play className="h-4 w-4 mr-2" />
          {t('template.center.card.actions.install')}
        </Button>
        <Button variant="outline" className="flex-1" disabled={isExporting} onClick={() => onExport(template)}>
          {isExporting ? (
            t('template.center.card.actions.exporting')
          ) : (
            <span className="flex items-center gap-2">
              <Download className="h-4 w-4" />
              {t('template.center.card.actions.export')}
            </span>
          )}
        </Button>
      </div>
    </Card>
  );
};

export default TemplateCard;
