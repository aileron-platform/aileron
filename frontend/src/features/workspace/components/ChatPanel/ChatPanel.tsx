import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bot } from 'lucide-react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ChatPanel');
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { ChatPanelHeader } from './ChatPanelHeader';
import { ChatMessageArea } from './ChatMessageArea';
import { ChatInputBar } from './ChatInputBar';
import { TypingIndicator } from './TypingIndicator';
import { FileChooserDialog } from './dialogs/FileChooserDialog';
import { UploadFileDialog } from './dialogs/UploadFileDialog';
import { SlashCommandPickerDialog } from '@/shared/components/slash-command-picker';
import { OpenSpecActionPickerDialog } from './OpenSpecActionPickerDialog';
import { QueuedMessagesPanel } from './QueuedMessagesPanel';
import { useChatPanelStateContext } from './chatPanelStateContext';
import {
  WORKSPACE_CHAT_ADD_REFERENCE_EVENT,
  WORKSPACE_CHAT_INSERT_DRAFT_EVENT,
  WORKSPACE_CHAT_SEND_DRAFT_EVENT,
  type ChatDraftEventDetail,
  type ChatCodeReferenceEventDetail,
} from './chatEvents';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { WorkspaceWizardModule } from '@/features/workspace-wizard/WorkspaceWizardModule';
import { useAgentSession } from './useAgentSession';
import { useAgentSessionStore } from './agentSessionStore';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  PermissionScope,
  isPermissionMode,
  type PermissionMode,
  type PermissionConfig,
  type CodexPermissionConfig,
  type ToolDecisionOption,
  type ToolDecisionType,
  type ToolDecisionOutcome,
} from './agentSessionTypes';
import {
  DEFAULT_CODEX_PERMISSION_CONFIG,
  isCodexPermissionConfig,
} from './CodexPermissionSelector';
import type { AgentMessage } from './agentSessionTypes';
import type { AskUserQuestionSubmitHandler } from './AgentContentBlockRenderer';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { slashCommandApi } from './slashCommandApi';
import { normalizeAgentType, getAgentToolConfig } from '../../features/agent-settings/utils';
import { useOpenSpecWorkspace } from '../../features/openspec/OpenSpecWorkspaceContext';
import { buildSessionResultPreviewPayload } from './previewPayload';
import { getEventDispatcher } from './agentSessionEvents';
import { syncCanvas } from '../../services/workspaceRuntimeApi';

// ============================================================================
// ChatPanel Component
// ============================================================================

export const ChatPanel: React.FC = () => {
  const { state: workspaceState, dispatch, fileTreeActions, workspaceRuntime } = useWorkspace();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [uiState, uiActions] = useChatPanelStateContext();

  const {
    state: agentState,
    sendMessage,
    createSession,
    selectSession,
    archiveSession,
    deleteSession,
    loadMoreMessages,
    stopTask,
    handleToolDecision,
    deleteQueuedMessage,
  } = useAgentSession({
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    workspaceId: workspaceRuntime.workspaceId || '',
    cliType: workspaceRuntime.cliType,
    autoConnect: true,
    gitContextId: workspaceState.versionControl.selectedGitContextId,
  });

  // Access the store for direct streaming state updates.
  const { store } = useAgentSessionStore();

  const addCodeReference = uiActions.addCodeReference;
  const { toast } = useToast();
  const { uploadFiles } = fileTreeActions;

  const [isAborting, setIsAborting] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [slashCommands, setSlashCommands] = useState<SlashCommandItem[]>([]);
  const hasLoadedSlashCommandsRef = useRef(false);
  const [permissionMode, setPermissionMode] = useState<PermissionMode>(() => {
    try {
      const saved = localStorage.getItem('chatPermissionMode');
      if (isPermissionMode(saved)) {
        return saved;
      }
    } catch (error) {
      logger.error('Failed to load permission mode from localStorage', { error });
    }
    return 'bypassPermissions';
  });
  const [codexPermissionConfig, setCodexPermissionConfig] = useState<CodexPermissionConfig>(() => {
    try {
      const saved = localStorage.getItem('chatCodexPermissionConfig');
      const parsed = saved ? JSON.parse(saved) : null;
      if (isCodexPermissionConfig(parsed)) {
        return parsed;
      }
    } catch (error) {
      logger.error('Failed to load Codex permission config from localStorage', { error });
    }
    return DEFAULT_CODEX_PERMISSION_CONFIG;
  });

  const cliType = workspaceRuntime.cliType || 'claude-code';
  const agentType = normalizeAgentType(workspaceRuntime.cliType);
  const agentConfig = useMemo(() => getAgentToolConfig(agentType), [agentType]);
  const effectivePermissionConfig = useMemo<PermissionConfig>(() => {
    if (agentType === 'codex') {
      return {
        mode: 'default',
        codex: codexPermissionConfig,
      };
    }
    return { mode: permissionMode };
  }, [agentType, codexPermissionConfig, permissionMode]);
  const {
    actions: openSpecActions,
    ensureLoaded: ensureOpenSpecLoaded,
    state: openSpecState,
    changes: openSpecChanges,
    focusChangeName: openSpecFocusChangeName,
  } = useOpenSpecWorkspace();

  useEffect(() => {
    if (!uiState.isOpenSpecDialogOpen) {
      return;
    }
    void ensureOpenSpecLoaded();
  }, [ensureOpenSpecLoaded, uiState.isOpenSpecDialogOpen]);

  const resolveDecisionOption = useCallback((
    allow: boolean,
    scope: PermissionScope | undefined,
    options?: ToolDecisionOption[]
  ) => {
    if (!options || options.length === 0) return undefined;

    if (allow) {
      if (scope && scope !== 'once') {
        const allowAlways = options.find(o => o.kind === 'allow_always');
        if (allowAlways) {
          return allowAlways.option_id || allowAlways.optionId;
        }
      }
      const allowOnce = options.find(o => o.kind === 'allow_once');
      if (allowOnce) {
        return allowOnce.option_id || allowOnce.optionId;
      }
      const fallbackAllow = options.find(o => o.kind?.startsWith('allow'));
      return fallbackAllow?.option_id || fallbackAllow?.optionId;
    }

    const rejectOnce = options.find(o => o.kind === 'reject_once');
    if (rejectOnce) {
      return rejectOnce.option_id || rejectOnce.optionId;
    }
    const rejectAlways = options.find(o => o.kind === 'reject_always');
    return rejectAlways?.option_id || rejectAlways?.optionId;
  }, []);

  const handlePermissionDecision = useCallback((requestId: string, allow: boolean, scope?: PermissionScope) => {
    const pending = agentState.pendingPermission;
    const taskId = pending?.task_id || agentState.activeTask?.task_id || '';
    const optionId = resolveDecisionOption(allow, scope, pending?.options);

    const outcome = allow ? 'selected' : (optionId ? 'selected' : 'cancelled');

    handleToolDecision({
      request_id: requestId,
      task_id: taskId,
      decision_type: 'permission',
      outcome,
      option_id: optionId,
      scope: allow ? (scope || 'once') : undefined,
      decided_by: 'user',
    });
  }, [handleToolDecision, agentState.pendingPermission, agentState.activeTask, resolveDecisionOption]);

  const handleAcpDecision = useCallback((payload: {
    requestId: string;
    decisionType: ToolDecisionType;
    outcome: ToolDecisionOutcome;
    optionId?: string;
    scope?: PermissionScope;
    content?: string;
  }) => {
    const pending = payload.decisionType === 'user_input'
      ? agentState.pendingUserInput
      : agentState.pendingPermission;
    const taskId = pending?.task_id || agentState.activeTask?.task_id || '';

    handleToolDecision({
      request_id: payload.requestId,
      task_id: taskId,
      decision_type: payload.decisionType,
      outcome: payload.outcome,
      option_id: payload.optionId,
      scope: payload.scope,
      decided_by: 'user',
      content: payload.content,
    });
  }, [handleToolDecision, agentState.pendingPermission, agentState.pendingUserInput, agentState.activeTask]);

  /**
   * 處理 AskUserQuestion 工具的使用者回覆
   * 透過 tool-decision API 將答案發送回後端
   */
  const handleAskUserQuestionSubmit: AskUserQuestionSubmitHandler = useCallback(
    async (toolUseId: string, answers: Record<string, string | string[]>) => {
      // 檢查 pendingUserInput - 這是後端發送的 tool-decision:request (user_input) 事件
      const pendingInput = agentState.pendingUserInput;

      if (!agentState.currentSessionId) {
        logger.error('Cannot submit AskUserQuestion: no active session');
        return;
      }

      // 使用 pendingUserInput 的 request_id，如果沒有則使用 toolUseId
      const requestId = pendingInput?.request_id || toolUseId;
      const taskId = pendingInput?.task_id || agentState.activeTask?.task_id || '';
      const optionId = resolveDecisionOption(true, 'once', pendingInput?.options);

      try {
        // 格式化答案為可讀的文字
        const formattedAnswers = Object.entries(answers)
          .map(([key, value]) => {
            const answerText = Array.isArray(value) ? value.join(', ') : value;
            return `${key}: ${answerText}`;
          })
          .join('\n');

        // 透過 tool-decision API 發送回答
        // 後端的 PermissionHooks 會從 reason/content 欄位讀取答案
        handleToolDecision({
          request_id: requestId,
          task_id: taskId,
          decision_type: 'user_input',
          outcome: 'selected',
          option_id: optionId,
          scope: 'once',
          decided_by: 'user',
          content: formattedAnswers,  // 使用者的答案
        });

        // 清除 pendingUserInput
        store.setPendingUserInput(null);
      } catch (error) {
        logger.error('Failed to submit AskUserQuestion answer', { error });
        toast({
          title: 'Error',
          description: error instanceof Error ? error.message : 'Failed to submit answer',
          variant: 'destructive',
        });
      }
    },
    [agentState.currentSessionId, agentState.activeTask, agentState.pendingUserInput, handleToolDecision, store, toast, resolveDecisionOption]
  );

  const handleDraftChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (import.meta.env.DEV) {
        logger.debug('handleDraftChange called', { value: event.target.value });
      }
      uiActions.setDraftMessage(event.target.value);
    },
    [uiActions]
  );
  const handleSend = useCallback(async () => {
    if (import.meta.env.DEV) {
      logger.debug('handleSend called', {
        draftMessage: uiState.draftMessage,
        pendingUploads: uiState.pendingUploads.length,
        codeReferences: uiState.codeReferences.length,
      });
    }

    if (
      !uiState.draftMessage.trim() &&
      uiState.pendingUploads.length === 0 &&
      uiState.codeReferences.length === 0
    ) {
      if (import.meta.env.DEV) {
        logger.debug('handleSend: No message content, returning.');
      }
      return;
    }

    let fullMessage = '';
    if (uiState.codeReferences.length > 0) {
      const codeRefTags = uiState.codeReferences.map(ref => {
        let relativePath = ref.filePath;
        if (relativePath.startsWith('/workspace/')) {
          relativePath = './' + relativePath.substring('/workspace/'.length);
        } else if (relativePath.startsWith('/workspace')) {
          relativePath = './' + relativePath.substring('/workspace'.length).replace(/^\//, '');
        } else if (relativePath.startsWith('/')) {
          relativePath = '.' + relativePath;
        } else if (!relativePath.startsWith('./')) {
          relativePath = './' + relativePath;
        }
        const lineRange = ref.startLine === ref.endLine ? `${ref.startLine}` : `${ref.startLine}-${ref.endLine}`;
        return `File:${relativePath}:${lineRange}`;
      }).join('\n');
      fullMessage = `${codeRefTags}\n${uiState.draftMessage.trim()}`;
    } else {
      fullMessage = uiState.draftMessage;
    }

    if (import.meta.env.DEV) {
      logger.debug('Sending message', { message: fullMessage, permissionMode });
    }

    try {
      setIsSendingMessage(true);
      await sendMessage(fullMessage, undefined, effectivePermissionConfig);
      uiActions.resetDraftMessage();
      if (uiState.pendingUploads.length > 0) uiActions.clearUploads();
      if (uiState.codeReferences.length > 0) uiActions.clearCodeReferences();
    } catch (error) {
      toast({
        title: 'Error Sending Message',
        description: error instanceof Error ? error.message : 'An unknown error occurred.',
        variant: 'destructive',
      });
    } finally {
      setIsSendingMessage(false);
    }
  }, [
    sendMessage,
    uiActions,
    uiState.codeReferences,
    uiState.draftMessage,
    uiState.pendingUploads.length,
    effectivePermissionConfig,
    permissionMode,
    toast,
  ]);

  const handleAbort = useCallback(async () => {
    if (isAborting || !agentState.activeTask) {
      return;
    }
    setIsAborting(true);

    // 立即清除本地 streaming 狀態（不等待後端響應）
    // 這確保 UI 立即停止顯示新內容
    store.endStreaming();
    store.endThinking();
    store.setStreamingContent('');
    store.setThinkingContent('');
    store.clearRunningTools();

    try {
      await stopTask();
      toast({
        title: 'Task Aborted',
        description: 'The current operation has been stopped.',
      });
    } catch (error) {
      toast({
        title: 'Abort Failed',
        description: error instanceof Error ? error.message : 'Please try again later.',
        variant: 'destructive',
      });
    } finally {
      setIsAborting(false);
    }
  }, [stopTask, agentState.activeTask, isAborting, toast, store]);

  const handleToggleCollapse = useCallback(() => {
    dispatch({ type: 'TOGGLE_RIGHT_CHAT' });
  }, [dispatch]);

  const handleToggleFullscreen = useCallback(() => {
    dispatch({ type: 'TOGGLE_CHAT_EXPANDED' });
  }, [dispatch]);

  const handleNewSession = useCallback(async () => {
    try {
      await createSession(undefined, effectivePermissionConfig);
    } catch (error) {
      toast({
        title: 'Error Creating Session',
        description: error instanceof Error ? error.message : 'An unknown error occurred.',
        variant: 'destructive',
      });
    }
  }, [createSession, effectivePermissionConfig, toast]);

  const handleClear = useCallback(async () => {
    if (agentState.currentSessionId) {
      await archiveSession(agentState.currentSessionId, 'cleared');
    }
  }, [archiveSession, agentState.currentSessionId]);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      toast({
        title: t('workspace.chat.header.sessions.deleteSuccess'),
        description: t('workspace.chat.header.sessions.deleteSuccessDescription'),
      });
    } catch (error) {
      toast({
        title: t('workspace.chat.header.sessions.deleteFailed'),
        description: error instanceof Error
          ? error.message
          : t('workspace.chat.header.sessions.deleteFailedDescription'),
        variant: 'destructive',
      });
    }
  }, [deleteSession, t, toast]);

  const handleExport = useCallback(() => {
    // This needs to be re-implemented based on AgentMessage structure
    const transcript = agentState.messages
      .map(msg => `[${msg.role}] ${getPreviewFromContent(msg.content_blocks)}`)
      .join('\n');
    if (transcript) {
      void navigator.clipboard?.writeText(transcript).catch(() => {
        logger.info('Conversation export', { transcript });
      });
      toast({ title: 'Copied to Clipboard', description: 'The conversation has been copied.' });
    }
  }, [agentState.messages, toast]);

  const handleWorkspaceFileSelect = useCallback(
    (path: string) => {
      const normalizedPath = path.startsWith('/') ? path.substring(1) : path;
      const mention = `@./${normalizedPath}`;
      const trimmed = uiState.draftMessage.trimEnd();
      const nextValue = trimmed.length > 0 ? `${trimmed} ${mention}` : mention;
      uiActions.setDraftMessage(nextValue);
    },
    [uiActions, uiState.draftMessage]
  );

  const handleOpenMessagePreview = useCallback(
    (message: AgentMessage) => {
      const messageText = message.content_blocks
        ?.filter(b => b.type === 'text')
        .map(b => (b as any).text as string)
        .join('\n') ?? '';

      if (/<artifact[^>]*type="web-canvas"/.test(messageText)) {
        dispatch({ type: 'SET_CANVAS_SUB_VIEW', payload: 'web-canvas' });
        dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'canvas' });
        dispatch({ type: 'ENSURE_NAVIGATION_ITEM_EXPANDED', payload: 'canvas' });
        navigate('/workspaces/canvas/web-canvas');
        if (workspaceRuntime.runtimeBaseUrl && workspaceRuntime.workspaceId) {
          syncCanvas(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId).catch(err => {
            logger.error('Canvas sync failed from artifact preview', { error: err });
          });
        }
        return;
      }

      const previewPayload = buildSessionResultPreviewPayload(message, agentState.tasks);
      if (!previewPayload) return;

      dispatch({ type: 'SET_CANVAS_SESSION_RESULT', payload: previewPayload });
      dispatch({ type: 'SET_CANVAS_SUB_VIEW', payload: 'session-result' });
      dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'canvas' });
      dispatch({ type: 'ENSURE_NAVIGATION_ITEM_EXPANDED', payload: 'canvas' });
      navigate('/workspaces/canvas/session-result');
    },
    [dispatch, navigate, agentState.tasks, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]
  );

  const typingIndicator = useMemo(() => <TypingIndicator t={t} />, [t]);
  const viewMode = workspaceState.chatExpanded ? 'detailed' : 'compact';

  const handleSlashCommandSelect = useCallback(
    (command: SlashCommandItem) => {
      const slashCommand = command?.invocation
        || `/${command?.displayName || (typeof command === 'string' ? command : String(command))}`;
      const trimmed = uiState.draftMessage.trimEnd();
      const nextValue = trimmed.length > 0 ? `${trimmed} ${slashCommand}` : slashCommand;
      uiActions.setDraftMessage(nextValue);
    },
    [uiActions, uiState.draftMessage]
  );

  const handlePermissionModeChange = useCallback((mode: string) => {
    if (!isPermissionMode(mode)) {
      logger.warn('Ignored invalid permission mode selection', { mode });
      return;
    }
    setPermissionMode(mode);
  }, []);

  const handleOpenSpecActionSelect = useCallback((nextDraft: string) => {
    const trimmed = uiState.draftMessage.trimEnd();
    const nextValue = trimmed.length > 0 ? `${trimmed} ${nextDraft.trim()}` : nextDraft.trim();
    uiActions.setDraftMessage(nextValue);
  }, [uiActions, uiState.draftMessage]);

  const handleDeleteQueuedMessage = useCallback(async (messageId: string) => {
    try {
      await deleteQueuedMessage(messageId);
      toast({
        title: t('workspace.chat.queue.deleted'),
        description: t('workspace.chat.queue.deletedDescription'),
      });
    } catch (error) {
      const status = typeof error === 'object' && error !== null && 'status' in error
        ? (error as { status?: number }).status
        : undefined;
      toast({
        title: t('workspace.chat.queue.deleteError'),
        description: status === 409
          ? t('workspace.chat.queue.alreadyProcessing')
          : error instanceof Error ? error.message : t('workspace.chat.queue.unknownDeleteError'),
        variant: 'destructive',
      });
    }
  }, [deleteQueuedMessage, toast, t]);

  const handleCopyQueuedMessage = useCallback((content: string) => {
    void navigator.clipboard?.writeText(content).then(() => {
      toast({
        title: t('workspace.chat.queue.copied'),
        description: t('workspace.chat.queue.copiedDescription'),
      });
    }).catch(() => {
      logger.error('Failed to copy to clipboard');
    });
  }, [toast, t]);

  useEffect(() => {
    const dispatcher = getEventDispatcher();
    const unsubscribe = dispatcher.subscribe({
      onQueueProcessingFailed: (sessionId, payload) => {
        if (sessionId !== agentState.currentSessionId) return;
        toast({
          title: t('workspace.chat.queue.processingFailed'),
          description: payload.error_message || t('workspace.chat.queue.processingFailedDescription'),
          variant: 'destructive',
        });
      },
    });

    return () => {
      unsubscribe();
    };
  }, [agentState.currentSessionId, toast, t]);

  const handleUploadConfirm = useCallback(async () => {
    if (uiState.pendingUploads.length === 0) {
      uiActions.closeUploadDialog();
      return;
    }
    uiActions.setUploads(prev => prev.map(item => ({ ...item, status: 'uploading' })));
    const currentUploads = uiState.pendingUploads;
    const result = await uploadFiles({
      files: currentUploads.map(item => item.file),
      targetPath: '/tmp',
      useSystemTmp: true,
      // ChatPanel keeps attachment staging semantics and does not auto-extract ZIP files here.
      archiveAction: 'store',
      keepArchive: false,
      conflictStrategy: 'rename',
    });
    if (!result.success) {
      uiActions.setUploads(prev => prev.map(item => ({ ...item, status: 'error' })));
      toast({
        title: t('workspace.chat.dialogs.upload.title'),
        description: result.message,
        variant: 'destructive',
      });
      return;
    }
    uiActions.setUploads(prev => prev.map(item => ({ ...item, status: 'ready' })));
    toast({
      title: t('workspace.chat.dialogs.upload.title'),
      description: result.message,
    });
    if (result.data?.uploadedPaths && Array.isArray(result.data.uploadedPaths)) {
      const filePaths = result.data.uploadedPaths
        .map((path: string) => `@${path}`)
        .join(' ');
      const trimmed = uiState.draftMessage.trimEnd();
      const nextValue = trimmed.length > 0 ? `${trimmed} ${filePaths}` : filePaths;
      uiActions.setDraftMessage(nextValue);
    }
    uiActions.closeUploadDialog();
  }, [t, toast, uiActions, uiState.draftMessage, uiState.pendingUploads, uploadFiles]);

  useEffect(() => {
    try {
      localStorage.setItem('chatPermissionMode', permissionMode);
    } catch (error) {
      logger.error('Failed to save permission mode to localStorage', { error });
    }
  }, [permissionMode]);

  useEffect(() => {
    try {
      localStorage.setItem('chatCodexPermissionConfig', JSON.stringify(codexPermissionConfig));
    } catch (error) {
      logger.error('Failed to save Codex permission config to localStorage', { error });
    }
  }, [codexPermissionConfig]);

  const loadSlashCommands = useCallback(async () => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setSlashCommands([]);
      return;
    }

    try {
      const commands = await slashCommandApi.listPickerItems(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        agentConfig.apiPathPrefix,
        agentConfig.availableScopes,
      );
      setSlashCommands(commands);
      hasLoadedSlashCommandsRef.current = true;
    } catch (error) {
      logger.error('Failed to load slash commands and skills', { error });
      setSlashCommands([]);
    }
  }, [
    workspaceRuntime.runtimeBaseUrl,
    workspaceRuntime.workspaceId,
    agentConfig.apiPathPrefix,
    agentConfig.availableScopes,
  ]);

  const handleOpenSlashDialog = useCallback(() => {
    if (!hasLoadedSlashCommandsRef.current) {
      void loadSlashCommands();
    }
    uiActions.openSlashDialog();
  }, [loadSlashCommands, uiActions]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId: workspaceRuntime.workspaceId,
    features: ['slashCommands', 'skills'],
    onRefresh: loadSlashCommands,
  });

  React.useEffect(() => {
    const handleAddReference = (event: Event) => {
      const customEvent = event as CustomEvent<ChatCodeReferenceEventDetail>;
      const detail = customEvent.detail;
      if (!detail) return;
      addCodeReference({
        filePath: detail.filePath,
        fileName: detail.fileName,
        startLine: detail.startLine,
        endLine: detail.endLine,
      });
      if (workspaceState.rightChatCollapsed) {
        dispatch({ type: 'SET_RIGHT_CHAT_COLLAPSED', payload: false });
      }
    };
    window.addEventListener(WORKSPACE_CHAT_ADD_REFERENCE_EVENT, handleAddReference);
    return () => {
      window.removeEventListener(WORKSPACE_CHAT_ADD_REFERENCE_EVENT, handleAddReference);
    };
  }, [addCodeReference, dispatch, workspaceState.rightChatCollapsed]);

  React.useEffect(() => {
    const openPanel = () => {
      if (workspaceState.rightChatCollapsed) {
        dispatch({ type: 'SET_RIGHT_CHAT_COLLAPSED', payload: false });
      }
    };
    const applyDraft = (detail?: ChatDraftEventDetail) => {
      if (!detail?.content) return;
      uiActions.setDraftMessage(
        detail.mode === 'append' && uiState.draftMessage
          ? `${uiState.draftMessage}\n\n${detail.content}`
          : detail.content
      );
      openPanel();
    };
    const handleInsertDraft = (event: Event) => {
      applyDraft((event as CustomEvent<ChatDraftEventDetail>).detail);
    };
    const handleSendDraft = (event: Event) => {
      const detail = (event as CustomEvent<ChatDraftEventDetail>).detail;
      if (!detail?.content) return;
      openPanel();
      sendMessage(detail.content, undefined, effectivePermissionConfig).catch(err => {
        logger.error('Failed to send form answers', { error: err });
      });
    };
    window.addEventListener(WORKSPACE_CHAT_INSERT_DRAFT_EVENT, handleInsertDraft);
    window.addEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, handleSendDraft);
    return () => {
      window.removeEventListener(WORKSPACE_CHAT_INSERT_DRAFT_EVENT, handleInsertDraft);
      window.removeEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, handleSendDraft);
    };
  }, [dispatch, uiActions, uiState.draftMessage, workspaceState.rightChatCollapsed, sendMessage, effectivePermissionConfig]);

  const hasActiveConversation = agentState.messages.length > 0 || !!agentState.activeTask;

  // Find current session to check its status
  const currentSession = useMemo(() => {
    if (!agentState.currentSessionId) return null;
    return agentState.sessions.find(s => s.session_id === agentState.currentSessionId) || null;
  }, [agentState.currentSessionId, agentState.sessions]);

  // Session is active when streaming/thinking, has queued messages, sending message, or task is actively running
  const hasQueuedMessages = agentState.messages.some(m => m.queued === true);

  // Check all tasks for the current session so multi-task sessions stay active correctly.
  const isTaskActive = agentState.tasks.some(task =>
    task.session_id === agentState.currentSessionId &&
    ['created', 'running', 'stopping', 'awaiting_permission'].includes(task.status)
  );

  const isSessionActive =
    agentState.isStreaming ||
    agentState.isThinking ||
    isSendingMessage ||
    hasQueuedMessages ||
    agentState.queuedMessages.length > 0 ||
    isTaskActive;

  return (
    <div
      className={cn(
        'flex h-full flex-col bg-card text-foreground',
        workspaceState.rightChatCollapsed ? 'items-center' : '',
        workspaceState.chatExpanded ? 'max-w-full' : ''
      )}
    >
      <ChatPanelHeader
        isCollapsed={workspaceState.rightChatCollapsed}
        isExpanded={workspaceState.chatExpanded}
        sessionId={agentState.currentSessionId}
        isConnected={agentState.connectionStatus === 'open'}
        sessions={agentState.sessions.map(s => ({
          session_id: s.session_id,
          title: s.title ?? '',
        }))}
        selectedSessionId={agentState.currentSessionId}
        isLoadingSessions={agentState.isLoadingSessions}
        hasActiveConversation={hasActiveConversation}
        hasPendingNewConversation={!agentState.currentSessionId && uiState.draftMessage.length > 0}
        isSelectedSessionDeleteBlocked={isSessionActive}
        onToggleCollapse={handleToggleCollapse}
        onToggleFullscreen={handleToggleFullscreen}
        onNewSession={handleNewSession}
        onRefresh={() => { /* loadSessions is handled by the hook */ }}
        onClear={handleClear}
        onExport={handleExport}
        onSessionSelect={selectSession}
        onSessionDelete={handleDeleteSession}
        t={t}
      />

      {!workspaceState.rightChatCollapsed ? (
        <>
          <ChatMessageArea
            messages={agentState.messages}
            hasActiveRequests={isSessionActive}
            hasActiveConversation={hasActiveConversation}
            onNewSession={handleNewSession}
            typingIndicator={typingIndicator}
            t={t}
            showTimestamp={viewMode === 'detailed'}
            totalMessages={agentState.totalMessages}
            isLoadingMoreMessages={agentState.isLoadingMessages}
            hasMoreMessages={agentState.hasMoreMessages}
            onLoadMoreMessages={loadMoreMessages}
            onPermissionDecision={handlePermissionDecision}
            onAcpDecision={handleAcpDecision}
            pendingPermission={agentState.pendingPermission}
            pendingUserInput={agentState.pendingUserInput}
            agentTool={currentSession?.agentic_tool || 'claude-code'}
            streamingContent={agentState.streamingContent}
            isStreaming={agentState.isStreaming}
            thinkingContent={agentState.thinkingContent}
            isThinking={agentState.isThinking}
            runningTools={agentState.runningTools}
            onPreviewMessage={handleOpenMessagePreview}
            previewLabel={t('workspace.chat.messages.viewResult')}
            onAskUserQuestionSubmit={handleAskUserQuestionSubmit}
            activeTaskId={agentState.activeTask?.task_id}
          />
          <QueuedMessagesPanel
            messages={agentState.queuedMessages}
            maxQueueSize={5}
            onDelete={handleDeleteQueuedMessage}
            onCopy={handleCopyQueuedMessage}
            t={t}
          />
          <ChatInputBar
            value={uiState.draftMessage}
            isConnected={agentState.connectionStatus === 'open'}
            hasActiveRequests={isSessionActive}
            isAborting={isAborting}
            attachments={uiState.pendingUploads}
            codeReferences={uiState.codeReferences}
            cliType={cliType}
            permissionMode={permissionMode}
            codexPermissionConfig={codexPermissionConfig}
            onChange={handleDraftChange}
            onSend={handleSend}
            onAbort={handleAbort}
            onOpenFilePicker={uiActions.openFileDialog}
            onOpenUploadDialog={uiActions.openUploadDialog}
            onOpenSlashDialog={handleOpenSlashDialog}
            onOpenOpenSpecDialog={uiActions.openOpenSpecDialog}
            onRemoveAttachment={uiActions.removeUpload}
            onRemoveCodeReference={uiActions.removeCodeReference}
            onPermissionModeChange={handlePermissionModeChange}
            onCodexPermissionConfigChange={setCodexPermissionConfig}
            t={t}
          />
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center justify-center text-muted-foreground">
            <Bot className="h-8 w-8" />
          </div>
        </div>
      )}

      <FileChooserDialog
        open={uiState.isFileDialogOpen}
        onOpenChange={(open) => (open ? uiActions.openFileDialog() : uiActions.closeFileDialog())}
        onFileSelect={handleWorkspaceFileSelect}
        t={t}
      />

      <UploadFileDialog
        open={uiState.isUploadDialogOpen}
        onOpenChange={(open) => (open ? uiActions.openUploadDialog() : uiActions.closeUploadDialog())}
        uploads={uiState.pendingUploads}
        onSelectFiles={uiActions.queueUploads}
        onRemoveUpload={uiActions.removeUpload}
        onClearUploads={uiActions.clearUploads}
        onConfirm={handleUploadConfirm}
        t={t}
      />

      <SlashCommandPickerDialog
        open={uiState.isSlashDialogOpen}
        onOpenChange={(open) => (open ? uiActions.openSlashDialog() : uiActions.closeSlashDialog())}
        commands={slashCommands}
        onSelect={handleSlashCommandSelect}
        availableScopes={agentConfig.availableScopes}
        labels={{
          title: t('workspace.chat.dialogs.slash.title'),
          description: t('workspace.chat.dialogs.slash.description'),
          searchPlaceholder: t('workspace.chat.dialogs.slash.searchPlaceholder'),
          empty: t('workspace.chat.dialogs.slash.empty'),
          scope: {
            all: t('workspace.chat.dialogs.slash.scopes.all'),
            project: t('workspace.chat.dialogs.slash.scopes.project'),
            user: t('workspace.chat.dialogs.slash.scopes.user'),
            plugin: t('workspace.chat.dialogs.slash.scopes.plugin'),
          },
          kind: {
            'slash-command': t('workspace.chat.dialogs.slash.types.slashCommand'),
            skill: t('workspace.chat.dialogs.slash.types.skill'),
          },
        }}
      />

      <OpenSpecActionPickerDialog
        open={uiState.isOpenSpecDialogOpen}
        onOpenChange={(open) => (open ? uiActions.openOpenSpecDialog() : uiActions.closeOpenSpecDialog())}
        actions={openSpecActions}
        changes={openSpecChanges}
        focusedChangeName={openSpecFocusChangeName}
        state={openSpecState}
        onSelect={handleOpenSpecActionSelect}
      />


      <WorkspaceWizardModule
        open={uiState.isWorkspaceWizardOpen}
        onOpenChange={(open) => (open ? uiActions.openWorkspaceWizard() : uiActions.closeWorkspaceWizard())}
        t={t}
      />
    </div>
  );
};

// Helper function to extract preview from content blocks
function getPreviewFromContent(content?: any[]): string {
  if (!content || content.length === 0) return '';
  const textBlock = content.find(b => b.type === 'text');
  return textBlock?.text || `[${content[0].type}]`;
}


export default ChatPanel;
