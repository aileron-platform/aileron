import React from 'react';
import { ArrowLeft, PenSquare } from 'lucide-react';
import { FeatureShellBreadcrumbBar, type FeatureShellBreadcrumbItem } from '@/shared/components/shell';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceEditorHeaderProps {
  breadcrumbs: FeatureShellBreadcrumbItem[];
  onBack: () => void;
}

export const MarketplaceEditorHeader: React.FC<MarketplaceEditorHeaderProps> = ({
  breadcrumbs,
  onBack,
}) => {
  const { t } = useI18n();

  return (
    <FeatureShellBreadcrumbBar
      items={breadcrumbs}
      title={t('marketplace.editor.editTitle')}
      icon={PenSquare}
      actions={(
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onBack}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.common.actions.back')}
          </Button>
        </div>
      )}
    />
  );
};
