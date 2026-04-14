import type { ChatSessionOption } from './types';

const UNTITLED_SESSION_PREFIX = 'session ';

const normalize = (value: string) => value.trim().toLowerCase();

export const isUntitledSessionTitle = (title: string, sessionId: string): boolean => {
  const trimmedTitle = title.trim();
  if (!trimmedTitle) return true;

  const normalizedTitle = normalize(trimmedTitle);
  const normalizedSessionId = normalize(sessionId);
  const shortSessionId = normalize(sessionId.slice(0, 4));

  if (normalizedTitle === normalizedSessionId || normalizedTitle === shortSessionId) {
    return true;
  }

  if (!normalizedTitle.startsWith(UNTITLED_SESSION_PREFIX)) {
    return false;
  }

  const suffix = normalizedTitle.slice(UNTITLED_SESSION_PREFIX.length).trim();
  return suffix === shortSessionId || suffix === normalizedSessionId;
};

export const resolveSessionDisplayLabel = (
  session: ChatSessionOption,
  defaultLabel: string,
): string => {
  if (isUntitledSessionTitle(session.title, session.session_id)) {
    return defaultLabel;
  }

  return session.title.trim();
};
