import React from 'react';
import { Database, Loader2, Save, Settings, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
} from '@/shared/components/ui/alert-dialog';
import { AlertDialogHeading } from '@/shared/components/ui/dialog-heading';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatKnowledgeBaseFileSize } from '../model/formatKnowledgeBaseFileSize';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

interface KnowledgeBaseSettingsTabProps {
  knowledgeBaseId: string;
  canManage: boolean;
  canManageVisibility: boolean;
  canDelete: boolean;
}

export const KnowledgeBaseSettingsTab: React.FC<KnowledgeBaseSettingsTabProps> = ({
  knowledgeBaseId,
  canManage,
  canManageVisibility,
  canDelete,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const navigate = useNavigate();
  const {
    detailById,
    isMutating,
    updateKnowledgeBase,
    updateKnowledgeBaseVisibility,
    deleteKnowledgeBase,
  } = useKnowledgeBase();
  const detail = detailById[knowledgeBaseId];

  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [validationKey, setValidationKey] = React.useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [deleteConfirmationName, setDeleteConfirmationName] = React.useState('');

  React.useEffect(() => {
    if (!detail) {
      return;
    }
    setName(detail.name);
    setDescription(detail.description ?? '');
    setValidationKey(null);
  }, [detail]);

  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const disabled = !canManage || isMutating;

  const handleSave = async () => {
    if (!canManage) {
      return;
    }
    setValidationKey(null);

    const nextName = name.trim();
    if (!nextName) {
      setValidationKey('knowledgeBase.detail.settings.validation.nameRequired');
      return;
    }

    try {
      const updated = await updateKnowledgeBase(knowledgeBaseId, {
        name: nextName,
        description: description.trim(),
      });
      toast({
        variant: 'success',
        title: t('knowledgeBase.detail.settings.toasts.saveSuccess.title'),
        description: updated.name,
      });
    } catch {
      toast({
        variant: 'destructive',
        title: t('knowledgeBase.detail.settings.toasts.saveFailed.title'),
        description: t('knowledgeBase.detail.settings.toasts.saveFailed.description'),
      });
    }
  };

  const handleDelete = async () => {
    if (!canDelete) {
      return;
    }
    try {
      await deleteKnowledgeBase(knowledgeBaseId, deleteConfirmationName);
      toast({
        variant: 'success',
        title: t('knowledgeBase.detail.delete.toasts.success.title'),
        description: detail.name,
      });
      navigate(ROUTES.knowledgeBase.root);
    } catch {
      toast({
        variant: 'destructive',
        title: t('knowledgeBase.detail.delete.toasts.failed.title'),
        description: t('knowledgeBase.detail.delete.toasts.failed.description'),
      });
    }
  };

  const handleVisibilityChange = async (visibility: 'private' | 'public') => {
    if (!canManageVisibility || visibility === detail.visibility) {
      return;
    }
    try {
      await updateKnowledgeBaseVisibility(knowledgeBaseId, { visibility });
      toast({
        variant: 'success',
        title: t('knowledgeBase.detail.settings.visibility.toasts.success'),
      });
    } catch {
      toast({
        variant: 'destructive',
        title: t('knowledgeBase.detail.settings.visibility.toasts.failed'),
      });
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <FeatureHeader
        title={t('knowledgeBase.navigation.settings')}
        icon={Settings}
        actions={(
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={disabled}
            onClick={() => { void handleSave(); }}
          >
            {isMutating
              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              : <Save className="mr-1.5 h-3.5 w-3.5" />}
            {t('knowledgeBase.common.actions.save')}
          </Button>
        )}
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="space-y-6 bg-background p-6">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {t('knowledgeBase.detail.settings.description')}
        </p>

        <form
          className="space-y-6"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="kb-settings-name">{t('knowledgeBase.detail.settings.nameLabel')}</Label>
            <Input
              id="kb-settings-name"
              value={name}
              disabled={disabled}
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-slug">{t('knowledgeBase.detail.settings.slugLabel')}</Label>
            <Input id="kb-settings-slug" value={detail.slug} disabled readOnly />
            <p className="text-xs text-muted-foreground">
              {t('knowledgeBase.detail.settings.slugHint')}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-description">{t('knowledgeBase.detail.settings.descriptionLabel')}</Label>
            <Textarea
              id="kb-settings-description"
              value={description}
              disabled={disabled}
              rows={4}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-visibility">
              {t('knowledgeBase.detail.settings.visibility.label')}
            </Label>
            <Select
              value={detail.visibility}
              disabled={!canManageVisibility || isMutating}
              onValueChange={(value: 'private' | 'public') => {
                void handleVisibilityChange(value);
              }}
            >
              <SelectTrigger id="kb-settings-visibility">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">
                  {t('knowledgeBase.detail.settings.visibility.options.private')}
                </SelectItem>
                <SelectItem value="public">
                  {t('knowledgeBase.detail.settings.visibility.options.public')}
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t('knowledgeBase.detail.settings.visibility.description')}
            </p>
          </div>

          {validationKey ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {t(validationKey)}
            </div>
          ) : null}
        </form>

        <section className="space-y-4 rounded-lg border border-border bg-card p-4 shadow-sm">
          <div className="flex items-start gap-3">
            <Database className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-foreground">
                {t('knowledgeBase.detail.settings.capacity.title')}
              </h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t('knowledgeBase.detail.settings.capacity.description')}
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">
                {t('knowledgeBase.detail.settings.capacity.currentUsage')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {formatKnowledgeBaseFileSize(detail.currentSizeBytes)}
              </p>
            </div>
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">
                {t('knowledgeBase.detail.settings.capacity.effectiveQuota')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {formatKnowledgeBaseFileSize(detail.effectiveQuotaBytes)}
              </p>
            </div>
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">
                {t('knowledgeBase.detail.settings.capacity.utilization')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {detail.utilizationPercent == null
                  ? t('knowledgeBase.detail.settings.capacity.notAvailable')
                  : `${detail.utilizationPercent.toFixed(1)}%`}
              </p>
            </div>
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">
                {t('knowledgeBase.detail.settings.capacity.quotaSource')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {t(`knowledgeBase.detail.settings.capacity.quotaSources.${detail.quotaSource}`)}
              </p>
            </div>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs font-medium text-muted-foreground">
              {t('knowledgeBase.detail.settings.capacity.ownerPressure')}
            </p>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
              <span className="font-semibold text-foreground">
                {formatKnowledgeBaseFileSize(detail.ownerQuotaUsedBytes)}
              </span>
              <span className="text-muted-foreground">/</span>
              <span className="font-semibold text-foreground">
                {formatKnowledgeBaseFileSize(detail.ownerEffectiveQuotaBytes)}
              </span>
            </div>
          </div>
        </section>

        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <Trash2 className="h-4 w-4 text-red-600" />
                <h4 className="text-sm font-semibold text-foreground">
                  {t('knowledgeBase.detail.settings.dangerZone.title')}
                </h4>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t('knowledgeBase.detail.settings.dangerZone.description')}
              </p>
            </div>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="h-8 px-3 text-xs"
              disabled={!canDelete || disabled}
              onClick={() => {
                setDeleteConfirmationName('');
                setDeleteConfirmOpen(true);
              }}
            >
              {t('knowledgeBase.detail.deleteAction')}
            </Button>
          </div>
        </div>
      </div>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogHeading icon={Trash2} tone="destructive">
              {t('knowledgeBase.detail.delete.title')}
            </AlertDialogHeading>
            <AlertDialogDescription>
              {t('knowledgeBase.detail.delete.description', { name: detail.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2">
            <Label htmlFor="kb-delete-confirmation-name">
              {t('knowledgeBase.detail.delete.confirmationLabel', { name: detail.name })}
            </Label>
            <Input
              id="kb-delete-confirmation-name"
              value={deleteConfirmationName}
              disabled={isMutating}
              onChange={(event) => setDeleteConfirmationName(event.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMutating}>
              {t('knowledgeBase.detail.delete.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={disabled || deleteConfirmationName !== detail.name}
              onClick={(event) => {
                event.preventDefault();
                void handleDelete();
              }}
            >
              {isMutating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {t('knowledgeBase.detail.delete.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </div>
  );
};
