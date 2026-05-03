import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot } from 'lucide-react';
import type { DocumentWorkflowDialogProps } from '@/shared/components/document-workflow';
import { formatDocumentContentSize } from '@/shared/components/document-workflow';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { CodexSubagentDefinition } from '../../services/agentSettingsApi';
import type { AgentDocument, AgentScope } from '../../types';

type EditMode = 'structured' | 'raw';
type ModelReasoningEffort = 'high' | 'medium' | 'low';
type SandboxMode = 'read-only' | 'workspace-write' | 'danger-full-access';

const MODEL_REASONING_EFFORT_OPTIONS: ModelReasoningEffort[] = ['high', 'medium', 'low'];
const SANDBOX_MODE_OPTIONS: SandboxMode[] = ['read-only', 'workspace-write', 'danger-full-access'];

interface CodexSubagentFormState {
  layer: Extract<AgentScope, 'project' | 'user'>;
  editMode: EditMode;
  name: string;
  description: string;
  developerInstructions: string;
  nicknameCandidates: string;
  model: string;
  modelReasoningEffort: string;
  sandboxMode: string;
  rawContent: string;
}

const definitionFromDocument = (document?: AgentDocument | null): CodexSubagentDefinition | null => {
  const value = document?.metadata?.definition;
  if (!value || typeof value !== 'object') return null;
  return value as CodexSubagentDefinition;
};

const buildInitialState = (document?: AgentDocument | null): CodexSubagentFormState => {
  const definition = definitionFromDocument(document);
  return {
    layer: document?.scope === 'user' ? 'user' : 'project',
    editMode: 'structured',
    name: definition?.name ?? '',
    description: definition?.description ?? '',
    developerInstructions: definition?.developer_instructions ?? '',
    nicknameCandidates: definition?.nickname_candidates?.join('\n') ?? '',
    model: definition?.model ?? '',
    modelReasoningEffort: definition?.model_reasoning_effort ?? 'medium',
    sandboxMode: definition?.sandbox_mode ?? 'workspace-write',
    rawContent: document?.content ?? '',
  };
};

const parseNicknameCandidates = (value: string): string[] | undefined => {
  const candidates = value
    .split(/\r?\n|,/)
    .map((candidate) => candidate.trim())
    .filter(Boolean);
  return candidates.length > 0 ? candidates : undefined;
};

export const CodexSubagentDialog: React.FC<DocumentWorkflowDialogProps<AgentDocument>> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [formState, setFormState] = useState<CodexSubagentFormState>(() => buildInitialState(initialValue));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const isEdit = mode === 'edit';

  useEffect(() => {
    if (!open) return;
    setFormState(buildInitialState(initialValue));
    setErrors({});
    setSubmitting(false);
  }, [initialValue, open]);

  const key = useCallback((suffix: string) => `workspace.agentSettings.codex.subagents.dialog.${suffix}`, []);

  const scopeOptions = useMemo(
    () => [
      { value: 'project' as const, label: t('workspace.agentSettings.codex.documents.scope.values.project') },
      { value: 'user' as const, label: t('workspace.agentSettings.codex.documents.scope.values.user') },
    ],
    [t],
  );

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (formState.editMode === 'raw') {
      if (!formState.rawContent.trim()) {
        nextErrors.rawContent = t(key('validation.rawContent'));
      }
    } else {
      if (!formState.name.trim()) nextErrors.name = t(key('validation.name'));
      if (!formState.description.trim()) nextErrors.description = t(key('validation.description'));
      if (!formState.developerInstructions.trim()) {
        nextErrors.developerInstructions = t(key('validation.developerInstructions'));
      }
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      const definition: CodexSubagentDefinition | undefined = formState.editMode === 'structured'
        ? {
            name: formState.name.trim(),
            description: formState.description.trim(),
            developer_instructions: formState.developerInstructions.trim(),
            nickname_candidates: parseNicknameCandidates(formState.nicknameCandidates),
            model: formState.model.trim() || undefined,
            model_reasoning_effort: formState.modelReasoningEffort.trim() || undefined,
            sandbox_mode: formState.sandboxMode.trim() || undefined,
          }
        : undefined;
      await onSubmit({
        id: initialValue?.id ?? `${formState.layer}:${formState.name || 'new'}`,
        title: definition?.name ?? initialValue?.title ?? t(key('fallbackTitle')),
        description: definition?.description,
        scope: formState.layer,
        content: formState.editMode === 'raw' ? formState.rawContent : initialValue?.content ?? '',
        size: formatDocumentContentSize(formState.editMode === 'raw' ? formState.rawContent : definition?.developer_instructions ?? ''),
        metadata: {
          ...initialValue?.metadata,
          source: formState.layer,
          relativePath: initialValue?.metadata?.relativePath,
          fileName: initialValue?.metadata?.relativePath,
          definition,
          rawMode: formState.editMode === 'raw',
        },
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-3xl flex-col p-0">
        <form className="flex min-h-0 flex-1 flex-col" onSubmit={handleSubmit}>
          <DialogHeader className="flex-shrink-0 border-b border-border px-6 py-5 pr-12">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              <DialogTitle>{t(key(isEdit ? 'title.edit' : 'title.create'))}</DialogTitle>
            </div>
            <DialogDescription>{t(key(isEdit ? 'description.edit' : 'description.create'))}</DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
            <div className="grid gap-2">
              <Label htmlFor="codex-subagent-layer">{t(key('fields.scope.label'))}</Label>
              <Select
                value={formState.layer}
                onValueChange={(value) => setFormState((previous) => ({ ...previous, layer: value as 'project' | 'user' }))}
              >
                <SelectTrigger id="codex-subagent-layer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Tabs
              value={formState.editMode}
              onValueChange={(value) => setFormState((previous) => ({ ...previous, editMode: value as EditMode }))}
            >
              <TabsList>
                <TabsTrigger value="structured">{t(key('tabs.structured'))}</TabsTrigger>
                <TabsTrigger value="raw">{t(key('tabs.raw'))}</TabsTrigger>
              </TabsList>

            <TabsContent value="structured" className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="codex-subagent-name">{t(key('fields.name.label'))}</Label>
                <Input
                  id="codex-subagent-name"
                  value={formState.name}
                  placeholder={t(key('fields.name.placeholder'))}
                  onChange={(event) => setFormState((previous) => ({ ...previous, name: event.target.value }))}
                />
                {errors.name ? <p className="text-xs text-destructive">{errors.name}</p> : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="codex-subagent-description">{t(key('fields.description.label'))}</Label>
                <Input
                  id="codex-subagent-description"
                  value={formState.description}
                  placeholder={t(key('fields.description.placeholder'))}
                  onChange={(event) => setFormState((previous) => ({ ...previous, description: event.target.value }))}
                />
                {errors.description ? <p className="text-xs text-destructive">{errors.description}</p> : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="codex-subagent-instructions">{t(key('fields.developerInstructions.label'))}</Label>
                <Textarea
                  id="codex-subagent-instructions"
                  className="min-h-40 font-mono"
                  value={formState.developerInstructions}
                  placeholder={t(key('fields.developerInstructions.placeholder'))}
                  onChange={(event) => setFormState((previous) => ({ ...previous, developerInstructions: event.target.value }))}
                />
                {errors.developerInstructions ? (
                  <p className="text-xs text-destructive">{errors.developerInstructions}</p>
                ) : null}
              </div>
              <div className="grid gap-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label htmlFor="codex-subagent-model">{t(key('fields.model.label'))}</Label>
                    <Input
                      id="codex-subagent-model"
                      value={formState.model}
                      placeholder={t(key('fields.model.placeholder'))}
                      onChange={(event) => setFormState((previous) => ({ ...previous, model: event.target.value }))}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="codex-subagent-reasoning">{t(key('fields.modelReasoningEffort.label'))}</Label>
                    <Select
                      value={formState.modelReasoningEffort}
                      onValueChange={(value) => setFormState((previous) => ({ ...previous, modelReasoningEffort: value }))}
                    >
                      <SelectTrigger id="codex-subagent-reasoning">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {MODEL_REASONING_EFFORT_OPTIONS.map((option) => (
                          <SelectItem key={option} value={option}>
                            <div className="flex flex-col items-start">
                              <span>{t(key(`fields.modelReasoningEffort.options.${option}.label`))}</span>
                              <span className="text-xs text-muted-foreground">
                                {t(key(`fields.modelReasoningEffort.options.${option}.description`))}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="codex-subagent-sandbox">{t(key('fields.sandboxMode.label'))}</Label>
                    <Select
                      value={formState.sandboxMode}
                      onValueChange={(value) => setFormState((previous) => ({ ...previous, sandboxMode: value }))}
                    >
                      <SelectTrigger id="codex-subagent-sandbox">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SANDBOX_MODE_OPTIONS.map((option) => (
                          <SelectItem key={option} value={option}>
                            <div className="flex flex-col items-start">
                              <span>{t(key(`fields.sandboxMode.options.${option}.label`))}</span>
                              <span className="text-xs text-muted-foreground">
                                {t(key(`fields.sandboxMode.options.${option}.description`))}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="codex-subagent-nicknames">{t(key('fields.nicknameCandidates.label'))}</Label>
                  <Textarea
                    id="codex-subagent-nicknames"
                    className="min-h-24"
                    value={formState.nicknameCandidates}
                    placeholder={t(key('fields.nicknameCandidates.placeholder'))}
                    onChange={(event) => setFormState((previous) => ({ ...previous, nicknameCandidates: event.target.value }))}
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="raw" className="space-y-2">
              <Label htmlFor="codex-subagent-raw">{t(key('fields.rawContent.label'))}</Label>
              <Textarea
                id="codex-subagent-raw"
                className="min-h-80 font-mono"
                value={formState.rawContent}
                placeholder={t(key('fields.rawContent.placeholder'))}
                onChange={(event) => setFormState((previous) => ({ ...previous, rawContent: event.target.value }))}
              />
              {errors.rawContent ? <p className="text-xs text-destructive">{errors.rawContent}</p> : null}
            </TabsContent>
            </Tabs>
          </div>

          <DialogFooter className="flex-shrink-0 border-t border-border px-6 py-4">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              {t(key('actions.cancel'))}
            </Button>
            <Button type="submit" disabled={submitting}>
              {t(key(isEdit ? 'actions.save' : 'actions.create'))}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default CodexSubagentDialog;
