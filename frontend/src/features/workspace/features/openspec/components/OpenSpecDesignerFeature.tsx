import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, Expand, FileCog, GitFork, type LucideIcon, Minimize2, Plus, RefreshCw, Wrench } from 'lucide-react';
import Editor from '@monaco-editor/react';
import yaml from 'js-yaml';
import { useApp } from '@/app/providers/AppProvider';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Separator } from '@/shared/components/ui/separator';
import { Textarea } from '@/shared/components/ui/textarea';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useOpenSpecWorkspace } from '../OpenSpecWorkspaceContext';
import { getOpenSpecDesignerSection } from '../utils/designerRouting';
import { openSpecApi, type OpenSpecDesignerSchemaDetail, type OpenSpecDesignerSection, type OpenSpecDesignerValidationResult } from '../../../components/ChatPanel/openSpecApi';

const stringifyRules = (rules: Record<string, string[]>) =>
  Object.entries(rules)
    .map(([key, values]) => `${key}:\n${values.map((value) => `  - ${value}`).join('\n')}`)
    .join('\n');

const parseRules = (value: string): Record<string, string[]> => {
  if (!value.trim()) {
    return {};
  }

  try {
    const parsed = yaml.load(value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {};
    }

    return Object.entries(parsed as Record<string, unknown>).reduce<Record<string, string[]>>((acc, [key, rawValue]) => {
      if (Array.isArray(rawValue)) {
        acc[key] = rawValue
          .map((item) => String(item).trim())
          .filter(Boolean);
        return acc;
      }

      if (typeof rawValue === 'string') {
        const normalized = rawValue.trim();
        acc[key] = normalized ? [normalized] : [];
        return acc;
      }

      return acc;
    }, {});
  } catch {
    return {};
  }
};

const schemaSections = ['proposal', 'specs', 'design', 'tasks'];

const SectionShell: React.FC<{
  icon: LucideIcon;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}> = ({ icon: Icon, title, description, actions, children }) => (
  <div className="flex h-full flex-col overflow-hidden border-t border-border bg-background">
    <div className="border-b border-border bg-background px-6 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-muted/30 text-primary">
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-foreground">{title}</h2>
            {description ? (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </div>
    <div className="flex-1 overflow-auto">{children}</div>
  </div>
);

export const OpenSpecDesignerFeature: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { state: appState } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const { workspaceRuntime } = useWorkspace();
  const { designer, refresh } = useOpenSpecWorkspace();
  const currentSection = getOpenSpecDesignerSection(location.pathname);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const [configDefaultSchema, setConfigDefaultSchema] = useState('');
  const [configContext, setConfigContext] = useState('');
  const [configRules, setConfigRules] = useState('');
  const [schemaDetail, setSchemaDetail] = useState<OpenSpecDesignerSchemaDetail | null>(null);
  const [selectedSchemaName, setSelectedSchemaName] = useState<string>('');
  const [schemaEditorValue, setSchemaEditorValue] = useState('');
  const [validationResult, setValidationResult] = useState<OpenSpecDesignerValidationResult | null>(null);
  const [forkSource, setForkSource] = useState('spec-driven');
  const [forkDestination, setForkDestination] = useState('');
  const [initName, setInitName] = useState('');
  const [initDescription, setInitDescription] = useState('');
  const [testChangeName, setTestChangeName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isForkDialogOpen, setIsForkDialogOpen] = useState(false);
  const [isInitDialogOpen, setIsInitDialogOpen] = useState(false);

  useEffect(() => {
    setConfigDefaultSchema(designer?.projectConfig.defaultSchema ?? '');
    setConfigContext(designer?.projectConfig.context ?? '');
    setConfigRules(stringifyRules(designer?.projectConfig.rules ?? {}));
  }, [designer]);

  useEffect(() => {
    if (!selectedSchemaName) {
      setSelectedSchemaName(
        designer?.overview.defaultSchema
          ?? designer?.projectSchemas[0]?.name
          ?? designer?.builtInSchemas[0]
          ?? '',
      );
    }
  }, [designer, selectedSchemaName]);

  useEffect(() => {
    if (!runtimeBaseUrl || !workspaceId || !selectedSchemaName) {
      setSchemaDetail(null);
      setSchemaEditorValue('');
      return;
    }
    let cancelled = false;
    void openSpecApi.getSchemaDetail(runtimeBaseUrl, workspaceId, selectedSchemaName)
      .then((detail) => {
        if (cancelled) return;
        setSchemaDetail(detail);
        setSchemaEditorValue(detail.rawSchema);
      })
      .catch((error) => {
        if (cancelled) return;
        setSchemaDetail(null);
        setSchemaEditorValue('');
        toast({
          title: t('workspace.openspec.designer.errors.loadSchemaTitle'),
          description: error instanceof Error ? error.message : t('workspace.openspec.designer.errors.generic'),
          variant: 'destructive',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [runtimeBaseUrl, selectedSchemaName, t, toast, workspaceId]);

  const allSchemaOptions = useMemo(
    () => {
      const project = designer?.projectSchemas ?? [];
      const builtIns = (designer?.builtInSchemas ?? [])
        .filter((name) => !project.some((schema) => schema.name === name))
        .map((name) => ({
          name,
          source: 'package' as const,
          isDefault: name === designer?.overview.defaultSchema,
        }));
      return [
        ...project.map((schema) => ({ name: schema.name, source: schema.source, isDefault: schema.isDefault })),
        ...builtIns,
      ];
    },
    [designer],
  );
  const canUseSelectedSchema = useMemo(
    () => allSchemaOptions.some((schema) => schema.name === selectedSchemaName),
    [allSchemaOptions, selectedSchemaName],
  );
  const effectiveSelectedSchemaName = useMemo(
    () => (canUseSelectedSchema ? selectedSchemaName : (allSchemaOptions[0]?.name ?? '')),
    [allSchemaOptions, canUseSelectedSchema, selectedSchemaName],
  );
  const editorTheme = useMemo(
    () => (appState.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs'),
    [appState.ui.currentTheme],
  );

  const withSubmit = async (action: () => Promise<void>) => {
    if (!runtimeBaseUrl || !workspaceId) {
      return;
    }
    setIsSubmitting(true);
    try {
      await action();
      await refresh({ reloadActiveDocument: false });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveProjectConfig = async () => withSubmit(async () => {
    const result = await openSpecApi.updateProjectConfig(runtimeBaseUrl!, workspaceId!, {
      defaultSchema: configDefaultSchema.trim() || null,
      context: configContext,
      rules: parseRules(configRules),
    });
    toast({ title: t('workspace.openspec.designer.messages.configSaved'), description: result.message });
  });

  const handleForkSchema = async () => withSubmit(async () => {
    const result = await openSpecApi.forkSchema(runtimeBaseUrl!, workspaceId!, {
      sourceSchema: forkSource,
      destinationSchema: forkDestination.trim(),
    });
    setForkDestination('');
    setSelectedSchemaName(result.schemaName ?? forkSource);
    setIsForkDialogOpen(false);
    toast({ title: t('workspace.openspec.designer.messages.schemaForked'), description: result.message });
  });

  const handleInitSchema = async () => withSubmit(async () => {
    const result = await openSpecApi.initSchema(runtimeBaseUrl!, workspaceId!, {
      name: initName.trim(),
      description: initDescription.trim() || undefined,
      artifacts: schemaSections,
    });
    setInitName('');
    setInitDescription('');
    setSelectedSchemaName(result.schemaName ?? '');
    setIsInitDialogOpen(false);
    toast({ title: t('workspace.openspec.designer.messages.schemaCreated'), description: result.message });
  });

  const handleSaveSchema = async () => withSubmit(async () => {
    if (!selectedSchemaName) return;
    const result = await openSpecApi.updateSchema(runtimeBaseUrl!, workspaceId!, selectedSchemaName, {
      rawSchema: schemaEditorValue,
    });
    setSchemaDetail(result.schemaDetail ?? null);
    toast({ title: t('workspace.openspec.designer.messages.schemaSaved'), description: result.message });
  });

  const handleValidateSchema = async () => withSubmit(async () => {
    if (!selectedSchemaName) return;
    const result = await openSpecApi.validateSchema(runtimeBaseUrl!, workspaceId!, selectedSchemaName);
    setValidationResult(result.validation ?? null);
    toast({
      title: result.validation?.valid
        ? t('workspace.openspec.designer.messages.validationPassed')
        : t('workspace.openspec.designer.messages.validationFailed'),
      description: result.message,
      variant: result.validation?.valid ? 'default' : 'destructive',
    });
  });

  const handleSetDefault = async () => withSubmit(async () => {
    if (!selectedSchemaName) return;
    const result = await openSpecApi.setDefaultSchema(runtimeBaseUrl!, workspaceId!, selectedSchemaName);
    toast({ title: t('workspace.openspec.designer.messages.defaultSet'), description: result.message });
  });

  const handleCreateTestChange = async () => withSubmit(async () => {
    if (!selectedSchemaName) return;
    const result = await openSpecApi.createTestChange(runtimeBaseUrl!, workspaceId!, selectedSchemaName, testChangeName.trim());
    setTestChangeName('');
    toast({ title: t('workspace.openspec.designer.messages.testChangeCreated'), description: result.message });
  });

  const sectionCards = (
    <div className="mx-auto grid w-full max-w-5xl gap-4 md:grid-cols-2 xl:grid-cols-3">
      {[
        { id: 'project-config' as OpenSpecDesignerSection, icon: FileCog, label: t('workspace.openspec.designer.sections.projectConfig'), description: t('workspace.openspec.designer.sectionDescriptions.projectConfig') },
        { id: 'schemas' as OpenSpecDesignerSection, icon: Wrench, label: t('workspace.openspec.designer.sections.schemas'), description: t('workspace.openspec.designer.sectionDescriptions.schemas') },
        { id: 'validation' as OpenSpecDesignerSection, icon: CheckCircle2, label: t('workspace.openspec.designer.sections.validation'), description: t('workspace.openspec.designer.sectionDescriptions.validation') },
      ].map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => navigate(`/workspaces/openspec/designer/${item.id}`)}
            className="flex min-h-40 w-full min-w-0 flex-col items-start rounded-md border border-border bg-background p-4 text-left transition-colors hover:bg-muted/50"
          >
            <Icon className="mb-3 h-5 w-5 text-primary" />
            <p className="w-full break-words text-sm font-semibold leading-5">{item.label}</p>
            <p className="mt-1 w-full break-words text-sm leading-6 text-muted-foreground">{item.description}</p>
          </button>
        );
      })}
    </div>
  );

  return (
    <div
      data-testid="openspec-designer-feature"
      className={cn(
        'flex h-full flex-col overflow-hidden bg-background',
        isExpanded && 'fixed inset-0 z-50',
      )}
    >
      <FeatureHeader
        title={t('workspace.openspec.designer.title')}
        icon={FileCog}
        info={<p className="truncate text-xs text-muted-foreground">{t('workspace.openspec.designer.subtitle')}</p>}
        actions={(
          <>
            <button
              type="button"
              className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
              onClick={() => setIsExpanded((value) => !value)}
              title={isExpanded ? t('workspace.openspec.designer.actions.restoreLayout') : t('workspace.openspec.designer.actions.expandLayout')}
              aria-label={isExpanded ? t('workspace.openspec.designer.actions.restoreLayout') : t('workspace.openspec.designer.actions.expandLayout')}
            >
              {isExpanded ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Expand className="h-3.5 w-3.5" />
              )}
            </button>
            <button
              type="button"
              className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
              onClick={() => void refresh({ reloadActiveDocument: false })}
              title={t('workspace.openspec.sidebar.refresh')}
              aria-label={t('workspace.openspec.sidebar.refresh')}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      />

      <ScrollArea className="flex-1">
        <div className="h-full">
          {currentSection === 'overview' ? (
            <SectionShell
              icon={FileCog}
              title={t('workspace.openspec.designer.overviewTitle')}
              description={t('workspace.openspec.designer.overviewDescription')}
            >
              <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6">
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">{t('workspace.openspec.designer.metrics.defaultSchema')}</p>
                      <p className="mt-1 text-sm font-medium">{designer?.overview.defaultSchema ?? t('workspace.openspec.designer.noDefaultSchema')}</p>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">{t('workspace.openspec.designer.metrics.projectConfig')}</p>
                      <p className="mt-1 text-sm font-medium">{designer?.overview.configPresent ? t('workspace.openspec.designer.present') : t('workspace.openspec.designer.missing')}</p>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">{t('workspace.openspec.designer.metrics.projectSchemas')}</p>
                      <p className="mt-1 text-sm font-medium">{designer?.overview.projectSchemaCount ?? 0}</p>
                    </div>
                  </div>
                </div>
                {sectionCards}
              </div>
            </SectionShell>
          ) : null}

          {currentSection === 'project-config' ? (
            <SectionShell
              icon={FileCog}
              title={t('workspace.openspec.designer.sections.projectConfig')}
              description={t('workspace.openspec.designer.projectConfigDescription')}
            >
              <div className="space-y-4 p-6">
                <div className="space-y-2">
                  <Label htmlFor="designer-default-schema">{t('workspace.openspec.designer.fields.defaultSchema')}</Label>
                  <Input id="designer-default-schema" value={configDefaultSchema} onChange={(event) => setConfigDefaultSchema(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="designer-context">{t('workspace.openspec.designer.fields.context')}</Label>
                  <Textarea id="designer-context" rows={8} value={configContext} onChange={(event) => setConfigContext(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="designer-rules">{t('workspace.openspec.designer.fields.rules')}</Label>
                  <Textarea id="designer-rules" rows={10} value={configRules} onChange={(event) => setConfigRules(event.target.value)} />
                </div>
                <Button onClick={() => void handleSaveProjectConfig()} disabled={isSubmitting}>
                  {t('workspace.openspec.designer.actions.saveProjectConfig')}
                </Button>
              </div>
            </SectionShell>
          ) : null}

          {currentSection === 'schemas' ? (
            <>
              <SectionShell
                icon={Wrench}
                title={t('workspace.openspec.designer.sections.schemas')}
                description={t('workspace.openspec.designer.schemasDescription')}
              >
                <div className="space-y-4 p-6">
                  <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/20 p-4 lg:flex-row lg:items-end lg:justify-between">
                    <div className="flex min-w-0 flex-1 flex-col gap-2 sm:max-w-sm">
                      <Label htmlFor="schema-detail-selector">{t('workspace.openspec.designer.fields.schemaName')}</Label>
                      <Select
                        value={effectiveSelectedSchemaName}
                        onValueChange={setSelectedSchemaName}
                      >
                        <SelectTrigger id="schema-detail-selector" className="bg-background">
                          <SelectValue placeholder={t('workspace.openspec.designer.selectSchema')} />
                        </SelectTrigger>
                        <SelectContent>
                          {allSchemaOptions.map((schema) => (
                            <SelectItem key={schema.name} value={schema.name}>
                              {schema.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => setIsForkDialogOpen(true)}>
                        {t('workspace.openspec.designer.actions.forkSchema')}
                      </Button>
                      <Button size="sm" onClick={() => setIsInitDialogOpen(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        {t('workspace.openspec.designer.actions.initSchema')}
                      </Button>
                    </div>
                  </div>
                  {schemaDetail ? (
                    <>
                      <div className="rounded-xl border border-border/70 bg-muted/20 px-3 py-2">
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
                          <div className="flex items-center gap-2">
                            <span>{t('workspace.openspec.designer.fields.sourceSchema')}:</span>
                            <span className="font-medium text-foreground">{schemaDetail.source}</span>
                            {schemaDetail.isDefault ? <Badge variant="secondary" className="text-[10px]">{t('workspace.openspec.designer.defaultLabel')}</Badge> : null}
                          </div>
                          <div className="flex items-center gap-2">
                            <span>{t('workspace.openspec.designer.fields.applyTracks')}:</span>
                            <span className="font-medium text-foreground">{schemaDetail.apply.tracks ?? '-'}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span>{t('workspace.openspec.designer.schemaEditabilityLabel')}:</span>
                            <span className="font-medium text-foreground">
                              {schemaDetail.source === 'project'
                                ? t('workspace.openspec.designer.schemaEditable')
                                : t('workspace.openspec.designer.schemaReadOnly')}
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 truncate text-xs text-muted-foreground">
                          <span className="mr-2">{t('workspace.openspec.designer.schemaPathLabel')}:</span>
                          <span className="font-medium text-foreground">{schemaDetail.path}</span>
                        </div>
                      </div>
                      <div className="overflow-hidden rounded-xl border border-border">
                        <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-2">
                          <div className="text-xs font-medium text-muted-foreground">schema.yaml</div>
                          <div className="text-xs text-muted-foreground">{t('workspace.openspec.designer.yamlEditorHint')}</div>
                        </div>
                        <div className="h-[620px]" data-testid="schema-yaml-editor">
                          <Editor
                            height="100%"
                            language="yaml"
                            value={schemaEditorValue}
                            theme={editorTheme}
                            onChange={(value) => setSchemaEditorValue(value ?? '')}
                            options={{
                              readOnly: schemaDetail.source !== 'project',
                              minimap: { enabled: false },
                              fontSize: 13,
                              wordWrap: 'on',
                              automaticLayout: true,
                              scrollBeyondLastLine: false,
                              fontFamily: 'var(--font-mono)',
                              lineNumbers: 'on',
                              tabSize: 2,
                              padding: { top: 12, bottom: 12 },
                            }}
                          />
                        </div>
                      </div>
                      <Button onClick={() => void handleSaveSchema()} disabled={isSubmitting || schemaDetail.source !== 'project'}>
                        {t('workspace.openspec.designer.actions.saveSchema')}
                      </Button>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">{t('workspace.openspec.designer.selectSchema')}</p>
                  )}
                </div>
              </SectionShell>

              <Dialog open={isForkDialogOpen} onOpenChange={setIsForkDialogOpen}>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <GitFork className="h-5 w-5 text-primary" />
                      {t('workspace.openspec.designer.actions.forkSchema')}
                    </DialogTitle>
                    <DialogDescription>{t('workspace.openspec.designer.schemasDescription')}</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="fork-source">{t('workspace.openspec.designer.fields.sourceSchema')}</Label>
                      <Select value={forkSource} onValueChange={setForkSource}>
                        <SelectTrigger id="fork-source">
                          <SelectValue placeholder={t('workspace.openspec.designer.selectSchema')} />
                        </SelectTrigger>
                        <SelectContent>
                          {allSchemaOptions.map((schema) => (
                            <SelectItem key={schema.name} value={schema.name}>
                              {schema.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="fork-destination">{t('workspace.openspec.designer.fields.destinationSchema')}</Label>
                      <Input id="fork-destination" value={forkDestination} onChange={(event) => setForkDestination(event.target.value)} />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsForkDialogOpen(false)} disabled={isSubmitting}>
                      {t('common.cancel')}
                    </Button>
                    <Button onClick={() => void handleForkSchema()} disabled={isSubmitting || !forkDestination.trim()}>
                      {t('workspace.openspec.designer.actions.forkSchema')}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <Dialog open={isInitDialogOpen} onOpenChange={setIsInitDialogOpen}>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <Plus className="h-5 w-5 text-primary" />
                      {t('workspace.openspec.designer.actions.initSchema')}
                    </DialogTitle>
                    <DialogDescription>{t('workspace.openspec.designer.schemasDescription')}</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="init-name">{t('workspace.openspec.designer.fields.schemaName')}</Label>
                      <Input id="init-name" value={initName} onChange={(event) => setInitName(event.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="init-description">{t('workspace.openspec.designer.fields.schemaDescription')}</Label>
                      <Textarea id="init-description" rows={4} value={initDescription} onChange={(event) => setInitDescription(event.target.value)} />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsInitDialogOpen(false)} disabled={isSubmitting}>
                      Cancel
                    </Button>
                    <Button onClick={() => void handleInitSchema()} disabled={isSubmitting || !initName.trim()}>
                      {t('workspace.openspec.designer.actions.initSchema')}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          ) : null}

          {currentSection === 'validation' ? (
            <SectionShell
              icon={CheckCircle2}
              title={t('workspace.openspec.designer.sections.validation')}
              description={t('workspace.openspec.designer.validationDescription')}
            >
              <div className="space-y-4 p-6">
                <div className="space-y-2">
                  <Label htmlFor="validation-schema">{t('workspace.openspec.designer.fields.schemaName')}</Label>
                  <Select
                    value={effectiveSelectedSchemaName}
                    onValueChange={setSelectedSchemaName}
                  >
                    <SelectTrigger id="validation-schema">
                      <SelectValue placeholder={t('workspace.openspec.designer.selectSchema')} />
                    </SelectTrigger>
                    <SelectContent>
                      {allSchemaOptions.map((schema) => (
                        <SelectItem key={schema.name} value={schema.name}>
                          {schema.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void handleValidateSchema()} disabled={isSubmitting || !canUseSelectedSchema}>
                    {t('workspace.openspec.designer.actions.validate')}
                  </Button>
                  <Button variant="outline" onClick={() => void handleSetDefault()} disabled={isSubmitting || !canUseSelectedSchema}>
                    {t('workspace.openspec.designer.actions.setDefault')}
                  </Button>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label htmlFor="test-change-name">{t('workspace.openspec.designer.fields.testChangeName')}</Label>
                  <Input id="test-change-name" value={testChangeName} onChange={(event) => setTestChangeName(event.target.value)} />
                  <Button variant="outline" onClick={() => void handleCreateTestChange()} disabled={isSubmitting || !canUseSelectedSchema || !testChangeName.trim()}>
                    {t('workspace.openspec.designer.actions.createTestChange')}
                  </Button>
                </div>
                {validationResult ? (
                  <>
                    <Separator />
                    <div className="space-y-3">
                      <div className="border border-border bg-muted/30 p-3 text-sm">
                        <p className="font-medium">{validationResult.valid ? t('workspace.openspec.designer.validationPass') : t('workspace.openspec.designer.validationFail')}</p>
                        <p className="mt-1 text-muted-foreground">
                          {t('workspace.openspec.designer.validationResolution', {
                            source: validationResult.resolutionSource,
                            path: validationResult.resolutionPath ?? '-',
                          })}
                        </p>
                      </div>
                      <div className="space-y-2">
                        {validationResult.diagnostics.map((diagnostic, index) => (
                          <div key={`${diagnostic.level}-${index}`} className="border border-border px-3 py-2 text-sm">
                            <span className="font-medium uppercase">{diagnostic.level}</span>
                            <p className="mt-1 text-muted-foreground">{diagnostic.message}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            </SectionShell>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  );
};

export default OpenSpecDesignerFeature;
