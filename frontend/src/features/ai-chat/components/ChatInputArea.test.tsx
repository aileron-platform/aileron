// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render as renderTestingLibrary, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState, type ReactElement, type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AiChatIntegrationProvider,
  type AiChatFileChooserProps,
} from '../contexts/AiChatIntegrationContext';
import { WORKSPACE_FILE_REFERENCE_MIME } from '@/shared/components/file-workbench';
import type { Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import type { AiChatHandoffRequest } from '../model/chatHandoffModel';
import { ChatInputArea } from './ChatInputArea';

const threadApiMock = vi.hoisted(() => ({
  transcribeAudio: vi.fn(),
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
}));

const workspaceMock = vi.hoisted(() => ({
  runtimeBaseUrl: 'http://runtime.test' as string | null,
}));

const integrationMock = vi.hoisted(() => ({
  codeReference: null as {
    filePath: string;
    fileName: string;
    startLine: number;
    endLine: number;
  } | null,
  clearCodeReference: vi.fn(),
}));

const slashCommandApiMock = vi.hoisted(() => ({
  listPickerItems: vi.fn(async () => []),
}));

vi.mock('../api/threadApi', () => ({
  getThreadApi: () => (workspaceMock.runtimeBaseUrl ? threadApiMock : null),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.progress !== undefined) {
        return `${key} ${params.progress}%`;
      }
      if (params?.line !== undefined) {
        return `${key} ${params.line}`;
      }
      if (params?.startLine !== undefined && params?.endLine !== undefined) {
        return `${key} ${params.startLine}-${params.endLine}`;
      }
      return key;
    },
  }),
}));

vi.mock('@/shared/components/slash-command-picker', () => ({
  SlashCommandPickerDialog: ({
    open,
    onOpenChange,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
  }) => (
    open ? (
      <div role="dialog" aria-label="slash-command-picker">
        <button type="button" onClick={() => onOpenChange(false)}>
          close-slash-command-picker
        </button>
      </div>
    ) : null
  ),
}));

vi.mock('@/shared/api/slashCommandApi', () => ({
  slashCommandApi: slashCommandApiMock,
}));

const TestFileChooser = ({ open, onFileSelect }: AiChatFileChooserProps) => (
  open ? (
    <button type="button" onClick={() => onFileSelect('/src/App.tsx')}>
      choose-workspace-file
    </button>
  ) : null
);

const IntegrationWrapper = ({ children }: { children: ReactNode }) => {
  const [codeReference, setCodeReference] = useState(integrationMock.codeReference);
  return (
    <AiChatIntegrationProvider
      value={{
        workspaceId: 'workspace-1',
        runtimeBaseUrl: workspaceMock.runtimeBaseUrl,
        fileChooser: TestFileChooser,
        openCanvas: null,
        codeReference,
        clearCodeReference: () => {
          integrationMock.clearCodeReference();
          setCodeReference(null);
        },
        pendingHandoff: null,
        handoffToAiChat: null,
        completeHandoff: null,
        failHandoff: null,
      }}
    >
      {children}
    </AiChatIntegrationProvider>
  );
};

const render = (element: ReactElement) => renderTestingLibrary(element, {
  wrapper: IntegrationWrapper,
});

afterEach(() => {
  cleanup();
});

class FakeMediaRecorder {
  static latest: FakeMediaRecorder | null = null;

  ondataavailable: ((event: { data: Blob }) => void) | null = null;

  onstop: (() => void | Promise<void>) | null = null;

  constructor() {
    FakeMediaRecorder.latest = this;
  }

  start() {}

  stop() {
    this.ondataavailable?.({ data: new Blob(['voice'], { type: 'audio/webm' }) });
    void this.onstop?.();
  }
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
  FakeMediaRecorder.latest = null;
  workspaceMock.runtimeBaseUrl = 'http://runtime.test';
  integrationMock.codeReference = null;
  integrationMock.clearCodeReference.mockReset();
  Object.defineProperty(global.navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
      }),
    },
  });
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder);
  threadApiMock.transcribeAudio.mockReset();
  threadApiMock.uploadAttachment.mockReset();
  threadApiMock.deleteAttachment.mockReset();
  slashCommandApiMock.listPickerItems.mockReset();
  slashCommandApiMock.listPickerItems.mockResolvedValue([]);
  threadApiMock.transcribeAudio.mockResolvedValue({ text: 'voice transcript' });
  threadApiMock.uploadAttachment.mockImplementation((_threadId: string, file: File, onProgress: (progress: number) => void) => {
    onProgress(50);
    return {
      promise: Promise.resolve({
        attachmentId: `att-${file.name}`,
        kind: file.type === 'application/pdf' ? 'pdf' : file.type.startsWith('image/') ? 'image' : 'text-file',
        name: file.name,
        mimeType: file.type,
        size: file.size,
      }),
      abort: vi.fn(),
    };
  });
  threadApiMock.deleteAttachment.mockResolvedValue(undefined);
});

const capabilities: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['sonnet-5', 'opus-4.8'],
      defaultModel: 'sonnet-5',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
  ],
};

const buildThread = (overrides: Partial<Thread> = {}): Thread => ({
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'aiChat.mock.threadTitles.draft',
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

describe('ChatInputArea', () => {
  it('shows a voice input button in the input toolbar', () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.input.voice.start' })).toBeInTheDocument();
  });

  it('places the slash command button before the voice input button', () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const slashButton = screen.getByRole('button', { name: 'aiChat.input.slashCommand' });
    const voiceButton = screen.getByRole('button', { name: 'aiChat.input.voice.start' });

    expect(slashButton.compareDocumentPosition(voiceButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('loads skills for the tool selected immediately before opening the slash picker', async () => {
    const capabilitiesWithCodex: WorkspaceCapabilities = {
      ...capabilities,
      defaultTool: 'codex',
      tools: [
        ...capabilities.tools,
        {
          id: 'codex',
          models: ['gpt-5.4'],
          defaultModel: 'gpt-5.4',
          modes: null,
          defaultMode: null,
          contextWindow: 200000,
        },
      ],
    };

    render(
      <ChatInputArea
        thread={buildThread({
          agenticTool: 'codex',
          model: 'gpt-5.4',
          claudeMode: null,
        })}
        capabilities={capabilitiesWithCodex}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.tool' }));
    fireEvent.click(screen.getByRole('button', { name: 'claude' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.slashCommand' }));

    await waitFor(() => expect(slashCommandApiMock.listPickerItems).toHaveBeenCalledWith(
      'http://runtime.test',
      'workspace-1',
      'claude-code',
    ));
  });

  it('does not reopen the slash picker while typing after it is closed', async () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const textbox = screen.getByRole('textbox');
    fireEvent.change(textbox, { target: { value: '/' } });
    expect(screen.getByRole('dialog', { name: 'slash-command-picker' })).toBeInTheDocument();
    await waitFor(() => expect(slashCommandApiMock.listPickerItems).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'close-slash-command-picker' }));
    expect(screen.queryByRole('dialog', { name: 'slash-command-picker' })).not.toBeInTheDocument();

    fireEvent.change(textbox, { target: { value: '/review' } });
    fireEvent.change(textbox, { target: { value: '/review details' } });

    expect(screen.queryByRole('dialog', { name: 'slash-command-picker' })).not.toBeInTheDocument();
  });

  it('only disables the agent menu after the first message is submitted', () => {
    const onPatchDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread({ status: 'complete' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={onPatchDraft}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.settings.tool' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.model' }));
    fireEvent.click(screen.getByRole('button', { name: 'opus-4.8' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.mode' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.plan' }));

    expect(onPatchDraft).toHaveBeenCalledWith({
      model: 'opus-4.8',
      claudeMode: 'execute',
    });
    expect(onPatchDraft).toHaveBeenCalledWith({
      model: 'sonnet-5',
      claudeMode: 'plan',
    });
  });

  it('falls back to allowed capability models when the thread model is stale', () => {
    render(
      <ChatInputArea
        thread={buildThread({ model: 'removed-model' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.settings.model' })).toHaveTextContent('sonnet-5');

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.model' }));

    expect(screen.queryByRole('button', { name: 'removed-model' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'sonnet-5' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'opus-4.8' })).toBeInTheDocument();
  });

  it('inserts voice transcript into a draft and patches the draft message', async () => {
    const onPatchDraft = vi.fn();
    threadApiMock.transcribeAudio.mockResolvedValue({ text: 'hello from voice' });
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={onPatchDraft}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.start' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'aiChat.input.voice.stop' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.stop' }));

    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('hello from voice'));
    expect(onPatchDraft).toHaveBeenLastCalledWith({
      draftMessage: { text: 'hello from voice', attachments: [] },
    });
  });

  it('inserts voice transcript locally for a working thread without patching a draft', async () => {
    const onPatchDraft = vi.fn();
    threadApiMock.transcribeAudio.mockResolvedValue({ text: 'queued voice' });
    render(
      <ChatInputArea
        thread={buildThread({ status: 'working' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={onPatchDraft}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.start' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'aiChat.input.voice.stop' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.stop' }));

    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('queued voice'));
    expect(onPatchDraft).not.toHaveBeenCalled();
  });

  it('blocks keyboard send while voice input is recording without blocking cancel', async () => {
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread({ draftMessage: { text: 'Send later', attachments: [] } })}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.start' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'aiChat.input.voice.stop' })).toBeInTheDocument());

    expect(screen.getByRole('button', { name: 'aiChat.input.send' })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(onSubmitDraft).not.toHaveBeenCalled();
  });

  it('keeps cancel available while a working thread is recording voice input', async () => {
    const onCancel = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread({ status: 'working' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
        onCancel={onCancel}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.voice.start' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'aiChat.input.voice.stop' })).toBeInTheDocument());

    const cancelButton = screen.getByRole('button', { name: 'aiChat.workbench.cancel' });
    expect(cancelButton).not.toBeDisabled();
    fireEvent.click(cancelButton);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('disables voice input when the runtime thread API is unavailable', () => {
    workspaceMock.runtimeBaseUrl = null;
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.input.voice.unavailable' })).toBeDisabled();
  });

  it('submits a draft message and clears the textbox', () => {
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Run diagnostics' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onSubmitDraft).toHaveBeenCalledWith({ text: 'Run diagnostics', attachments: [] });
    expect(screen.getByRole('textbox')).toHaveValue('');
  });

  it('shows a selected file range above the input and allows a reference-only send', () => {
    integrationMock.codeReference = {
      filePath: '/src/App.tsx',
      fileName: 'App.tsx',
      startLine: 12,
      endLine: 18,
    };
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const textbox = screen.getByRole('textbox');
    const fileName = screen.getByText('App.tsx');
    expect(fileName.compareDocumentPosition(textbox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('aiChat.input.codeReferenceRange 12-18')).toBeInTheDocument();

    const sendButton = screen.getByRole('button', { name: 'aiChat.input.send' });
    expect(sendButton).not.toBeDisabled();
    fireEvent.click(sendButton);

    expect(onSubmitDraft).toHaveBeenCalledWith({
      text: 'File:./src/App.tsx:12-18',
      attachments: [],
    });
    expect(integrationMock.clearCodeReference).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('App.tsx')).not.toBeInTheDocument();
  });

  it('removes a selected file range from the new composer context row', () => {
    integrationMock.codeReference = {
      filePath: '/src/App.tsx',
      fileName: 'App.tsx',
      startLine: 7,
      endLine: 7,
    };
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    expect(screen.getByText('aiChat.input.codeReferenceLine 7')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {
      name: 'aiChat.input.removeCodeReference App.tsx',
    }));

    expect(integrationMock.clearCodeReference).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('App.tsx')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.input.send' })).toBeDisabled();
  });

  it('prefixes typed text with the selected file range', () => {
    integrationMock.codeReference = {
      filePath: '/workspace/src/App.tsx',
      fileName: 'App.tsx',
      startLine: 12,
      endLine: 18,
    };
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Explain this selection' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onSubmitDraft).toHaveBeenCalledWith({
      text: 'File:./src/App.tsx:12-18\nExplain this selection',
      attachments: [],
    });
  });

  it('uploads files immediately, removes selected files, and submits attachment references', async () => {
    const user = userEvent.setup();
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const fileInput = screen.getByTestId('ai-chat-file-input') as HTMLInputElement;
    const inputClick = vi.spyOn(fileInput, 'click');
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.uploadFile' }));
    expect(inputClick).toHaveBeenCalled();

    await user.upload(fileInput, [
      new File(['image-bytes'], 'diagram.png', { type: 'image/png' }),
      new File(['%PDF-1.7'], 'brief.pdf', { type: 'application/pdf' }),
      new File(['notes body'], 'notes.txt', { type: 'text/plain' }),
    ]);

    expect(await screen.findByText('diagram.png')).toBeInTheDocument();
    expect(screen.getByText('brief.pdf')).toBeInTheDocument();
    expect(screen.getByText('notes.txt')).toBeInTheDocument();
    expect(await screen.findAllByText('aiChat.input.attachmentReady')).toHaveLength(3);

    await user.click(screen.getByRole('button', { name: 'aiChat.input.removeAttachment diagram.png' }));
    expect(screen.queryByText('diagram.png')).not.toBeInTheDocument();
    expect(threadApiMock.deleteAttachment).toHaveBeenCalledWith('thread-1', 'att-diagram.png');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Review attachments' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onSubmitDraft).toHaveBeenCalledWith({
      text: 'Review attachments',
      attachments: [
        { attachmentId: 'att-brief.pdf' },
        { attachmentId: 'att-notes.txt' },
      ],
    });
    expect(screen.queryByText('brief.pdf')).not.toBeInTheDocument();
    expect(screen.queryByText('notes.txt')).not.toBeInTheDocument();
  });

  it('keeps the file input browser-addressable for native upload flows', () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const fileInput = screen.getByTestId('ai-chat-file-input');

    expect(fileInput).toHaveAttribute('id', 'ai-chat-file-input');
    expect(fileInput).toHaveAttribute('name', 'ai-chat-file-input');
    expect(fileInput).not.toHaveClass('hidden');
  });

  it('uses the integration file chooser slot to insert a workspace file reference', () => {
    const onPatchDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={onPatchDraft}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.fileReference' }));
    fireEvent.click(screen.getByRole('button', { name: 'choose-workspace-file' }));

    expect(screen.getByRole('textbox')).toHaveValue('@./src/App.tsx');
    expect(onPatchDraft).toHaveBeenCalledWith({
      draftMessage: { text: '@./src/App.tsx', attachments: [] },
    });
    expect(screen.queryByRole('button', { name: 'choose-workspace-file' })).not.toBeInTheDocument();
  });

  it('inserts a dragged workspace file reference without uploading an attachment', () => {
    const onPatchDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={onPatchDraft}
      />,
    );

    const dataTransfer = {
      types: [WORKSPACE_FILE_REFERENCE_MIME],
      getData: vi.fn((type: string) => (
        type === WORKSPACE_FILE_REFERENCE_MIME ? './src/App.tsx' : ''
      )),
      files: [],
    };

    fireEvent.dragOver(screen.getByRole('textbox').closest('[data-expanded]')!, { dataTransfer });
    fireEvent.drop(screen.getByRole('textbox').closest('[data-expanded]')!, { dataTransfer });

    expect(screen.getByRole('textbox')).toHaveValue('@./src/App.tsx');
    expect(onPatchDraft).toHaveBeenCalledWith({
      draftMessage: { text: '@./src/App.tsx', attachments: [] },
    });
    expect(threadApiMock.uploadAttachment).not.toHaveBeenCalled();
  });

  it('normalizes dragged absolute workspace paths to dot-relative references', () => {
    render(
      <ChatInputArea
        thread={buildThread({ draftMessage: { text: 'Check this', attachments: [] } })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const dataTransfer = {
      types: [WORKSPACE_FILE_REFERENCE_MIME],
      getData: vi.fn((type: string) => (
        type === WORKSPACE_FILE_REFERENCE_MIME ? '/README.md' : ''
      )),
      files: [],
    };

    fireEvent.drop(screen.getByRole('textbox').closest('[data-expanded]')!, { dataTransfer });

    expect(screen.getByRole('textbox')).toHaveValue('Check this\n@./README.md');
  });

  it('shows upload progress and blocks submit while a file is uploading', async () => {
    const user = userEvent.setup();
    const abort = vi.fn();
    threadApiMock.uploadAttachment.mockImplementation((_threadId: string, _file: File, onProgress: (progress: number) => void) => {
      onProgress(50);
      return {
        promise: new Promise(() => undefined),
        abort,
      };
    });

    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const fileInput = screen.getByTestId('ai-chat-file-input') as HTMLInputElement;
    await user.upload(fileInput, new File(['large-image'], 'large.png', { type: 'image/png' }));

    expect(await screen.findByText('large.png')).toBeInTheDocument();
    expect(screen.getByText('aiChat.input.attachmentUploading 50%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.input.send' })).toBeDisabled();
  });

  it('submits with Enter and keeps Shift+Enter as a newline', async () => {
    const user = userEvent.setup();
    const onSubmitDraft = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={onSubmitDraft}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    const textbox = screen.getByRole('textbox');
    await user.type(textbox, 'Line one');
    await user.keyboard('{Shift>}{Enter}{/Shift}Line two');

    expect(textbox).toHaveValue('Line one\nLine two');
    expect(onSubmitDraft).not.toHaveBeenCalled();

    await user.keyboard('{Enter}');

    expect(onSubmitDraft).toHaveBeenCalledWith({
      text: 'Line one\nLine two',
      attachments: [],
    });
    expect(textbox).toHaveValue('');
  });

  it('sizes the composer from content instead of focus state', () => {
    const scrollHeight = vi
      .spyOn(HTMLTextAreaElement.prototype, 'scrollHeight', 'get')
      .mockReturnValue(96);
    try {
      render(
        <ChatInputArea
          thread={buildThread()}
          capabilities={capabilities}
          onSubmitDraft={vi.fn()}
          onPostMessage={vi.fn()}
          onPatchDraft={vi.fn()}
        />,
      );

      const textbox = screen.getByRole('textbox') as HTMLTextAreaElement;
      const composer = textbox.closest('[data-expanded]');
      expect(composer).toHaveAttribute('data-expanded', 'false');
      expect(textbox.style.height).toBe('40px');

      fireEvent.focus(textbox);
      expect(composer).toHaveAttribute('data-active', 'true');
      expect(composer).toHaveAttribute('data-expanded', 'false');
      expect(textbox.style.height).toBe('40px');

      fireEvent.change(textbox, { target: { value: 'Line one' } });
      expect(composer).toHaveAttribute('data-expanded', 'false');
      expect(textbox.style.height).toBe('40px');

      fireEvent.change(textbox, { target: { value: 'Line one\nLine two' } });
      expect(composer).toHaveAttribute('data-expanded', 'true');
      expect(textbox.style.height).toBe('96px');

      fireEvent.change(textbox, { target: { value: 'Line one' } });
      expect(composer).toHaveAttribute('data-expanded', 'false');
      expect(textbox.style.height).toBe('40px');

      fireEvent.change(textbox, { target: { value: '' } });
      expect(composer).toHaveAttribute('data-active', 'true');
      expect(composer).toHaveAttribute('data-expanded', 'false');
      expect(textbox.style.height).toBe('40px');
    } finally {
      scrollHeight.mockRestore();
    }
  });

  it('does not replace current input with a stale local draft response', () => {
    const props = {
      capabilities,
      onSubmitDraft: vi.fn(),
      onPostMessage: vi.fn(),
      onPatchDraft: vi.fn(),
    };
    const { rerender } = render(<ChatInputArea thread={buildThread()} {...props} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'C' } });
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Complete input' } });
    rerender(
      <ChatInputArea
        thread={buildThread({ draftMessage: { text: 'C', attachments: [] } })}
        {...props}
      />,
    );

    expect(screen.getByRole('textbox')).toHaveValue('Complete input');

    rerender(
      <ChatInputArea
        thread={buildThread({ draftMessage: { text: 'Complete input', attachments: [] } })}
        {...props}
      />,
    );
    rerender(
      <ChatInputArea
        thread={buildThread({ draftMessage: { text: 'Updated elsewhere', attachments: [] } })}
        {...props}
      />,
    );

    expect(screen.getByRole('textbox')).toHaveValue('Updated elsewhere');
  });

  it('posts follow-up messages for submitted threads', () => {
    const onPostMessage = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread({ status: 'complete' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={onPostMessage}
        onPatchDraft={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Follow up' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    expect(onPostMessage).toHaveBeenCalledWith({ text: 'Follow up', attachments: [] });
  });

  it('shows stop instead of send while the thread is running', () => {
    const onCancel = vi.fn();
    render(
      <ChatInputArea
        thread={buildThread({ status: 'working' })}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
        onCancel={onCancel}
      />,
    );

    expect(screen.queryByRole('button', { name: 'aiChat.input.send' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.workbench.cancel' }));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['claude', 'sonnet-5', 'execute', '/aileron-web-canvas-review'],
    ['codex', 'gpt-5.4', null, '$aileron-web-canvas-review'],
    ['opencode', 'glm-5', null, '/aileron-web-canvas-review'],
  ] as const)(
    'formats an inserted skill for the selected %s agent without opening the slash picker',
    async (agenticTool, model, claudeMode, invocation) => {
      const allAgentCapabilities: WorkspaceCapabilities = {
        defaultTool: 'claude',
        tools: [
          ...capabilities.tools,
          {
            id: 'codex',
            models: ['gpt-5.4'],
            defaultModel: 'gpt-5.4',
            modes: null,
            defaultMode: null,
            contextWindow: 200000,
          },
          {
            id: 'opencode',
            models: ['glm-5'],
            defaultModel: 'glm-5',
            modes: null,
            defaultMode: null,
            contextWindow: 200000,
          },
        ],
      };
      const draftHandoff: AiChatHandoffRequest = {
        id: `handoff-${agenticTool}`,
        workspaceId: 'workspace-1',
        content: '#1 spacing',
        delivery: 'draft',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      };
      render(
        <ChatInputArea
          thread={buildThread({ agenticTool, model, claudeMode })}
          capabilities={allAgentCapabilities}
          onSubmitDraft={vi.fn()}
          onPostMessage={vi.fn()}
          onPatchDraft={vi.fn()}
          draftHandoff={draftHandoff}
          onDraftHandoffApplied={vi.fn()}
        />,
      );

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue(`${invocation}\n\n#1 spacing`);
      });
    },
  );

  it('does not open the slash picker for an inserted skill draft', () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
        draftHandoff={{
          id: 'handoff-no-dialog',
          workspaceId: 'workspace-1',
          content: '#1 spacing',
          delivery: 'draft',
          mode: 'replace',
          skillName: 'aileron-web-canvas-review',
        }}
        onDraftHandoffApplied={vi.fn()}
      />,
    );

    expect(screen.queryByRole('dialog', { name: 'slash-command-picker' })).not.toBeInTheDocument();
  });

  it('keeps settings on the left and borderless tool actions on the right', () => {
    render(
      <ChatInputArea
        thread={buildThread()}
        capabilities={capabilities}
        onSubmitDraft={vi.fn()}
        onPostMessage={vi.fn()}
        onPatchDraft={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.settings.tool' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.settings.mode' })).toBeInTheDocument();

    const fileButton = screen.getByRole('button', { name: 'aiChat.input.fileReference' });
    expect(fileButton).toHaveClass('text-muted-foreground');
    expect(fileButton).not.toHaveClass('border');
    expect(fileButton.parentElement).toHaveClass('ml-auto');
  });

});
