export const WORKSPACE_CHAT_ADD_REFERENCE_EVENT = 'workspace:chat:add-code-reference';
export const WORKSPACE_CHAT_INSERT_DRAFT_EVENT = 'workspace:chat:insert-draft';
export const WORKSPACE_CHAT_SEND_DRAFT_EVENT = 'workspace:chat:send-draft';

export interface ChatCodeReferenceEventDetail {
  filePath: string;
  fileName: string;
  startLine: number;
  endLine: number;
}

export const dispatchAddCodeReferenceEvent = (detail: ChatCodeReferenceEventDetail): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<ChatCodeReferenceEventDetail>(WORKSPACE_CHAT_ADD_REFERENCE_EVENT, {
      detail,
    }),
  );
};

export interface ChatDraftEventDetail {
  content: string;
  mode?: 'append' | 'replace';
}

export const dispatchInsertDraftEvent = (detail: ChatDraftEventDetail): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<ChatDraftEventDetail>(WORKSPACE_CHAT_INSERT_DRAFT_EVENT, {
      detail,
    }),
  );
};

export const dispatchSendDraftEvent = (detail: ChatDraftEventDetail): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<ChatDraftEventDetail>(WORKSPACE_CHAT_SEND_DRAFT_EVENT, {
      detail,
    }),
  );
};
