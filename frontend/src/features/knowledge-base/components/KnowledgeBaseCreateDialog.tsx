import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React from 'react';
import { BookOpen, Briefcase, FileText, Heart, Loader2, Microscope, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { useToast } from '@/shared/components/ui/use-toast';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import type { KnowledgeBaseTemplateMetadata } from '@/shared/types/knowledgeBase';
import { listKnowledgeBaseTemplates } from '../api/knowledgeBaseApi';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

export interface KnowledgeBaseCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const slugify = (value: string): string => value
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/^-+|-+$/g, '');

const ICON_MAP: Record<string, React.FC<{ className?: string }>> = {
  FileText: ({ className }) => <FileText className={className} />,
  Microscope: ({ className }) => <Microscope className={className} />,
  BookOpen: ({ className }) => <BookOpen className={className} />,
  Heart: ({ className }) => <Heart className={className} />,
  Briefcase: ({ className }) => <Briefcase className={className} />,
};

type Step = 'template' | 'metadata';

export const KnowledgeBaseCreateDialog: React.FC<KnowledgeBaseCreateDialogProps> = ({
  open,
  onOpenChange,
}) => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useI18n();
  const { createKnowledgeBase, isMutating } = useKnowledgeBase();

  const [step, setStep] = React.useState<Step>('template');
  const [selectedTemplateId, setSelectedTemplateId] = React.useState('general');
  const [templates, setTemplates] = React.useState<KnowledgeBaseTemplateMetadata[]>([]);
  const [name, setName] = React.useState('');
  const [slug, setSlug] = React.useState('');
  const [description, setDescription] = React.useState('');

  React.useEffect(() => {
    if (!open) {
      setStep('template');
      setSelectedTemplateId('general');
      setName('');
      setSlug('');
      setDescription('');
    }
  }, [open]);

  React.useEffect(() => {
    if (open && templates.length === 0) {
      listKnowledgeBaseTemplates().then(setTemplates).catch(() => {});
    }
  }, [open, templates.length]);

  const canSubmit = name.trim().length > 0 && slug.trim().length > 0 && !isMutating;

  const handleNameChange = (value: string) => {
    setName(value);
    setSlug((current) => (current ? current : slugify(value)));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    try {
      const created = await createKnowledgeBase({
        name: name.trim(),
        slug: slugify(slug),
        description: description.trim() || undefined,
        templateId: selectedTemplateId,
      });
      toast({
        variant: 'success',
        title: t('knowledgeBase.create.successTitle'),
        description: t('knowledgeBase.create.successDescription', { name: created.name }),
      });
      onOpenChange(false);
      navigate(ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(created.id));
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('knowledgeBase.create.failedTitle'),
        description: error instanceof Error ? error.message : t('knowledgeBase.create.failedDescription'),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        {step === 'template' ? (
          <div className="space-y-4">
            <DialogHeader>
              <DialogHeading icon={Sparkles}>
                {t('knowledgeBase.create.template.title')}
              </DialogHeading>
              <DialogDescription>{t('knowledgeBase.create.template.subtitle')}</DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {templates.map((tmpl) => {
                const IconComponent = ICON_MAP[tmpl.icon] ?? ICON_MAP.FileText;
                const isSelected = selectedTemplateId === tmpl.id;
                return (
                  <button
                    key={tmpl.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(tmpl.id)}
                    className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                      isSelected
                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                        : 'border-border hover:border-primary/50 hover:bg-accent/30'
                    }`}
                  >
                    <IconComponent className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{t(tmpl.nameKey)}</div>
                      <div className="text-xs text-muted-foreground">{t(tmpl.descriptionKey)}</div>
                    </div>
                  </button>
                );
              })}
            </div>

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                {t('knowledgeBase.common.actions.cancel')}
              </Button>
              <Button type="button" onClick={() => setStep('metadata')}>
                {t('knowledgeBase.create.template.next')}
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogHeading icon={Sparkles}>
                {t('knowledgeBase.create.dialogTitle')}
              </DialogHeading>
              <DialogDescription>{t('knowledgeBase.create.dialogDescription')}</DialogDescription>
            </DialogHeader>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="kb-create-name">
                {t('knowledgeBase.create.nameLabel')}
              </label>
              <Input
                id="kb-create-name"
                value={name}
                onChange={(event) => handleNameChange(event.target.value)}
                placeholder={t('knowledgeBase.create.namePlaceholder')}
                disabled={isMutating}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="kb-create-slug">
                {t('knowledgeBase.create.slugLabel')}
              </label>
              <Input
                id="kb-create-slug"
                value={slug}
                onChange={(event) => setSlug(slugify(event.target.value))}
                placeholder={t('knowledgeBase.create.slugPlaceholder')}
                disabled={isMutating}
              />
              <p className="text-xs text-muted-foreground">
                {t('knowledgeBase.create.slugHint')}
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="kb-create-description">
                {t('knowledgeBase.create.descriptionLabel')}
              </label>
              <Textarea
                id="kb-create-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={t('knowledgeBase.create.descriptionPlaceholder')}
                disabled={isMutating}
                rows={4}
              />
            </div>

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setStep('template')} disabled={isMutating}>
                {t('knowledgeBase.create.template.back')}
              </Button>
              <Button type="submit" disabled={!canSubmit}>
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t('knowledgeBase.common.actions.create')}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};
