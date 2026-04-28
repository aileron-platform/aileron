import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { WebCanvasFeature } from './WebCanvasFeature';

const mocks = vi.hoisted(() => ({
  fetchWorkspaceDetail: vi.fn(),
  fetchCanvasRoutes: vi.fn(),
  checkCanvasHealth: vi.fn(),
  fetchCanvasReviewNotes: vi.fn(),
  createCanvasReviewNote: vi.fn(),
  updateCanvasReviewNoteStatus: vi.fn(),
  deleteCanvasReviewNote: vi.fn(),
  syncCanvas: vi.fn(),
  resetCanvas: vi.fn(),
  toast: vi.fn(),
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

vi.mock('../../providers/WorkspaceContext', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    },
  }),
}));

vi.mock('../../services/workspacePublicUrl', () => ({
  resolvePreferredWorkspaceUrl: () => 'http://canvas.local',
}));

vi.mock('../../services/workspaceRuntimeApi', () => ({
  fetchWorkspaceDetail: mocks.fetchWorkspaceDetail,
  fetchCanvasRoutes: mocks.fetchCanvasRoutes,
  checkCanvasHealth: mocks.checkCanvasHealth,
  fetchCanvasReviewNotes: mocks.fetchCanvasReviewNotes,
  createCanvasReviewNote: mocks.createCanvasReviewNote,
  updateCanvasReviewNoteStatus: mocks.updateCanvasReviewNoteStatus,
  deleteCanvasReviewNote: mocks.deleteCanvasReviewNote,
  syncCanvas: mocks.syncCanvas,
  resetCanvas: mocks.resetCanvas,
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

describe('WebCanvasFeature review mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchWorkspaceDetail.mockResolvedValue({
      runtimeStatus: {
        canvasExternalUrl: 'http://canvas.local',
        canvasInternalUrl: 'http://canvas-internal.local',
      },
    });
    mocks.fetchCanvasRoutes.mockResolvedValue({
      workspaceId: 'ws-1',
      type: 'html',
      manifestStatus: 'valid',
      defaultPath: '/',
      routes: [{ path: '/' }],
      total: 1,
      scannedAt: '2026-04-28T00:00:00Z',
    });
    mocks.checkCanvasHealth.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'healthy',
      type: 'html',
      manifestStatus: 'valid',
      rendererRunning: true,
      portAvailable: true,
      message: 'OK',
    });
    mocks.fetchCanvasReviewNotes.mockResolvedValue({ workspaceId: 'ws-1', notes: [], total: 0 });
    mocks.createCanvasReviewNote.mockResolvedValue({
      id: 'note-1',
      workspaceId: 'ws-1',
      routePath: '/',
      canvasUrl: 'http://canvas.local/?lang=en',
      target: areaTarget,
      instruction: 'Move it',
      status: 'open',
      replies: [],
      createdAt: '2026-04-28T00:00:00Z',
      updatedAt: '2026-04-28T00:00:00Z',
    });
  });

  it('toggles review mode and creates a note from a selected bridge target', async () => {
    render(<WebCanvasFeature />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'BRIDGE_READY',
        payload: { routePath: '/' },
      },
    }));
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: areaTarget },
      },
    }));

    expect(await screen.findByText('workspace.canvas.webCanvas.review.form.title')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('workspace.canvas.webCanvas.review.form.placeholder'), {
      target: { value: 'Move it' },
    });
    fireEvent.click(screen.getByRole('button', { name: /workspace.canvas.webCanvas.review.form.create/ }));

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
  });

  it('ignores bridge messages from non-active frames', async () => {
    render(<WebCanvasFeature />);

    window.dispatchEvent(new MessageEvent('message', {
      source: window,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: areaTarget },
      },
    }));

    expect(screen.queryByText('workspace.canvas.webCanvas.review.form.title')).not.toBeInTheDocument();
  });

  it('keeps review selection mode active so bridge can update a single target into a multi-target selection', async () => {
    render(<WebCanvasFeature />);

    const toggle = await screen.findByRole('button', {
      name: 'workspace.canvas.webCanvas.review.toolbar.toggle',
    });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    fireEvent.click(toggle);

    const iframe = screen.getByTitle('workspace.canvas.webCanvas.iframeTitle') as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'BRIDGE_READY',
        payload: { routePath: '/' },
      },
    }));
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: elementTarget },
      },
    }));
    expect(await screen.findByText('section #hero')).toBeInTheDocument();

    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        source: 'aileron-web-canvas-review',
        version: 1,
        type: 'TARGET_SELECTED',
        payload: { routePath: '/', target: multiTarget },
      },
    }));

    expect(await screen.findByText('workspace.canvas.webCanvas.review.target.multi:2')).toBeInTheDocument();
  });

  it('collapses and expands Canvas edit instructions', async () => {
    mocks.fetchCanvasReviewNotes.mockResolvedValue({
      workspaceId: 'ws-1',
      notes: [{
        id: 'note-1',
        workspaceId: 'ws-1',
        routePath: '/',
        canvasUrl: 'http://canvas.local/?lang=en',
        target: areaTarget,
        instruction: 'Move this block',
        status: 'open',
        replies: [],
        createdAt: '2026-04-28T00:00:00Z',
        updatedAt: '2026-04-28T00:00:00Z',
      }],
      total: 1,
    });

    render(<WebCanvasFeature />);

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
});
