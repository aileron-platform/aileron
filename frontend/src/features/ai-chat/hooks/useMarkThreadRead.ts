import { useEffect } from 'react';
import { setLastReadAt } from '../storage/aiChatStorage';
import type { Thread } from '../model/threadModel';

interface UseMarkThreadReadOptions {
  thread: Thread | null | undefined;
  workspaceId: string;
  userId: string;
}

export const useMarkThreadRead = ({ thread, workspaceId, userId }: UseMarkThreadReadOptions): void => {
  useEffect(() => {
    if (!thread) return;
    setLastReadAt(userId, workspaceId, thread.id, thread.updatedAt);
  }, [thread?.id, thread?.updatedAt, thread, userId, workspaceId]);
};
