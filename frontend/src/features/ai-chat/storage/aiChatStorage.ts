import { isRunning } from '../model/threadStatusModel';
import type { ThreadListSortMode } from '../model/threadListModel';
import type { AgenticToolId, AgentMode, WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import type { Thread } from '../model/threadModel';

interface PreferredThreadSettings {
  agenticTool: AgenticToolId;
  model: string;
  claudeMode: AgentMode | null;
}

const lastThreadKey = (userId: string, workspaceId: string) => `aichat.lastThread.${userId}.${workspaceId}`;

const lastReadKey = (userId: string, workspaceId: string, threadId: string) =>
  `aichat.lastRead.${userId}.${workspaceId}.${threadId}`;

const preferredSettingsKey = 'aichat.preferredSettings';
const threadListSortKey = (userId: string, workspaceId: string) =>
  `aichat.threadListSort.${userId}.${workspaceId}`;
const defaultThreadListSortMode: ThreadListSortMode = 'activity';
const showInitMessagesKey = 'aichat.showInitMessages';

const subscribers = new Set<() => void>();

const notifyLocalSubscribers = (): void => {
  subscribers.forEach((callback) => callback());
};

const writeItem = (key: string, value: string): void => {
  localStorage.setItem(key, value);
  // Browser storage events only fire in other tabs; same-tab surfaces need direct notification.
  notifyLocalSubscribers();
};

export const getLastThreadId = (userId: string, workspaceId: string): string | null =>
  localStorage.getItem(lastThreadKey(userId, workspaceId));

export const setLastThreadId = (userId: string, workspaceId: string, threadId: string): void => {
  writeItem(lastThreadKey(userId, workspaceId), threadId);
};

const getLastReadAt = (userId: string, workspaceId: string, threadId: string): string | null =>
  localStorage.getItem(lastReadKey(userId, workspaceId, threadId));

export const setLastReadAt = (userId: string, workspaceId: string, threadId: string, isoTime: string): void => {
  writeItem(lastReadKey(userId, workspaceId, threadId), isoTime);
};

const isPreferredThreadSettings = (value: unknown): value is PreferredThreadSettings => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.agenticTool === 'string'
    && typeof candidate.model === 'string'
    && (typeof candidate.claudeMode === 'string' || candidate.claudeMode === null)
  );
};

export const getPreferredThreadSettings = (
  capabilities: WorkspaceCapabilities,
): PreferredThreadSettings | null => {
  const raw = localStorage.getItem(preferredSettingsKey);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isPreferredThreadSettings(parsed)) return null;
    const tool = capabilities.tools.find((item) => item.id === parsed.agenticTool);
    if (!tool || !tool.models.includes(parsed.model)) return null;
    if (tool.modes) {
      if (!parsed.claudeMode || !tool.modes.includes(parsed.claudeMode)) return null;
    } else if (parsed.claudeMode !== null) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

export const setPreferredThreadSettings = (settings: PreferredThreadSettings): void => {
  writeItem(preferredSettingsKey, JSON.stringify(settings));
};

const isThreadListSortMode = (value: string | null): value is ThreadListSortMode =>
  value === 'activity' || value === 'created' || value === 'title';

export const getThreadListSortMode = (
  userId: string,
  workspaceId: string,
): ThreadListSortMode => {
  const value = localStorage.getItem(threadListSortKey(userId, workspaceId));
  return isThreadListSortMode(value) ? value : defaultThreadListSortMode;
};

export const setThreadListSortMode = (
  userId: string,
  workspaceId: string,
  mode: ThreadListSortMode,
): void => {
  writeItem(threadListSortKey(userId, workspaceId), mode);
};

export const getShowInitMessages = (): boolean => localStorage.getItem(showInitMessagesKey) === 'true';

export const setShowInitMessages = (value: boolean): void => {
  writeItem(showInitMessagesKey, value ? 'true' : 'false');
};

export const isUnread = (
  thread: Pick<Thread, 'id' | 'updatedAt' | 'status'>,
  userId: string,
  workspaceId: string,
): boolean => {
  if (thread.status === 'draft' || isRunning(thread.status)) return false;
  const lastRead = getLastReadAt(userId, workspaceId, thread.id);
  if (lastRead === null) return true;
  return Date.parse(lastRead) < Date.parse(thread.updatedAt);
};

export const subscribeLocalState = (onChange: () => void): (() => void) => {
  subscribers.add(onChange);
  const handleStorage = (event: StorageEvent): void => {
    if (event.key?.startsWith('aichat.')) onChange();
  };
  window.addEventListener('storage', handleStorage);
  return () => {
    subscribers.delete(onChange);
    window.removeEventListener('storage', handleStorage);
  };
};
