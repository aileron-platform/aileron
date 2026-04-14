import React, { useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { useNavigate } from 'react-router-dom';

const logger = createLogger('TemplateCenterView');
import { LayoutGrid, RefreshCcw, Upload, Plus, Search, Trash2, Settings } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';
import { useTemplateManagementContext } from '../../providers/TemplateManagementProvider';
import { TemplateCard } from './components/TemplateCard';
import { TemplateInstallDialog } from './components/TemplateInstallDialog';
import { TemplateImportDialog } from './components/TemplateImportDialog';
import { useToast } from '@/shared/components/ui/use-toast';
import type { Template, TemplateFeatureKey, TemplateInstallOptions, CliType } from '@/shared/types/templates';
import { listFeaturesForCli } from '@/shared/types/templates';
import { filterTemplates } from '../../utils/templateSelectors';
import { useI18n } from '@/shared/hooks/useI18n';
import * as templateApi from '@/shared/services/templateApi';
import { apiClient } from '@/shared/api/apiClient';
import { ROUTES } from '@/shared/constants/routes';

const PAGE_SIZE_OPTIONS = [6, 12, 24];

export const TemplateCenterView: React.FC = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useI18n();
  const {
    templates,
    categories,
    workspaces,
    isLoading,
    error,
    deleteTemplate,
    exportTemplate,
    importTemplate,
    installTemplate,
    reloadFromSource,
    layout,
    setCenterLeftWidth,
  } = useTemplateManagementContext();

  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [activeFeatures, setActiveFeatures] = useState<Set<TemplateFeatureKey>>(new Set());
  const [activeCliType, setActiveCliType] = useState<'all' | CliType>('all');

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [installDialogOpen, setInstallDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState<Template | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [exportingSet, setExportingSet] = useState<Set<string>>(new Set());
  const [isCreating, setIsCreating] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');

  // 從後端讀取對應 CLI 類型可用的功能鍵（失敗時回退本地規則）
  const [remoteFeatureKeys, setRemoteFeatureKeys] = useState<TemplateFeatureKey[] | null>(null);
  React.useEffect(() => {
    let aborted = false;
    const ctrl = new AbortController();
    const fetchKeys = async () => {
      try {
        const qs = activeCliType ? `?cli_type=${encodeURIComponent(activeCliType)}` : '';
        // 使用 apiClient 以自動帶上認證 token
        const data = await apiClient.get<{ items: string[] }>(`/templates/features${qs}`);
        if (aborted) return;
        // 簡單的型別守衛：僅接受已知鍵
        const allowed: TemplateFeatureKey[] = ['mcp','slashCommands','hooks','claudeMd','subAgents','outputStyles','skills','scripts'];
        const keys = data.items.filter((k): k is TemplateFeatureKey => (allowed as string[]).includes(k));
        setRemoteFeatureKeys(keys);
      } catch (err) {
        // 只在非中斷錯誤時記錄警告
        if (!aborted && err instanceof Error && err.name !== 'AbortError') {
          logger.warn('無法從後端取得 feature 列表，改用本地規則', { error: err });
        }
        if (!aborted) setRemoteFeatureKeys(null);
      }
    };
    fetchKeys();
    return () => { aborted = true; ctrl.abort(); };
  }, [activeCliType]);

  // 根據範本的 CLI 類型，僅顯示相容的工作區供安裝選擇
  const compatibleWorkspaces = useMemo(() => {
    if (!selectedTemplate || !selectedTemplate.cliType) return workspaces;
    return workspaces.filter(w => !w.cliType || w.cliType === selectedTemplate.cliType);
  }, [workspaces, selectedTemplate]);

  // 左側篩選側欄：寬度改由 Provider 統一管理
  const leftPaneWidth = layout.centerLeftWidth;
  const [leftDragging, setLeftDragging] = useState<boolean>(false);
  const LEFT_PANE_MIN = 220;
  const LEFT_PANE_MAX = 420;
  const onDragLeftPane = (e: React.MouseEvent) => {
    setLeftDragging(true);
    const startX = e.clientX;
    const startW = leftPaneWidth;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX;
      const next = Math.max(LEFT_PANE_MIN, Math.min(LEFT_PANE_MAX, startW + dx));
      setCenterLeftWidth(next);
    };
    const onUp = () => {
      setLeftDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const filteredTemplates = useMemo(() => {
    return filterTemplates(templates, {
      searchTerm,
      categoryId: activeCategory,
      feature: activeFeatures.size === 0 ? 'all' : Array.from(activeFeatures),
      cliType: activeCliType,
    });
  }, [templates, searchTerm, activeCategory, activeFeatures, activeCliType]);

  const totalPages = Math.max(1, Math.ceil(filteredTemplates.length / pageSize));
  const currentPageClamped = Math.min(currentPage, totalPages);

  const pagedTemplates = useMemo(() => {
    const start = (currentPageClamped - 1) * pageSize;
    return filteredTemplates.slice(start, start + pageSize);
  }, [filteredTemplates, currentPageClamped, pageSize]);

  const featureFilters: Array<{ id: TemplateFeatureKey | 'all'; label: string }> = useMemo(() => {
    const fallbackKeys = listFeaturesForCli(activeCliType);
    const keys = remoteFeatureKeys ?? fallbackKeys;

    const labelFor = (k: TemplateFeatureKey) => {
      if (k === 'claudeMd' && (activeCliType === 'codex' || activeCliType === 'gemini')) {
        return t('template.center.filters.featureOptions.agentMd');
      }
      switch (k) {
        case 'mcp':
          return t('template.center.filters.featureOptions.mcp');
        case 'slashCommands':
          return t('template.center.filters.featureOptions.slashCommands');
        case 'hooks':
          return t('template.center.filters.featureOptions.hooks');
        case 'claudeMd':
          return t('template.center.filters.featureOptions.claudeMd');
        case 'subAgents':
          return t('template.center.filters.featureOptions.subAgents');
        case 'outputStyles':
          return t('template.center.filters.featureOptions.outputStyles');
        case 'skills':
          return t('template.center.filters.featureOptions.skills');
        case 'scripts':
          return t('template.center.filters.featureOptions.scripts');
        default:
          return k;
      }
    };

    const items = keys.map(k => ({ id: k, label: labelFor(k) }));
    return [{ id: 'all', label: t('template.center.filters.allFeatures') }, ...items];
  }, [t, activeCliType, remoteFeatureKeys]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setActiveCategory('all');
    setActiveCliType('all');
    setActiveFeatures(new Set());
    setCurrentPage(1);
  };


  // 當 CLI 類型改變時，移除不在可用清單中的功能選擇
  React.useEffect(() => {
    const availableIds = new Set(featureFilters.map(f => f.id).filter(id => id !== 'all'));
    const validFeatures = Array.from(activeFeatures).filter(f => availableIds.has(f));
    if (validFeatures.length !== activeFeatures.size) {
      setActiveFeatures(new Set(validFeatures));
    }
  }, [activeCliType, featureFilters, activeFeatures]);

  const handleDelete = async () => {
    if (!deletingTemplate) return;
    try {
      await deleteTemplate(deletingTemplate.id);
      toast({


        title: t('template.center.toasts.deleteSuccess.title'),
        description: t('template.center.toasts.deleteSuccess.description', {
          name: deletingTemplate.name,
        }),
      });
    } catch (err) {
      logger.error('刪除失敗', { error: err });
      toast({
        title: t('template.center.toasts.deleteFailed.title'),
        description: t('template.center.toasts.deleteFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setDeletingTemplate(null);
    }
  };

  const handleCreateTemplate = async () => {
    setCreateDialogOpen(true);
  };

  const handleConfirmCreate = async (templateId: string) => {
    if (!templateId) {
      return;
    }
    setIsCreating(true);
    try {
      // 準備初始資料
      const newTemplateData: templateApi.TemplateBasicInfo = {
        templateId: templateId, // 模板代號
        name: templateId, // 初始名稱與代號相同，之後可在編輯頁面修改
        version: '1.0.0',
        description: '',
        author: {
          name: 'Admin User',
          email: 'admin@aileron.com',
        },
        keywords: [],
        cli_type: 'claude-code' as const,
      };

      // 調用後端 API 創建模板
      const createdTemplate = await templateApi.createTemplate(newTemplateData);

      // 重新載入模板列表
      await reloadFromSource();

      toast({
        title: t('template.editor.toasts.createSuccess.title'),
        description: t('template.editor.toasts.createSuccess.description', {
          name: createdTemplate.name,
        }),
        variant: 'success',
      });

      // 關閉對話框
      setCreateDialogOpen(false);

      // 導航到編輯頁面 - 修正 URL 路徑
      navigate(`templates/${createdTemplate.id}/edit`);
    } catch (error) {
      logger.error('Failed to create template', { error });

      // 提供更具體的錯誤信息
      let errorMessage = t('template.center.createDialog.errors.generic');
      if (error instanceof Error) {
        if (error.message.includes('422')) {
          errorMessage = t('template.center.createDialog.errors.invalidPayload');
        } else if (error.message.includes('401') || error.message.includes('Authentication failed')) {
          errorMessage = t('template.center.createDialog.errors.unauthorized');
        } else if (error.message.includes('409')) {
          errorMessage = t('template.center.createDialog.errors.duplicate');
        } else {
          errorMessage = error.message;
        }
      }

      toast({
        title: t('template.editor.toasts.createFailed.title'),
        description: errorMessage,
        variant: 'destructive',
      });

      // 重要：創建失敗時不要導航，保持在對話框中讓用戶可以重試
      return;
    } finally {
      setIsCreating(false);
    }
  };

  const handleExport = async (template: Template) => {
    setExportingSet(prev => new Set(prev).add(template.id));
    try {
      await exportTemplate(template.id);
      toast({
        title: t('template.center.toasts.exportSuccess.title'),
        description: t('template.center.toasts.exportSuccess.description', {
          name: template.name,
        }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('匯出失敗', { error: err });
      toast({
        title: t('template.center.toasts.exportFailed.title'),
        description: t('template.center.toasts.exportFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setExportingSet(prev => {
        const next = new Set(prev);
        next.delete(template.id);
        return next;
      });
    }
  };

  const handleImport = async (file: File) => {
    try {
      setIsImporting(true);
      if (!file.name.endsWith('.zip')) {
        throw new Error(t('template.center.errors.invalidFileType'));
      }
      await importTemplate(file);
      toast({
        title: t('template.center.toasts.importSuccess.title'),
        description: t('template.center.toasts.importSuccess.description', {
          name: file.name.replace('.zip', ''),
        }),
        variant: 'success',
      });
      setImportDialogOpen(false);
    } catch (err) {
      logger.error('匯入失敗', { error: err });
      toast({
        title: t('template.center.toasts.importFailed.title'),
        description:
          err instanceof Error
            ? err.message
            : t('template.center.toasts.importFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleInstall = async (workspaceId: string, options: TemplateInstallOptions) => {
    if (!selectedTemplate) return;
    try {
      const result = await installTemplate(selectedTemplate.id, workspaceId, options);
      toast({
        title: t('template.center.toasts.installSuccess.title'),
        description: t('template.center.toasts.installSuccess.description', {
          template: result.template.name,
          workspace: result.workspace.name,
        }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('安裝失敗', { error: err });
      toast({
        title: t('template.center.toasts.installFailed.title'),
        description:
          err instanceof Error
            ? err.message
            : t('template.center.toasts.installFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setInstallDialogOpen(false);
      setSelectedTemplate(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('template.center.header.title')}
        icon={LayoutGrid}
        info={
          <div className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap">
            <span>{t('template.center.header.description')}</span>
            <span className="text-muted-foreground/50">·</span>
            <span>
              {t('template.center.header.stats', {
                total: filteredTemplates.length,
                visible: pagedTemplates.length,
              })}
            </span>
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => setImportDialogOpen(true)}>
              <Upload className="h-3.5 w-3.5 mr-1" /> {t('template.center.actions.import')}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateTemplate} disabled={isCreating}>
              <Plus className="h-3.5 w-3.5 mr-1" />
              {isCreating ? t('template.editor.creating') : t('template.center.actions.create')}
            </Button>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(ROUTES.TEMPLATE_CENTER_SETTINGS)}>
              <Settings className="h-3.5 w-3.5 mr-1" /> {t('template.center.actions.settings')}
            </Button>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={reloadFromSource}>
              <RefreshCcw className="h-3.5 w-3.5 mr-1" /> {t('template.center.actions.refresh')}
            </Button>
          </div>
        }
      />

      <div className="flex h-[calc(100%-3rem)] min-h-0">
        <aside
          className="hidden lg:block relative flex-shrink-0 bg-muted/20 p-6 border-r border-border"
          style={{ width: leftPaneWidth }}
        >
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm font-semibold text-foreground">
                {t('template.center.filters.searchLabel')}
              </p>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchTerm}
                  onChange={event => {
                    setSearchTerm(event.target.value);
                    setCurrentPage(1);
                  }}
                  placeholder={t('template.center.filters.searchPlaceholder')}
                  className="pl-10"
                />
              </div>
            </div>

            {/* CLI 類型篩選器 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">
                  {t('template.center.filters.cliLabel')}
                </p>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleResetFilters}>
                  {t('template.center.filters.clear')}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={activeCliType === 'all' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    setActiveCliType('all');
                    setCurrentPage(1);
                  }}
                >
                  {t('template.center.filters.allCli')}
                </Button>
                <Button
                  variant={activeCliType === 'claude-code' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    setActiveCliType('claude-code');
                    setCurrentPage(1);
                  }}
                >
                  {t('template.center.filters.cliOptions.claudeCode')}
                </Button>
                <Button
                  variant={activeCliType === 'codex' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    setActiveCliType('codex');
                    setCurrentPage(1);
                  }}
                >
                  {t('template.center.filters.cliOptions.codex')}
                </Button>
                <Button
                  variant={activeCliType === 'gemini' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    setActiveCliType('gemini');
                    setCurrentPage(1);
                  }}
                >
                  {t('template.center.filters.cliOptions.gemini')}
                </Button>
              </div>
            </div>


            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">
                  {t('template.center.filters.featureLabel')}
                </p>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleResetFilters}>
                  {t('template.center.filters.clear')}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {featureFilters.map(filter => {
                  const isAll = filter.id === 'all';
                  const isActive = isAll ? activeFeatures.size === 0 : activeFeatures.has(filter.id as TemplateFeatureKey);
                  return (
                    <Button
                      key={filter.id}
                      variant={isActive ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => {
                        if (isAll) {
                          setActiveFeatures(new Set());
                        } else {
                          const featureKey = filter.id as TemplateFeatureKey;
                          const newFeatures = new Set(activeFeatures);
                          if (newFeatures.has(featureKey)) {
                            newFeatures.delete(featureKey);
                          } else {
                            newFeatures.add(featureKey);
                          }
                          setActiveFeatures(newFeatures);
                        }
                        setCurrentPage(1);
                      }}
                    >
                      {filter.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-foreground">
                {t('template.center.filters.categoryLabel')}
              </p>
              <div className="flex flex-col gap-2">
                <Button
                  variant={activeCategory === 'all' ? 'default' : 'outline'}
                  size="sm"
                  className="justify-start h-7 px-2 text-xs"
                  onClick={() => {

                    setActiveCategory('all');
                    setCurrentPage(1);
                  }}
                >
                  {t('template.center.filters.allTemplates')}
                </Button>
                {categories.map(category => (
                  <Button
                    key={category.id}
                    variant={activeCategory === category.id ? 'default' : 'outline'}
                    size="sm"
                    className="justify-start h-7 px-2 text-xs"
                    onClick={() => {
                      setActiveCategory(category.id);
                    setCurrentPage(1);
                  }}
                >
                  {category.name}
                </Button>
                ))}


              </div>
            </div>
          </div>
          {/* Resizer Handle：對齊 Workspace - 4px 寬 */}
          <div
            className={`absolute right-0 top-0 h-full w-1 cursor-col-resize z-10 transition-colors ${leftDragging ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'}`}
            onMouseDown={onDragLeftPane}
            role="separator"
            aria-orientation="vertical"
            aria-label={t('template.center.accessibility.resizePane')}
          />

        </aside>

        <main className="flex-1 overflow-hidden">
          <div className="flex h-full flex-col">
            <div className="flex h-10 items-center border-b border-border bg-muted/10 px-4">
              <div className="flex flex-wrap items-center gap-3 w-full">
                <div className="flex items-center gap-2">
                  <LayoutGrid className="h-4 w-4 text-primary" />
                  <p className="text-sm font-semibold text-foreground">
                    {t('template.center.list.title')}
                  </p>
                </div>

                <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {t('template.center.list.stats.visible', {
                      visible: pagedTemplates.length,
                      total: filteredTemplates.length,
                    })}
                  </span>
                  <span>
                    {t('template.center.list.stats.page', {
                      current: currentPageClamped,
                      total: totalPages,
                    })}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-auto px-6 py-6">
              {isLoading ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  {t('template.center.list.loading')}
                </div>
              ) : error ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <p>{t('template.center.list.error.title')}</p>
                  <Button size="sm" className="h-7 px-2 text-xs" onClick={reloadFromSource}>
                    {t('template.center.list.error.retry')}
                  </Button>
                </div>
              ) : filteredTemplates.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <Search className="h-10 w-10" />
                  <p>{t('template.center.list.empty.title')}</p>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={handleResetFilters}>
                    {t('template.center.list.empty.reset')}
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {pagedTemplates.map(template => (
                      <TemplateCard
                        key={template.id}
                        template={template}
                        onOpenDetail={item => navigate(ROUTES.TEMPLATE_DETAIL(item.id))}
                        onInstall={item => {
                          setSelectedTemplate(item);
                          setInstallDialogOpen(true);
                        }}
                        onEdit={item => navigate(ROUTES.TEMPLATE_EDIT(item.id))}
                        onDelete={item => setDeletingTemplate(item)}
                        onExport={handleExport}
                        isExporting={exportingSet.has(template.id)}
                      />
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4 text-sm">
                    <div className="flex items-center gap-3">
                      <span>
                        {t('template.center.pagination.pageCount', {
                          current: currentPageClamped,
                          total: totalPages,
                        })}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          disabled={currentPageClamped <= 1}
                          onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        >
                          {t('template.center.pagination.previous')}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          disabled={currentPageClamped >= totalPages}
                          onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        >
                          {t('template.center.pagination.next')}
                        </Button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span>{t('template.center.pagination.perPage')}</span>
                      <div className="flex items-center gap-2">
                        {PAGE_SIZE_OPTIONS.map(size => (
                          <Button
                            key={size}
                            variant={pageSize === size ? 'default' : 'outline'}
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => {
                              setPageSize(size);
                              setCurrentPage(1);
                            }}
                          >
                            {t('template.center.pagination.perPageOption', { count: size })}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>

      <TemplateInstallDialog
        open={installDialogOpen}
        template={selectedTemplate}
        workspaces={compatibleWorkspaces}
        onOpenChange={open => {
          setInstallDialogOpen(open);
          if (!open) setSelectedTemplate(null);
        }}
        onInstall={handleInstall}
      />

      <TemplateImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        isImporting={isImporting}
        onImport={handleImport}
      />


      <AlertDialog open={Boolean(deletingTemplate)} onOpenChange={open => !open && setDeletingTemplate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('template.center.dialogs.delete.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('template.center.dialogs.delete.description', {
                name: deletingTemplate?.name ?? '',
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('template.center.dialogs.delete.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
            >
              <Trash2 className="mr-2 h-4 w-4" /> {t('template.center.dialogs.delete.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('template.center.createDialog.title')}</DialogTitle>
            <DialogDescription>
              {t('template.center.createDialog.description')}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="template-name">{t('template.center.createDialog.nameLabel')}</Label>
              <Input
                id="template-name"
                placeholder={t('template.center.createDialog.placeholder')}
                value={newTemplateName}
                onChange={(e) => {
                  // 只允許英文、數字和連字號
                  const value = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
                  setNewTemplateName(value);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const normalized = newTemplateName.trim();
                    if (normalized && /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(normalized)) {
                      handleConfirmCreate(normalized);
                    }
                  }
                }}
              />
              {newTemplateName && !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(newTemplateName) && (
                <p className="text-sm text-destructive">
                  {t('template.center.createDialog.validation.kebabCase')}
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setCreateDialogOpen(false);
                setNewTemplateName('');
              }}
            >
              {t('template.center.createDialog.actions.cancel')}
            </Button>
            <Button
              onClick={() => handleConfirmCreate(newTemplateName.trim())}
              disabled={!newTemplateName.trim() || !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(newTemplateName) || isCreating}
            >
              {isCreating
                ? t('template.center.createDialog.actions.creating')
                : t('template.center.createDialog.actions.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TemplateCenterView;
