import React from 'react';
import { ArrowLeft, PenSquare, Save } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplacePackageHeaderProps {
  mode: 'create' | 'edit';
  isDirty: boolean;
  saveStatus: 'idle' | 'success' | 'error' | 'conflict';
  onDiscard: () => void;
  onSave: () => void | Promise<unknown>;
  onBack: () => void;
}

export const MarketplacePackageHeader: React.FC<MarketplacePackageHeaderProps> = ({
  mode,
  isDirty,
  saveStatus,
  onDiscard,
  onSave,
  onBack,
}) => {
  const { t } = useI18n();

  return (
    <FeatureHeader
      title={mode === 'create' ? t('marketplace.editor.createTitle') : t('marketplace.editor.editTitle')}
      icon={PenSquare}
      info={(
        <div className="flex items-center gap-2 text-xs">
          {isDirty ? <span className="text-amber-600">{t('marketplace.editor.dirty')}</span> : null}
          {saveStatus === 'success' ? <span className="text-emerald-600">{t('marketplace.editor.saveStatus.success')}</span> : null}
          {saveStatus === 'error' ? <span className="text-destructive">{t('marketplace.editor.saveStatus.validationError')}</span> : null}
          {saveStatus === 'conflict' ? <span className="text-destructive">{t('marketplace.editor.saveStatus.revisionConflict')}</span> : null}
        </div>
      )}
      actions={(
        <div className="flex items-center gap-2">
          {isDirty ? (
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onDiscard}>
              {t('marketplace.editor.actions.discard')}
            </Button>
          ) : null}
          <Button size="sm" className="h-7 px-2 text-xs" onClick={() => { void onSave(); }}>
            <Save className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.actions.save')}
          </Button>
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onBack}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.common.actions.back')}
          </Button>
        </div>
      )}
    />
  );
};
