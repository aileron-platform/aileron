import React, { useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  FileCode2,
  FileCog,
  FileText,
  Folder,
  FolderOpen,
  GitFork,
  Plus,
  RefreshCw,
  ShieldCheck,
  Search,
  Wrench,
  X,
} from 'lucide-react';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useOpenSpecWorkspace } from '../OpenSpecWorkspaceContext';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useToast } from '@/shared/components/ui/use-toast';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { openSpecApi } from '../../../components/ChatPanel/openSpecApi';

const normalize = (value: string) => value.trim().toLowerCase();

const OpenSpecCustomizationSidebar: React.FC = () => {
  const { layout, toggleSecondColumn, workspaceRuntime, dispatch, state } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const {
    customization,
    isCustomizationLoading,
    refreshCustomization,
    openCustomizationValidationDialog,
    openCustomizationDebugDialog,
  } = useOpenSpecWorkspace();
  const isCollapsed = layout.secondColumnCollapsed;
  const [query, setQuery] = useState('');
  const [expandedSchemas, setExpandedSchemas] = useState<string[]>([]);
  const [forkOpen, setForkOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [forkSource, setForkSource] = useState('spec-driven');
  const [forkDestination, setForkDestination] = useState('');
  const [newSchemaName, setNewSchemaName] = useState('');
  const [newSchemaDescription, setNewSchemaDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!customization?.builtInSchemas?.length) {
      return;
    }
    if (!customization.builtInSchemas.includes(forkSource)) {
      setForkSource(customization.builtInSchemas[0]);
    }
  }, [customization?.builtInSchemas, forkSource]);

  useEffect(() => {
    if (!customization) {
      return;
    }
    setExpandedSchemas((previous) => {
      if (previous.length > 0) {
        return previous;
      }
      return customization.schemas.slice(0, 2).map((schema) => schema.name);
    });
  }, [customization]);

  useEffect(() => {
    if (!customization) {
      return;
    }
    const availablePaths = new Set<string>([
      customization.configPath,
      ...customization.schemas.flatMap((schema) => [
        schema.schemaPath,
        ...schema.templateFiles.map((file) => file.path),
      ]),
    ]);
    if (!availablePaths.has(state.openspec.selectedPath ?? '')) {
      dispatch({ type: 'SET_OPENSPEC_SELECTED_PATH', payload: customization.configPath });
    }
  }, [customization, dispatch, state.openspec.selectedPath]);

  const filteredSchemas = useMemo(() => {
    if (!customization) {
      return [];
    }
    const keyword = normalize(query);
    if (!keyword) {
      return customization.schemas;
    }
    return customization.schemas
      .map((schema) => {
        const matchesSchema = normalize(schema.name).includes(keyword);
        const templateFiles = schema.templateFiles.filter((file) => normalize(file.name).includes(keyword));
        if (matchesSchema) {
          return schema;
        }
        if (keyword === 'schema' || normalize('schema.yaml').includes(keyword)) {
          return schema;
        }
        if (templateFiles.length > 0) {
          return { ...schema, templateFiles };
        }
        return null;
      })
      .filter((schema): schema is NonNullable<typeof schema> => Boolean(schema));
  }, [customization, query]);

  const handleSelectPath = (path: string) => {
    dispatch({ type: 'SET_OPENSPEC_SELECTED_PATH', payload: path });
  };

  const handleToggleSchema = (schemaName: string) => {
    setExpandedSchemas((previous) => (
      previous.includes(schemaName)
        ? previous.filter((item) => item !== schemaName)
        : [...previous, schemaName]
    ));
  };

  const withMutation = async (callback: () => Promise<void>) => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) {
      return;
    }
    setIsSubmitting(true);
    try {
      await callback();
      await refreshCustomization();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForkSchema = async () => withMutation(async () => {
    const result = await openSpecApi.forkCustomizationSchema(
      workspaceRuntime.runtimeBaseUrl!,
      workspaceRuntime.workspaceId!,
      {
        sourceSchema: forkSource,
        destinationSchema: forkDestination.trim(),
      },
    );
    setForkDestination('');
    setForkOpen(false);
    if (result.path) {
      handleSelectPath(`${result.path}/schema.yaml`);
    }
    toast({ title: t('workspace.openspec.customization.messages.schemaForked'), description: result.message });
  });

  const handleCreateSchema = async () => withMutation(async () => {
    const result = await openSpecApi.initCustomizationSchema(
      workspaceRuntime.runtimeBaseUrl!,
      workspaceRuntime.workspaceId!,
      {
        name: newSchemaName.trim(),
        description: newSchemaDescription.trim() || undefined,
        artifacts: ['proposal', 'specs', 'design', 'tasks'],
      },
    );
    setNewSchemaName('');
    setNewSchemaDescription('');
    setCreateOpen(false);
    if (result.path) {
      handleSelectPath(`${result.path}/schema.yaml`);
    }
    toast({ title: t('workspace.openspec.customization.messages.schemaCreated'), description: result.message });
  });

  const selectedPath = state.openspec.selectedPath;

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div className={cn('flex h-10 items-center border-b border-border bg-card px-3', isCollapsed ? 'justify-center' : 'justify-between')}>
        {!isCollapsed ? (
          <div className="flex min-w-0 items-center gap-2">
            <Wrench className="h-4 w-4 text-primary" />
            <span className="truncate text-sm font-medium">{t('workspace.openspec.customization.title')}</span>
          </div>
        ) : null}
        <button
          onClick={toggleSecondColumn}
          className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
          aria-label={isCollapsed ? t('workspace.openspec.sidebar.expand') : t('workspace.openspec.sidebar.collapse')}
        >
          <ChevronLeft className={cn('h-3.5 w-3.5 transition-transform', isCollapsed && 'rotate-180')} />
        </button>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder
          icon={Wrench}
          className="text-primary"
          iconClassName="text-primary"
        />
      ) : (
        <>
          <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                placeholder={t('workspace.openspec.customization.searchPlaceholder')}
                onChange={event => setQuery(event.target.value)}
                className="h-7 pl-8 text-xs"
              />
              {query ? (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  onClick={() => setQuery('')}
                  className="absolute right-1.5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground hover:bg-muted/60"
                >
                  <X className="h-3 w-3" />
                </Button>
              ) : null}
            </div>
          </div>

          <div className="flex h-10 items-center border-b border-border bg-card px-3">
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setForkOpen(true)}
                aria-label={t('workspace.openspec.customization.actions.forkSchema')}
                title={t('workspace.openspec.customization.actions.forkSchema')}
                className="h-7 w-7 p-0"
              >
                <GitFork className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setCreateOpen(true)}
                aria-label={t('workspace.openspec.customization.actions.createSchema')}
                title={t('workspace.openspec.customization.actions.createSchema')}
                className="h-7 w-7 p-0"
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void openCustomizationValidationDialog()}
                disabled={!selectedPath}
                aria-label={t('workspace.openspec.customization.actions.validate')}
                title={t('workspace.openspec.customization.actions.validate')}
                className="h-7 w-7 p-0"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void openCustomizationDebugDialog()}
                disabled={!selectedPath}
                aria-label={t('workspace.openspec.customization.actions.debug')}
                title={t('workspace.openspec.customization.actions.debug')}
                className="h-7 w-7 p-0"
              >
                <FileCode2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void refreshCustomization()}
                disabled={isCustomizationLoading}
                aria-label={t('workspace.openspec.customization.actions.refresh')}
                title={t('workspace.openspec.customization.actions.refresh')}
                className="h-7 w-7 p-0"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', isCustomizationLoading && 'animate-spin')} />
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-1 p-2">
              <div className="mb-1 flex h-6 items-center gap-2 px-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                <FolderOpen className="h-3.5 w-3.5 text-yellow-500" />
                <span>openspec</span>
              </div>

              <button
                type="button"
                onClick={() => customization && handleSelectPath(customization.configPath)}
                className={cn(
                  'flex h-7 w-full items-center gap-2 rounded-md px-2 pl-6 text-left text-xs transition-colors',
                  selectedPath === customization?.configPath
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                )}
              >
                <FileCog className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1 truncate">config.yaml</span>
              </button>

              <div className="pt-1">
                <div className="mb-1 flex h-6 items-center gap-2 px-2 pl-6 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  <FolderOpen className="h-3.5 w-3.5 text-yellow-500" />
                  <span>schemas</span>
                </div>
                <div className="space-y-1">
                  {filteredSchemas.map((schema) => {
                    const isExpanded = expandedSchemas.includes(schema.name);
                    return (
                      <div key={schema.name}>
                        <button
                          type="button"
                          onClick={() => handleToggleSchema(schema.name)}
                          className={cn(
                            'flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-xs transition-colors',
                            (selectedPath === schema.schemaPath || schema.templateFiles.some((file) => file.path === selectedPath))
                              ? 'bg-accent text-accent-foreground'
                              : 'text-foreground/90 hover:bg-muted/40',
                          )}
                        >
                          <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform', !isExpanded && '-rotate-90')} />
                          {isExpanded ? (
                            <FolderOpen className="h-3.5 w-3.5 shrink-0 text-yellow-500" />
                          ) : (
                            <Folder className="h-3.5 w-3.5 shrink-0 text-yellow-500" />
                          )}
                          <span className="flex-1 truncate font-medium">{schema.name}</span>
                          <div className="flex items-center gap-1">
                            {schema.isDefault ? <Badge variant="secondary" className="h-4 px-1.5 text-[9px] font-medium">{t('workspace.openspec.customization.defaultBadge')}</Badge> : null}
                            {schema.isInvalid ? <Badge variant="destructive" className="h-4 px-1.5 text-[9px] font-medium">{t('workspace.openspec.customization.invalidBadge')}</Badge> : null}
                          </div>
                        </button>
                        {isExpanded ? (
                          <div className="space-y-1 pl-5 pt-1">
                            <button
                              type="button"
                              onClick={() => handleSelectPath(schema.schemaPath)}
                              className={cn(
                                'flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-xs transition-colors',
                                selectedPath === schema.schemaPath
                                  ? 'bg-accent text-accent-foreground'
                                  : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                              )}
                            >
                              <FileCode2 className="h-3.5 w-3.5 shrink-0" />
                              <span className="truncate">schema.yaml</span>
                            </button>
                            {schema.templateFiles.length > 0 ? (
                              <div className="flex h-6 items-center gap-2 px-2 pl-6 text-[11px] uppercase tracking-wide text-muted-foreground">
                                <FolderOpen className="h-3 w-3 shrink-0" />
                                <span>templates</span>
                              </div>
                            ) : null}
                            {schema.templateFiles.map((file) => (
                              <button
                                key={file.path}
                                type="button"
                                onClick={() => handleSelectPath(file.path)}
                                className={cn(
                                  'flex h-7 w-full items-center gap-2 rounded-md px-2 pl-10 text-left text-xs transition-colors',
                                  selectedPath === file.path
                                    ? 'bg-accent text-accent-foreground'
                                    : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                                )}
                              >
                                <FileText className="h-3.5 w-3.5 shrink-0" />
                                <span className="truncate">{file.name}</span>
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </ScrollArea>
        </>
      )}

      <Dialog open={forkOpen} onOpenChange={setForkOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitFork className="h-5 w-5 text-primary" />
              {t('workspace.openspec.customization.actions.forkSchema')}
            </DialogTitle>
            <DialogDescription>{t('workspace.openspec.customization.dialogs.forkDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="fork-source-schema">{t('workspace.openspec.customization.fields.sourceSchema')}</Label>
              <Select value={forkSource} onValueChange={setForkSource}>
                <SelectTrigger id="fork-source-schema">
                  <SelectValue placeholder={t('workspace.openspec.customization.fields.sourceSchema')} />
                </SelectTrigger>
                <SelectContent>
                  {(customization?.builtInSchemas ?? []).map((schemaName) => (
                    <SelectItem key={schemaName} value={schemaName}>
                      {schemaName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fork-destination-schema">{t('workspace.openspec.customization.fields.destinationSchema')}</Label>
              <Input id="fork-destination-schema" value={forkDestination} onChange={(event) => setForkDestination(event.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setForkOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={() => void handleForkSchema()} disabled={isSubmitting || !forkDestination.trim()}>
              {t('workspace.openspec.customization.actions.forkSchema')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-primary" />
              {t('workspace.openspec.customization.actions.createSchema')}
            </DialogTitle>
            <DialogDescription>{t('workspace.openspec.customization.dialogs.createDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-schema-name">{t('workspace.openspec.customization.fields.schemaName')}</Label>
              <Input id="new-schema-name" value={newSchemaName} onChange={(event) => setNewSchemaName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-schema-description">{t('workspace.openspec.customization.fields.schemaDescription')}</Label>
              <Input id="new-schema-description" value={newSchemaDescription} onChange={(event) => setNewSchemaDescription(event.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={() => void handleCreateSchema()} disabled={isSubmitting || !newSchemaName.trim()}>
              {t('workspace.openspec.customization.actions.createSchema')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default OpenSpecCustomizationSidebar;
