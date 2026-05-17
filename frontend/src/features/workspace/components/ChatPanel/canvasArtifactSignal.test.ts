import { describe, expect, it } from 'vitest';

import { hasCanvasArtifactSignal } from './canvasArtifactSignal';

describe('canvas artifact signal detection', () => {
  it('matches the canvas artifact tag', () => {
    expect(hasCanvasArtifactSignal('Done.\n<artifact type="canvas" />')).toBe(true);
  });

  it('is false when the tag is missing', () => {
    expect(hasCanvasArtifactSignal('Done. No artifact here.')).toBe(false);
  });

  it('is false when runtime text is missing', () => {
    expect(hasCanvasArtifactSignal('')).toBe(false);
    expect(hasCanvasArtifactSignal(null)).toBe(false);
    expect(hasCanvasArtifactSignal(undefined)).toBe(false);
  });

  it('matches when attributes are in any order', () => {
    expect(hasCanvasArtifactSignal('<artifact title="Page" type="canvas" />')).toBe(true);
  });

  it('does not match the old web-canvas tag', () => {
    expect(hasCanvasArtifactSignal('<artifact type="web-canvas" />')).toBe(false);
  });
});
