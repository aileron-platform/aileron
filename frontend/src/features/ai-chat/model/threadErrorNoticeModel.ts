import { isRunning } from './threadStatusModel';
import type { AgenticToolId } from './threadCapabilitiesModel';
import type { Thread } from './threadModel';

interface ThreadErrorNoticeModel {
  titleKey: string;
  titleParams?: Record<string, string>;
  descriptionKey: string;
  summary: string | null;
  detail: string | null;
  retryable: boolean;
}

const agentNameByTool: Record<AgenticToolId, string> = {
  claude: 'Claude',
  codex: 'Codex',
  opencode: 'OpenCode',
};

const detailFromErrorInfo = (
  errorInfo: Record<string, unknown> | null,
  summary: string | null,
): string | null => {
  if (!errorInfo || Object.keys(errorInfo).length === 0) {
    return null;
  }

  const details = { ...errorInfo };
  if (summary && details.message === summary) {
    delete details.message;
  }

  if (Object.keys(details).length === 0) {
    return null;
  }
  return JSON.stringify(details, null, 2);
};

export const buildThreadErrorNoticeModel = (thread: Thread): ThreadErrorNoticeModel | null => {
  if (isRunning(thread.status)) {
    return null;
  }
  const summary = thread.errorMessage?.trim() || null;
  const detail = detailFromErrorInfo(thread.errorInfo, summary);
  const errorCode = thread.errorCode;
  if (thread.status !== 'error' && !errorCode && !detail) {
    return null;
  }

  if (errorCode === 'prompt_too_long') {
    return {
      titleKey: 'aiChat.error.promptTooLong.title',
      descriptionKey: 'aiChat.error.promptTooLong.description',
      summary,
      detail,
      retryable: false,
    };
  }

  if (errorCode === 'invalid_tool_selection') {
    return {
      titleKey: 'aiChat.error.invalidToolSelection.title',
      descriptionKey: 'aiChat.error.invalidToolSelection.description',
      summary,
      detail,
      retryable: false,
    };
  }

  if (errorCode === 'runtime_restarted') {
    return {
      titleKey: 'aiChat.error.runtimeRestarted.title',
      descriptionKey: 'aiChat.error.runtimeRestarted.description',
      summary,
      detail,
      retryable: true,
    };
  }

  if (errorCode === 'queued_message_drain_failed') {
    return {
      titleKey: 'aiChat.error.queuedMessageDrainFailed.title',
      descriptionKey: 'aiChat.error.queuedMessageDrainFailed.description',
      summary,
      detail,
      retryable: true,
    };
  }

  if (
    !errorCode
    || errorCode === 'agent_error'
    || errorCode === 'agent_process_failed'
  ) {
    return {
      titleKey: 'aiChat.error.agentFailed.title',
      titleParams: { agentName: agentNameByTool[thread.agenticTool] },
      descriptionKey: 'aiChat.error.agentFailed.description',
      summary,
      detail,
      retryable: true,
    };
  }

  return {
    titleKey: 'aiChat.error.unknown.title',
    descriptionKey: 'aiChat.error.unknown.description',
    summary,
    detail,
    retryable: true,
  };
};
