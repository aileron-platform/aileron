import { describe, it, expect, vi, beforeEach } from 'vitest';

const ARTIFACT_RE = /<artifact[^>]*type="web-canvas"/;

const mockDispatch = vi.fn();
const mockNavigate = vi.fn();
const mockSyncCanvas = vi.fn().mockResolvedValue({ success: true });

function detectAndHandle(
  text: string,
  currentFeature: string,
  currentSubView: string,
  hasRuntime: boolean,
) {
  if (!text) return;
  if (!ARTIFACT_RE.test(text)) return;

  const alreadyOnCanvas = currentFeature === 'canvas' && currentSubView === 'web-canvas';

  if (!alreadyOnCanvas) {
    mockDispatch({ type: 'SET_CANVAS_SUB_VIEW', payload: 'web-canvas' });
    mockDispatch({ type: 'SET_CURRENT_FEATURE', payload: 'canvas' });
    mockDispatch({ type: 'ENSURE_NAVIGATION_ITEM_EXPANDED', payload: 'canvas' });
    mockNavigate('/workspaces/canvas/web-canvas');
  }

  if (hasRuntime) {
    mockSyncCanvas('http://runtime', 'ws-1').catch(() => {});
  }
}

describe('artifact signal detection', () => {
  beforeEach(() => {
    mockDispatch.mockClear();
    mockNavigate.mockClear();
    mockSyncCanvas.mockClear();
  });

  it('triggers navigation when artifact tag present', () => {
    detectAndHandle(
      'Done.\n<artifact type="web-canvas" title="My Page" />',
      'file-management',
      'session-result',
      true,
    );
    expect(mockDispatch).toHaveBeenCalledWith({ type: 'SET_CURRENT_FEATURE', payload: 'canvas' });
    expect(mockNavigate).toHaveBeenCalledWith('/workspaces/canvas/web-canvas');
    expect(mockSyncCanvas).toHaveBeenCalledTimes(1);
  });

  it('is no-op when artifact tag absent', () => {
    detectAndHandle('Done. No artifact here.', 'file-management', 'session-result', true);
    expect(mockDispatch).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(mockSyncCanvas).not.toHaveBeenCalled();
  });

  it('is no-op for empty text', () => {
    detectAndHandle('', 'file-management', 'session-result', true);
    expect(mockDispatch).not.toHaveBeenCalled();
    expect(mockSyncCanvas).not.toHaveBeenCalled();
  });

  it('skips navigation dispatches when already on canvas/web-canvas but still calls syncCanvas', () => {
    detectAndHandle(
      '<artifact type="web-canvas" title="Page" />',
      'canvas',
      'web-canvas',
      true,
    );
    expect(mockDispatch).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(mockSyncCanvas).toHaveBeenCalledTimes(1);
  });

  it('does not call syncCanvas when runtime is unavailable', () => {
    detectAndHandle(
      '<artifact type="web-canvas" title="Page" />',
      'file-management',
      'session-result',
      false,
    );
    expect(mockSyncCanvas).not.toHaveBeenCalled();
  });

  it('matches artifact with attributes in any order', () => {
    detectAndHandle(
      '<artifact title="Page" type="web-canvas" />',
      'file-management',
      'session-result',
      true,
    );
    expect(mockDispatch).toHaveBeenCalled();
  });
});
