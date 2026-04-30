import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SharedDrawioViewer } from './SharedDrawioViewer';
import { SharedImageViewer } from './SharedImageViewer';
import { SharedMarkdownViewer } from './SharedMarkdownViewer';
import { SharedMermaidViewer } from './SharedMermaidViewer';
import type { FileViewerWorkbenchAdapter } from './types';

const mermaidInitializeMock = vi.hoisted(() => vi.fn());
const mermaidRenderMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values?.count !== undefined ? `${key}:${values.count}` : key
    ),
  }),
}));

vi.mock('mermaid', () => ({
  default: {
    initialize: mermaidInitializeMock,
    render: mermaidRenderMock,
  },
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <article>{content}</article>,
}));

vi.mock('./CodeTextEditor', () => ({
  CodeTextEditor: ({ content }: { content: string }) => <textarea aria-label="shared-code-editor" value={content} readOnly />,
}));

class DrawioUnavailableError extends Error {
  readonly status = 503;
  readonly errorCode = 'DRAWIO_UNAVAILABLE';
  readonly reason?: string;

  constructor(reason: string) {
    super('Draw.io unavailable');
    this.reason = reason;
  }
}

describe('shared specialized file viewers', () => {
  beforeEach(() => {
    mermaidInitializeMock.mockReset();
    mermaidRenderMock.mockReset();
    mermaidRenderMock.mockResolvedValue({ svg: '<svg data-testid="diagram-svg"></svg>' });
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:viewer-object'),
      revokeObjectURL: vi.fn(),
    });
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('renders Markdown content and edits only when a change handler is provided', async () => {
    const onContentChange = vi.fn();

    render(
      <SharedMarkdownViewer
        content="# Shared"
        fileName="readme.md"
        onContentChange={onContentChange}
      />,
    );

    expect(screen.getByText('# Shared')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('shared.fileViewer.markdown.edit'));
    fireEvent.change(screen.getByPlaceholderText('shared.fileViewer.markdown.editPlaceholder'), {
      target: { value: '# Updated' },
    });
    fireEvent.click(screen.getByLabelText('shared.fileViewer.markdown.save'));

    expect(onContentChange).toHaveBeenCalledWith('# Updated');
  });

  it('keeps Markdown toolbar actions available through the shared focus toolbar', () => {
    render(
      <SharedMarkdownViewer
        content="# Shared"
        fileName="readme.md"
        isFocusMode
        renderFocusToolbar={({ actions, title, subtitle }) => (
          <header>
            <h1>{title}</h1>
            <span>{subtitle}</span>
            <div>{actions}</div>
          </header>
        )}
      />,
    );

    expect(screen.getByRole('heading', { name: 'readme.md' })).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.markdown.title')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.zoomIn')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.copy')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.download')).toBeInTheDocument();
  });

  it('renders Mermaid through the shared renderer and exposes shared toolbar actions', async () => {
    render(
      <SharedMermaidViewer
        content="graph TD; A-->B;"
        fileName="diagram.mmd"
      />,
    );

    await waitFor(() => {
      expect(mermaidInitializeMock).toHaveBeenCalledWith(expect.objectContaining({ startOnLoad: false }));
      expect(mermaidRenderMock).toHaveBeenCalledWith(expect.stringMatching(/^shared-mermaid-/), 'graph TD; A-->B;');
    });
    expect(document.querySelector('.mermaid-diagram svg')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.mermaid.zoomIn')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.mermaid.copySvg')).toBeInTheDocument();
  });

  it('defers Mermaid loading until diagram content is rendered', () => {
    render(
      <SharedMermaidViewer
        content="   "
        fileName="empty.mmd"
      />,
    );

    expect(mermaidInitializeMock).not.toHaveBeenCalled();
    expect(mermaidRenderMock).not.toHaveBeenCalled();
    expect(screen.getByText('shared.fileViewer.mermaid.empty')).toBeInTheDocument();
  });

  it('shows a localized Mermaid error fallback when rendering fails', async () => {
    mermaidRenderMock.mockRejectedValueOnce(new Error('Invalid diagram'));

    render(
      <SharedMermaidViewer
        content="graph TD;"
        fileName="broken.mmd"
      />,
    );

    expect(await screen.findByText('shared.fileViewer.mermaid.error.title')).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.mermaid.error.description')).toBeInTheDocument();
    expect(screen.getByText('Invalid diagram')).toBeInTheDocument();
  });

  it('loads image blobs through the injected adapter and keeps image tools shared', async () => {
    const adapter: FileViewerWorkbenchAdapter = {
      readFile: vi.fn(),
      readBlob: vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/png' })),
    };

    render(
      <SharedImageViewer
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={adapter}
      />,
    );

    await waitFor(() => {
      expect(adapter.readBlob).toHaveBeenCalledWith('/assets/logo.png');
    });
    expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    expect(screen.getByLabelText('shared.fileViewer.image.rotate')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.image.download')).toBeInTheDocument();
  });

  it('loads Draw.io viewer URLs through the injected adapter and switches edit mode', async () => {
    const adapter: FileViewerWorkbenchAdapter = {
      readFile: vi.fn(),
      getDrawioViewerUrl: vi
        .fn()
        .mockResolvedValueOnce('about:blank?mode=view')
        .mockResolvedValueOnce('about:blank?mode=edit'),
      saveDrawio: vi.fn(),
    };

    render(
      <SharedDrawioViewer
        content="<mxfile />"
        originalContent="<mxfile />"
        filePath="/docs/diagram.drawio"
        fileName="diagram.drawio"
        readOnly={false}
        adapter={adapter}
        onContentChange={vi.fn()}
        onModifiedChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(adapter.getDrawioViewerUrl).toHaveBeenCalledWith('/docs/diagram.drawio', 'view');
    });

    fireEvent.click(screen.getByLabelText('shared.fileViewer.drawio.edit'));

    await waitFor(() => {
      expect(adapter.getDrawioViewerUrl).toHaveBeenCalledWith('/docs/diagram.drawio', 'edit');
    });
    expect(document.querySelector('iframe')).toBeInTheDocument();
  });

  it('renders Draw.io service-unavailable XML fallback without the code editor provider path', async () => {
    const adapter: FileViewerWorkbenchAdapter = {
      readFile: vi.fn(),
      getDrawioViewerUrl: vi.fn().mockRejectedValue(new DrawioUnavailableError('DISABLED')),
    };

    render(
      <SharedDrawioViewer
        content="<mxfile><diagram /></mxfile>"
        originalContent="<mxfile><diagram /></mxfile>"
        filePath="/docs/diagram.drawio"
        fileName="diagram.drawio"
        readOnly={false}
        adapter={adapter}
        onContentChange={vi.fn()}
        onModifiedChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('shared.fileViewer.drawio.serviceUnavailable.title')).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.drawio.serviceUnavailable.disabled')).toBeInTheDocument();
    expect(screen.getByText('<mxfile><diagram /></mxfile>')).toBeInTheDocument();
    expect(screen.queryByLabelText('shared-code-editor')).not.toBeInTheDocument();
  });
});
