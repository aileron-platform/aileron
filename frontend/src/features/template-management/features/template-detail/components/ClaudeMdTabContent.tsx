import React, { useState } from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { BookOpen, Edit3, Download, Copy } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import MarkdownEditor from '@/shared/components/composite/MarkdownEditor';
import { useClaudeMd } from '../../template-editor/hooks/useClaudeMd';

interface ClaudeMdTabContentProps {
  templateId?: string;
  claudeMd?: string | null;
  onEdit?: () => void;
}

export const ClaudeMdTabContent: React.FC<ClaudeMdTabContentProps> = ({
  templateId,
  claudeMd: initialClaudeMd,
  onEdit
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);

  const {
    content,
    isLoading,
    isSaving,
    error,
    saveContent,
    setContent,
  } = useClaudeMd({
    templateId,
    initialContent: initialClaudeMd || ''
  });

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: t('template.detail.claudeMd.actions.copySuccess.title'),
        description: t('template.detail.claudeMd.actions.copySuccess.description'),
      });
    } catch (error) {
      toast({
        title: t('template.detail.claudeMd.actions.copyFailed.title'),
        description: t('template.detail.claudeMd.actions.copyFailed.description'),
        variant: 'destructive',
      });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Claude.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: t('template.detail.claudeMd.actions.downloadSuccess.title'),
      description: t('template.detail.claudeMd.actions.downloadSuccess.description'),
    });
  };

  const handleSave = async () => {
    await saveContent(content);
    setIsEditing(false);
  };

  const handleEdit = () => {
    setIsEditing(true);
    onEdit?.();
  };

  const Header: React.FC<{
    status: 'configured' | 'missing';
    isEditing: boolean;
    onSave?: () => void;
    onCancel?: () => void;
    onEdit?: () => void;
  }> = ({ status, isEditing, onSave, onCancel, onEdit }) => (
    <div className="flex items-center justify-between p-4 border-b border-border bg-background flex-shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-foreground">{t('template.detail.claudeMd.header.title')}</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('template.detail.claudeMd.header.description')}
        </p>
        {(isLoading || isSaving) && (
          <div className="flex items-center gap-2 text-sm">
            {isLoading && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                {t('template.detail.claudeMd.status.loading')}
              </div>
            )}
            {isSaving && (
              <div className="flex items-center gap-1 text-blue-600">
                <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                {t('template.detail.claudeMd.status.saving')}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs">
          {t(
            status === 'configured'
              ? 'template.detail.claudeMd.status.configured'
              : 'template.detail.claudeMd.status.missing',
          )}
        </Badge>

        {isEditing ? (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={onCancel}
              disabled={isSaving}
            >
              {t('common.cancel')}
            </Button>
            <Button
              size="sm"
              onClick={onSave}
              disabled={isSaving}
            >
              {isSaving ? t('common.saving') : t('common.save')}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              disabled={isLoading}
            >
              <Copy className="h-3 w-3 mr-1" />
              {t('template.detail.claudeMd.actions.copy')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={isLoading}
            >
              <Download className="h-3 w-3 mr-1" />
              {t('template.detail.claudeMd.actions.download')}
            </Button>
            {templateId && (
              <Button
                variant="outline"
                size="sm"
                onClick={onEdit}
                disabled={isLoading}
              >
                <Edit3 className="h-3 w-3 mr-1" />
                {t('template.detail.claudeMd.actions.edit')}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );

  if (!content && !isLoading) {
    return (
      <div className="h-full flex flex-col">
        <Header
          status="missing"
          isEditing={isEditing}
          onSave={handleSave}
          onCancel={() => setIsEditing(false)}
          onEdit={handleEdit}
        />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
              <BookOpen className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-2">
              {t('template.detail.claudeMd.empty.title')}
            </h3>
            <p className="text-muted-foreground">
              {t('template.detail.claudeMd.empty.description')}
            </p>
            {templateId && (
              <Button
                variant="outline"
                className="mt-4"
                onClick={handleEdit}
                disabled={isLoading}
              >
                <Edit3 className="h-4 w-4 mr-2" />
                {t('template.detail.claudeMd.actions.create')}
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (isEditing) {
    return (
      <div className="h-full flex flex-col">
        <Header
          status="configured"
          isEditing={isEditing}
          onSave={handleSave}
          onCancel={() => setIsEditing(false)}
        />
        <div className="flex-1 overflow-auto p-4">
          <div className="h-full">
            <MarkdownEditor
              value={content}
              onChange={setContent}
              placeholder={t('template.editor.claudeMd.editor.placeholder')}
              className="h-full"
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <Header
        status="configured"
        isEditing={isEditing}
        onSave={handleSave}
        onCancel={() => setIsEditing(false)}
        onEdit={handleEdit}
      />

      <div className="flex-1 overflow-auto p-4">
        <div className="bg-muted/50 rounded-lg p-4">
          <pre className="text-sm leading-relaxed whitespace-pre-wrap overflow-x-auto">{content}</pre>
        </div>
      </div>
    </div>
  );
};

export default ClaudeMdTabContent;

