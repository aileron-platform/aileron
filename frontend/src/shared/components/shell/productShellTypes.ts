import type React from 'react';

/**
 * Runtime behaviour that a product may declare for one semantic shell region.
 * Geometry is owned by ProductShell; adapters only provide these limits.
 */
export interface ProductShellRegionBehavior {
  collapsible: boolean;
  resizable: boolean;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
}

export interface ProductShellColumnRenderState {
  collapsed: boolean;
}

export interface ProductShellRegionHeader {
  leading?: React.ReactNode;
  title?: React.ReactNode;
  info?: React.ReactNode;
  actions?: React.ReactNode;
}

export interface ProductShellColumnRegion {
  content: (state: ProductShellColumnRenderState) => React.ReactNode;
  behavior: ProductShellRegionBehavior;
  presentation: {
    accessibleLabel: string;
    responsive: 'always' | 'desktop-up';
    header?: ProductShellRegionHeader;
  };
}

export interface ProductShellMainRegion {
  content: React.ReactNode;
  accessibleLabel: string;
}

export type ProductShellCompanionRenderState =
  | { placement: 'side'; collapsed: boolean; fullscreen: boolean }
  | { placement: 'bottom'; collapsed: false; fullscreen: boolean };

export type ProductShellCompanionRail = 'standard' | 'compact';

export interface ProductShellCompanionRegion {
  content: (state: ProductShellCompanionRenderState) => React.ReactNode;
  placement: 'side' | 'bottom';
  side: ProductShellRegionBehavior;
  bottom: {
    defaultHeight: number;
    minHeight: number;
    maxHeight: number;
    mainMinHeight: number;
  };
  presentation: {
    accessibleLabel: string;
    rail: ProductShellCompanionRail;
    header?: ProductShellRegionHeader;
    collapsedContent?: React.ReactNode;
    collapseLabel: string;
    expandLabel: string;
    resizeLabel: string;
  };
  revealRequestId?: number;
}

export type ProductShellDisplay =
  | { mode: 'main-expanded'; onExit: () => void }
  | { mode: 'companion-fullscreen'; onExit: () => void };

export interface ProductShellPreferences {
  navigation?: { collapsed: boolean; width: number };
  navigator?: { collapsed: boolean; width: number };
  companion?: {
    collapsed: boolean;
    width: number;
    height: number;
    placement: 'side' | 'bottom';
  };
}

export type ProductShellBody =
  | {
      kind: 'regions';
      navigation?: ProductShellColumnRegion;
      navigator?: ProductShellColumnRegion;
      main: ProductShellMainRegion;
      companion?: ProductShellCompanionRegion;
    }
  | {
      kind: 'state';
      content: React.ReactNode;
    };

export interface ProductShellPreferencesAdapter {
  identity: string;
  load(): ProductShellPreferences | null;
  save(preferences: ProductShellPreferences): void;
}

export interface ProductShellProps {
  topBar?: React.ReactNode;
  header?: React.ReactNode;
  body: ProductShellBody;
  preferences?: ProductShellPreferencesAdapter;
  display?: ProductShellDisplay;
}
