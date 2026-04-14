export const WORKSPACE_CHAT_ADD_REFERENCE_EVENT = 'workspace:chat:add-code-reference';

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
