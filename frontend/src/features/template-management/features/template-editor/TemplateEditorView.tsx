import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PenSquare, ArrowLeft, Save } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { useTemplateManagementContext } from '../../providers/TemplateManagementProvider';
import {
  createEmptyFormValues,
  mapTemplateToFormValues,
} from './formTypes';
import TemplateForm from './TemplateForm';
import { useTemplateEditorForm } from './hooks/useTemplateEditorForm';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTemplateApi } from './hooks/useTemplateApi';


interface TemplateEditorViewProps {
  mode: 'create' | 'edit';
}

export const TemplateEditorView: React.FC<TemplateEditorViewProps> = ({ mode }) => {
  const navigate = useNavigate();
  const { templateId } = useParams<{ templateId: string }>();
  const { t } = useI18n();
  const {
    templates,
    categories,
    isLoading,
    reloadFromSource,
  } = useTemplateManagementContext();

  const { values, setValues } = useTemplateEditorForm({ initial: createEmptyFormValues(categories) });
  const lastTemplateKeyRef = useRef<string | null>(null);
  const [activeTab, setActiveTab] = useState('basic');

  const { isSaving, saveCanonicalTemplate } = useTemplateApi({
    templateId,
    onSuccess: reloadFromSource
  });

  const template = useMemo(
    () => (mode === 'edit' ? templates.find(item => item.id === templateId) : null),
    [mode, templates, templateId],
  );

  const templateKey = template ? `${template.id}-${template.updatedAt ?? ''}-${template.version}` : null;

  useEffect(() => {
    if (mode !== 'edit') return;
    if (!template || !templateKey) return;
    if (lastTemplateKeyRef.current === templateKey) return;
    lastTemplateKeyRef.current = templateKey;
    setValues(mapTemplateToFormValues(template));
  }, [mode, template, templateKey, setValues]);

  useEffect(() => {
    if (mode !== 'create') return;
    if (categories.length === 0) return;
    if (lastTemplateKeyRef.current === 'create') return;
    lastTemplateKeyRef.current = 'create';
    setValues(createEmptyFormValues(categories));
  }, [mode, categories, setValues]);

  const handleAddKeyword = useCallback((keyword: string) => {
    setValues(prev => (prev.keywords.includes(keyword) ? prev : { ...prev, keywords: [...prev.keywords, keyword] }));
  }, [setValues]);

  const handleRemoveKeyword = useCallback((keyword: string) => {
    setValues(prev => ({ ...prev, keywords: prev.keywords.filter(item => item !== keyword) }));
  }, [setValues]);

  const handleSave = useCallback(async () => {
    await saveCanonicalTemplate(values);
  }, [values, saveCanonicalTemplate]);

  const notReady = (mode === 'edit' && !template) || (mode === 'create' && categories.length === 0);
  if (isLoading || notReady) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {t('template.editor.loading')}
      </div>
    );
  }


  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={
          mode === 'create'
            ? t('template.editor.header.create')
            : t('template.editor.header.edit', { name: template?.name ?? '' })
        }
        icon={PenSquare}
        actions={
          <div className="flex items-center gap-2">
            <Button onClick={handleSave} disabled={isSaving} size="sm" className="h-7 px-2 text-xs">
              <Save className="mr-1.5 h-3.5 w-3.5" />
              {isSaving ? t('template.editor.toolbar.saving') : t('template.editor.toolbar.save')}
            </Button>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate('../..')}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> {t('template.editor.toolbar.back')}
            </Button>
          </div>
        }
      />

      <div className="h-[calc(100%-3rem)] overflow-auto">
        <TemplateForm
          values={values}
          onChange={setValues}
          onAddKeyword={handleAddKeyword}
          onRemoveKeyword={handleRemoveKeyword}
          templateId={templateId}
          onReloadTemplate={reloadFromSource}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          isEditMode={mode === 'edit'}
        />
      </div>
    </div>
  );
};

export default TemplateEditorView;
