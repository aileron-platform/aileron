const UNTITLED_THREAD_TITLE_KEY = 'aiChat.thread.untitled';

export const resolveThreadTitle = (
  title: string,
  t: (key: string) => string,
): string => {
  if (title === UNTITLED_THREAD_TITLE_KEY) {
    return t(UNTITLED_THREAD_TITLE_KEY);
  }
  return title;
};
