import { describe, expect, it, vi } from 'vitest';
import { resolveThreadTitle } from './threadTitleModel';

describe('resolveThreadTitle', () => {
  it('translates the controlled untitled thread key', () => {
    const t = vi.fn((key: string) => `translated:${key}`);

    expect(resolveThreadTitle('aiChat.thread.untitled', t)).toBe('translated:aiChat.thread.untitled');
    expect(t).toHaveBeenCalledWith('aiChat.thread.untitled');
  });

  it('returns dynamic thread titles verbatim', () => {
    const t = vi.fn((key: string) => `translated:${key}`);

    expect(resolveThreadTitle('User typed title', t)).toBe('User typed title');
    expect(t).not.toHaveBeenCalled();
  });
});
