import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, CheckCircle2, CircleHelp, Compass, Play, Search, Wrench } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Textarea } from '@/shared/components/ui/textarea';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  OpenSpecActionAvailability,
  OpenSpecActionGroup,
  OpenSpecActionItem,
  OpenSpecNavigationChange,
  OpenSpecWorkspaceState,
} from './openSpecApi';

interface OpenSpecActionPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  actions: OpenSpecActionItem[];
  changes: OpenSpecNavigationChange[];
  focusedChangeName?: string | null;
  state: OpenSpecWorkspaceState | null;
  onSelect: (draft: string) => void;
}

type ActionFilter = 'all' | 'recommended' | 'enabled' | 'blocked' | 'setup';

const groupIcons: Record<OpenSpecActionGroup, React.ComponentType<{ className?: string }>> = {
  start: Compass,
  plan: BookOpen,
  implement: Play,
  finalize: CheckCircle2,
  learn: CircleHelp,
};

const groupOrder: OpenSpecActionGroup[] = ['start', 'plan', 'implement', 'finalize', 'learn'];

const availabilityTone: Record<OpenSpecActionAvailability, string> = {
  enabled: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  disabled: 'border-slate-200 bg-slate-100 text-slate-600',
  hidden: 'border-amber-200 bg-amber-50 text-amber-700',
  setup_required: 'border-amber-200 bg-amber-50 text-amber-700',
  sync_required: 'border-orange-200 bg-orange-50 text-orange-700',
  blocked: 'border-rose-200 bg-rose-50 text-rose-700',
};

const trimDraft = (value: string) => value.trim();

const buildActionStatusLabel = (
  availability: OpenSpecActionAvailability,
  t: (key: string) => string,
) => {
  switch (availability) {
    case 'enabled':
      return t('workspace.chat.dialogs.openspec.available');
    case 'setup_required':
      return t('workspace.chat.dialogs.openspec.setupRequired');
    case 'sync_required':
      return t('workspace.chat.dialogs.openspec.syncRequired');
    case 'blocked':
      return t('workspace.chat.dialogs.openspec.blocked');
    case 'hidden':
      return t('workspace.chat.dialogs.openspec.hidden');
    default:
      return t('workspace.chat.dialogs.openspec.unavailable');
  }
};

const getActionTargetOptions = (
  action: OpenSpecActionItem,
  changes: OpenSpecNavigationChange[],
  focusedChangeName?: string | null,
) => {
  if (action.id === 'archive') {
    return changes.filter((change) => change.status === 'complete');
  }
  if (action.id === 'bulk-archive') {
    return changes.filter((change) => change.status === 'complete');
  }
  if (action.inputKind === 'change') {
    const inProgress = changes.filter((change) => change.status === 'in-progress');
    if (inProgress.length > 0) {
      return inProgress;
    }
  }
  const focused = changes.find((change) => change.name === focusedChangeName);
  return focused ? [focused] : [];
};

const describeWhenToUseKey = (action: OpenSpecActionItem) => {
  switch (action.id) {
    case 'propose':
      return 'workspace.chat.dialogs.openspec.usage.propose';
    case 'explore':
      return 'workspace.chat.dialogs.openspec.usage.explore';
    case 'new':
      return 'workspace.chat.dialogs.openspec.usage.new';
    case 'continue':
      return 'workspace.chat.dialogs.openspec.usage.continue';
    case 'ff':
      return 'workspace.chat.dialogs.openspec.usage.ff';
    case 'apply':
      return 'workspace.chat.dialogs.openspec.usage.apply';
    case 'verify':
      return 'workspace.chat.dialogs.openspec.usage.verify';
    case 'sync':
      return 'workspace.chat.dialogs.openspec.usage.sync';
    case 'archive':
      return 'workspace.chat.dialogs.openspec.usage.archive';
    case 'bulk-archive':
      return 'workspace.chat.dialogs.openspec.usage.bulkArchive';
    case 'onboard':
      return 'workspace.chat.dialogs.openspec.usage.onboard';
    default:
      return null;
  }
};

export const OpenSpecActionPickerDialog: React.FC<OpenSpecActionPickerDialogProps> = ({
  open,
  onOpenChange,
  actions,
  changes,
  focusedChangeName,
  state,
  onSelect,
}) => {
  const { t } = useI18n();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<ActionFilter>('all');
  const [showHidden, setShowHidden] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [selectedChangeName, setSelectedChangeName] = useState('');
  const [structuredChangeName, setStructuredChangeName] = useState('');
  const [structuredDescription, setStructuredDescription] = useState('');
  const [schemaName, setSchemaName] = useState('spec-driven');
  const [selectedArchiveTargets, setSelectedArchiveTargets] = useState<string[]>([]);
  const [showExpandedGuide, setShowExpandedGuide] = useState(false);

  const hiddenExpandedCount = useMemo(
    () => actions.filter((action) => action.profile !== 'core' && action.availability === 'hidden').length,
    [actions],
  );
  const shouldShowExpandedLockedCard = hiddenExpandedCount > 0 && state?.profile === 'core';

  const visibleActions = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    return actions.filter((action) => {
      if (!showHidden && action.availability === 'hidden') {
        return false;
      }
      if (selectedFilter === 'recommended' && !action.recommended) {
        return false;
      }
      if (selectedFilter === 'enabled' && action.availability !== 'enabled') {
        return false;
      }
      if (selectedFilter === 'blocked' && !['blocked', 'disabled', 'hidden'].includes(action.availability)) {
        return false;
      }
      if (selectedFilter === 'setup' && !['setup_required', 'sync_required'].includes(action.availability)) {
        return false;
      }
      if (!normalized) {
        return true;
      }
      return `${action.title} ${action.description} ${action.reason ?? ''}`
        .toLowerCase()
        .includes(normalized);
    });
  }, [actions, searchTerm, selectedFilter, showHidden]);

  useEffect(() => {
    if (visibleActions.length === 0) {
      setSelectedActionId(null);
      return;
    }
    if (!selectedActionId || !visibleActions.some((action) => action.id === selectedActionId)) {
      setSelectedActionId(visibleActions[0].id);
    }
  }, [selectedActionId, visibleActions]);

  const selectedAction = useMemo(
    () => visibleActions.find((action) => action.id === selectedActionId) ?? null,
    [selectedActionId, visibleActions],
  );

  const targetOptions = useMemo(
    () => (selectedAction ? getActionTargetOptions(selectedAction, changes, focusedChangeName) : []),
    [changes, focusedChangeName, selectedAction],
  );

  useEffect(() => {
    if (!selectedAction) {
      setSelectedChangeName('');
      return;
    }
    if (selectedAction.inputKind === 'change') {
      const draftChange = selectedAction.draftTemplate.trim().split(/\s+/).slice(1).join(' ').trim();
      const nextTarget = (
        targetOptions.find((change) => change.name === focusedChangeName)
        ?? targetOptions.find((change) => change.name === draftChange)
        ?? targetOptions[0]
      );
      setSelectedChangeName(nextTarget?.name ?? '');
      return;
    }
    setSelectedChangeName('');
  }, [focusedChangeName, selectedAction, targetOptions]);

  useEffect(() => {
    if (!selectedAction) {
      return;
    }
    if (selectedAction.id === 'bulk-archive') {
      setSelectedArchiveTargets(targetOptions.map((change) => change.name));
      return;
    }
    setSelectedArchiveTargets([]);
  }, [selectedAction, targetOptions]);

  useEffect(() => {
    if (!selectedAction) {
      setStructuredChangeName('');
      setStructuredDescription('');
      setSchemaName('spec-driven');
      return;
    }
    if (selectedAction.id === 'new') {
      setStructuredChangeName('');
      setSchemaName('spec-driven');
      return;
    }
    if (selectedAction.id === 'propose') {
      setStructuredDescription('');
    }
  }, [selectedAction]);

  const groupedActions = useMemo(() => {
    return groupOrder
      .map((group) => ({
        group,
        items: visibleActions.filter((action) => action.group === group),
      }))
      .filter((entry) => entry.items.length > 0);
  }, [visibleActions]);

  const draftPreview = useMemo(() => {
    if (!selectedAction) {
      return '';
    }
    const command = selectedAction.draftTemplate.trim().split(/\s+/)[0];
    if (selectedAction.inputKind === 'change') {
      return selectedChangeName ? `${command} ${selectedChangeName}` : `${command} `;
    }
    if (selectedAction.id === 'new') {
      const parts = [command];
      if (trimDraft(structuredChangeName)) {
        parts.push(trimDraft(structuredChangeName));
      }
      if (trimDraft(schemaName)) {
        parts.push('--schema', trimDraft(schemaName));
      }
      return parts.join(' ').trim();
    }
    if (selectedAction.id === 'propose') {
      return [command, trimDraft(structuredDescription)].filter(Boolean).join(' ').trim();
    }
    if (selectedAction.id === 'bulk-archive' && selectedArchiveTargets.length > 0) {
      return [command, ...selectedArchiveTargets].join(' ').trim();
    }
    return trimDraft(selectedAction.draftTemplate);
  }, [
    schemaName,
    selectedAction,
    selectedArchiveTargets,
    selectedChangeName,
    structuredChangeName,
    structuredDescription,
  ]);

  const canInsertDraft = selectedAction?.availability === 'enabled' && trimDraft(draftPreview).length > 0;

  const handleInsertDraft = () => {
    if (!canInsertDraft) {
      return;
    }
    onSelect(trimDraft(draftPreview));
    onOpenChange(false);
  };

  const handleSelectAction = (action: OpenSpecActionItem) => {
    setSelectedActionId(action.id);
    if (action.availability === 'hidden' && action.profile !== 'core') {
      setShowExpandedGuide(true);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[82vh] flex-col sm:max-w-6xl">
          <DialogHeader className="space-y-1">
            <DialogTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-primary" />
              {t('workspace.chat.dialogs.openspec.title')}
            </DialogTitle>
            <DialogDescription>
              {t('workspace.chat.dialogs.openspec.description')}
            </DialogDescription>
            {state ? (
              <div className="flex flex-wrap items-center gap-2 pt-2 text-xs text-muted-foreground">
                <Badge variant="secondary">{t(`workspace.chat.dialogs.openspec.profile.${state.profile}`)}</Badge>
                <span>
                  {state.initialized
                    ? t('workspace.chat.dialogs.openspec.status.initialized')
                    : t('workspace.chat.dialogs.openspec.status.notInitialized')}
                </span>
                {state.projectSynced === false ? (
                  <Badge variant="outline" className="border-orange-200 bg-orange-50 text-orange-700">
                    {t('workspace.chat.dialogs.openspec.syncRequired')}
                  </Badge>
                ) : null}
                {state.cliVersion ? <span>{t('workspace.chat.dialogs.openspec.version', { version: state.cliVersion })}</span> : null}
              </div>
            ) : null}
          </DialogHeader>

          <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="flex min-h-0 flex-col gap-3">
              <div className="flex flex-col gap-3 rounded-md border border-border/60 bg-muted/20 p-3">
                <div className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <Input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder={t('workspace.chat.dialogs.openspec.searchPlaceholder')}
                    className="h-8 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {(['all', 'recommended', 'enabled', 'blocked', 'setup'] as ActionFilter[]).map((filter) => (
                    <Button
                      key={filter}
                      type="button"
                      variant={selectedFilter === filter ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => setSelectedFilter(filter)}
                    >
                      {t(`workspace.chat.dialogs.openspec.filters.${filter}`)}
                    </Button>
                  ))}
                  <Button
                    type="button"
                    variant={showHidden ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setShowHidden((value) => !value)}
                  >
                    {showHidden
                      ? t('workspace.chat.dialogs.openspec.hideHidden')
                      : t('workspace.chat.dialogs.openspec.showHidden')}
                  </Button>
                  {shouldShowExpandedLockedCard ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="ml-auto h-7 px-2 text-xs text-amber-800 hover:bg-amber-50 hover:text-amber-900"
                      onClick={() => setShowExpandedGuide(true)}
                    >
                      {t('workspace.chat.dialogs.openspec.expandedLocked.chip', { count: hiddenExpandedCount })}
                    </Button>
                  ) : null}
                </div>
              </div>

              <div className="min-h-0 flex-1">
                <ScrollArea className="h-full rounded-md border border-border/60 bg-muted/20">
                  <div className="flex flex-col gap-5 p-4">
                    {groupedActions.length === 0 ? (
                      <div className="py-12 text-center text-sm text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.empty')}
                      </div>
                    ) : (
                      groupedActions.map(({ group, items }) => {
                        const Icon = groupIcons[group];
                        return (
                          <section key={group} className="space-y-3">
                            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                              <Icon className="h-4 w-4 text-primary" />
                              <span>{t(`workspace.chat.dialogs.openspec.groups.${group}`)}</span>
                            </div>
                            <div className="grid gap-3">
                              {items.map((action) => {
                                const isSelected = selectedActionId === action.id;
                                const disabled = action.availability !== 'enabled';
                                return (
                                  <button
                                    key={action.id}
                                    type="button"
                                    onClick={() => handleSelectAction(action)}
                                    className={cn(
                                      'w-full rounded-xl border bg-card/80 p-4 text-left shadow-sm transition-all duration-200',
                                      isSelected
                                        ? 'border-primary/70 bg-primary/5'
                                        : 'border-border hover:border-primary/40 hover:bg-primary/5',
                                    )}
                                  >
                                    <div className="flex items-start justify-between gap-4">
                                      <div className="space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="font-mono text-sm text-primary">{action.draftTemplate.trim() || action.title}</span>
                                          <Badge variant="secondary" className="text-xs capitalize">
                                            {t(`workspace.chat.dialogs.openspec.profile.${action.profile}`)}
                                          </Badge>
                                          <Badge variant="outline" className={cn('text-xs', availabilityTone[action.availability])}>
                                            {buildActionStatusLabel(action.availability, t)}
                                          </Badge>
                                          {action.recommended ? (
                                            <Badge variant="outline" className="text-xs">
                                              {t('workspace.chat.dialogs.openspec.recommended')}
                                            </Badge>
                                          ) : null}
                                          {action.availability === 'hidden' ? (
                                            <Badge variant="outline" className="border-amber-200 bg-amber-50 text-xs text-amber-700">
                                              {t('workspace.chat.dialogs.openspec.hiddenByProfile')}
                                            </Badge>
                                          ) : null}
                                        </div>
                                        <p className="text-sm font-medium text-foreground">{action.title}</p>
                                        <p className="text-sm text-muted-foreground">{action.description}</p>
                                        {action.reason ? (
                                          <p className={cn('text-xs', disabled ? 'text-muted-foreground' : 'text-amber-700')}>
                                            {action.reason}
                                          </p>
                                        ) : null}
                                        {action.availability === 'hidden' && action.profile !== 'core' ? (
                                          <p className="text-xs font-medium text-amber-800">
                                            {t('workspace.chat.dialogs.openspec.expandedLocked.inlineCta')}
                                          </p>
                                        ) : null}
                                      </div>
                                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted-foreground">
                                        <Wrench className="h-4 w-4" />
                                      </span>
                                    </div>
                                  </button>
                                );
                              })}
                            </div>
                          </section>
                        );
                      })
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>

            <div className="flex min-h-0 flex-col rounded-md border border-border/60 bg-muted/20">
              <div className="border-b border-border/60 px-4 py-3">
                <h3 className="text-sm font-semibold">{t('workspace.chat.dialogs.openspec.detailTitle')}</h3>
              </div>
              {selectedAction ? (
                <ScrollArea className="min-h-0 flex-1">
                  <div className="space-y-4 p-4">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm text-primary">{selectedAction.draftTemplate.trim() || selectedAction.title}</span>
                        <Badge variant="secondary">{selectedAction.title}</Badge>
                        <Badge variant="outline" className={cn('text-xs', availabilityTone[selectedAction.availability])}>
                          {buildActionStatusLabel(selectedAction.availability, t)}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{selectedAction.description}</p>
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.whenToUse')}
                      </div>
                      <p className="text-sm text-foreground">
                        {describeWhenToUseKey(selectedAction)
                          ? t(describeWhenToUseKey(selectedAction)!)
                          : selectedAction.description}
                      </p>
                    </div>

                    {selectedAction.recommendedReason ? (
                      <div className="space-y-1">
                        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          {t('workspace.chat.dialogs.openspec.recommendationReason')}
                        </div>
                        <p className="text-sm text-foreground">{selectedAction.recommendedReason}</p>
                      </div>
                    ) : null}

                    <div className="space-y-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.availability')}
                      </div>
                      <p className="text-sm text-foreground">{selectedAction.reason ?? buildActionStatusLabel(selectedAction.availability, t)}</p>
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.syntax')}
                      </div>
                      <code className="block rounded-md bg-card px-3 py-2 text-xs">{selectedAction.draftTemplate.trim() || selectedAction.title}</code>
                    </div>

                    {selectedAction.exampleCommand ? (
                      <div className="space-y-1">
                        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          {t('workspace.chat.dialogs.openspec.example')}
                        </div>
                        <code className="block rounded-md bg-card px-3 py-2 text-xs">{selectedAction.exampleCommand}</code>
                      </div>
                    ) : null}

                    <div className="space-y-2">
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.parameters')}
                      </div>

                      {selectedAction.inputKind === 'none' ? (
                        <p className="text-sm text-muted-foreground">{t('workspace.chat.dialogs.openspec.noParameters')}</p>
                      ) : null}

                      {selectedAction.inputKind === 'change' ? (
                        targetOptions.length > 0 ? (
                          <Select value={selectedChangeName} onValueChange={setSelectedChangeName}>
                            <SelectTrigger>
                              <SelectValue placeholder={t('workspace.chat.dialogs.openspec.selectChange')} />
                            </SelectTrigger>
                            <SelectContent>
                              {targetOptions.map((change) => (
                                <SelectItem key={change.name} value={change.name}>
                                  {change.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <p className="text-sm text-muted-foreground">{t('workspace.chat.dialogs.openspec.noTargetChanges')}</p>
                        )
                      ) : null}

                      {selectedAction.id === 'new' ? (
                        <div className="space-y-2">
                          <Input
                            value={structuredChangeName}
                            onChange={(event) => setStructuredChangeName(event.target.value)}
                            placeholder={t('workspace.chat.dialogs.openspec.changeName')}
                          />
                          <Input
                            value={schemaName}
                            onChange={(event) => setSchemaName(event.target.value)}
                            placeholder={t('workspace.chat.dialogs.openspec.schemaLabel')}
                          />
                        </div>
                      ) : null}

                      {selectedAction.id === 'propose' ? (
                        <Textarea
                          value={structuredDescription}
                          onChange={(event) => setStructuredDescription(event.target.value)}
                          placeholder={t('workspace.chat.dialogs.openspec.descriptionInput')}
                          className="min-h-[96px]"
                        />
                      ) : null}

                      {selectedAction.id === 'bulk-archive' ? (
                        targetOptions.length > 0 ? (
                          <div className="space-y-2 rounded-md border border-border/60 bg-card p-3">
                            {targetOptions.map((change) => {
                              const checked = selectedArchiveTargets.includes(change.name);
                              return (
                                <label key={change.name} className="flex items-center gap-2 text-sm">
                                  <Checkbox
                                    checked={checked}
                                    onCheckedChange={(nextChecked) => {
                                      setSelectedArchiveTargets((prev) => {
                                        if (nextChecked) {
                                          return prev.includes(change.name) ? prev : [...prev, change.name];
                                        }
                                        return prev.filter((name) => name !== change.name);
                                      });
                                    }}
                                  />
                                  <span>{change.name}</span>
                                </label>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">{t('workspace.chat.dialogs.openspec.noTargetChanges')}</p>
                        )
                      ) : null}
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t('workspace.chat.dialogs.openspec.insertDraft')}
                      </div>
                      <code className="block rounded-md bg-card px-3 py-2 text-xs">{draftPreview || selectedAction.draftTemplate.trim()}</code>
                    </div>

                    {selectedAction.availability === 'hidden' && selectedAction.profile !== 'core' ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full"
                        onClick={() => setShowExpandedGuide(true)}
                      >
                        {t('workspace.chat.dialogs.openspec.expandedLocked.cta')}
                      </Button>
                    ) : null}

                    <Button
                      type="button"
                      className="w-full"
                      disabled={!canInsertDraft}
                      onClick={handleInsertDraft}
                    >
                      {t('workspace.chat.dialogs.openspec.insertDraft')}
                    </Button>
                  </div>
                </ScrollArea>
              ) : (
                <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted-foreground">
                  {t('workspace.chat.dialogs.openspec.detailPlaceholder')}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showExpandedGuide} onOpenChange={setShowExpandedGuide}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="space-y-2">
            <DialogTitle>{t('workspace.chat.dialogs.openspec.expandedGuide.title')}</DialogTitle>
            <DialogDescription>
              {t('workspace.chat.dialogs.openspec.expandedGuide.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 text-sm">
            <div className="rounded-md border border-border/60 bg-muted/20 p-3">
              <div className="font-medium text-foreground">
                {t('workspace.chat.dialogs.openspec.expandedGuide.currentStateTitle')}
              </div>
              <p className="mt-1 text-muted-foreground">
                {t('workspace.chat.dialogs.openspec.expandedGuide.currentStateDescription')}
              </p>
            </div>

            <div className="space-y-3">
              <div className="rounded-md border border-border/60 bg-card p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t('workspace.chat.dialogs.openspec.expandedGuide.stepOneLabel')}
                </div>
                <p className="mt-1 text-foreground">
                  {t('workspace.chat.dialogs.openspec.expandedGuide.stepOneDescription')}
                </p>
                <code className="mt-2 block rounded-md bg-muted px-3 py-2 text-xs">openspec config profile</code>
              </div>

              <div className="rounded-md border border-border/60 bg-card p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t('workspace.chat.dialogs.openspec.expandedGuide.stepTwoLabel')}
                </div>
                <p className="mt-1 text-foreground">
                  {t('workspace.chat.dialogs.openspec.expandedGuide.stepTwoDescription')}
                </p>
                <code className="mt-2 block rounded-md bg-muted px-3 py-2 text-xs">openspec update /workspace</code>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              {t('workspace.chat.dialogs.openspec.expandedGuide.note')}
            </p>

            <Button type="button" className="w-full" onClick={() => setShowExpandedGuide(false)}>
              {t('workspace.chat.dialogs.openspec.expandedGuide.close')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default OpenSpecActionPickerDialog;
