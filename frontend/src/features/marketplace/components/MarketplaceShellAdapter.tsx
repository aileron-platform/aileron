import React from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ProductShell,
  type ProductShellBody,
  type ProductShellColumnRegion,
  type ProductShellRegionBehavior,
  type ProductShellRegionChrome,
} from '@/shared/components/shell';

export type MarketplaceShellColumnRenderState = { collapsed: boolean };

export interface MarketplaceShellRegionHeader {
  leading?: React.ReactNode;
  title?: React.ReactNode;
  info?: React.ReactNode;
  actions?: React.ReactNode;
}

export type MarketplaceShellRegionPreset =
  | 'navigation'
  | 'settings-navigation'
  | 'navigator'
  | 'settings-navigator'
  | 'detail-navigation'
  | 'editor-navigation'
  | 'center-filters';

export type MarketplaceShellRegionContent =
  | React.ReactNode
  | ((state: MarketplaceShellColumnRenderState) => React.ReactNode);

export interface MarketplaceShellColumnSurface {
  content: MarketplaceShellRegionContent;
  accessibleLabel: string;
  preset?: MarketplaceShellRegionPreset;
  title?: React.ReactNode;
  icon?: LucideIcon;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  header?: MarketplaceShellRegionHeader;
}

export interface MarketplaceShellMainSurface {
  content: React.ReactNode;
  accessibleLabel: string;
}

export type MarketplaceShellStateSurface = {
  kind: 'state';
  header?: React.ReactNode;
  content: React.ReactNode;
};

export interface MarketplaceRegionsShellSurface {
  kind: 'regions' | 'settings';
  header?: React.ReactNode;
  navigation?: MarketplaceShellColumnSurface;
  navigator?: MarketplaceShellColumnSurface;
  main: MarketplaceShellMainSurface;
}

export type MarketplaceShellSurface =
  | MarketplaceShellStateSurface
  | MarketplaceRegionsShellSurface;

export interface MarketplaceShellAdapterProps {
  navigationSlot?: React.ReactNode;
  surface: MarketplaceShellSurface;
}

const REGION_PRESETS: Record<MarketplaceShellRegionPreset, {
  behavior: ProductShellRegionBehavior;
  chrome: ProductShellRegionChrome;
  responsive: 'always' | 'desktop-up';
}> = {
  navigation: {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 520,
    },
    chrome: 'navigation',
    responsive: 'always',
  },
  'settings-navigation': {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 360,
    },
    chrome: 'navigation',
    responsive: 'always',
  },
  navigator: {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 270,
      minWidth: 270,
      maxWidth: 520,
    },
    chrome: 'navigator-muted',
    responsive: 'always',
  },
  'settings-navigator': {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 270,
      minWidth: 270,
      maxWidth: 352,
    },
    chrome: 'navigator-plain',
    responsive: 'always',
  },
  'detail-navigation': {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 520,
    },
    chrome: 'navigator-plain',
    responsive: 'always',
  },
  'editor-navigation': {
    behavior: {
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 520,
    },
    chrome: 'navigation',
    responsive: 'always',
  },
  'center-filters': {
    behavior: {
      collapsible: false,
      resizable: true,
      defaultWidth: 270,
      minWidth: 270,
      maxWidth: 420,
    },
    chrome: 'navigator-muted',
    responsive: 'desktop-up',
  },
};

const mapHeader = (surface: MarketplaceShellColumnSurface): MarketplaceShellRegionHeader | undefined => {
  if (surface.header) {
    return surface.header;
  }
  if (!surface.title && !surface.icon && !surface.info && !surface.actions) {
    return undefined;
  }
  const Icon = surface.icon;
  return {
    leading: Icon
      ? <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-primary" />
      : undefined,
    title: surface.title,
    info: surface.info,
    actions: surface.actions,
  };
};

const mapColumn = (
  surface: MarketplaceShellColumnSurface,
  slot: 'navigation' | 'navigator',
): ProductShellColumnRegion => {
  const preset = surface.preset ?? (slot === 'navigation' ? 'navigation' : 'navigator');
  const configuration = REGION_PRESETS[preset];
  return {
    content: (state) => (
      state.collapsed && typeof surface.content !== 'function'
        ? null
        : typeof surface.content === 'function'
          ? surface.content(state)
          : surface.content
    ),
    behavior: configuration.behavior,
    presentation: {
      accessibleLabel: surface.accessibleLabel,
      chrome: configuration.chrome,
      responsive: configuration.responsive,
      header: mapHeader(surface),
    },
  };
};

const bodyForSurface = (surface: MarketplaceShellSurface): ProductShellBody => {
  if (surface.kind === 'state') {
    return surface;
  }
  return {
    kind: 'regions',
    navigation: surface.navigation ? mapColumn(surface.navigation, 'navigation') : undefined,
    navigator: surface.navigator ? mapColumn(surface.navigator, 'navigator') : undefined,
    main: surface.main,
  };
};

/**
 * Marketplace is the only feature-level owner of the ProductShell mapping.
 * Route components provide named surfaces; shared shell geometry remains in
 * ProductShell and is never recreated here.
 */
export const MarketplaceShellAdapter: React.FC<MarketplaceShellAdapterProps> = ({
  navigationSlot,
  surface,
}) => (
  <ProductShell
    topBar={navigationSlot}
    header={surface.header}
    body={bodyForSurface(surface)}
  />
);
