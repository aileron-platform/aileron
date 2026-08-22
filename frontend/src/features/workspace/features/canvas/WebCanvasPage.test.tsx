import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { WebCanvasPage } from './WebCanvasPage';
import {
  AILERON_CANVAS_BRIDGE_SOURCE,
  AILERON_CANVAS_BRIDGE_VERSION,
} from './lib/aileronCanvasBridgeClient';
import { ResolvedThemeProvider } from '@/shared/contexts/ResolvedThemeContext';

const mocks = vi.hoisted(() => ({
  fetchCanvasRoutes: vi.fn(),
  checkCanvasHealth: vi.fn(),
  fetchCanvasReviewNotes: vi.fn(),
  createCanvasReviewNote: vi.fn(),
  updateCanvasReviewNoteStatus: vi.fn(),
  deleteCanvasReviewNote: vi.fn(),
  syncCanvas: vi.fn(),
  toast: vi.fn(),
  handoffToAiChat: vi.fn(),
}));

vi.mock('@/features/ai-chat/public', () => ({
  useAiChatIntegration: () => ({
    handoffToAiChat: mocks.handoffToAiChat,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      if (values?.count != null) return `${key}:${values.count}`;
      return key;
    },
    state: { currentLanguage: 'en' },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock('../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
      runtimeStatus: {
        canvasUrl: '/workspaces/ws-1/canvas',
      },
    },
  }),
}));

vi.mock('../../api/workspaceRuntimeApi', () => ({
  fetchCanvasRoutes: mocks.fetchCanvasRoutes,
  checkCanvasHealth: mocks.checkCanvasHealth,
  fetchCanvasReviewNotes: mocks.fetchCanvasReviewNotes,
  createCanvasReviewNote: mocks.createCanvasReviewNote,
  updateCanvasReviewNoteStatus: mocks.updateCanvasReviewNoteStatus,
  deleteCanvasReviewNote: mocks.deleteCanvasReviewNote,
  syncCanvas: mocks.syncCanvas,
}));

const areaTarget = {
  type: 'area' as const,
  rect: { x: 10, y: 20, width: 100, height: 80, coordinateSpace: 'viewport' as const },
};

const elementTarget = {
  type: 'element' as const,
  selector: '#hero',
  selectorKind: 'id' as const,
  tagName: 'section',
  textPreview: 'Hero',
  htmlPreview: '<section id="hero">Hero</section>',
  parentHtmlPreview: '<main><section id="hero">Hero</section></main>',
  rect: { x: 10, y: 20, width: 100, height: 80, coordinateSpace: 'viewport' as const },
  documentRect: { x: 10, y: 20, width: 100, height: 80, coordinateSpace: 'document' as const },
};

const multiTarget = {
  type: 'multi-element' as const,
  elements: [
    elementTarget,
    { ...elementTarget, selector: '#cta', textPreview: 'CTA' },
  ],
  rect: { x: 10, y: 20, width: 180, height: 80, coordinateSpace: 'viewport' as const },
};

describe('WebCanvasPage review mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
    mocks.fetchCanvasRoutes.mockResolvedValue({
      workspaceId: 'ws-1',
      type: 'active',
      manifestStatus: 'valid',
      defaultPath: '/',
      routes: [{ path: '/' }],
      total: 1,
      scannedAt: '2026-04-28T00:00:00Z',
    });
    mocks.checkCanvasHealth.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'healthy',
      type: 'active',
      manifestStatus: 'valid',
      rendererRunning: true,
      portAvailable: true,
      message: 'OK',
    });
    mocks.fetchCanvasReviewNotes.mockResolvedValue({ workspaceId: 'ws-1', notes: [], total: 0 });
    mocks.handoffToAiChat.mockResolvedValue(undefined);
    mocks.syncCanvas.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'completed',
      type: 'active',
      manifestStatus: 'valid',
      message: 'Canvas renderer reused',
      rendererAction: 'reused',
      rendererActionReason: 'manifest-unchanged',
      syncedAt: '2026-04-29T00:00:00Z',
    });
    mocks.createCanvasReviewNote.mockResolvedValue({
      id: 'note-1',
      workspaceId: 'ws-1',
      routePath: '/',
      canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
      target: areaTarget,
      instruction: 'Move it',
      status: 'open',
      replies: [],
      createdAt: '2026-04-28T00:00:00Z',
      updatedAt: '2026-04-28T00:00:00Z',
    });
    mocks.updateCanvasReviewNoteStatus.mockImplementation(
      async (_runtimeBaseUrl: string, _workspaceId: string, noteId: string, status: string) => ({
        id: noteId,
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: areaTarget,
        instruction: 'Move it',
        status,
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:01:00Z',
      }),
    );
  });

  it('keeps Sync Canvas as the only Canvas update action in the toolbar', async () => {
    render(<WebCanvasPage />);

    const syncButton = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.actions.sync.label',
    });
    await waitFor(() => expect(syncButton).not.toBeDisabled());

    expect(screen.queryByTitle('workspace.canvas.header.actions.refresh')).not.toBeInTheDocument();
    expect(screen.queryByTitle('workspace.canvas.header.actions.menu')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.canvas.webCanvas.actions.reset.label')).not.toBeInTheDocument();

    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(mocks.syncCanvas).toHaveBeenCalledWith('http://runtime.local', 'ws-1');
    });
  });

  it('does not overlay a manifest error for a healthy active canvas', async () => {
    mocks.fetchCanvasRoutes.mockResolvedValue({
      workspaceId: 'ws-1',
      type: 'active',
      kind: 'static',
      manifestStatus: 'valid',
      runtimeStatus: 'healthy',
      defaultPath: '/',
      routes: [{ path: '/' }],
      total: 1,
      scannedAt: '2026-04-28T00:00:00Z',
    });

    render(<WebCanvasPage />);

    await waitFor(() => {
      expect(screen.queryByText('workspace.canvas.webCanvas.manifest.errors.invalid.title')).not.toBeInTheDocument();
    });
    expect(screen.queryByText('workspace.canvas.webCanvas.manifest.errors.invalid.description')).not.toBeInTheDocument();
  });

  it('leaves missing-manifest guidance to the default Canvas document', async () => {
    mocks.fetchCanvasRoutes.mockResolvedValue({
      workspaceId: 'ws-1',
      type: 'default',
      manifestStatus: 'missing',
      runtimeStatus: 'healthy',
      defaultPath: '/',
      routes: [{ path: '/' }],
      total: 1,
      scannedAt: '2026-04-28T00:00:00Z',
    });
    mocks.checkCanvasHealth.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'healthy',
      type: 'default',
      manifestStatus: 'missing',
      rendererRunning: true,
      portAvailable: true,
      message: 'OK',
    });

    render(<WebCanvasPage />);

    const iframe = await screen.findByTitle('workspace.canvas.webCanvas.iframeTitle');
    await waitFor(() => {
      expect(iframe).toHaveAttribute('src', '/workspaces/ws-1/canvas/?lang=en');
    });
    expect(screen.queryByText('workspace.canvas.webCanvas.default.guidance.title')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.canvas.webCanvas.default.guidance.description')).not.toBeInTheDocument();
  });

  it('does not combine script and same-origin iframe sandbox permissions', async () => {
    render(<WebCanvasPage />);

    const iframe = await screen.findByTitle('workspace.canvas.webCanvas.iframeTitle');

    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts allow-forms');
  });

  it('shows all manifest routes when the route dropdown is opened', async () => {
    mocks.fetchCanvasRoutes.mockResolvedValue({
      workspaceId: 'ws-1',
      type: 'active',
      manifestStatus: 'valid',
      defaultPath: '/about',
      routes: [
        { path: '/' },
        { path: '/about' },
        { path: '/portfolio' },
        { path: '/contact' },
      ],
      total: 4,
      scannedAt: '2026-04-28T00:00:00Z',
    });

    render(<WebCanvasPage />);

    const routeInput = await screen.findByPlaceholderText('workspace.canvas.webCanvas.routePlaceholder');
    await waitFor(() => expect(routeInput).toHaveValue('/about'));

    fireEvent.focus(routeInput);

    expect(await screen.findByText('/')).toBeInTheDocument();
    expect(screen.getByText('/about')).toBeInTheDocument();
    expect(screen.getByText('/portfolio')).toBeInTheDocument();
    expect(screen.getByText('/contact')).toBeInTheDocument();
  });

  it('refreshes Canvas route metadata after renderer reuse sync', async () => {
    mocks.fetchCanvasRoutes
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        type: 'active',
        manifestStatus: 'valid',
        defaultPath: '/',
        routes: [{ path: '/' }],
        total: 1,
        scannedAt: '2026-04-28T00:00:00Z',
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        type: 'active',
        manifestStatus: 'valid',
        defaultPath: '/products',
        routes: [{ path: '/products' }],
        total: 1,
        scannedAt: '2026-04-29T00:00:00Z',
      });

    render(<WebCanvasPage />);

    const syncButton = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.actions.sync.label',
    });
    await waitFor(() => expect(syncButton).not.toBeDisabled());
    expect(mocks.fetchCanvasRoutes).toHaveBeenCalledTimes(1);
    expect(mocks.checkCanvasHealth).toHaveBeenCalledTimes(1);

    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(mocks.syncCanvas).toHaveBeenCalledWith('http://runtime.local', 'ws-1');
    });
    await waitFor(() => {
      expect(mocks.fetchCanvasRoutes).toHaveBeenCalledTimes(2);
      expect(mocks.checkCanvasHealth).toHaveBeenCalledTimes(2);
      expect(screen.getByPlaceholderText('workspace.canvas.webCanvas.routePlaceholder')).toHaveValue('/products');
      expect(mocks.fetchCanvasReviewNotes).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        { routePath: '/products' },
      );
    });
  });

  it('falls back to a full Canvas data reload when sync metadata is absent', async () => {
    mocks.syncCanvas.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      status: 'completed',
      type: 'active',
      manifestStatus: 'valid',
      message: 'Canvas synced',
    });

    render(<WebCanvasPage />);

    const syncButton = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.actions.sync.label',
    });
    await waitFor(() => expect(syncButton).not.toBeDisabled());

    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(mocks.fetchCanvasRoutes).toHaveBeenCalledTimes(2);
      expect(mocks.checkCanvasHealth).toHaveBeenCalledTimes(2);
    });
  });

  it('falls back to a full Canvas data reload when the renderer restarted', async () => {
    mocks.syncCanvas.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      status: 'completed',
      type: 'active',
      manifestStatus: 'valid',
      message: 'Canvas renderer restarted',
      rendererAction: 'restarted',
      rendererActionReason: 'dependencies-changed',
      syncedAt: '2026-04-29T00:00:00Z',
    });

    render(<WebCanvasPage />);

    const syncButton = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.actions.sync.label',
    });
    await waitFor(() => expect(syncButton).not.toBeDisabled());

    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(mocks.fetchCanvasRoutes).toHaveBeenCalledTimes(2);
      expect(mocks.checkCanvasHealth).toHaveBeenCalledTimes(2);
    });
  });

  it('adds a selected target to the edit list without showing a success toast', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-pressed', 'true'));

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'BRIDGE_READY',
        payload: { routePath: '/' },
      },
    }));
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: areaTarget },
      },
    }));

    expect(await screen.findByText('workspace.canvas.webCanvas.review.form.title')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder'), {
      target: { value: 'Move it' },
    });
    fireEvent.click(screen.getByRole('button', { name: /workspace.canvas.webCanvas.review.form.addToList/ }));

    await waitFor(() => {
      expect(mocks.createCanvasReviewNote).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        expect.objectContaining({
          routePath: '/',
          target: areaTarget,
          instruction: 'Move it',
        }),
      );
    });
    expect(mocks.toast).not.toHaveBeenCalled();
  });

  it('creates a selected-target note and sends it through AI Chat immediately', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: areaTarget },
      },
    }));

    fireEvent.change(await screen.findByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder'), {
      target: { value: 'Move it' },
    });
    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.form.sendNow',
    }));

    await waitFor(() => {
      expect(mocks.handoffToAiChat).toHaveBeenCalledWith({
        content: expect.stringContaining('instruction: Move it'),
        delivery: 'submit',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      });
      expect(mocks.updateCanvasReviewNoteStatus).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'note-1',
        'seen',
      );
    });
  });

  it('syncs the header route and created note route from iframe navigation', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-pressed', 'true'));

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'ROUTE_CHANGED',
        payload: { routePath: '/products' },
      },
    }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('workspace.canvas.webCanvas.routePlaceholder')).toHaveValue('/products');
      expect(mocks.fetchCanvasReviewNotes).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        { routePath: '/products' },
      );
    });

    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/products', target: areaTarget },
      },
    }));

    fireEvent.change(await screen.findByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder'), {
      target: { value: 'Move it on products' },
    });
    fireEvent.click(screen.getByRole('button', { name: /workspace.canvas.webCanvas.review.form.addToList/ }));

    await waitFor(() => {
      expect(mocks.createCanvasReviewNote).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        expect.objectContaining({
          routePath: '/products',
          canvasUrl: '/workspaces/ws-1/canvas/products?lang=en',
          instruction: 'Move it on products',
        }),
      );
    });
  });

  it('syncs the resolved app theme to the canvas iframe', async () => {
    const { rerender } = render(
      <ResolvedThemeProvider value="dark">
        <WebCanvasPage />
      </ResolvedThemeProvider>,
    );

    const iframe = await screen.findByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    const contentWindow = { postMessage: vi.fn() } as unknown as Window;
    Object.defineProperty(iframe, 'contentWindow', {
      configurable: true,
      value: contentWindow,
    });
    window.dispatchEvent(new MessageEvent('message', {
      source: contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'BRIDGE_READY',
        payload: { routePath: '/' },
      },
    }));

    await waitFor(() => {
      expect(contentWindow.postMessage).toHaveBeenCalledWith(expect.objectContaining({
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'SET_THEME',
        payload: { theme: 'dark' },
      }), '*');
    });

    vi.mocked(contentWindow.postMessage).mockClear();
    rerender(
      <ResolvedThemeProvider value="light">
        <WebCanvasPage />
      </ResolvedThemeProvider>,
    );

    await waitFor(() => {
      expect(contentWindow.postMessage).toHaveBeenCalledWith(expect.objectContaining({
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'SET_THEME',
        payload: { theme: 'light' },
      }), '*');
    });
  });

  it('ignores bridge messages from non-active frames', async () => {
    render(<WebCanvasPage />);

    window.dispatchEvent(new MessageEvent('message', {
      source: window,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: areaTarget },
      },
    }));

    expect(screen.queryByText('workspace.canvas.webCanvas.review.form.title')).not.toBeInTheDocument();
  });

  it('keeps review selection mode active so bridge can update a single target into a multi-target selection', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'BRIDGE_READY',
        payload: { routePath: '/' },
      },
    }));
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: elementTarget },
      },
    }));
    expect(await screen.findByText('section #hero')).toBeInTheDocument();

    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: multiTarget },
      },
    }));

    expect(await screen.findByText('workspace.canvas.webCanvas.review.target.multi:2')).toBeInTheDocument();
  });

  it('preserves an unsaved review instruction when bridge sends target rect updates for the same route', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: elementTarget },
      },
    }));

    const instructionInput = await screen.findByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder');
    fireEvent.change(instructionInput, {
      target: { value: 'Keep this draft' },
    });

    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_RECTS',
        payload: {
          routePath: '/',
          rects: [{
            id: 'note-1',
            selector: '#hero',
            resolved: true,
            rect: { x: 20, y: 30, width: 100, height: 80, coordinateSpace: 'viewport' },
          }],
        },
      },
    }));

    expect(screen.getByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder')).toHaveValue('Keep this draft');
    expect(screen.getByText('section #hero')).toBeInTheDocument();
  });

  it('allows dragging the selected target edit instruction form', async () => {
    render(<WebCanvasPage />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: AILERON_CANVAS_BRIDGE_SOURCE,
        version: AILERON_CANVAS_BRIDGE_VERSION,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: elementTarget },
      },
    }));

    const dragHandle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.form.dragHandle',
    });
    const panel = dragHandle.closest('.pointer-events-auto') as HTMLElement;
    expect(panel).toBeTruthy();
    vi.spyOn(panel.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 800,
      bottom: 600,
      width: 800,
      height: 600,
      toJSON: () => undefined,
    });
    vi.spyOn(panel, 'getBoundingClientRect').mockReturnValue({
      x: 424,
      y: 16,
      left: 424,
      top: 16,
      right: 784,
      bottom: 220,
      width: 360,
      height: 204,
      toJSON: () => undefined,
    });

    const pointerDown = new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 500, clientY: 40 });
    Object.defineProperty(pointerDown, 'pointerId', { value: 1 });
    const pointerMove = new MouseEvent('pointermove', { bubbles: true, clientX: 460, clientY: 90 });
    Object.defineProperty(pointerMove, 'pointerId', { value: 1 });
    const pointerUp = new MouseEvent('pointerup', { bubbles: true });
    Object.defineProperty(pointerUp, 'pointerId', { value: 1 });
    fireEvent(dragHandle, pointerDown);
    fireEvent(dragHandle, pointerMove);
    fireEvent(dragHandle, pointerUp);

    expect(panel).toHaveStyle({ left: '384px', top: '66px' });
  });

  it('collapses and expands Canvas edit instructions', async () => {
    mocks.fetchCanvasReviewNotes.mockResolvedValue({
      workspaceId: 'ws-1',
      notes: [{
        id: 'note-1',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: areaTarget,
        instruction: 'Move this block',
        status: 'open',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      }],
      total: 1,
    });

    render(<WebCanvasPage />);

    expect(await screen.findByText('Move this block')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.notes.collapse',
    }));
    expect(screen.queryByText('Move this block')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.notes.expand',
    }));
    expect(await screen.findByText('Move this block')).toBeInTheDocument();
  });

  it('clears a pending instruction after sending it to AI', async () => {
    mocks.fetchCanvasReviewNotes.mockResolvedValue({
      workspaceId: 'ws-1',
      notes: [{
        id: 'note-1',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: areaTarget,
        instruction: 'Move this block',
        status: 'open',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      }],
      total: 1,
    });
    mocks.updateCanvasReviewNoteStatus.mockResolvedValue({
      id: 'note-1',
      workspaceId: 'ws-1',
      routePath: '/',
      canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
      target: areaTarget,
      instruction: 'Move this block',
      status: 'seen',
      replies: [],
      createdAt: '2026-04-28T00:00:00Z',
      updatedAt: '2026-04-28T00:01:00Z',
    });
    render(<WebCanvasPage />);

    expect(await screen.findByText('Move this block')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.notes.sendToChat',
    }));

    await waitFor(() => {
      expect(mocks.updateCanvasReviewNoteStatus).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'note-1',
        'seen',
      );
      expect(screen.queryByText('Move this block')).not.toBeInTheDocument();
    });
    expect(mocks.handoffToAiChat).toHaveBeenCalledWith({
      content: [
        '#1',
        'noteId: note-1',
        'routePath: /',
        'targetType: area',
        'area: {"x":10,"y":20,"width":100,"height":80,"coordinateSpace":"viewport"}',
        'instruction: Move this block',
      ].join('\n'),
      delivery: 'draft',
      mode: 'replace',
      skillName: 'aileron-web-canvas-review',
    });
    expect(mocks.handoffToAiChat.mock.calls[0][0].content).not.toContain('workspace.canvas.webCanvas.review.prompt.workflow');
  });

  it('shows only pending instructions and sends all pending instructions together', async () => {
    const notes = [
      {
        id: 'note-1',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: areaTarget,
        instruction: 'Move this block',
        status: 'open',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      },
      {
        id: 'note-2',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: multiTarget,
        instruction: 'Resize these cards',
        status: 'open',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      },
      {
        id: 'note-3',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
        target: elementTarget,
        instruction: 'Already sent',
        status: 'seen',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      },
    ];
    mocks.fetchCanvasReviewNotes.mockResolvedValue({ workspaceId: 'ws-1', notes, total: 3 });
    mocks.updateCanvasReviewNoteStatus.mockImplementation(
      async (_runtimeBaseUrl: string, _workspaceId: string, noteId: string, status: string) => ({
        ...notes.find((note) => note.id === noteId),
        status,
        updatedAt: '2026-04-28T00:01:00Z',
      })
    );
    render(<WebCanvasPage />);

    expect(await screen.findByText('Move this block')).toBeInTheDocument();
    expect(screen.getByText('Resize these cards')).toBeInTheDocument();
    expect(screen.queryByText('Already sent')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.notes.sendAllToChat',
    }));

    await waitFor(() => {
      expect(mocks.updateCanvasReviewNoteStatus).toHaveBeenCalledTimes(2);
      expect(mocks.updateCanvasReviewNoteStatus).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'note-1',
        'seen',
      );
      expect(mocks.updateCanvasReviewNoteStatus).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'note-2',
        'seen',
      );
      expect(screen.queryByText('Move this block')).not.toBeInTheDocument();
      expect(screen.queryByText('Resize these cards')).not.toBeInTheDocument();
    });
    expect(mocks.handoffToAiChat).toHaveBeenCalledWith({
      content: expect.stringContaining('#1\nnoteId: note-1'),
      delivery: 'draft',
      mode: 'replace',
      skillName: 'aileron-web-canvas-review',
    });
    const content = mocks.handoffToAiChat.mock.calls[0][0].content;
    expect(content).toContain('#2\nnoteId: note-2');
    expect(content).toContain('elements: #hero, #cta');
    expect(content).not.toContain('workspace.canvas.webCanvas.review.prompt.batchTitle');
    expect(content).not.toContain('workspace.canvas.webCanvas.review.prompt.workflow');
  });

  it('keeps an instruction open when the AI Chat handoff fails', async () => {
    const note = {
      id: 'note-1',
      workspaceId: 'ws-1',
      routePath: '/',
      canvasUrl: '/workspaces/ws-1/canvas/?lang=en',
      target: areaTarget,
      instruction: 'Move this block',
      status: 'open',
      replies: [],
      createdAt: '2026-04-28T00:00:00Z',
      updatedAt: '2026-04-28T00:00:00Z',
    };
    mocks.fetchCanvasReviewNotes.mockResolvedValue({ workspaceId: 'ws-1', notes: [note], total: 1 });
    mocks.handoffToAiChat.mockRejectedValueOnce(new Error('handoff failed'));
    render(<WebCanvasPage />);

    expect(await screen.findByText('Move this block')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.canvas.webCanvas.review.notes.sendToChat',
    }));

    await waitFor(() => {
      expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'workspace.canvas.webCanvas.review.toast.handoffFailedTitle',
        variant: 'destructive',
      }));
    });
    expect(mocks.updateCanvasReviewNoteStatus).not.toHaveBeenCalled();
    expect(screen.getByText('Move this block')).toBeInTheDocument();
  });
});
