import { render, screen, fireEvent, act } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import SlashCommandsPage from './SlashCommandsPage';
import { ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import type { ClaudeDocument } from '../data';

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <article data-testid="md-content">{content}</article>,
}));

vi.mock('../../agent-settings/components/dialogs/AgentCommandDialog', () => ({
  AgentCommandDialog: ({ open }: { open: boolean }) =>
    open ? <div data-testid="agent-command-dialog" /> : null,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && typeof params.count === 'number') return `${key}:${params.count}`;
      if (params && typeof params.size === 'string') return `${params.size}`;
      return key;
    },
  }),
}));

const buildDocument = (overrides: Partial<ClaudeDocument>): ClaudeDocument => ({
  id: 'project:hello.md',
  scope: 'project',
  title: 'hello.md',
  description: 'desc',
  content: '# hello',
  size: '12 B',
  metadata: { fileName: 'hello.md' },
  ...overrides,
});

const createCollection = (
  items: ClaudeDocument[],
  overrides: Partial<ReturnType<typeof baseCollection>> = {},
) => ({
  ...baseCollection(items),
  ...overrides,
});

const baseCollection = (items: ClaudeDocument[]) => ({
  items,
  loading: false,
  error: null as string | null,
  selectedId: items[0]?.id ?? null,
  select: vi.fn(),
  refresh: vi.fn().mockResolvedValue(undefined),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
});

const renderWithContext = (
  slashCommands: ReturnType<typeof createCollection>,
) =>
  render(
    <ClaudeCodeContext.Provider
      value={{
        slashCommands,
        outputStyles: createCollection([]),
        subagents: createCollection([]),
        memory: createCollection([]),
      }}
    >
      <SlashCommandsPage />
    </ClaudeCodeContext.Provider>,
  );

describe('Claude SlashCommandsPage', () => {
  it('shows loading state when ClaudeCodeContext is missing', () => {
    render(<SlashCommandsPage />);
    expect(screen.getByText('workspace.claudeCode.documents.loading')).toBeInTheDocument();
  });

  it('renders the document indicated by context selectedId, not the first item', () => {
    // 第二欄 sidebar 把 selectedId 指到第二筆，第三欄必須跟著切。
    const docs = [
      buildDocument({ id: 'project:alpha.md', title: 'alpha.md', content: 'alpha body' }),
      buildDocument({ id: 'project:beta.md', title: 'beta.md', content: 'beta body' }),
    ];
    const collection = createCollection(docs, { selectedId: 'project:beta.md' });

    renderWithContext(collection);

    expect(screen.getByRole('heading', { name: 'beta.md' })).toBeInTheDocument();
    expect(screen.getByTestId('md-content')).toHaveTextContent('beta body');
    expect(screen.queryByText('alpha body')).not.toBeInTheDocument();
  });

  it('reflects context updates when selectedId changes (shared state with sidebar)', () => {
    const docs = [
      buildDocument({ id: 'project:alpha.md', title: 'alpha.md', content: 'alpha body' }),
      buildDocument({ id: 'project:beta.md', title: 'beta.md', content: 'beta body' }),
    ];
    const collection = createCollection(docs, { selectedId: 'project:alpha.md' });

    const { rerender } = renderWithContext(collection);
    expect(screen.getByRole('heading', { name: 'alpha.md' })).toBeInTheDocument();

    rerender(
      <ClaudeCodeContext.Provider
        value={{
          slashCommands: { ...collection, selectedId: 'project:beta.md' },
          outputStyles: createCollection([]),
          subagents: createCollection([]),
          memory: createCollection([]),
        }}
      >
        <SlashCommandsPage />
      </ClaudeCodeContext.Provider>,
    );
    expect(screen.getByRole('heading', { name: 'beta.md' })).toBeInTheDocument();
  });

  it('navigation buttons call collection.select (delegates state to context)', () => {
    const docs = [
      buildDocument({ id: 'project:alpha.md', title: 'alpha.md' }),
      buildDocument({ id: 'project:beta.md', title: 'beta.md' }),
    ];
    const collection = createCollection(docs, { selectedId: 'project:alpha.md' });

    renderWithContext(collection);

    // ChevronRight 是第三欄的 next button；按下應透過 context 切到下一筆。
    const buttons = screen.getAllByRole('button');
    const nextBtn = buttons.find((b) => b.querySelector('svg.lucide-chevron-right'));
    expect(nextBtn).toBeDefined();
    fireEvent.click(nextBtn!);

    expect(collection.select).toHaveBeenCalledWith('project:beta.md');
  });

  it('refresh action calls collection.refresh', async () => {
    const collection = createCollection([
      buildDocument({ id: 'project:alpha.md', title: 'alpha.md' }),
    ]);

    renderWithContext(collection);

    const refreshBtn = screen
      .getAllByRole('button')
      .find((b) => b.textContent?.includes('refresh'));
    expect(refreshBtn).toBeDefined();
    await act(async () => {
      fireEvent.click(refreshBtn!);
    });

    expect(collection.refresh).toHaveBeenCalled();
  });

  it('shows empty state when there are no slash commands', () => {
    renderWithContext(createCollection([]));

    expect(
      screen.getByText('workspace.agentSettings.common.slashCommands.empty.title'),
    ).toBeInTheDocument();
  });
});
