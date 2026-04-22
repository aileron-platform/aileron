/**
 * Markdown 預覽組件
 * 提供 Markdown 文件的渲染和互動功能
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Maximize2,
  Minimize2,
  Download,
  Copy,
  Check,
  FileText,
  Edit3,
  Eye,
  Save,
  X,
  CheckSquare,
  ListTree,
  ArrowDownCircle,
  Search,
  ChevronDown,
} from 'lucide-react';
import type { Components } from 'react-markdown';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Progress } from '@/shared/components/ui/progress';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { cn } from '@/shared/utils/cn';
import { sharedComponents } from '@/shared/components/markdown/markdownComponents';
import { preprocessMarkdown } from '@/shared/components/markdown/markdownPreprocess';
import { remarkLineBreakTag } from '@/shared/components/markdown/remarkLineBreakTag';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useChatPanelStateContext } from '../../../components/ChatPanel/chatPanelStateContext';
import { createLogger } from '@/shared/services/logger';
import {
  classifyMarkdownHref,
  resolveWorkspaceMarkdownPath,
} from '../utils/markdownLinkUtils';
import {
  getOpenSpecDocumentKind,
  parseOpenSpecSpecOutline,
  parseOpenSpecTasks,
  toggleOpenSpecTask,
} from '../../openspec/utils/openSpecMarkdown';
import { useOpenSpecWorkspace } from '../../openspec/OpenSpecWorkspaceContext';

const logger = createLogger('MarkdownViewer');

interface MarkdownViewerProps {
  content: string;
  fileName: string;
  filePath?: string;
  className?: string;
}

type HeadingIdResolver = (text: string, level: number) => string | undefined;

/** 遞迴收集檔案樹中所有節點的路徑 */
const collectTreePaths = (nodes: Array<{ path: string; children?: unknown[] }>): Set<string> => {
  const paths = new Set<string>();
  const traverse = (nodeList: typeof nodes) => {
    nodeList.forEach(node => {
      paths.add(node.path);
      if (node.children && Array.isArray(node.children)) {
        traverse(node.children as typeof nodes);
      }
    });
  };
  traverse(nodes);
  return paths;
};

const extractNodeText = (children: React.ReactNode): string => {
  return React.Children.toArray(children)
    .map((child) => {
      if (typeof child === 'string' || typeof child === 'number') {
        return String(child);
      }
      if (React.isValidElement(child)) {
        return extractNodeText(child.props.children);
      }
      return '';
    })
    .join('')
    .trim();
};

const countTasks = (content: string) => {
  const sections = parseOpenSpecTasks(content);
  const total = sections.reduce((sum, section) => sum + section.tasks.length, 0);
  const done = sections.reduce(
    (sum, section) => sum + section.tasks.filter((task) => task.checked).length,
    0,
  );
  return { sections, total, done };
};

const normalizeOpenSpecHeadingText = (text: string, level: number): string => {
  if (level === 3) {
    return text.replace(/^Requirement:\s*/, '').trim();
  }
  if (level === 4) {
    return text.replace(/^Scenario:\s*/, '').trim();
  }
  return text.trim();
};

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  fileName,
  filePath,
  className,
}) => {
  const { t } = useI18n();
  const processedContent = useMemo(() => preprocessMarkdown(content), [content]);
  const { toast } = useToast();
  const workspaceContext = useWorkspace();
  const { workspace, fileEditor, fileTreeActions, fileTreeState, openFileInTab } = workspaceContext;
  const [, chatUiActions] = useChatPanelStateContext();
  const { actions: openSpecActions } = useOpenSpecWorkspace();
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editContent, setEditContent] = useState(content);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeSpecHeadingId, setActiveSpecHeadingId] = useState<string | null>(null);
  const [isSpecOutlineVisible, setIsSpecOutlineVisible] = useState(true);
  const [specOutlineQuery, setSpecOutlineQuery] = useState('');
  const [expandedRequirementIds, setExpandedRequirementIds] = useState<string[]>([]);
  const [isTaskSaving, setIsTaskSaving] = useState(false);

  const tasksScrollRef = useRef<HTMLDivElement | null>(null);
  const taskRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const specScrollRef = useRef<HTMLDivElement | null>(null);

  const activeTab = workspace.openTabs.find((tab) => tab.id === workspace.activeTabId);
  const isModified = activeTab ? fileEditor.modifiedTabs.includes(activeTab.id) : false;
  const openSpecKind = getOpenSpecDocumentKind(filePath);
  const focusedOpenSpecChange = useMemo(() => {
    if (!filePath?.startsWith('/openspec/changes/')) {
      return null;
    }
    const segments = filePath.split('/').filter(Boolean);
    return segments[2] || null;
  }, [filePath]);
  const contextualOpenSpecActions = useMemo(() => {
    if (!openSpecKind) {
      return [];
    }
    const mapping: Record<NonNullable<typeof openSpecKind>, string[]> = {
      proposal: ['continue', 'ff'],
      design: ['continue', 'ff'],
      tasks: ['apply', 'verify'],
      spec: ['sync', 'archive'],
    };
    return openSpecActions
      .filter((action) => mapping[openSpecKind].includes(action.id))
      .filter((action) => ['enabled', 'blocked', 'setup_required', 'sync_required'].includes(action.availability));
  }, [openSpecActions, openSpecKind]);

  const taskSummary = useMemo(() => countTasks(content), [content]);
  const specOutline = useMemo(() => parseOpenSpecSpecOutline(content), [content]);
  const filteredSpecOutline = useMemo(() => {
    const query = specOutlineQuery.trim().toLowerCase();
    if (!query) {
      return specOutline;
    }

    return specOutline
      .map((requirement) => {
        const matchesRequirement = requirement.title.toLowerCase().includes(query);
        const scenarios = requirement.scenarios.filter((scenario) =>
          scenario.title.toLowerCase().includes(query),
        );
        if (matchesRequirement) {
          return requirement;
        }
        if (scenarios.length > 0) {
          return { ...requirement, scenarios };
        }
        return null;
      })
      .filter(Boolean) as typeof specOutline;
  }, [specOutline, specOutlineQuery]);

  useEffect(() => {
    setEditContent(content);
  }, [content]);

  useEffect(() => {
    if (openSpecKind !== 'spec') {
      setSpecOutlineQuery('');
      setExpandedRequirementIds([]);
      setIsSpecOutlineVisible(true);
      return;
    }

    setExpandedRequirementIds((prev) => {
      const availableIds = new Set(specOutline.map((requirement) => requirement.id));
      const next = prev.filter((id) => availableIds.has(id));
      if (next.length > 0) {
        return next;
      }
      return specOutline.length > 0 ? [specOutline[0].id] : [];
    });
  }, [openSpecKind, specOutline]);

  useEffect(() => {
    if (openSpecKind !== 'spec') {
      setActiveSpecHeadingId(null);
      return;
    }

    const container = specScrollRef.current;
    if (!container) {
      return;
    }

    const orderedIds = specOutline.flatMap((requirement) => [
      requirement.id,
      ...requirement.scenarios.map((scenario) => scenario.id),
    ]);

    const updateActiveHeading = () => {
      const headings = orderedIds
        .map((id) => {
          const element = container.querySelector<HTMLElement>(`#${CSS.escape(id)}`);
          if (!element) {
            return null;
          }
          return {
            id,
            top: element.offsetTop,
          };
        })
        .filter(Boolean) as Array<{ id: string; top: number }>;

      if (headings.length === 0) {
        setActiveSpecHeadingId(null);
        return;
      }

      const current = headings
        .filter((heading) => heading.top <= container.scrollTop + 120)
        .at(-1) ?? headings[0];

      setActiveSpecHeadingId(current.id);
    };

    updateActiveHeading();
    container.addEventListener('scroll', updateActiveHeading);
    return () => container.removeEventListener('scroll', updateActiveHeading);
  }, [openSpecKind, specOutline]);

  useEffect(() => {
    if (openSpecKind !== 'spec' || !activeSpecHeadingId) {
      return;
    }

    const activeRequirement = specOutline.find(
      (requirement) =>
        requirement.id === activeSpecHeadingId ||
        requirement.scenarios.some((scenario) => scenario.id === activeSpecHeadingId),
    );

    if (!activeRequirement) {
      return;
    }

    setExpandedRequirementIds((prev) =>
      prev.includes(activeRequirement.id) ? prev : [...prev, activeRequirement.id],
    );
  }, [activeSpecHeadingId, openSpecKind, specOutline]);

  // 縮放控制
  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.1, 2));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 0.1, 0.5));
  };

  const handleResetZoom = () => {
    setZoom(1);
  };

  // 下載 Markdown
  const handleDownload = () => {
    if (!content) return;

    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 複製內容
  const handleCopy = async () => {
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      logger.error('Failed to copy content', { error: err });
    }
  };

  // 放大模式控制
  const handleFullscreen = () => {
    setIsExpanded(!isExpanded);
  };

  // 切換編輯模式
  const handleToggleEditMode = () => {
    if (isEditMode) {
      setIsEditMode(false);
    } else {
      setEditContent(content);
      setIsEditMode(true);
    }
  };

  // 儲存編輯內容
  const handleSave = () => {
    if (!activeTab) return;

    fileEditor.updateTabContent(activeTab.id, editContent);
    const originalContent = fileEditor.originalContents[activeTab.id] || '';
    fileEditor.setTabModified(activeTab.id, editContent !== originalContent);
    setIsEditMode(false);
  };

  // 取消編輯
  const handleCancelEdit = () => {
    setEditContent(content);
    setIsEditMode(false);
  };

  const handleRefresh = useCallback(async () => {
    if (!activeTab) {
      return;
    }

    if (isModified) {
      const confirmed = typeof window === 'undefined'
        ? true
        : window.confirm(t('workspace.fileManagement.markdown.refreshConfirm'));

      if (!confirmed) {
        return;
      }
    }

    setIsRefreshing(true);
    try {
      const result = await fileEditor.reloadCurrentFile();
      if (!result.success) {
        toast({
          title: t('workspace.fileManagement.markdown.refreshFailed'),
          description: result.error,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t('workspace.fileManagement.markdown.refreshFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [activeTab, fileEditor, isModified, t, toast]);

  const applyContentUpdate = useCallback(
    (nextContent: string) => {
      if (!activeTab) {
        return;
      }
      fileEditor.updateTabContent(activeTab.id, nextContent);
      const originalContent = fileEditor.originalContents[activeTab.id] || '';
      fileEditor.setTabModified(activeTab.id, nextContent !== originalContent);
    },
    [activeTab, fileEditor],
  );

  const handleTaskToggle = useCallback(
    async (lineIndex: number, checked: boolean) => {
      if (!activeTab || !filePath) {
        return;
      }

      const nextContent = toggleOpenSpecTask(content, lineIndex, checked);
      applyContentUpdate(nextContent);

      setIsTaskSaving(true);
      try {
        const result = await fileTreeActions.saveFileContent(filePath, nextContent);
        if (!result.success) {
          throw new Error(result.message || t('workspace.openspec.tasks.saveFailed'));
        }

        fileEditor.setOriginalContent(activeTab.id, nextContent);
        fileEditor.setTabModified(activeTab.id, false);
      } catch (error) {
        toast({
          title: t('workspace.openspec.tasks.saveFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      } finally {
        setIsTaskSaving(false);
      }
    },
    [activeTab, applyContentUpdate, content, filePath, fileTreeActions, fileEditor, t, toast],
  );

  const handleJumpToNextIncomplete = useCallback(() => {
    const nextTask = taskSummary.sections
      .flatMap((section) => section.tasks)
      .find((task) => !task.checked);

    if (!nextTask) {
      return;
    }

    taskRefs.current[nextTask.id]?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    });
  }, [taskSummary.sections]);

  const handleOpenSpecContextAction = useCallback((draftTemplate: string) => {
    const trimmed = draftTemplate.trim();
    if (!trimmed) {
      return;
    }
    const command = trimmed.split(/\s+/)[0];
    const nextDraft = focusedOpenSpecChange && /^(\/opsx:(apply|continue|ff|verify|sync|archive))$/.test(command)
      ? `${command} ${focusedOpenSpecChange}`
      : trimmed;

    chatUiActions.setDraftMessage(nextDraft);
    if (workspaceContext.dispatch && workspaceContext.state?.rightChatCollapsed) {
      workspaceContext.dispatch({ type: 'SET_RIGHT_CHAT_COLLAPSED', payload: false });
    }
  }, [chatUiActions, focusedOpenSpecChange, workspaceContext]);

  const openWorkspaceLink = useCallback(
    (href?: string | null) => {
      const kind = classifyMarkdownHref(href);

      if (kind !== 'internal' || !filePath || !href) {
        return false;
      }

      const resolved = resolveWorkspaceMarkdownPath(filePath, href);
      if (!resolved) {
        return false;
      }

      const paths = collectTreePaths(fileTreeState.nodes);
      if (paths.has(resolved)) {
        openFileInTab(resolved);
      } else {
        toast({
          title: t('workspace.fileManagement.markdown.linkOpenFailed'),
          description: resolved,
          variant: 'destructive',
        });
      }
      return true;
    },
    [filePath, fileTreeState.nodes, openFileInTab, t, toast],
  );

  const buildMarkdownComponents = useCallback(
    (headingIdResolver?: HeadingIdResolver): Components => ({
      h1: ({ node: _node, children, ...props }) => {
        const id = headingIdResolver?.(extractNodeText(children), 1);
        return (
          <h1 id={id} className="text-3xl font-bold mt-6 mb-4 pb-2 border-b scroll-mt-6" {...props}>
            {children}
          </h1>
        );
      },
      h2: ({ node: _node, children, ...props }) => {
        const id = headingIdResolver?.(extractNodeText(children), 2);
        return (
          <h2 id={id} className="text-2xl font-bold mt-5 mb-3 pb-2 border-b scroll-mt-6" {...props}>
            {children}
          </h2>
        );
      },
      h3: ({ node: _node, children, ...props }) => {
        const id = headingIdResolver?.(extractNodeText(children), 3);
        return (
          <h3 id={id} className="text-xl font-bold mt-4 mb-2 scroll-mt-6" {...props}>
            {children}
          </h3>
        );
      },
      h4: ({ node: _node, children, ...props }) => {
        const id = headingIdResolver?.(extractNodeText(children), 4);
        return (
          <h4 id={id} className="text-lg font-bold mt-3 mb-2 scroll-mt-6" {...props}>
            {children}
          </h4>
        );
      },
      h5: ({ node: _node, children, ...props }) => (
        <h5 className="text-base font-bold mt-2 mb-1" {...props}>
          {children}
        </h5>
      ),
      h6: ({ node: _node, children, ...props }) => (
        <h6 className="text-sm font-bold mt-2 mb-1" {...props}>
          {children}
        </h6>
      ),
      p: ({ node: _node, ...props }) => (
        <p className="my-3 leading-7" {...props} />
      ),
      a: ({ node: _node, href, children, ...props }) => {
        const kind = classifyMarkdownHref(href);

        if (kind === 'internal') {
          return (
            <a
              href={kind === 'anchor' ? href : '#'}
              className="text-primary hover:underline cursor-pointer"
              onClick={(e) => {
                if (kind === 'anchor') {
                  return;
                }
                e.preventDefault();
                openWorkspaceLink(href);
              }}
              {...props}
            >
              {children}
            </a>
          );
        }

        if (kind === 'anchor') {
          return (
            <a className="text-primary hover:underline" href={href} {...props}>
              {children}
            </a>
          );
        }

        return (
          <a
            className="text-primary hover:underline"
            target="_blank"
            rel="noopener noreferrer"
            href={href}
            {...props}
          >
            {children}
          </a>
        );
      },
      code: ({ node: _node, className, children, ...props }: any) => {
        const isInline = !className;
        return isInline ? (
          <code className="px-1.5 py-0.5 rounded bg-muted text-foreground text-sm font-mono" {...props}>{children}</code>
        ) : (
          <code className={cn('text-foreground font-mono text-sm', className)} {...props}>{children}</code>
        );
      },
      pre: ({ node: _node, children, ...props }) => (
        <pre className="my-4 p-4 rounded bg-muted text-foreground text-sm overflow-x-auto" {...props}>{children}</pre>
      ),
      blockquote: sharedComponents.blockquote,
      ul: ({ node: _node, ...props }) => (
        <ul className="my-3 ml-6 list-disc" {...props} />
      ),
      ol: ({ node: _node, ...props }) => (
        <ol className="my-3 ml-6 list-decimal" {...props} />
      ),
      li: ({ node: _node, ...props }) => (
        <li className="my-1" {...props} />
      ),
      table: ({ node: _node, ...props }) => (
        <div className="my-4 overflow-x-auto">
          <table className="min-w-full border-collapse border border-border" {...props} />
        </div>
      ),
      thead: ({ node: _node, ...props }) => (
        <thead className="bg-muted" {...props} />
      ),
      th: ({ node: _node, ...props }) => (
        <th className="border border-border px-4 py-2 text-left font-semibold" {...props} />
      ),
      td: ({ node: _node, ...props }) => (
        <td className="border border-border px-4 py-2" {...props} />
      ),
      hr: sharedComponents.hr,
      img: ({ node: _node, src, ...props }) => (
        src ? <img className="max-w-full h-auto rounded my-4" src={src} {...props} /> : null
      ),
    }),
    [openWorkspaceLink],
  );

  const renderDefaultMarkdown = () => (
    <div
      className="p-6 max-w-4xl mx-auto"
      style={{
        transform: `scale(${zoom})`,
        transformOrigin: 'top center',
        transition: 'transform 0.2s ease-out',
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkLineBreakTag]}
        className="prose prose-sm dark:prose-invert max-w-none"
        components={buildMarkdownComponents()}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );

  const renderTasksView = () => {
    const percent = taskSummary.total > 0 ? (taskSummary.done / taskSummary.total) * 100 : 0;

    return (
      <div ref={tasksScrollRef} className="h-full overflow-auto">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
          <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-base font-semibold">
                  <CheckSquare className="h-4 w-4 text-primary" />
                  <span>{fileName}</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('workspace.openspec.tasks.summary', {
                    done: taskSummary.done,
                    total: taskSummary.total,
                  })}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleJumpToNextIncomplete}
                disabled={taskSummary.done >= taskSummary.total || isTaskSaving}
              >
                <ArrowDownCircle className="mr-1 h-4 w-4" />
                {isTaskSaving ? t('workspace.openspec.tasks.saving') : t('workspace.openspec.tasks.nextIncomplete')}
              </Button>
            </div>
            <div className="mt-4 space-y-2">
              <Progress value={percent} className="h-2" />
              <div className="text-xs text-muted-foreground">
                {taskSummary.total > 0 ? `${Math.round(percent)}%` : t('workspace.openspec.tasks.noTasks')}
              </div>
            </div>
          </section>

          {taskSummary.sections.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              {t('workspace.openspec.tasks.noTasks')}
            </div>
          ) : (
            taskSummary.sections.map((section) => {
              const done = section.tasks.filter((task) => task.checked).length;
              const total = section.tasks.length;
              const progress = total > 0 ? (done / total) * 100 : 0;

              return (
                <section key={section.id} className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold">{section.title}</h3>
                      <p className="text-sm text-muted-foreground">
                        {t('workspace.openspec.tasks.summary', { done, total })}
                      </p>
                    </div>
                    <div className="min-w-32">
                      <Progress value={progress} className="h-2" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    {section.tasks.map((task) => (
                      <div
                        key={task.id}
                        ref={(node) => {
                          taskRefs.current[task.id] = node;
                        }}
                        className={cn(
                          'flex items-start gap-3 rounded-xl border px-3 py-3 transition-colors',
                          task.checked ? 'border-emerald-200 bg-emerald-50/50' : 'border-border bg-background',
                        )}
                      >
                        <Checkbox
                          checked={task.checked}
                          onCheckedChange={(value) => handleTaskToggle(task.lineIndex, value === true)}
                          className="mt-0.5"
                          aria-label={task.label}
                          disabled={isTaskSaving}
                        />
                        <div className="min-w-0 flex-1">
                          <p
                            className={cn(
                              'text-sm leading-6 text-foreground',
                              task.checked && 'text-muted-foreground line-through',
                            )}
                          >
                            {task.label}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })
          )}
        </div>
      </div>
    );
  };

  const renderSpecView = () => {
    const headingLookup = new Map<string, string>();
    specOutline.forEach((requirement) => {
      headingLookup.set(`3:${requirement.title}`, requirement.id);
      requirement.scenarios.forEach((scenario) => {
        headingLookup.set(`4:${scenario.title}`, scenario.id);
      });
    });

    const scrollToHeading = (id: string) => {
      const container = specScrollRef.current;
      const element = container?.querySelector<HTMLElement>(`#${CSS.escape(id)}`);
      if (!container || !element) {
        return;
      }
      container.scrollTo({
        top: Math.max(element.offsetTop - 24, 0),
        behavior: 'smooth',
      });
    };

    const toggleRequirementExpanded = (requirementId: string) => {
      setExpandedRequirementIds((prev) =>
        prev.includes(requirementId)
          ? prev.filter((id) => id !== requirementId)
          : [...prev, requirementId],
      );
    };

    return (
      <div ref={specScrollRef} className="h-full overflow-auto">
        <div className="mx-auto flex max-w-6xl gap-6 p-6">
          <div
            className="min-w-0 flex-1"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top center',
              transition: 'transform 0.2s ease-out',
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkLineBreakTag]}
              className="prose prose-sm dark:prose-invert max-w-none"
              components={buildMarkdownComponents((text, level) => {
                const normalizedText = normalizeOpenSpecHeadingText(text, level);
                return headingLookup.get(`${level}:${normalizedText}`);
              })}
            >
              {processedContent}
            </ReactMarkdown>
          </div>

          {isSpecOutlineVisible ? (
            <aside className="sticky top-6 hidden h-fit w-72 shrink-0 rounded-2xl border border-border bg-card p-4 xl:block">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <ListTree className="h-4 w-4 text-primary" />
                  <span>{t('workspace.openspec.spec.tocTitle')}</span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setIsSpecOutlineVisible(false)}
                  aria-label={t('workspace.openspec.spec.hideToc')}
                  title={t('workspace.openspec.spec.hideToc')}
                >
                  <ListTree className="h-4 w-4" />
                </Button>
              </div>

              <div className="relative mb-3">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={specOutlineQuery}
                  onChange={(event) => setSpecOutlineQuery(event.target.value)}
                  placeholder={t('workspace.openspec.spec.searchPlaceholder')}
                  className="h-8 pl-8 text-xs"
                />
              </div>

              {filteredSpecOutline.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('workspace.openspec.spec.emptyToc')}</p>
              ) : (
                <div className="max-h-[calc(100vh-12rem)] space-y-2 overflow-y-auto pr-1">
                  {filteredSpecOutline.map((requirement) => {
                    const isExpanded = expandedRequirementIds.includes(requirement.id);
                    return (
                      <div key={requirement.id} className="space-y-1">
                        <div className="flex items-start gap-1">
                          <button
                            type="button"
                            onClick={() => toggleRequirementExpanded(requirement.id)}
                            aria-label={
                              isExpanded
                                ? t('workspace.openspec.spec.collapseRequirement')
                                : t('workspace.openspec.spec.expandRequirement')
                            }
                            title={
                              isExpanded
                                ? t('workspace.openspec.spec.collapseRequirement')
                                : t('workspace.openspec.spec.expandRequirement')
                            }
                            className="mt-0.5 rounded p-1 hover:bg-muted/60"
                          >
                            <ChevronDown
                              className={cn(
                                'h-3.5 w-3.5 transition-transform',
                                isExpanded ? 'rotate-0' : '-rotate-90',
                              )}
                            />
                          </button>
                          <button
                            type="button"
                            onClick={() => scrollToHeading(requirement.id)}
                            className={cn(
                              'flex-1 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                              activeSpecHeadingId === requirement.id
                                ? 'bg-primary/10 text-primary'
                                : 'hover:bg-muted/60',
                            )}
                          >
                            <span className="block truncate">{requirement.title}</span>
                          </button>
                        </div>
                        {isExpanded ? (
                          <div className="ml-6 space-y-1 border-l border-border pl-3">
                            {requirement.scenarios.map((scenario) => (
                              <button
                                key={scenario.id}
                                type="button"
                                onClick={() => scrollToHeading(scenario.id)}
                                className={cn(
                                  'w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                                  activeSpecHeadingId === scenario.id
                                    ? 'bg-primary/10 text-primary'
                                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                                )}
                              >
                                <span className="block truncate">{scenario.title}</span>
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </aside>
          ) : null}
        </div>
      </div>
    );
  };

  const renderPreviewContent = () => {
    if (openSpecKind === 'tasks') {
      return renderTasksView();
    }
    if (openSpecKind === 'spec') {
      return renderSpecView();
    }
    return renderDefaultMarkdown();
  };

  return (
    <div
      id="markdown-preview-container"
      className={cn(
        'h-full flex flex-col bg-background',
        isExpanded && 'fixed inset-0 z-50',
        className,
      )}
    >
      {/* 工具列 */}
      <div className="h-10 px-3 border-b border-border flex items-center justify-between bg-card flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {openSpecKind === 'tasks' ? (
            <CheckSquare className="w-4 h-4" />
          ) : openSpecKind === 'spec' ? (
            <ListTree className="w-4 h-4" />
          ) : (
            <FileText className="w-4 h-4" />
          )}
          <span>{t('workspace.fileManagement.markdown.title')}</span>
        </div>

        <div className="flex items-center gap-1">
          {isEditMode ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSave}
                title={t('workspace.fileManagement.markdown.save')}
              >
                <Save className="w-4 h-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancelEdit}
                title={t('workspace.fileManagement.markdown.cancel')}
              >
                <X className="w-4 h-4" />
              </Button>

              <div className="w-px h-4 bg-border mx-1" />

              <Button
                variant="ghost"
                size="sm"
                onClick={handleToggleEditMode}
                title={t('workspace.fileManagement.markdown.switchToPreview')}
              >
                <Eye className="w-4 h-4" />
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomOut}
                disabled={zoom <= 0.5}
                title={t('workspace.fileManagement.markdown.zoomOut')}
              >
                <ZoomOut className="w-4 h-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetZoom}
                title={t('workspace.fileManagement.markdown.resetZoom')}
              >
                <span className="text-xs min-w-[3rem] text-center">
                  {Math.round(zoom * 100)}%
                </span>
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomIn}
                disabled={zoom >= 2}
                title={t('workspace.fileManagement.markdown.zoomIn')}
              >
                <ZoomIn className="w-4 h-4" />
              </Button>

              <div className="w-px h-4 bg-border mx-1" />

              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
                title={isRefreshing
                  ? t('workspace.fileManagement.markdown.refreshing')
                  : t('workspace.fileManagement.markdown.refresh')}
                aria-label={isRefreshing
                  ? t('workspace.fileManagement.markdown.refreshing')
                  : t('workspace.fileManagement.markdown.refresh')}
              >
                <RefreshCw className={cn('w-4 h-4', isRefreshing && 'animate-spin')} />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                disabled={!content}
                title={t('workspace.fileManagement.markdown.copy')}
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleDownload}
                disabled={!content}
                title={t('workspace.fileManagement.markdown.download')}
              >
                <Download className="w-4 h-4" />
              </Button>

              <div className="w-px h-4 bg-border mx-1" />

              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsSpecOutlineVisible((prev) => !prev)}
                title={
                  isSpecOutlineVisible
                    ? t('workspace.openspec.spec.hideToc')
                    : t('workspace.openspec.spec.showToc')
                }
                aria-label={
                  isSpecOutlineVisible
                    ? t('workspace.openspec.spec.hideToc')
                    : t('workspace.openspec.spec.showToc')
                }
                className={openSpecKind === 'spec' ? '' : 'hidden'}
              >
                <ListTree className="w-4 h-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleToggleEditMode}
                title={t('workspace.fileManagement.markdown.edit')}
              >
                <Edit3 className="w-4 h-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleFullscreen}
                title={isExpanded ? t('workspace.fileManagement.markdown.exitExpanded') : t('workspace.fileManagement.markdown.expand')}
              >
                {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </Button>
            </>
          )}
        </div>
      </div>

      {contextualOpenSpecActions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-primary/5 px-3 py-2">
          {contextualOpenSpecActions.map((action) => (
            <Button
              key={action.id}
              variant={action.availability === 'enabled' ? 'default' : 'outline'}
              size="sm"
              disabled={action.availability !== 'enabled'}
              title={action.reason ?? action.recommendedReason ?? action.description}
              onClick={() => handleOpenSpecContextAction(action.draftTemplate)}
            >
              {action.title}
            </Button>
          ))}
        </div>
      ) : null}

      {/* 預覽/編輯區域 */}
      <div className="flex-1 overflow-auto bg-background">
        {isEditMode ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full h-full p-6 bg-background text-foreground font-mono text-sm resize-none focus:outline-none"
            placeholder={t('workspace.fileManagement.markdown.editPlaceholder')}
          />
        ) : content.trim() ? (
          renderPreviewContent()
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-sm">{t('workspace.fileManagement.markdown.empty')}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
