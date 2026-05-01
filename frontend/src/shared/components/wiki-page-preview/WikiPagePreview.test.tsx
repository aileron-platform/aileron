import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { WikiPagePreview } from './index';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => params?.defaultValue ?? key,
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(async () => ({
    frontmatter: { title: 'OpenAI', type: 'entity', tags: ['ai'], sources: ['openai.md'] },
    body: '# OpenAI\n\nSee [[concepts/llm|LLM]].',
    resolved: {
      sources: [{ name: 'openai.md', path: 'raw/sources/openai.md', exists: true }],
      related: [{ slug: 'concepts/llm', path: 'wiki/concepts/llm.md', title: 'LLM', exists: true }],
    },
  })),
  },
}));

describe('WikiPagePreview', () => {
  it('renders page frontmatter and navigates from wikilinks and sources', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onSourceOpen = vi.fn();

    render(
      <WikiPagePreview
        kbId="kb-1"
        path="wiki/entities/openai.md"
        onNavigate={onNavigate}
        onSourceOpen={onSourceOpen}
      />,
    );

    expect((await screen.findAllByText('OpenAI')).length).toBeGreaterThan(0);
    await user.click(screen.getAllByRole('button', { name: 'LLM' })[0]);
    expect(onNavigate).toHaveBeenCalledWith('wiki/concepts/llm.md');

    await user.click(screen.getByRole('button', { name: /openai.md/ }));
    await waitFor(() => expect(onSourceOpen).toHaveBeenCalledWith('raw/sources/openai.md'));
  });
});
