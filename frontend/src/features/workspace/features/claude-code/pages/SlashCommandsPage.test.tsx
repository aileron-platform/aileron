import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import SlashCommandsPage from './SlashCommandsPage';
import { ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import type { ClaudeDocument } from '../types';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'workspace.claudeCode.documents.stats.total') {
        return `共 ${params?.count ?? 0} 項`;
      }
      if (key === 'workspace.claudeCode.documents.size.badge') {
        return `大小：${params?.size ?? ''}`;
      }

      const translations: Record<string, string> = {
        'workspace.claudeCode.documents.meta.slash-commands.title': 'Slash Command 設定',
        'workspace.claudeCode.documents.actions.refresh': '重整',
        'workspace.claudeCode.documents.actions.edit': '編輯',
        'workspace.claudeCode.documents.actions.copyContent': '複製內容',
        'workspace.claudeCode.documents.actions.download': '下載',
        'workspace.claudeCode.documents.actions.delete': '刪除',
        'workspace.claudeCode.documents.loading': '載入資料中',
        'workspace.claudeCode.documents.scope.values.project': '專案',
        'workspace.claudeCode.documents.scope.values.user': '個人',
        'workspace.claudeCode.slashCommands.actions.create': '新增 Slash Command',
        'workspace.claudeCode.slashCommands.empty.title': '尚未建立任何 Slash Command',
        'workspace.claudeCode.slashCommands.empty.description': '請建立新的指令。',
        'workspace.claudeCode.slashCommands.pageTitle': 'Slash Command 設定',
      };

      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <div>{content}</div>,
}));

const buildDocument = (overrides: Partial<ClaudeDocument>): ClaudeDocument => ({
  id: 'project:first.md',
  title: 'First',
  description: 'first command',
  content: 'first command content',
  scope: 'project',
  size: '1KB',
  metadata: { fileName: 'first.md' },
  ...overrides,
});

const createCollection = (items: ClaudeDocument[], selectedId: string | null = items[0]?.id ?? null) => ({
  items,
  loading: false,
  error: null,
  selectedId,
  select: vi.fn(),
  refresh: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
});

describe('SlashCommandsPage', () => {
  it('renders the slash command selected by ClaudeCodeProvider', () => {
    const first = buildDocument({
      id: 'project:first.md',
      title: 'First',
      content: 'first command content',
    });
    const second = buildDocument({
      id: 'project:second.md',
      title: 'Second',
      content: 'second command content',
    });

    render(
      <ClaudeCodeContext.Provider
        value={{
          slashCommands: createCollection([first, second], second.id),
          outputStyles: createCollection([]),
          subagents: createCollection([]),
          memory: createCollection([]),
        }}
      >
        <SlashCommandsPage />
      </ClaudeCodeContext.Provider>,
    );

    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getByText('second command content')).toBeInTheDocument();
    expect(screen.queryByText('first command content')).not.toBeInTheDocument();
  });
});
