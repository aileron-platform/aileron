import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbenchProvider } from './FileViewerWorkbenchContext';
import { ImageViewer } from './ImageViewer';
import { MarkdownViewer } from './MarkdownViewer';
import { MermaidViewer } from './MermaidViewer';
import type { FileViewerWorkbenchAdapter } from './types';
import {
  ApiClient,
  registerExecutionGrantProvider,
  registerExecutionGrantRejectionHandler,
} from '@/shared/api/apiClient';

const mermaidInitializeMock = vi.hoisted(() => vi.fn());
const mermaidRenderMock = vi.hoisted(() => vi.fn());
const i18nStateMock = vi.hoisted(() => ({ currentLanguage: 'en' }));
const tMock = vi.hoisted(() => (key: string, values?: Record<string, unknown>) => (
  values?.count !== undefined ? `${key}:${values.count}` : key
));
const alternateTMock = vi.hoisted(() => (key: string, values?: Record<string, unknown>) => (
  values?.count !== undefined ? `${key}:${values.count}` : key
));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: i18nStateMock.currentLanguage === 'en' ? tMock : alternateTMock,
    state: {
      currentLanguage: i18nStateMock.currentLanguage,
    },
  }),
}));

vi.mock('mermaid', () => ({
  default: {
    initialize: mermaidInitializeMock,
    render: mermaidRenderMock,
  },
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({
    content,
    onLinkClick,
  }: {
    content: string;
    onLinkClick?: (href: string, event: React.MouseEvent<HTMLAnchorElement>) => void;
  }) => (
    <article>
      {content}
      <a
        href="../../schemas/spec-driven-api/standards/configuration-standards.md"
        onClick={(event) => onLinkClick?.('../../schemas/spec-driven-api/standards/configuration-standards.md', event)}
      >
        config
      </a>
    </article>
  ),
}));

vi.mock('./CodeTextEditor', () => ({
  CodeTextEditor: ({ content }: { content: string }) => <textarea aria-label="shared-code-editor" value={content} readOnly />,
}));

const firePointerEvent = (
  element: Element,
  type: string,
  init: MouseEventInit & { pointerId: number; pointerType: string },
) => {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, ...init });
  Object.defineProperty(event, 'pointerId', { value: init.pointerId });
  Object.defineProperty(event, 'pointerType', { value: init.pointerType });
  fireEvent(element, event);
};

const renderWithFormatActions = (
  ui: React.ReactElement,
  registerSpy?: (node: React.ReactNode | null, registrationKey?: string, ownerKey?: string) => void,
) => {
  const Harness: React.FC = () => {
    const [actions, setActions] = React.useState<React.ReactNode | null>(null);
    const registerFormatActions = React.useCallback((node: React.ReactNode | null, registrationKey?: string, ownerKey?: string) => {
      registerSpy?.(node, registrationKey, ownerKey);
      setActions(node);
    }, []);

    return (
      <FileViewerWorkbenchProvider registerFormatActions={registerFormatActions}>
        <div data-testid="registered-format-actions">{actions}</div>
        {ui}
      </FileViewerWorkbenchProvider>
    );
  };

  return render(<Harness />);
};

const ImageViewerHarness: React.FC<React.ComponentProps<typeof ImageViewer>> = (props) => {
  const [actions, setActions] = React.useState<React.ReactNode | null>(null);
  const registerFormatActions = React.useCallback((node: React.ReactNode | null) => {
    setActions(node);
  }, []);

  return (
    <FileViewerWorkbenchProvider registerFormatActions={registerFormatActions}>
      <div data-testid="registered-format-actions">{actions}</div>
      <ImageViewer {...props} />
    </FileViewerWorkbenchProvider>
  );
};

describe('specialized file viewers', () => {
  beforeEach(() => {
    i18nStateMock.currentLanguage = 'en';
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

    renderWithFormatActions(
      <MarkdownViewer
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

  it('persists Markdown edits when the shared save action is clicked', async () => {
    const onContentChange = vi.fn();
    const onSave = vi.fn().mockResolvedValue(undefined);

    renderWithFormatActions(
      <MarkdownViewer
        content="# Shared"
        fileName="readme.md"
        onContentChange={onContentChange}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByLabelText('shared.fileViewer.markdown.edit'));
    fireEvent.change(screen.getByPlaceholderText('shared.fileViewer.markdown.editPlaceholder'), {
      target: { value: '# Saved' },
    });
    fireEvent.click(screen.getByLabelText('shared.fileViewer.markdown.save'));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('# Saved');
    });
    expect(onContentChange).toHaveBeenCalledWith('# Saved');
  });

  it('keeps Markdown toolbar actions available through the shared focus toolbar', () => {
    const registerFormatActions = vi.fn();

    const view = renderWithFormatActions(
      <MarkdownViewer
        content="# Shared"
        fileName="readme.md"
      />,
      registerFormatActions,
    );

    expect(screen.getByLabelText('shared.fileViewer.markdown.zoomIn')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.copy')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.download')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.markdown.zoomIn')).toHaveClass('!h-7', '!px-2');
    expect(screen.getByLabelText('shared.fileViewer.markdown.copy').querySelector('svg')).toHaveClass('h-3.5', 'w-3.5');
    expect(registerFormatActions).toHaveBeenCalledWith(expect.any(Object), expect.any(String), expect.any(String));

    view.unmount();
    expect(registerFormatActions).toHaveBeenCalledWith(null, expect.any(String), expect.any(String));
  });

  it('allows empty Markdown files to enter edit mode from the shared toolbar', () => {
    renderWithFormatActions(
      <MarkdownViewer
        content=""
        fileName="empty.md"
        onContentChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByLabelText('shared.fileViewer.markdown.edit'));

    expect(screen.getByPlaceholderText('shared.fileViewer.markdown.editPlaceholder')).toBeInTheDocument();
  });

  it('does not re-register Markdown toolbar actions on parent rerenders with unstable callbacks', async () => {
    const registerSpy = vi.fn();

    const Harness: React.FC = () => {
      const [actions, setActions] = React.useState<React.ReactNode | null>(null);
      const registerFormatActions = React.useCallback((node: React.ReactNode | null, registrationKey?: string, ownerKey?: string) => {
        registerSpy(node, registrationKey, ownerKey);
        setActions(node);
      }, []);

      return (
        <FileViewerWorkbenchProvider registerFormatActions={registerFormatActions}>
          <div data-testid="registered-format-actions">{actions}</div>
          <MarkdownViewer
            content="# Shared"
            fileName="readme.md"
            onReload={() => Promise.resolve('# Shared')}
            onContentChange={vi.fn()}
          />
        </FileViewerWorkbenchProvider>
      );
    };

    render(<Harness />);

    expect(await screen.findByLabelText('shared.fileViewer.markdown.edit')).toBeInTheDocument();
    await waitFor(() => {
      expect(registerSpy.mock.calls.filter(([node]) => node !== null)).toHaveLength(1);
    });
  });

  it('opens internal Markdown links through the workspace tab callback', () => {
    const onOpenPath = vi.fn();

    renderWithFormatActions(
      <MarkdownViewer
        content="[Config](../../schemas/spec-driven-api/standards/configuration-standards.md)"
        fileName="design.md"
        filePath="/guides/parse-policy-excel-file/design.md"
        onOpenPath={onOpenPath}
      />,
    );

    fireEvent.click(screen.getByRole('link', { name: 'config' }));

    expect(onOpenPath).toHaveBeenCalledWith('/schemas/spec-driven-api/standards/configuration-standards.md');
  });

  it('renders Mermaid through the shared renderer and exposes shared toolbar actions', async () => {
    renderWithFormatActions(
      <MermaidViewer
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

  it('allows panning the Mermaid diagram after zooming', async () => {
    renderWithFormatActions(
      <MermaidViewer
        content="graph TD; A-->B;"
        fileName="diagram.mmd"
      />,
    );

    await waitFor(() => {
      expect(document.querySelector('.mermaid-diagram svg')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('shared.fileViewer.mermaid.zoomIn'));

    const panSurface = screen.getByTestId('mermaid-pan-surface');
    firePointerEvent(panSurface, 'pointerdown', {
      pointerId: 1,
      pointerType: 'mouse',
      button: 0,
      clientX: 100,
      clientY: 100,
    });
    firePointerEvent(panSurface, 'pointermove', {
      pointerId: 1,
      pointerType: 'mouse',
      clientX: 160,
      clientY: 130,
    });
    firePointerEvent(panSurface, 'pointerup', {
      pointerId: 1,
      pointerType: 'mouse',
      clientX: 160,
      clientY: 130,
    });

    expect(panSurface).toHaveStyle({ transform: 'translate(60px, 30px) scale(1.1)' });
  });

  it('defers Mermaid loading until diagram content is rendered', () => {
    renderWithFormatActions(
      <MermaidViewer
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

    renderWithFormatActions(
      <MermaidViewer
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

    renderWithFormatActions(
      <ImageViewer
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={adapter}
      />,
    );

    await waitFor(() => {
      expect(adapter.readBlob).toHaveBeenCalledWith('/assets/logo.png');
    });
    expect(adapter.readBlob).toHaveBeenCalledTimes(1);
    expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    expect(screen.getByLabelText('shared.fileViewer.image.rotate')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.image.download')).toBeInTheDocument();
  });

  it('renders the fresh image after a Blob execution grant is renewed', async () => {
    const grants = vi.fn()
      .mockResolvedValueOnce('stale-image-grant')
      .mockResolvedValueOnce('fresh-image-grant');
    const rejectGrant = vi.fn().mockReturnValue(true);
    registerExecutionGrantProvider(grants);
    registerExecutionGrantRejectionHandler(rejectGrant);
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH' },
      }), { status: 423 }))
      .mockResolvedValueOnce(new Response('fresh image', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      }));
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });
    const readBlob = vi.fn((path: string) => client.getBlob(path));

    try {
      renderWithFormatActions(
        <ImageViewer
          filePath="/assets/logo.png"
          fileName="logo.png"
          adapter={{ readFile: vi.fn(), readBlob }}
        />,
      );

      expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
      expect(screen.queryByText('shared.fileViewer.image.error')).not.toBeInTheDocument();
      expect(readBlob).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(grants).toHaveBeenCalledTimes(2);
      expect(rejectGrant).toHaveBeenCalledTimes(1);
    } finally {
      registerExecutionGrantProvider(null);
      registerExecutionGrantRejectionHandler(null);
      fetchMock.mockRestore();
    }
  });

  it('keeps the loaded image when adapter and translation identities change for the same path', async () => {
    const initialReadBlob = vi.fn().mockResolvedValue(new Blob(['first'], { type: 'image/png' }));
    const initialAdapter: FileViewerWorkbenchAdapter = {
      readFile: vi.fn(),
      readBlob: initialReadBlob,
    };
    const view = render(
      <ImageViewerHarness
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={initialAdapter}
      />,
    );

    expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    expect(initialReadBlob).toHaveBeenCalledTimes(1);

    const replacementReadBlob = vi.fn().mockResolvedValue(new Blob(['replacement'], { type: 'image/png' }));
    i18nStateMock.currentLanguage = 'zh-TW';
    view.rerender(
      <ImageViewerHarness
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={{ readFile: vi.fn(), readBlob: replacementReadBlob }}
      />,
    );

    expect(initialReadBlob).toHaveBeenCalledTimes(1);
    expect(replacementReadBlob).not.toHaveBeenCalled();
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    expect(screen.getByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    expect(screen.queryByText('shared.fileViewer.image.loading')).not.toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.image.rotate')).toBeInTheDocument();
  });

  it('reloads a changed image path with the latest adapter and replaces the old object URL', async () => {
    vi.mocked(URL.createObjectURL)
      .mockReturnValueOnce('blob:first-image')
      .mockReturnValueOnce('blob:second-image');
    const firstReadBlob = vi.fn().mockResolvedValue(new Blob(['first'], { type: 'image/png' }));
    const view = render(
      <ImageViewerHarness
        filePath="/assets/first.png"
        fileName="first.png"
        adapter={{ readFile: vi.fn(), readBlob: firstReadBlob }}
      />,
    );

    expect(await screen.findByAltText('first.png')).toHaveAttribute('src', 'blob:first-image');

    const secondReadBlob = vi.fn().mockResolvedValue(new Blob(['second'], { type: 'image/png' }));
    view.rerender(
      <ImageViewerHarness
        filePath="/assets/second.png"
        fileName="second.png"
        adapter={{ readFile: vi.fn(), readBlob: secondReadBlob }}
      />,
    );

    expect(await screen.findByAltText('second.png')).toHaveAttribute('src', 'blob:second-image');
    expect(firstReadBlob).toHaveBeenCalledTimes(1);
    expect(secondReadBlob).toHaveBeenCalledTimes(1);
    expect(secondReadBlob).toHaveBeenCalledWith('/assets/second.png');
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:first-image');
  });

  it('revokes the current image object URL on unmount', async () => {
    const view = render(
      <ImageViewerHarness
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={{
          readFile: vi.fn(),
          readBlob: vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/png' })),
        }}
      />,
    );

    expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    view.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:viewer-object');
  });

  it('loads the image when readBlob becomes available for the current path', async () => {
    const view = render(
      <ImageViewerHarness
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={{ readFile: vi.fn() }}
      />,
    );

    expect(await screen.findByText('shared.fileViewer.image.unavailable')).toBeInTheDocument();

    const readBlob = vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/png' }));
    view.rerender(
      <ImageViewerHarness
        filePath="/assets/logo.png"
        fileName="logo.png"
        adapter={{ readFile: vi.fn(), readBlob }}
      />,
    );

    expect(await screen.findByAltText('logo.png')).toHaveAttribute('src', 'blob:viewer-object');
    expect(readBlob).toHaveBeenCalledTimes(1);
    expect(readBlob).toHaveBeenCalledWith('/assets/logo.png');
  });

  it('does not let a stale image load replace the current path', async () => {
    let resolveFirstBlob: (blob: Blob) => void = () => undefined;
    const firstBlob = new Promise<Blob>((resolve) => {
      resolveFirstBlob = resolve;
    });
    const firstReadBlob = vi.fn().mockReturnValue(firstBlob);
    vi.mocked(URL.createObjectURL)
      .mockReturnValueOnce('blob:current-image')
      .mockReturnValueOnce('blob:stale-image');
    const view = render(
      <ImageViewerHarness
        filePath="/assets/slow.png"
        fileName="slow.png"
        adapter={{ readFile: vi.fn(), readBlob: firstReadBlob }}
      />,
    );

    await waitFor(() => {
      expect(firstReadBlob).toHaveBeenCalledWith('/assets/slow.png');
    });

    const currentReadBlob = vi.fn().mockResolvedValue(new Blob(['current'], { type: 'image/png' }));
    view.rerender(
      <ImageViewerHarness
        filePath="/assets/current.png"
        fileName="current.png"
        adapter={{ readFile: vi.fn(), readBlob: currentReadBlob }}
      />,
    );

    expect(await screen.findByAltText('current.png')).toHaveAttribute('src', 'blob:current-image');
    resolveFirstBlob(new Blob(['stale'], { type: 'image/png' }));

    await waitFor(() => {
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:stale-image');
    });
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:current-image');
    expect(screen.getByAltText('current.png')).toHaveAttribute('src', 'blob:current-image');
  });

});
