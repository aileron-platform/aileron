import React from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, Edit, MoreHorizontal, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { CodeTextEditor } from '@/shared/components/file-workbench/viewer-entry';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/shared/types/marketplace';
import { cn } from '@/shared/utils/cn';

import { MarketplaceSectionSidebarShell } from '../../components/MarketplaceSectionSidebarShell';
import { downloadBlob } from '../../utils/downloadBlob';
import {
  getMarketplaceItemFileName,
  marketplaceEditorItemDescription,
  type MarketplaceEditorResourceItem,
  type MarketplaceMarkdownEditorTab,
  type MarketplaceResourceFormat,
} from './marketplaceEditorResourceItems';

export interface MarketplaceAgentsMdEditorProps {
  provider: MarketplaceProvider;
  onDirty: () => void;
  onContentChange: (path: string, content: string) => void;
}

export const MarketplaceAgentsMdEditor: React.FC<MarketplaceAgentsMdEditorProps> = ({ provider, onDirty, onContentChange }) => {
  const { t } = useI18n();
  const fileName = provider === 'gemini' ? 'GEMINI.md' : 'AGENTS.md';
  const [content, setContent] = React.useState('');
  const [savedContent, setSavedContent] = React.useState('');
  const hasUnsavedChanges = content !== savedContent;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    downloadBlob(blob, fileName);
  };

  return (
    <MarkdownDocumentShell
      title={t('marketplace.editor.agentsMd.title')}
      refreshLabel={t('marketplace.common.actions.refresh')}
      saveLabel={t('marketplace.common.actions.save')}
      runtimeLoadingLabel={t('marketplace.editor.agentsMd.status.loading')}
      loadingLabel={t('marketplace.editor.agentsMd.status.loading')}
      isRuntimeReady
      isLoading={false}
      isSaving={false}
      value={content}
      onChange={(value) => {
        setContent(value);
        onContentChange(fileName, value);
        onDirty();
      }}
      onRefresh={() => setContent(savedContent)}
      onSave={() => setSavedContent(content)}
      saveDisabled={!hasUnsavedChanges}
      statusMessage={(
        <span className="font-mono text-xs text-muted-foreground">
          {fileName}
        </span>
      )}
      placeholder={t('marketplace.editor.agentsMd.placeholder')}
      headerExtras={(
        <>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => void handleCopy()}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.agentsMd.actions.copy')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleDownload}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.agentsMd.actions.download')}
          </Button>
        </>
      )}
    />
  );
};

export interface MarketplaceMarkdownEditorViewerProps {
  tab: MarketplaceMarkdownEditorTab;
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  format?: MarketplaceResourceFormat;
  commitVersion: number;
  discardVersion: number;
  onDirty: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

export const MarketplaceMarkdownEditorViewer: React.FC<MarketplaceMarkdownEditorViewerProps> = ({
  tab,
  icon: Icon,
  items,
  format = 'markdown',
  commitVersion,
  discardVersion,
  onDirty,
  onItemsChange,
}) => {
  const { t } = useI18n();
  const [baseItems, setBaseItems] = React.useState(items);
  const [localItems, setLocalItems] = React.useState(items);
  const [selectedId, setSelectedId] = React.useState(items[0]?.id ?? null);
  const [search, setSearch] = React.useState('');
  const [renameItem, setRenameItem] = React.useState<MarketplaceEditorResourceItem | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [drafts, setDrafts] = React.useState<Record<string, string>>(
    () => Object.fromEntries(items.map(item => [item.id, item.content])),
  );
  const didMountRef = React.useRef(false);

  const materializeItems = React.useCallback((
    nextItems: MarketplaceEditorResourceItem[],
    nextDrafts: Record<string, string>,
  ): MarketplaceEditorResourceItem[] => (
    nextItems.map(item => ({
      ...item,
      content: nextDrafts[item.id] ?? item.content,
    }))
  ), []);

  const emitItemsChange = React.useCallback((
    nextItems: MarketplaceEditorResourceItem[],
    nextDrafts: Record<string, string>,
  ) => {
    onItemsChange?.(materializeItems(nextItems, nextDrafts));
  }, [materializeItems, onItemsChange]);

  React.useEffect(() => {
    setBaseItems(items);
    setLocalItems(items);
    setDrafts(Object.fromEntries(items.map(item => [item.id, item.content])));
    setSelectedId(items[0]?.id ?? null);
  }, [items]);

  React.useEffect(() => {
    if (!didMountRef.current) return;
    setBaseItems(localItems.map(item => ({
      ...item,
      content: drafts[item.id] ?? item.content,
    })));
    setLocalItems(prev => prev.map(item => ({
      ...item,
      content: drafts[item.id] ?? item.content,
    })));
  }, [commitVersion]);

  React.useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    setLocalItems(baseItems);
    setDrafts(Object.fromEntries(baseItems.map(item => [item.id, item.content])));
    setSelectedId(prev => (prev && baseItems.some(item => item.id === prev) ? prev : baseItems[0]?.id ?? null));
  }, [discardVersion]);

  const dirtyItemIds = React.useMemo(() => {
    const baseById = new Map(baseItems.map(item => [item.id, item]));
    return new Set(localItems.filter(item => {
      const baseItem = baseById.get(item.id);
      if (!baseItem) return true;
      return baseItem.path !== item.path || baseItem.content !== (drafts[item.id] ?? item.content);
    }).map(item => item.id));
  }, [baseItems, drafts, localItems]);

  const filteredItems = React.useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return localItems;
    return localItems.filter(item => (
      getMarketplaceItemFileName(item).toLowerCase().includes(query) ||
      marketplaceEditorItemDescription(item, t).toLowerCase().includes(query) ||
      (drafts[item.id] ?? item.content).toLowerCase().includes(query)
    ));
  }, [drafts, localItems, search, t]);

  React.useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredItems.some(item => item.id === selectedId)) {
      setSelectedId(filteredItems[0].id);
    }
  }, [filteredItems, selectedId]);

  const selectedItem = filteredItems.find(item => item.id === selectedId) ?? null;
  const currentIndex = selectedItem ? filteredItems.findIndex(item => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < filteredItems.length - 1;
  const selectedContent = selectedItem ? (drafts[selectedItem.id] ?? selectedItem.content) : '';
  const isSelectedDirty = selectedItem ? dirtyItemIds.has(selectedItem.id) : false;

  const handleCopy = async () => {
    if (!selectedItem) return;
    await navigator.clipboard.writeText(selectedContent);
  };

  const handleDownload = () => {
    if (!selectedItem) return;
    const blob = new Blob([selectedContent], { type: format === 'toml' ? 'application/toml' : 'text/markdown' });
    downloadBlob(blob, getMarketplaceItemFileName(selectedItem));
  };

  const handleCreate = (value: MarketplaceMarkdownCreateDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const nextItem: MarketplaceEditorResourceItem = {
      id,
      titleKey: 'marketplace.editor.documentViewer.create.defaultTitle',
      descriptionKey: 'marketplace.editor.documentViewer.create.defaultDescription',
      title: value.path,
      description: value.path,
      path: value.path,
      content: value.content,
      badge: format === 'toml' ? 'toml' : 'md',
    };
    const nextItems = [...localItems, nextItem];
    const nextDrafts = { ...drafts, [id]: value.content };
    setLocalItems(nextItems);
    setDrafts(nextDrafts);
    setSelectedId(id);
    setCreateDialogOpen(false);
    emitItemsChange(nextItems, nextDrafts);
    onDirty();
  };

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-80 flex-shrink-0">
        <MarketplaceSectionSidebarShell
          title={t(`marketplace.editor.documentViewer.${tab}.title`)}
          icon={<Icon className="h-4 w-4" />}
          actions={(
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('marketplace.editor.documentViewer.actions.refresh')}
                aria-label={t('marketplace.editor.documentViewer.actions.refresh')}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('marketplace.editor.documentViewer.actions.add')}
                aria-label={t('marketplace.editor.documentViewer.actions.add')}
                onClick={() => setCreateDialogOpen(true)}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </>
          )}
          searchValue={search}
          onSearchChange={setSearch}
          onSearchClear={() => setSearch('')}
          searchPlaceholder={t('marketplace.editor.documentViewer.search.placeholder')}
          body={(
            <div className="h-full space-y-2 overflow-y-auto p-3">
              {filteredItems.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {t('marketplace.editor.documentViewer.empty.filtered')}
                </div>
              ) : (
                filteredItems.map(item => {
                  const isActive = selectedItem?.id === item.id;
                  const content = drafts[item.id] ?? item.content;
                  const isItemDirty = dirtyItemIds.has(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={cn(
                        'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                        isActive
                          ? 'border-primary/60 bg-primary/10 shadow-sm'
                          : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40',
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">
                            {isItemDirty ? (
                              <span
                                className="mr-1.5 inline-block h-2 w-2 rounded-full bg-amber-500 align-middle"
                                aria-label={t('marketplace.editor.documentViewer.unsavedFile')}
                              />
                            ) : null}
                            {getMarketplaceItemFileName(item)}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            {marketplaceEditorItemDescription(item, t)}
                          </div>
                        </div>
                        <div className="text-right text-[11px] text-muted-foreground">
                          {t('common.markdownFileViewer.units.bytes', { count: content.length })}
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          )}
        />
      </div>

      <main className="flex-1 bg-background">
        {selectedItem ? (
          <div className="flex h-full flex-col">
            <div className="sticky top-0 z-10 bg-background">
              <div className="border-b border-border bg-background p-4">
                <div className="flex items-center justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon className="h-5 w-5 shrink-0 text-primary" />
                      <h3 className="truncate font-semibold text-foreground">
                        {getMarketplaceItemFileName(selectedItem)}
                      </h3>
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {marketplaceEditorItemDescription(selectedItem, t)}
                    </p>
                    {isSelectedDirty ? (
                      <Badge variant="outline" className="border-amber-500/40 bg-amber-50 text-amber-700">
                        {t('marketplace.editor.documentViewer.unsavedFile')}
                      </Badge>
                    ) : null}
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedId(filteredItems[currentIndex - 1].id)}
                      disabled={!canNavigatePrevious}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedId(filteredItems[currentIndex + 1].id)}
                      disabled={!canNavigateNext}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                      <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                      {t('marketplace.editor.documentViewer.actions.delete')}
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          title={t('marketplace.editor.documentViewer.actions.more')}
                          aria-label={t('marketplace.editor.documentViewer.actions.more')}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setRenameItem(selectedItem)}>
                          <Edit className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.common.rename.action')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void handleCopy()}>
                          <Copy className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.documentViewer.actions.copy')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={handleDownload}>
                          <Download className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.documentViewer.actions.download')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-hidden">
              {format === 'toml' ? (
                <div className="flex h-full flex-col">
                  <CodeTextEditor
                    fileName={selectedItem.path}
                    content={selectedContent}
                    originalContent={selectedItem.content}
                    onContentChange={(value) => {
                      const nextDrafts = { ...drafts, [selectedItem.id]: value };
                      setDrafts(nextDrafts);
                      emitItemsChange(localItems, nextDrafts);
                      onDirty();
                    }}
                    onModifiedChange={() => undefined}
                  />
                  <div className="border-t border-border px-3 py-2 font-mono text-xs text-muted-foreground">
                    {selectedItem.path}
                  </div>
                </div>
              ) : (
                <MarkdownEditor
                  value={selectedContent}
                  onChange={(value) => {
                    const nextDrafts = { ...drafts, [selectedItem.id]: value };
                    setDrafts(nextDrafts);
                    emitItemsChange(localItems, nextDrafts);
                    onDirty();
                  }}
                  placeholder={t('marketplace.editor.documentViewer.editor.placeholder')}
                  className="h-full min-h-0 rounded-none border-0"
                  textareaClassName="min-h-[calc(100vh-18rem)] font-mono text-sm"
                  statusMessage={(
                    <span className="font-mono text-xs text-muted-foreground">
                      {selectedItem.path}
                    </span>
                  )}
                />
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Icon className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t(`marketplace.editor.documentViewer.${tab}.empty`)}</p>
          </div>
        )}
      </main>
      <MarketplaceRenameDialog
        open={Boolean(renameItem)}
        initialPath={renameItem?.path ?? ''}
        onOpenChange={(open) => {
          if (!open) setRenameItem(null);
        }}
        onSubmit={(nextPath) => {
          if (!renameItem) return;
          const nextItems = localItems.map(item => (
            item.id === renameItem.id ? { ...item, path: nextPath } : item
          ));
          setLocalItems(nextItems);
          setRenameItem(null);
          emitItemsChange(nextItems, drafts);
          onDirty();
        }}
      />
      <MarketplaceMarkdownCreateDialog
        open={createDialogOpen}
        tab={tab}
        icon={Icon}
        format={format}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreate}
      />
    </div>
  );
};

interface MarketplaceMarkdownCreateDialogValue {
  path: string;
  content: string;
}

interface MarketplaceMarkdownCreateDialogProps {
  open: boolean;
  tab: MarketplaceMarkdownEditorTab;
  icon: React.ComponentType<{ className?: string }>;
  format: MarketplaceResourceFormat;
  onOpenChange: (open: boolean) => void;
  onSubmit: (value: MarketplaceMarkdownCreateDialogValue) => void;
}

const marketplaceDefaultResourcePath = (tab: MarketplaceMarkdownEditorTab, format: MarketplaceResourceFormat): string => {
  switch (tab) {
    case 'agents':
      return 'agents/new-subagent.md';
    case 'commands':
      return format === 'toml' ? 'commands/new-command.toml' : 'commands/new-command.md';
    case 'outputStyle':
      return 'output-styles/new-output-style.md';
    case 'policies':
      return 'policies/new-policy.toml';
  }
};

const marketplaceResourceExtension = (format: MarketplaceResourceFormat): string => (
  format === 'toml' ? '.toml' : '.md'
);

const MarketplaceMarkdownCreateDialog: React.FC<MarketplaceMarkdownCreateDialogProps> = ({
  open,
  tab,
  icon: Icon,
  format,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [path, setPath] = React.useState(marketplaceDefaultResourcePath(tab, format));
  const [content, setContent] = React.useState('');
  const [errors, setErrors] = React.useState<{ path?: string; content?: string }>({});

  React.useEffect(() => {
    if (!open) return;
    setPath(marketplaceDefaultResourcePath(tab, format));
    setContent('');
    setErrors({});
  }, [format, open, tab]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors: { path?: string; content?: string } = {};
    if (!path.trim()) {
      nextErrors.path = t('marketplace.editor.documentViewer.create.validation.pathRequired');
    }
    if (!content.trim()) {
      nextErrors.content = t('marketplace.editor.documentViewer.create.validation.contentRequired');
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onSubmit({
      path: path.trim().endsWith(marketplaceResourceExtension(format))
        ? path.trim()
        : `${path.trim()}${marketplaceResourceExtension(format)}`,
      content,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            {t('marketplace.editor.documentViewer.create.title', {
              resource: t(`marketplace.editor.documentViewer.${tab}.title`),
            })}
          </DialogTitle>
          <DialogDescription>
            {t('marketplace.editor.documentViewer.create.description', {
              format: t(`marketplace.editor.documentViewer.formats.${format}`),
            })}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex flex-1 flex-col overflow-hidden px-6 pb-6 pt-4">
            <div className="mb-4 flex-shrink-0 space-y-2">
              <Label htmlFor={`marketplace-${tab}-create-path`}>
                {t('marketplace.editor.documentViewer.create.fields.path.label')}
              </Label>
              <Input
                id={`marketplace-${tab}-create-path`}
                value={path}
                onChange={event => setPath(event.target.value)}
                placeholder={t('marketplace.editor.documentViewer.create.fields.path.placeholder')}
                className="font-mono text-sm"
              />
              {errors.path ? <p className="text-xs text-destructive">{errors.path}</p> : null}
              <p className="text-xs text-muted-foreground">
                {t('marketplace.editor.documentViewer.create.fields.path.helper', {
                  extension: marketplaceResourceExtension(format),
                })}
              </p>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <Label className="mb-2">
                {t('marketplace.editor.documentViewer.create.fields.content.label')}
              </Label>
              <div className="min-h-0 flex-1 overflow-hidden rounded-lg border">
                {format === 'toml' ? (
                  <CodeTextEditor
                    fileName={path}
                    content={content}
                    originalContent=""
                    onContentChange={setContent}
                    onModifiedChange={() => undefined}
                  />
                ) : (
                  <MarkdownEditor
                    value={content}
                    onChange={value => setContent(value ?? '')}
                    placeholder={t('marketplace.editor.documentViewer.editor.placeholder')}
                    className="h-full"
                    textareaClassName="min-h-[calc(85vh-18rem)] font-mono text-sm"
                  />
                )}
              </div>
              {errors.content ? <p className="mt-2 text-xs text-destructive">{errors.content}</p> : null}
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('marketplace.common.actions.cancel')}
            </Button>
            <Button type="submit">
              {t('marketplace.editor.documentViewer.create.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplaceRenameDialogProps {
  open: boolean;
  initialPath: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (path: string) => void;
}

const MarketplaceRenameDialog: React.FC<MarketplaceRenameDialogProps> = ({
  open,
  initialPath,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [path, setPath] = React.useState(initialPath);

  React.useEffect(() => {
    if (open) {
      setPath(initialPath);
    }
  }, [initialPath, open]);

  const trimmedPath = path.trim();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('marketplace.editor.common.rename.title')}</DialogTitle>
          <DialogDescription>
            {t('marketplace.editor.common.rename.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('marketplace.editor.common.rename.pathLabel')}
          </label>
          <Input
            value={path}
            onChange={event => setPath(event.target.value)}
            placeholder={t('marketplace.editor.common.rename.pathPlaceholder')}
            className="font-mono text-sm"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button disabled={!trimmedPath} onClick={() => onSubmit(trimmedPath)}>
            {t('marketplace.common.actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
