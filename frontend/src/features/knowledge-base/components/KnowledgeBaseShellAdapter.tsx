import React from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ProductShell,
  type ProductShellBody,
  type ProductShellColumnRegion,
} from '@/shared/components/shell';

/**
 * A Knowledge Base surface describes product content only. The adapter owns
 * the ProductShell region mapping so route components never construct shell
 * geometry or resize controls directly.
 */
export type KnowledgeBaseShellRegionContent =
  | React.ReactNode
  | ((state: { collapsed: boolean }) => React.ReactNode);

export interface KnowledgeBaseShellRegionHeader {
  leading?: React.ReactNode;
  title?: React.ReactNode;
  info?: React.ReactNode;
  actions?: React.ReactNode;
}

export interface KnowledgeBaseShellColumnSurface {
  content: KnowledgeBaseShellRegionContent;
  accessibleLabel: string;
  title?: React.ReactNode;
  icon?: LucideIcon;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  header?: KnowledgeBaseShellRegionHeader;
}

export interface KnowledgeBaseShellMainSurface {
  content: React.ReactNode;
  accessibleLabel: string;
}

export type KnowledgeBaseShellSurface =
  | {
      kind: 'regions';
      header?: React.ReactNode;
      navigation?: KnowledgeBaseShellColumnSurface;
      navigator?: KnowledgeBaseShellColumnSurface;
      main: KnowledgeBaseShellMainSurface;
    }
  | {
      kind: 'state';
      header?: React.ReactNode;
      content: React.ReactNode;
    };

export interface KnowledgeBaseShellAdapterProps {
  navigationSlot?: React.ReactNode;
  surface: KnowledgeBaseShellSurface;
}

const NAVIGATION_BEHAVIOR = {
  collapsible: true,
  resizable: true,
  defaultWidth: 240,
  minWidth: 240,
  maxWidth: 600,
};

const NAVIGATOR_BEHAVIOR = {
  collapsible: true,
  resizable: true,
  defaultWidth: 270,
  minWidth: 270,
  maxWidth: 600,
};

const mapHeader = (surface: KnowledgeBaseShellColumnSurface): KnowledgeBaseShellRegionHeader | undefined => {
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
  surface: KnowledgeBaseShellColumnSurface,
  slot: 'navigation' | 'navigator',
): ProductShellColumnRegion => ({
  content: (state) => (
    state.collapsed && typeof surface.content !== 'function'
      ? null
      : typeof surface.content === 'function'
        ? surface.content(state)
        : surface.content
  ),
  behavior: slot === 'navigation' ? NAVIGATION_BEHAVIOR : NAVIGATOR_BEHAVIOR,
  presentation: {
    accessibleLabel: surface.accessibleLabel,
    responsive: 'always',
    header: mapHeader(surface),
  },
});

export const KnowledgeBaseShellAdapter: React.FC<KnowledgeBaseShellAdapterProps> = ({
  navigationSlot,
  surface,
}) => {
  const body: ProductShellBody = surface.kind === 'state'
    ? { kind: 'state', content: surface.content }
    : {
        kind: 'regions',
        navigation: surface.navigation ? mapColumn(surface.navigation, 'navigation') : undefined,
        navigator: surface.navigator ? mapColumn(surface.navigator, 'navigator') : undefined,
        main: surface.main,
      };

  return (
    <ProductShell
      topBar={navigationSlot}
      header={surface.header}
      body={body}
    />
  );
};
