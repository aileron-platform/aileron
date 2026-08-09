import { useSyncExternalStore } from 'react';
import { getShowInitMessages, setShowInitMessages, subscribeLocalState } from '../storage/aiChatStorage';

export const useShowInitMessages = (): [boolean, (value: boolean) => void] => {
  const showInitMessages = useSyncExternalStore(subscribeLocalState, getShowInitMessages);
  return [showInitMessages, setShowInitMessages];
};
