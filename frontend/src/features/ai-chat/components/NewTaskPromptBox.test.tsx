// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { NewTaskPromptBox } from './NewTaskPromptBox';

const threadApiMock = vi.hoisted(() => ({
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
}));

vi.mock('../api/threadApi', () => ({
  getThreadApi: () => threadApiMock,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params?.progress === undefined ? key : `${key} ${params.progress}%`
    ),
  }),
}));

vi.mock('../contexts/AiChatIntegrationContext', () => ({
  useAiChatIntegration: () => ({
    workspaceId: 'workspace-1',
    runtimeBaseUrl: 'http://runtime.test',
    fileChooser: null,
    openCanvas: null,
  }),
}));

vi.mock('@/shared/components/slash-command-picker', () => ({
  SlashCommandPickerDialog: () => null,
}));

vi.mock('@/shared/api/slashCommandApi', () => ({
  slashCommandApi: {
    listPickerItems: vi.fn(async () => []),
  },
}));

const capabilities: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['sonnet-5'],
      defaultModel: 'sonnet-5',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
  ],
};

const buildThread = (overrides: Partial<Thread> = {}): Thread => ({
  id: 'thread-new-task',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'aiChat.thread.untitled',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'draft',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: '2026-07-09T01:00:00.000Z',
  updatedAt: '2026-07-09T01:00:00.000Z',
  messages: [],
  queuedMessages: [],
  draftMessage: null,
  ...overrides,
});

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  localStorage.clear();
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
  threadApiMock.uploadAttachment.mockReset();
  threadApiMock.deleteAttachment.mockReset();
  threadApiMock.uploadAttachment.mockImplementation((_threadId: string, file: File, onProgress: (progress: number) => void) => {
    onProgress(100);
    return {
      promise: Promise.resolve({
        attachmentId: `att-${file.name}`,
        kind: file.type.startsWith('image/') ? 'image' : 'text-file',
        name: file.name,
        mimeType: file.type,
        size: file.size,
      }),
      abort: vi.fn(),
    };
  });
  threadApiMock.deleteAttachment.mockResolvedValue(undefined);
});

describe('NewTaskPromptBox', () => {
  it('submits the entered prompt with default settings', () => {
    const onSubmit = vi.fn();
    render(
      <NewTaskPromptBox
        capabilities={capabilities}
        onEnsureDraft={vi.fn(async () => buildThread())}
        onSubmit={onSubmit}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'build the login flow' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onSubmit).toHaveBeenCalledWith({
      settings: {
        agenticTool: 'claude',
        model: 'sonnet-5',
        claudeMode: 'execute',
      },
      message: {
        text: 'build the login flow',
        attachments: [],
      },
    });
  });

  it('uses the last selected settings for new task drafts', () => {
    const onSubmit = vi.fn();
    const multiToolCapabilities: WorkspaceCapabilities = {
      defaultTool: 'claude',
      tools: [
        ...capabilities.tools,
        {
          id: 'codex',
          models: ['gpt-5.6-sol'],
          defaultModel: 'gpt-5.6-sol',
          modes: null,
          defaultMode: null,
          contextWindow: 200000,
        },
      ],
    };
    localStorage.setItem(
      'aichat.preferredSettings',
      JSON.stringify({ agenticTool: 'codex', model: 'gpt-5.6-sol', claudeMode: null }),
    );
    render(
      <NewTaskPromptBox
        capabilities={multiToolCapabilities}
        onEnsureDraft={vi.fn(async () => buildThread())}
        onSubmit={onSubmit}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'use codex' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onSubmit).toHaveBeenCalledWith({
      settings: {
        agenticTool: 'codex',
        model: 'gpt-5.6-sol',
        claudeMode: null,
      },
      message: {
        text: 'use codex',
        attachments: [],
      },
    });
  });

  it('remembers settings changed before a draft is created', () => {
    const multiModelCapabilities: WorkspaceCapabilities = {
      defaultTool: 'claude',
      tools: [
        {
          ...capabilities.tools[0],
          models: ['sonnet-5', 'opus-4.8'],
          defaultModel: 'sonnet-5',
        },
      ],
    };
    render(
      <NewTaskPromptBox
        capabilities={multiModelCapabilities}
        onEnsureDraft={vi.fn(async () => buildThread())}
        onSubmit={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.model' }));
    fireEvent.click(screen.getByRole('button', { name: 'opus-4.8' }));

    expect(localStorage.getItem('aichat.preferredSettings')).toBe(JSON.stringify({
      agenticTool: 'claude',
      model: 'opus-4.8',
      claudeMode: 'execute',
    }));
  });

  it('uses the ensured draft thread for first attachment upload and removal', async () => {
    const user = userEvent.setup();
    const ensuredDraft = buildThread({ id: 'draft-for-first-attachment' });
    render(
      <NewTaskPromptBox
        capabilities={capabilities}
        onEnsureDraft={vi.fn(async () => ensuredDraft)}
        onSubmit={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    await user.upload(
      screen.getByTestId('ai-chat-file-input'),
      new File(['notes'], 'notes.txt', { type: 'text/plain' }),
    );

    await waitFor(() => {
      expect(threadApiMock.uploadAttachment).toHaveBeenCalledWith(
        'draft-for-first-attachment',
        expect.any(File),
        expect.any(Function),
      );
    });
    expect(await screen.findByText('aiChat.input.attachmentReady')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'aiChat.input.removeAttachment notes.txt' }));

    expect(threadApiMock.deleteAttachment).toHaveBeenCalledWith(
      'draft-for-first-attachment',
      'att-notes.txt',
    );
  });
});
