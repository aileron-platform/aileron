import React from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, Edit, MoreHorizontal, Plus, RefreshCw, Trash2 } from 'lucide-react';

import {
  MarkdownDocumentShell,
  MultiDocumentEditorShell,
  MultiDocumentSidebar,
} from '@/shared/components/document-workflow';
import { CodeTextEditor } from '@/shared/components/file-workbench/viewer-entry';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/shared/types/marketplace';
import { cn } from '@/shared/utils/cn';

import { downloadBlob } from '../../utils/downloadBlob';
import {
  getMarketplaceItemFileName,
  marketplaceEditorItemDescription,
  type MarketplaceEditorResourceItem,
  type MarketplaceMarkdownEditorTab,
  type MarketplaceResourceFormat,
} from './marketplaceEditorResourceItems';
import { useMarketplaceMarkdownEditorState } from './useMarketplaceMarkdownEditorState';

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
  const {
    search,
    setSearch,
    renameItem,
    setRenameItem,
    createDialogOpen,
    setCreateDialogOpen,
    sidebarItems,
    dirtyItemIds,
    selectedItem,
    selectedContent,
    isSelectedDirty,
    canNavigatePrevious,
    canNavigateNext,
    handleSelectPrevious,
    handleSelectNext,
    handleSelectItem,
    handleCreate,
    handleRenameSubmit,
    handleContentChange,
    handleCopy,
    handleDownload,
  } = useMarketplaceMarkdownEditorState({
    format,
    items,
    commitVersion,
    discardVersion,
    t,
    onDirty,
    onItemsChange,
  });

  return (
    <>
      <MultiDocumentEditorShell
        title={t(`marketplace.editor.documentViewer.${tab}.title`)}
        icon={Icon}
        sidebar={(
          <MultiDocumentSidebar
            title={t(`marketplace.editor.documentViewer.${tab}.title`)}
            icon={Icon}
            items={sidebarItems}
            selectedId={selectedItem?.id ?? null}
            onSelect={handleSelectItem}
            isLoading={false}
            labels={{
              searchPlaceholder: t('marketplace.editor.documentViewer.search.placeholder'),
              loading: t('marketplace.editor.documentViewer.empty.filtered'),
              empty: t('marketplace.editor.documentViewer.empty.filtered'),
              dirty: t('marketplace.editor.documentViewer.unsavedFile'),
            }}
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
            showSearch
            searchValue={search}
            onSearchChange={setSearch}
            getDirty={(item) => dirtyItemIds.has(item.id)}
            renderItemMeta={(item) => (
              <span className="text-[11px] text-muted-foreground">
                {t('common.markdownFileViewer.units.bytes', { count: item.contentLength })}
              </span>
            )}
            getSearchText={(item) => [item.searchText]}
          />
        )}
        headerActions={(
          <div className="flex items-center gap-2">
            {selectedItem ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSelectPrevious}
                  disabled={!canNavigatePrevious}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSelectNext}
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
              </>
            ) : null}
          </div>
        )}
        mainArea={(
          <main className="flex-1 min-h-0 overflow-hidden bg-background">
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
                        onContentChange={handleContentChange}
                        onModifiedChange={() => undefined}
                      />
                      <div className="border-t border-border px-3 py-2 font-mono text-xs text-muted-foreground">
                        {selectedItem.path}
                      </div>
                    </div>
                  ) : (
                    <MarkdownEditor
                      value={selectedContent}
                      onChange={handleContentChange}
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
        )}
        labels={{ loading: t('marketplace.editor.documentViewer.empty.filtered') }}
      />
      <MarketplaceRenameDialog
        open={Boolean(renameItem)}
        initialPath={renameItem?.path ?? ''}
        onOpenChange={(open) => {
          if (!open) setRenameItem(null);
        }}
        onSubmit={handleRenameSubmit}
      />
      <MarketplaceMarkdownCreateDialog
        open={createDialogOpen}
        tab={tab}
        icon={Icon}
        format={format}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreate}
      />
    </>
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
          <DialogHeading icon={Icon}>
            {t('marketplace.editor.documentViewer.create.title', {
              resource: t(`marketplace.editor.documentViewer.${tab}.title`),
            })}
          </DialogHeading>
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
          <DialogHeading icon={Edit}>
            {t('marketplace.editor.common.rename.title')}
          </DialogHeading>
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
