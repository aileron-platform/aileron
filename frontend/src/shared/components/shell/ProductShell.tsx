import React from 'react';
import { SidebarCollapseToggle } from '@/shared/components/layout/CollapsedSidebarControls';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  assertProductShellCompanionRegion,
  assertProductShellRegionBehavior,
  clampProductShellValue,
  PRODUCT_SHELL_COLLAPSED_COLUMN_WIDTH,
  PRODUCT_SHELL_COMPACT_COMPANION_WIDTH,
  PRODUCT_SHELL_DEFAULT_COMPANION,
  PRODUCT_SHELL_DEFAULT_NAVIGATOR_BEHAVIOR,
  PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR,
  PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
  resolveProductShellPreferences,
  toProductShellPreferences,
  type ProductShellResolvedPreferences,
} from './productShellPreferences';
import type {
  ProductShellBody,
  ProductShellColumnRegion,
  ProductShellCompanionRegion,
  ProductShellCompanionRenderState,
  ProductShellPreferences,
  ProductShellProps,
  ProductShellRegionBehavior,
  ProductShellRegionHeader,
} from './productShellTypes';

type ShellColumnKey = 'navigation' | 'navigator';

type ProductShellRuntimeState = ProductShellResolvedPreferences;

interface ResizeState {
  kind: ShellColumnKey | 'companion-width' | 'companion-height';
  startPointer: number;
  startValue: number;
}

const BODY_CLASS_NAMES = ['select-none', 'cursor-col-resize', 'cursor-row-resize'] as const;

const getColumnBehavior = (
  body: ProductShellBody,
  key: ShellColumnKey,
): ProductShellRegionBehavior => {
  if (body.kind === 'regions') {
    const region = body[key];
    if (region) {
      assertProductShellRegionBehavior(region.behavior, key);
      return region.behavior;
    }
  }
  return key === 'navigator'
    ? PRODUCT_SHELL_DEFAULT_NAVIGATOR_BEHAVIOR
    : PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR;
};

const getCompanionRegion = (body: ProductShellBody): ProductShellCompanionRegion | undefined => {
  if (body.kind !== 'regions' || !body.companion) {
    return undefined;
  }
  assertProductShellCompanionRegion(body.companion);
  return body.companion;
};

const visibleWidth = (
  state: { width: number; collapsed: boolean } | undefined,
  behavior: ProductShellRegionBehavior | undefined,
): number => {
  if (!state || !behavior) {
    return 0;
  }
  return behavior.collapsible && state.collapsed
    ? PRODUCT_SHELL_COLLAPSED_COLUMN_WIDTH
    : state.width;
};

const shouldYieldSideCompanion = (
  body: ProductShellBody,
  current: ProductShellRuntimeState,
): boolean => {
  const companion = getCompanionRegion(body);
  if (
    !companion
    || companion.placement !== 'side'
    || !companion.side.collapsible
    || current.companion.collapsed
  ) {
    return false;
  }

  const navigationWidth = visibleWidth(
    current.navigation,
    body.kind === 'regions' ? body.navigation?.behavior : undefined,
  );
  const navigatorWidth = visibleWidth(
    current.navigator,
    body.kind === 'regions' ? body.navigator?.behavior : undefined,
  );

  return getInnerWidth() < navigationWidth
    + navigatorWidth
    + companion.side.minWidth
    + PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH;
};

const hasRegions = (body: ProductShellBody): body is Extract<ProductShellBody, { kind: 'regions' }> => (
  body.kind === 'regions'
);

const getInnerWidth = (): number => (
  typeof window === 'undefined' ? 1440 : window.innerWidth
);

const getInnerHeight = (): number => (
  typeof window === 'undefined' ? 900 : window.innerHeight
);

const withClampedRuntime = (
  current: ProductShellRuntimeState,
  body: ProductShellBody,
  rootElement: HTMLElement | null,
): ProductShellRuntimeState => {
  const navigationBehavior = getColumnBehavior(body, 'navigation');
  const navigatorBehavior = getColumnBehavior(body, 'navigator');
  const companion = getCompanionRegion(body);
  const companionSide = companion?.side ?? PRODUCT_SHELL_DEFAULT_COMPANION;
  const companionBottom = companion?.bottom ?? PRODUCT_SHELL_DEFAULT_COMPANION;
  const navigationMax = Math.max(
    navigationBehavior.minWidth,
    Math.min(
      navigationBehavior.maxWidth,
      getInnerWidth()
        - visibleWidth(current.navigator, body.kind === 'regions' ? body.navigator?.behavior : undefined)
        - (current.companion.placement === 'side' && companion
          ? visibleWidth(current.companion, companionSide)
          : 0)
        - PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
    ),
  );
  const navigatorMax = Math.max(
    navigatorBehavior.minWidth,
    Math.min(
      navigatorBehavior.maxWidth,
      getInnerWidth()
        - visibleWidth(current.navigation, body.kind === 'regions' ? body.navigation?.behavior : undefined)
        - (current.companion.placement === 'side' && companion
          ? visibleWidth(current.companion, companionSide)
          : 0)
        - PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
    ),
  );
  const companionWidthMax = Math.max(
    companionSide.minWidth,
    Math.min(
      companionSide.maxWidth,
      getInnerWidth()
        - visibleWidth(current.navigation, body.kind === 'regions' ? body.navigation?.behavior : undefined)
        - visibleWidth(current.navigator, body.kind === 'regions' ? body.navigator?.behavior : undefined)
        - PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
    ),
  );

  const measuredRectHeight = rootElement?.getBoundingClientRect().height;
  const measuredHeight = measuredRectHeight === 0 && current.companion.height > companionBottom.defaultHeight
    ? 0
    : rootElement?.clientHeight
      || measuredRectHeight
      || (current.companion.height > companionBottom.defaultHeight ? 0 : undefined);
  const availableHeight = measuredHeight ?? getInnerHeight();
  const bottomHeightMax = Math.max(
    companionBottom.minHeight,
    Math.min(
      companionBottom.maxHeight,
      availableHeight - companionBottom.mainMinHeight - 4,
    ),
  );

  return {
    navigation: {
      collapsed: current.navigation.collapsed,
      width: clampProductShellValue(current.navigation.width, navigationBehavior.minWidth, navigationMax),
    },
    navigator: {
      collapsed: current.navigator.collapsed,
      width: clampProductShellValue(current.navigator.width, navigatorBehavior.minWidth, navigatorMax),
    },
    companion: {
      ...current.companion,
      width: clampProductShellValue(current.companion.width, companionSide.minWidth, companionWidthMax),
      height: clampProductShellValue(current.companion.height, companionBottom.minHeight, bottomHeightMax),
    },
  };
};

const withInitialCompanionClamp = (
  current: ProductShellRuntimeState,
  body: ProductShellBody,
  rootElement: HTMLElement | null,
): ProductShellRuntimeState => {
  const companion = getCompanionRegion(body);
  if (!companion) {
    return current;
  }
  const companionWidthMax = Math.max(
    companion.side.minWidth,
    Math.min(
      companion.side.maxWidth,
      getInnerWidth()
        - visibleWidth(current.navigation, body.kind === 'regions' ? body.navigation?.behavior : undefined)
        - visibleWidth(current.navigator, body.kind === 'regions' ? body.navigator?.behavior : undefined)
        - PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
    ),
  );
  const measuredRectHeight = rootElement?.getBoundingClientRect().height;
  const measuredClientHeight = rootElement?.clientHeight;
  const measuredHeight = measuredClientHeight || measuredRectHeight;
  const availableHeight = rootElement && measuredHeight === 0
    ? current.companion.height > companion.bottom.defaultHeight ? 0 : getInnerHeight()
    : measuredHeight || getInnerHeight();
  const maxHeight = Math.max(
    companion.bottom.minHeight,
    Math.min(
      companion.bottom.maxHeight,
      availableHeight - companion.bottom.mainMinHeight - 4,
    ),
  );
  const height = clampProductShellValue(
    current.companion.height,
    companion.bottom.minHeight,
    maxHeight,
  );
  const width = clampProductShellValue(
    current.companion.width,
    companion.side.minWidth,
    companionWidthMax,
  );
  return height === current.companion.height && width === current.companion.width
    ? current
    : { ...current, companion: { ...current.companion, width, height } };
};

const readInitialRuntime = (
  body: ProductShellBody,
  loaded: ProductShellPreferences | null | undefined,
): ProductShellRuntimeState => {
  const navigationBehavior = getColumnBehavior(body, 'navigation');
  const navigatorBehavior = getColumnBehavior(body, 'navigator');
  const companion = getCompanionRegion(body);
  const resolved = resolveProductShellPreferences(
    loaded,
    navigationBehavior,
    navigatorBehavior,
    companion,
  );
  return {
    ...resolved,
    companion: {
      ...resolved.companion,
      placement: companion?.placement ?? resolved.companion.placement,
    },
  };
};

const renderHeaderSlots = (header: ProductShellRegionHeader | undefined): React.ReactNode => {
  if (!header) {
    return null;
  }
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      {header.leading ? <div className="flex shrink-0 items-center">{header.leading}</div> : null}
      {header.title ? (
        <div className="min-w-0 flex-1 text-sm font-medium text-foreground">
          {typeof header.title === 'string' || typeof header.title === 'number' ? (
            <span className="block truncate">{header.title}</span>
          ) : header.title}
        </div>
      ) : null}
      {header.info ? <div className="flex shrink-0 items-center">{header.info}</div> : null}
      {header.actions ? <div className="ml-auto flex shrink-0 items-center gap-1">{header.actions}</div> : null}
    </div>
  );
};

const getColumnChrome = (region: ProductShellColumnRegion): {
  region: string;
  header: string;
  content: string;
} => {
  switch (region.presentation.chrome) {
    case 'navigation':
      return {
        region: 'border-r border-border bg-background',
        header: 'border-b border-sidebar-border bg-card',
        content: 'bg-background',
      };
    case 'navigator-plain':
      return {
        region: 'border-r border-border bg-background',
        header: 'border-b border-border bg-card',
        content: 'bg-background',
      };
    case 'navigator-muted':
      return {
        region: 'border-r border-border bg-muted/20',
        header: 'border-b border-border bg-card',
        content: 'bg-muted/20',
      };
    default:
      return {
        region: 'border-r border-border bg-background',
        header: 'border-b border-border bg-card',
        content: 'bg-background',
      };
  }
};

const getCompanionChrome = (region: ProductShellCompanionRegion): {
  region: string;
  collapsedWidth: number;
  header: string;
  content: string;
} => region.presentation.chrome === 'plain-compact-rail'
  ? {
      region: 'border-l border-border bg-background',
      collapsedWidth: PRODUCT_SHELL_COMPACT_COMPANION_WIDTH,
      header: 'border-b border-border bg-background',
      content: 'bg-background',
    }
  : {
      region: 'border-l border-border bg-muted/20',
      collapsedWidth: PRODUCT_SHELL_COLLAPSED_COLUMN_WIDTH,
      header: 'border-b border-border bg-card',
      content: 'bg-muted/20',
    };

export const ProductShell: React.FC<ProductShellProps> = ({
  topBar,
  header,
  body,
  preferences,
  display,
}) => {
  const { t } = useI18n();
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const identity = preferences?.identity;
  const loadedPreferences = React.useMemo(
    () => preferences?.load() ?? null,
    [identity],
  );
  const [layout, setLayout] = React.useState<ProductShellRuntimeState>(() => (
    readInitialRuntime(body, loadedPreferences)
  ));
  const [responsiveCompanionCollapsed, setResponsiveCompanionCollapsed] = React.useState(() => (
    shouldYieldSideCompanion(body, readInitialRuntime(body, loadedPreferences))
  ));
  const layoutRef = React.useRef(layout);
  layoutRef.current = layout;
  const currentAdapterRef = React.useRef<ProductShellProps['preferences']>(preferences);
  currentAdapterRef.current = preferences;
  const pendingSaveRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const resizeRef = React.useRef<ResizeState | null>(null);
  const [resizeState, setResizeState] = React.useState<ResizeState | null>(null);
  const lastIdentityRef = React.useRef(identity);
  const lastBodyKindRef = React.useRef(body.kind);
  const revealRef = React.useRef<{ identity: string | undefined; requestId: number }>({
    identity,
    requestId: hasRegions(body) ? body.companion?.revealRequestId ?? 0 : 0,
  });

  const clearPendingSave = React.useCallback(() => {
    if (pendingSaveRef.current) {
      clearTimeout(pendingSaveRef.current);
      pendingSaveRef.current = null;
    }
  }, []);

  const scheduleSave = React.useCallback((next: ProductShellRuntimeState) => {
    const adapter = currentAdapterRef.current;
    if (!adapter) {
      return;
    }
    clearPendingSave();
    pendingSaveRef.current = setTimeout(() => {
      pendingSaveRef.current = null;
      if (currentAdapterRef.current?.identity !== adapter.identity) {
        return;
      }
      adapter.save(toProductShellPreferences(next));
    }, 500);
  }, [clearPendingSave]);

  const commitLayout = React.useCallback((
    updater: (current: ProductShellRuntimeState) => ProductShellRuntimeState,
    persist = true,
  ) => {
    setLayout((current) => {
      const next = updater(current);
      if (persist) {
        scheduleSave(next);
      }
      return next;
    });
  }, [scheduleSave]);

  React.useEffect(() => () => {
    clearPendingSave();
    resizeRef.current = null;
    BODY_CLASS_NAMES.forEach((className) => document.body.classList.remove(className));
  }, [clearPendingSave]);

  React.useEffect(() => {
    if (lastIdentityRef.current === identity) {
      return;
    }
    lastIdentityRef.current = identity;
    clearPendingSave();
    const nextLayout = readInitialRuntime(body, loadedPreferences);
    setLayout(nextLayout);
    setResponsiveCompanionCollapsed(shouldYieldSideCompanion(body, nextLayout));
  }, [body, clearPendingSave, identity, loadedPreferences]);

  React.useEffect(() => {
    if (lastBodyKindRef.current === 'regions' && body.kind === 'state') {
      clearPendingSave();
    }
    lastBodyKindRef.current = body.kind;
  }, [body.kind, clearPendingSave]);

  React.useEffect(() => {
    const nextRuntime = withInitialCompanionClamp(layoutRef.current, body, rootRef.current);
    setLayout((current) => (
      current.companion.height === nextRuntime.companion.height
        && current.companion.width === nextRuntime.companion.width
        ? current
        : nextRuntime
    ));
    setResponsiveCompanionCollapsed(shouldYieldSideCompanion(body, layoutRef.current));
  }, [body]);

  React.useEffect(() => {
    const nextResponsiveState = hasRegions(body)
      ? shouldYieldSideCompanion(body, layout)
      : false;
    setResponsiveCompanionCollapsed((current) => (
      current === nextResponsiveState ? current : nextResponsiveState
    ));
  }, [body, layout]);

  React.useEffect(() => {
    if (!hasRegions(body) || !body.companion) {
      return;
    }
    const nextPlacement = body.companion.placement;
    if (layoutRef.current.companion.placement !== nextPlacement) {
      setLayout((current) => {
        const next = {
          ...current,
          companion: { ...current.companion, placement: nextPlacement },
        };
        scheduleSave(next);
        return next;
      });
    }
  }, [body, scheduleSave]);

  React.useEffect(() => {
    if (!hasRegions(body)) {
      return;
    }
    const nextRequestId = body.companion?.revealRequestId ?? 0;
    const previous = revealRef.current;
    if (previous.identity !== identity) {
      revealRef.current = { identity, requestId: nextRequestId };
      return;
    }
    if (
      body.companion
      && body.companion.placement === 'side'
      && nextRequestId > previous.requestId
      && body.companion.side.collapsible
      && layoutRef.current.companion.collapsed
    ) {
      commitLayout((current) => ({
        ...current,
        companion: { ...current.companion, collapsed: false },
      }));
    }
    revealRef.current.requestId = nextRequestId;
  }, [body, commitLayout, identity]);

  React.useEffect(() => {
    if (!resizeState) {
      return;
    }
    const handleMouseMove = (event: MouseEvent) => {
      const activeResize = resizeRef.current;
      if (!activeResize) {
        return;
      }
      const currentBody = body;
      const companion = getCompanionRegion(currentBody);
      const navigationBehavior = getColumnBehavior(currentBody, 'navigation');
      const navigatorBehavior = getColumnBehavior(currentBody, 'navigator');
      if (activeResize.kind === 'companion-height' && companion) {
        const dynamicMax = Math.max(
          companion.bottom.minHeight,
          Math.min(
            companion.bottom.maxHeight,
            (
              rootRef.current?.clientHeight
              || rootRef.current?.getBoundingClientRect().height
              || getInnerHeight()
            ) - companion.bottom.mainMinHeight - 4,
          ),
        );
        const nextHeight = clampProductShellValue(
          activeResize.startValue - (event.clientY - activeResize.startPointer),
          companion.bottom.minHeight,
          dynamicMax,
        );
        commitLayout((current) => ({
          ...current,
          companion: { ...current.companion, height: nextHeight },
        }));
        return;
      }

      const isCompanionWidth = activeResize.kind === 'companion-width';
      const behavior = isCompanionWidth
        ? companion?.side
        : activeResize.kind === 'navigation' ? navigationBehavior : navigatorBehavior;
      if (!behavior) {
        return;
      }
      const visibleSiblingWidth = activeResize.kind === 'navigation'
        ? visibleWidth(layoutRef.current.navigator, currentBody.kind === 'regions' ? currentBody.navigator?.behavior : undefined)
        : activeResize.kind === 'navigator'
          ? visibleWidth(layoutRef.current.navigation, currentBody.kind === 'regions' ? currentBody.navigation?.behavior : undefined)
          : visibleWidth(layoutRef.current.navigation, currentBody.kind === 'regions' ? currentBody.navigation?.behavior : undefined)
            + visibleWidth(layoutRef.current.navigator, currentBody.kind === 'regions' ? currentBody.navigator?.behavior : undefined);
      const dynamicMax = Math.max(
        behavior.minWidth,
        Math.min(
          behavior.maxWidth,
          getInnerWidth() - visibleSiblingWidth - PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
        ),
      );
      const sign = isCompanionWidth ? -1 : 1;
      const nextWidth = clampProductShellValue(
        activeResize.startValue + sign * (event.clientX - activeResize.startPointer),
        behavior.minWidth,
        dynamicMax,
      );
      commitLayout((current) => {
        if (activeResize.kind === 'navigation') {
          return { ...current, navigation: { ...current.navigation, width: nextWidth } };
        }
        if (activeResize.kind === 'navigator') {
          return { ...current, navigator: { ...current.navigator, width: nextWidth } };
        }
        return { ...current, companion: { ...current.companion, width: nextWidth } };
      });
    };
    const handleMouseUp = () => {
      resizeRef.current = null;
      setResizeState(null);
      BODY_CLASS_NAMES.forEach((className) => document.body.classList.remove(className));
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      resizeRef.current = null;
      BODY_CLASS_NAMES.forEach((className) => document.body.classList.remove(className));
    };
  }, [body, commitLayout, resizeState]);

  React.useEffect(() => {
    if (!hasRegions(body)) {
      return undefined;
    }
    const handleWindowResize = () => {
      setResponsiveCompanionCollapsed(shouldYieldSideCompanion(body, layoutRef.current));
      setLayout((current) => withClampedRuntime(current, body, rootRef.current));
    };
    window.addEventListener('resize', handleWindowResize);
    const resizeObserver = typeof ResizeObserver !== 'undefined' && rootRef.current
      ? new ResizeObserver(handleWindowResize)
      : null;
    if (resizeObserver && rootRef.current) {
      resizeObserver.observe(rootRef.current);
    }
    return () => {
      window.removeEventListener('resize', handleWindowResize);
      resizeObserver?.disconnect();
    };
  }, [body]);

  React.useEffect(() => {
    if (!display || display.mode === 'main-expanded' || display.mode === 'companion-fullscreen') {
      if (!display) {
        return undefined;
      }
      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          display.onExit();
        }
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
    return undefined;
  }, [display]);

  const startResize = (kind: ResizeState['kind'], event: React.MouseEvent) => {
    event.preventDefault();
    const startValue = kind === 'navigation'
      ? layoutRef.current.navigation.width
      : kind === 'navigator'
        ? layoutRef.current.navigator.width
        : kind === 'companion-width'
          ? layoutRef.current.companion.width
          : layoutRef.current.companion.height;
    const next: ResizeState = {
      kind,
      startPointer: kind === 'companion-height' ? event.clientY : event.clientX,
      startValue,
    };
    resizeRef.current = next;
    setResizeState(next);
    document.body.classList.add('select-none', kind === 'companion-height' ? 'cursor-row-resize' : 'cursor-col-resize');
  };

  const toggleColumn = (key: ShellColumnKey) => {
    const region = hasRegions(body) ? body[key] : undefined;
    if (!region?.behavior.collapsible) {
      return;
    }
    commitLayout((current) => ({
      ...current,
      [key]: { ...current[key], collapsed: !current[key].collapsed },
    }));
  };

  const toggleCompanion = () => {
    const companion = getCompanionRegion(body);
    if (!companion?.side.collapsible || companion.placement !== 'side') {
      return;
    }
    commitLayout((current) => ({
      ...current,
      companion: {
        ...current.companion,
        collapsed: responsiveCompanionCollapsed ? false : !current.companion.collapsed,
      },
    }));
  };

  const renderColumn = (key: ShellColumnKey, region: ProductShellColumnRegion | undefined): React.ReactNode => {
    if (!region) {
      return null;
    }
    const chrome = getColumnChrome(region);
    const state = layout[key];
    const collapsed = region.behavior.collapsible && state.collapsed;
    const isVisibleByDisplay = display?.mode !== 'main-expanded' && display?.mode !== 'companion-fullscreen';
    if (!isVisibleByDisplay) {
      return null;
    }
    const hiddenAtResponsiveBreakpoint = region.presentation.responsive === 'desktop-up';
    const hasHeader = Boolean(region.presentation.header) || region.behavior.collapsible;
    return (
      <aside
        aria-label={region.presentation.accessibleLabel}
        data-shell-region={key}
        className={cn(
          'relative flex h-full min-h-0 shrink-0 flex-col transition-[width] duration-200',
          chrome.region,
          hiddenAtResponsiveBreakpoint && 'max-[1023px]:hidden',
        )}
        style={{ width: collapsed ? PRODUCT_SHELL_COLLAPSED_COLUMN_WIDTH : state.width }}
      >
        {hasHeader ? (
          <div className={cn(
            'flex h-10 shrink-0 items-center gap-2 px-3',
            collapsed ? 'justify-center px-0' : 'justify-between',
            chrome.header,
          )}>
            {collapsed ? null : renderHeaderSlots(region.presentation.header)}
            {region.behavior.collapsible ? (
              <SidebarCollapseToggle
                collapsed={collapsed}
                label={collapsed ? t('shared.shell.expandSidebar') : t('shared.shell.collapseSidebar')}
                onClick={() => toggleColumn(key)}
              />
            ) : null}
          </div>
        ) : null}
        <div className={cn(
          'flex min-h-0 flex-1 flex-col overflow-hidden [&>*]:min-h-0 [&>*]:flex-1',
          chrome.content,
        )}>
          {collapsed && key !== 'navigation' ? (
            <div className="flex min-h-0 flex-1 flex-col items-center overflow-hidden pt-3">
              {region.presentation.header?.leading}
            </div>
          ) : region.content({ collapsed })}
        </div>
        {region.behavior.resizable && !collapsed ? (
          <div
            role="separator"
            aria-orientation="vertical"
            className={cn(
              'absolute right-0 top-0 h-full w-1 cursor-col-resize transition-colors',
              resizeState?.kind === key ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
            )}
            onMouseDown={(event) => startResize(key, event)}
          />
        ) : null}
      </aside>
    );
  };

  const renderCompanion = (region: ProductShellCompanionRegion): React.ReactNode => {
    const chrome = getCompanionChrome(region);
    const fullscreen = display?.mode === 'companion-fullscreen';
    const placement = region.placement;
    const rawCollapsed = layout.companion.collapsed;
    const collapsedByResponsive = placement === 'side'
      && region.side.collapsible
      && responsiveCompanionCollapsed
      && !fullscreen;
    const collapsed = placement === 'side'
      && region.side.collapsible
      && (rawCollapsed || collapsedByResponsive)
      && !fullscreen;
    const renderState: ProductShellCompanionRenderState = placement === 'side'
      ? { placement, collapsed, fullscreen }
      : { placement, collapsed: false, fullscreen };
    if (placement === 'bottom') {
      return (
        <section
          aria-label={region.presentation.accessibleLabel}
          data-shell-region="companion"
          className={cn(
            'flex min-h-0 w-full shrink-0 flex-col border-t border-border bg-background',
            fullscreen && 'fixed inset-0 z-50 h-screen',
          )}
          style={fullscreen ? undefined : { height: layout.companion.height }}
        >
          {!fullscreen ? (
            <div
              role="separator"
              aria-label={region.presentation.resizeLabel}
              aria-orientation="horizontal"
              className={cn(
                'h-1 w-full shrink-0 cursor-row-resize transition-colors',
                resizeState?.kind === 'companion-height' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
              )}
              onMouseDown={(event) => startResize('companion-height', event)}
            />
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {region.presentation.header ? (
              <div
                data-testid="shell-companion-header"
                className={cn('flex h-10 shrink-0 items-center gap-2 px-3', chrome.header)}
              >
                {renderHeaderSlots(region.presentation.header)}
              </div>
            ) : null}
            {region.content(renderState)}
          </div>
        </section>
      );
    }

    return (
      <section
        aria-label={region.presentation.accessibleLabel}
        data-shell-region="companion"
        className={cn(
          'relative flex h-full min-h-0 shrink-0 flex-col transition-[width] duration-200',
          chrome.region,
          fullscreen && 'fixed inset-0 z-50 w-screen',
        )}
        style={fullscreen ? undefined : {
          width: collapsed
            ? collapsedByResponsive ? PRODUCT_SHELL_COMPACT_COMPANION_WIDTH : chrome.collapsedWidth
            : layout.companion.width,
        }}
      >
        {!collapsed ? (
          <div className={cn('flex h-10 shrink-0 items-center justify-between gap-2 px-3', chrome.header)}>
            {renderHeaderSlots(region.presentation.header)}
            <div className="flex shrink-0 items-center gap-1">
              <SidebarCollapseToggle
                collapsed={false}
                label={region.presentation.collapseLabel}
                onClick={toggleCompanion}
              />
            </div>
          </div>
        ) : (
          <div className={cn('flex h-10 shrink-0 items-center justify-center', chrome.header)}>
            <SidebarCollapseToggle
              collapsed
              label={region.presentation.expandLabel}
              onClick={toggleCompanion}
            />
          </div>
        )}
        {!collapsed ? (
          <div className={cn('flex min-h-0 flex-1 flex-col overflow-hidden', chrome.content)}>
            {region.content(renderState)}
          </div>
        ) : region.presentation.collapsedContent ? (
          <div className={cn('flex min-h-0 flex-1 flex-col overflow-hidden', chrome.content)}>
            {region.presentation.collapsedContent}
          </div>
        ) : null}
        {region.side.resizable && !collapsed && !fullscreen ? (
          <div
            role="separator"
            aria-label={region.presentation.resizeLabel}
            aria-orientation="vertical"
            className={cn(
              'absolute left-0 top-0 h-full w-1 cursor-col-resize transition-colors',
              resizeState?.kind === 'companion-width' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
            )}
            onMouseDown={(event) => startResize('companion-width', event)}
          />
        ) : null}
      </section>
    );
  };

  const displayMode = display?.mode;
  const isMainExpanded = displayMode === 'main-expanded';
  const isCompanionFullscreen = displayMode === 'companion-fullscreen';
  const regionsBody = hasRegions(body) ? body : null;
  const main = regionsBody?.main;
  const companion = regionsBody?.companion;
  const bodyContent = body.kind === 'state' ? (
    <div data-shell-state className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto bg-muted/20">
      {body.content}
    </div>
  ) : isCompanionFullscreen ? (
    companion ? renderCompanion(companion) : null
  ) : (
    <div data-shell-body className="flex min-h-0 min-w-0 flex-1 overflow-hidden bg-muted/20">
      {!isMainExpanded ? renderColumn('navigation', regionsBody.navigation) : null}
      {!isMainExpanded ? renderColumn('navigator', regionsBody.navigator) : null}
      {!isCompanionFullscreen && main ? (
        <main
          aria-label={main.accessibleLabel}
          data-shell-region="main"
          className={cn('flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background', isMainExpanded && 'w-full')}
        >
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">{main.content}</div>
          {!isMainExpanded && companion?.placement === 'bottom' ? renderCompanion(companion) : null}
        </main>
      ) : null}
      {!isMainExpanded && companion?.placement === 'side' ? renderCompanion(companion) : null}
    </div>
  );

  return (
    <div
      ref={rootRef}
      data-testid="product-shell"
      className="flex h-screen w-screen min-h-0 flex-col bg-background text-foreground"
    >
      {!isMainExpanded && !isCompanionFullscreen && topBar ? (
        <div data-shell-top-bar className="shrink-0">{topBar}</div>
      ) : null}
      {!isMainExpanded && !isCompanionFullscreen && header ? (
        <div data-shell-header className="flex h-10 w-full min-w-0 shrink-0 items-center border-b border-border bg-background">
          {header}
        </div>
      ) : null}
      {bodyContent}
    </div>
  );
};
