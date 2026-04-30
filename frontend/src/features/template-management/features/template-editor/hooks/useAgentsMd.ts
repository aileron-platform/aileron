import { useState, useCallback, useEffect } from 'react';
import { getAgentsMd, updateAgentsMd, type AgentsMdResponse } from '@/features/template-management/api/templateApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useAgentsMd');

export interface UseAgentsMdOptions {
  templateId?: string;
  initialContent?: string;
  onSuccess?: () => void;
}

export interface UseAgentsMdReturn {
  content: string;
  persistedContent: string;
  hasUnsavedChanges: boolean;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  loadContent: () => Promise<void>;
  saveContent: (newContent: string) => Promise<void>;
  setContent: (content: string) => void;
}

export function useAgentsMd({ templateId, initialContent = '', onSuccess }: UseAgentsMdOptions): UseAgentsMdReturn {
  const [content, setContent] = useState(initialContent);
  const [persistedContent, setPersistedContent] = useState(initialContent);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const { t } = useI18n();

  // 載入 AGENTS.md 內容
  const loadContent = useCallback(async () => {
    if (!templateId) {
      setContent(initialContent);
      setPersistedContent(initialContent);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response: AgentsMdResponse = await getAgentsMd(templateId);

      if (response.success && response.data) {
        setContent(response.data.content);
        setPersistedContent(response.data.content);
      } else {
        const errorMsg = response.error || response.message || t('template.editor.agentsMd.errors.loadFailed');
        setError(errorMsg);
        toast({
          title: t('template.editor.agentsMd.toasts.loadFailed.title'),
          description: errorMsg,
          variant: 'destructive',
        });
      }
    } catch (err) {
      const errorMsg = t('template.editor.agentsMd.errors.loadFailed');
      setError(errorMsg);
      toast({
        title: t('template.editor.agentsMd.toasts.loadFailed.title'),
        description: errorMsg,
        variant: 'destructive',
      });
      logger.error('Failed to load content', { error: err });
    } finally {
      setIsLoading(false);
    }
  }, [templateId, toast, t]);

  // 保存 AGENTS.md 內容
  const saveContent = useCallback(async (newContent: string) => {
    if (!templateId) {
      setContent(newContent);
      setPersistedContent(newContent);
      setError(null);
      onSuccess?.();
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const response: AgentsMdResponse = await updateAgentsMd(templateId, {
        content: newContent,
      });

      if (response.success) {
        setContent(newContent);
        setPersistedContent(newContent);
        toast({
          title: t('template.editor.agentsMd.toasts.saveSuccess.title'),
          description: t('template.editor.agentsMd.toasts.saveSuccess.description'),
        });
        onSuccess?.(); // 保存成功後重新載入模板列表
      } else {
        const errorMsg = response.error || response.message || t('template.editor.agentsMd.errors.saveFailed');
        setError(errorMsg);
        toast({
          title: t('template.editor.agentsMd.toasts.saveFailed.title'),
          description: errorMsg,
          variant: 'destructive',
        });
      }
    } catch (err) {
      const errorMsg = t('template.editor.agentsMd.errors.saveFailed');
      setError(errorMsg);
      toast({
        title: t('template.editor.agentsMd.toasts.saveFailed.title'),
        description: errorMsg,
        variant: 'destructive',
      });
      logger.error('Failed to save content', { error: err });
    } finally {
      setIsSaving(false);
    }
  }, [templateId, toast, t, onSuccess]);

  // 當 templateId 變更時自動載入內容
  useEffect(() => {
    if (templateId) {
      loadContent();
    }
  }, [templateId, loadContent]);

  useEffect(() => {
    if (!templateId) {
      setContent(initialContent);
      setPersistedContent(initialContent);
      setError(null);
    }
  }, [initialContent, templateId]);

  return {
    content,
    persistedContent,
    hasUnsavedChanges: content !== persistedContent,
    isLoading,
    isSaving,
    error,
    loadContent,
    saveContent,
    setContent,
  };
}
