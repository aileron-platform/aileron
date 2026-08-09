import type React from 'react';
import type { LucideIcon } from 'lucide-react';

/**
 * Semantic regions emitted by the document workbench.
 *
 * The workbench owns document state and content. A product shell owns the
 * geometry, persistence, and interaction contract for these regions.
 */
export interface DocumentWorkbenchRenderSurface {
  kind: 'regions';
  header: React.ReactNode;
  navigator?: {
    content: (state: { collapsed: boolean }) => React.ReactNode;
    accessibleLabel: string;
    title?: React.ReactNode;
    icon?: LucideIcon;
    info?: React.ReactNode;
    actions?: React.ReactNode;
    header?: {
      leading?: React.ReactNode;
      title?: React.ReactNode;
      info?: React.ReactNode;
      actions?: React.ReactNode;
    };
  };
  main: {
    content: React.ReactNode;
    accessibleLabel: string;
  };
}
