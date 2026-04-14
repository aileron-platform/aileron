import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MarkdownSidebar } from './MarkdownSidebar';
import { ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import type { ClaudeDocument } from '../data';

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    layout: {
      secondColumnCollapsed: false,
    },
    toggleSecondColumn: vi.fn(),
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'workspace.claudeCode.documents.size.badge') {
        return `${params?.size ?? ''}`;
      }

      const translations: Record<string, string> = {
        'workspace.claudeCode.documents.meta.memory.title': 'Memory',
        'workspace.claudeCode.documents.meta.slash-commands.title': 'Slash Commands',
        'workspace.claudeCode.documents.sidebar.defaultTitle': 'Documents',
        'workspace.claudeCode.documents.sidebar.searchPlaceholder': '搜尋文件',
        'workspace.claudeCode.documents.sidebar.toggle.collapse': '收合',
        'workspace.claudeCode.documents.sidebar.toggle.expand': '展開',
        'workspace.claudeCode.documents.sidebar.loading': '載入中',
        'workspace.claudeCode.documents.sidebar.empty': '沒有文件',
        'workspace.claudeCode.documents.scope.values.project': '專案',
        'workspace.claudeCode.documents.scope.values.user': '使用者',
        'workspace.claudeCode.documents.scope.values.local': '本機',
        'workspace.claudeCode.documents.scope.values.plugin': '外掛',
        'workspace.claudeCode.documents.sidebar.scope.all': '全部',
      };

      return translations[key] ?? key;
    },
  }),
}));

const buildDocument = (overrides: Partial<ClaudeDocument>): ClaudeDocument => ({
  id: 'user:test.md',
  scope: 'user',
  title: 'Test',
  description: 'desc',
  content: '# test',
  size: '12 B',
  metadata: { fileName: 'test.md' },
  ...overrides,
});

const createCollection = (items: ClaudeDocument[]) => ({
  items,
  loading: false,
  error: null,
  selectedId: items[0]?.id ?? null,
  select: vi.fn(),
  refresh: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
});

describe('MarkdownSidebar memory mode', () => {
  it('hides scope filter and scope badge for memory documents', () => {
    const memoryCollection = createCollection([
      buildDocument({
        id: 'user:memory.md',
        title: 'Memory Note',
        description: 'stored memory',
      }),
    ]);

    render(
      <ClaudeCodeContext.Provider
        value={{
          slashCommands: createCollection([]),
          outputStyles: createCollection([]),
          subagents: createCollection([]),
          memory: memoryCollection,
        }}
      >
        <MarkdownSidebar subView="memory" />
      </ClaudeCodeContext.Provider>,
    );

    expect(screen.getByText('Memory Note')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByText('使用者')).not.toBeInTheDocument();
  });

  it('keeps scope filter visible for non-memory document views', () => {
    render(
      <ClaudeCodeContext.Provider
        value={{
          slashCommands: createCollection([
            buildDocument({
              id: 'project:command.md',
              scope: 'project',
              title: 'Command',
            }),
          ]),
          outputStyles: createCollection([]),
          subagents: createCollection([]),
          memory: createCollection([]),
        }}
      >
        <MarkdownSidebar subView="slash-commands" />
      </ClaudeCodeContext.Provider>,
    );

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });
});
