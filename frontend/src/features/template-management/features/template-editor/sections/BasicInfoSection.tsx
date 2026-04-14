import React from 'react';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import type { TemplateFormValues } from '../formTypes';
import { Plus } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface BasicInfoSectionProps {
  values: TemplateFormValues;
  onChange: (next: TemplateFormValues) => void;
  onAddKeyword: (keyword: string) => void;
  onRemoveKeyword: (keyword: string) => void;
  isEditMode?: boolean;
}

const BasicInfoSection: React.FC<BasicInfoSectionProps> = ({ values, onChange, onAddKeyword, onRemoveKeyword, isEditMode = false }) => {
  const { t } = useI18n();
  const [keywordInput, setKeywordInput] = React.useState('');
  const { categories } = useTemplateManagementContext();

  const handleFieldChange = <K extends keyof TemplateFormValues>(key: K, value: TemplateFormValues[K]) => {
    onChange({ ...values, [key]: value });
  };

  const handleAddKeyword = () => {
    const trimmed = keywordInput.trim();
    if (!trimmed) return;
    onAddKeyword(trimmed);
    setKeywordInput('');
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.templateId.label')}
          </label>
          <Input
            value={values.templateId}
            placeholder={t('template.editor.basicInfo.fields.templateId.placeholder')}
            onChange={event => handleFieldChange('templateId', event.target.value)}
            disabled={isEditMode} // 編輯模式下禁用
            className={isEditMode ? 'bg-muted cursor-not-allowed' : ''}
          />
          <p className="text-xs text-muted-foreground">
            {t('template.editor.basicInfo.fields.templateId.hint')}
          </p>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.name.label')}
          </label>
          <Input
            value={values.name}
            placeholder={t('template.editor.basicInfo.fields.name.placeholder')}
            onChange={event => handleFieldChange('name', event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.category.label')}
          </label>
          <Select
            value={values.categoryId || ''}
            onValueChange={(value) => handleFieldChange('categoryId', value || undefined)}
          >
            <SelectTrigger>
              <SelectValue placeholder={t('template.editor.basicInfo.fields.category.placeholder')} />
            </SelectTrigger>
            <SelectContent>
              {categories.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.author.name.label')}
          </label>
          <Input
            value={values.authorName}
            placeholder={t('template.editor.basicInfo.fields.author.name.placeholder')}
            onChange={event => handleFieldChange('authorName', event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.version.label')}
          </label>
          <Input
            value={values.version}
            placeholder={t('template.editor.basicInfo.fields.version.placeholder')}
            onChange={event => handleFieldChange('version', event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.author.email.label')}
          </label>
          <Input
            type="email"
            value={values.authorEmail}
            placeholder={t('template.editor.basicInfo.fields.author.email.placeholder')}
            onChange={event => handleFieldChange('authorEmail', event.target.value)}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <label className="text-sm font-semibold text-foreground">
            {t('template.editor.basicInfo.fields.author.url.label')}
          </label>
          <Input
            value={values.authorUrl}
            placeholder={t('template.editor.basicInfo.fields.author.url.placeholder')}
            onChange={event => handleFieldChange('authorUrl', event.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-semibold text-foreground">
          {t('template.editor.basicInfo.fields.description.label')}
        </label>
        <Textarea
          value={values.description}
          rows={4}
          placeholder={t('template.editor.basicInfo.fields.description.placeholder')}
          onChange={event => handleFieldChange('description', event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-semibold text-foreground">
          {t('template.editor.basicInfo.fields.initCommands.label')}
        </label>
        <Textarea
          value={values.initCommands}
          rows={6}
          placeholder={t('template.editor.basicInfo.fields.initCommands.placeholder')}
          onChange={event => handleFieldChange('initCommands', event.target.value)}
          className="font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">
          {t('template.editor.basicInfo.fields.initCommands.hint')}
        </p>
      </div>

      <div className="space-y-3">
        <label className="text-sm font-semibold text-foreground">
          {t('template.editor.basicInfo.fields.keywords.label')}
        </label>
        <div className="flex flex-wrap gap-2">
          {values.keywords.map(keyword => (
            <Badge key={keyword} variant="secondary" className="flex items-center gap-2">
              #{keyword}
              <button
                type="button"
                className="text-xs text-muted-foreground hover:text-destructive"
                onClick={() => onRemoveKeyword(keyword)}
              >
                {t('template.editor.basicInfo.fields.keywords.remove')}
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={keywordInput}
            placeholder={t('template.editor.basicInfo.fields.keywords.placeholder')}
            onChange={event => setKeywordInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.preventDefault();
                handleAddKeyword();
              }
            }}
          />
          <Button type="button" variant="outline" onClick={handleAddKeyword}>
            <Plus className="h-4 w-4 mr-2" />
            {t('template.editor.basicInfo.fields.keywords.add')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default BasicInfoSection;
