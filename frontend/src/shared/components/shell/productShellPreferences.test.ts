import { describe, expect, it } from 'vitest';
import {
  assertProductShellCompanionRegion,
  assertProductShellRegionBehavior,
  resolveProductShellPreferences,
} from './productShellPreferences';

describe('ProductShell preference contracts', () => {
  it('clamps loaded widths and heights while preserving placement and collapse state', () => {
    const result = resolveProductShellPreferences({
      navigation: { collapsed: true, width: 1 },
      navigator: { collapsed: false, width: 1000 },
      companion: { collapsed: true, width: 1000, height: 1, placement: 'bottom' },
    }, {
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 120,
      maxWidth: 480,
    }, {
      collapsible: true,
      resizable: true,
      defaultWidth: 320,
      minWidth: 160,
      maxWidth: 600,
    }, {
      content: () => null,
      placement: 'bottom',
      side: {
        collapsible: true,
        resizable: true,
        defaultWidth: 300,
        minWidth: 200,
        maxWidth: 700,
      },
      bottom: { defaultHeight: 240, minHeight: 160, maxHeight: 520, mainMinHeight: 320 },
      presentation: {
        accessibleLabel: 'companion',
        rail: 'standard',
        collapseLabel: 'collapse',
        expandLabel: 'expand',
        resizeLabel: 'resize',
      },
    });

    expect(result.navigation).toEqual({ collapsed: true, width: 120 });
    expect(result.navigator).toEqual({ collapsed: false, width: 600 });
    expect(result.companion).toEqual({
      collapsed: true,
      width: 700,
      height: 160,
      placement: 'bottom',
    });
  });

  it('falls back malformed values to declared defaults', () => {
    const result = resolveProductShellPreferences({
      navigation: { collapsed: false, width: Number.NaN },
      companion: { collapsed: false, width: Number.POSITIVE_INFINITY, height: Number.NaN, placement: 'side' },
    });
    expect(result.navigation.width).toBe(256);
    expect(result.companion.width).toBe(320);
    expect(result.companion.height).toBe(240);
  });

  it('fails fast when a region default falls outside its declared limits', () => {
    expect(() => assertProductShellRegionBehavior({
      collapsible: true,
      resizable: true,
      defaultWidth: 100,
      minWidth: 120,
      maxWidth: 600,
    }, 'navigation')).toThrow('Invalid ProductShell navigation region behavior limits');
  });

  it('fails fast when companion height limits are invalid', () => {
    expect(() => assertProductShellCompanionRegion({
      content: () => null,
      placement: 'side',
      side: {
        collapsible: true,
        resizable: true,
        defaultWidth: 300,
        minWidth: 200,
        maxWidth: 700,
      },
      bottom: { defaultHeight: 100, minHeight: 160, maxHeight: 520, mainMinHeight: 320 },
      presentation: {
        accessibleLabel: 'companion',
        rail: 'standard',
        collapseLabel: 'collapse',
        expandLabel: 'expand',
        resizeLabel: 'resize',
      },
    })).toThrow('Invalid ProductShell companion height limits');
  });
});
