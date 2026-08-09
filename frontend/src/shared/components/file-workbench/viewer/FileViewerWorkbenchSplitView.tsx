import React from 'react';
import { SplitPaneGroup, SPLIT_PANE_MAX_COUNT, type SplitPaneDirection } from '@/shared/components/split-pane';
import { FileViewerWorkbench } from './FileViewerWorkbench';
import type { FileViewerWorkbenchProps, FileViewerWorkbenchTab } from './types';

export interface FileWorkbenchPane {
  id: string;
  tabIds: string[];
  activeTabId: string | null;
}

type SinglePaneOnlyProps = 'tabs' | 'activeTabId' | 'onActiveTabChange' | 'onSplitTab' | 'canSplitTab' | 'onForeignTabDrop';

export interface FileViewerWorkbenchSplitViewProps extends Omit<FileViewerWorkbenchProps, SinglePaneOnlyProps> {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  onActiveTabChange: (tabId: string | null) => void;
  panes?: FileWorkbenchPane[];
  onPanesChange?: (panes: FileWorkbenchPane[]) => void;
  direction?: SplitPaneDirection;
  sizes?: number[];
  onSizesChange?: (sizes: number[]) => void;
}

let paneIdCounter = 0;
const nextPaneId = (): string => {
  paneIdCounter += 1;
  return `pane-${paneIdCounter}`;
};

const buildDefaultPanes = (tabs: FileViewerWorkbenchTab[], activeTabId: string | null): FileWorkbenchPane[] => [
  { id: nextPaneId(), tabIds: tabs.map((tab) => tab.id), activeTabId },
];

const areTabsEqual = (current: FileViewerWorkbenchTab, next: FileViewerWorkbenchTab): boolean => {
  const currentEntries = Object.entries(current);
  const nextEntries = Object.entries(next);
  return currentEntries.length === nextEntries.length
    && currentEntries.every(([key, value]) => Object.is(value, next[key as keyof FileViewerWorkbenchTab]));
};

export const FileViewerWorkbenchSplitView: React.FC<FileViewerWorkbenchSplitViewProps> = ({
  tabs,
  activeTabId,
  onActiveTabChange,
  panes: controlledPanes,
  onPanesChange,
  direction = 'horizontal',
  sizes,
  onSizesChange,
  onTabsChange,
  onOpenPath,
  ...workbenchProps
}) => {
  const [uncontrolledPanes, setUncontrolledPanes] = React.useState<FileWorkbenchPane[]>(
    () => controlledPanes ?? buildDefaultPanes(tabs, activeTabId),
  );
  const panes = controlledPanes ?? uncontrolledPanes;
  const tabIdsKey = tabs.map((tab) => tab.id).join('|');
  const paneMembershipKey = panes.map((pane) => `${pane.id}:${pane.tabIds.join(',')}`).join('|');
  const activePaneIdRef = React.useRef<string | null>(null);

  const setActivePaneId = React.useCallback((paneId: string) => {
    activePaneIdRef.current = paneId;
  }, []);

  const setPanes = React.useCallback((next: FileWorkbenchPane[]) => {
    const nonEmpty = next.filter((pane) => pane.tabIds.length > 0);
    if (onPanesChange) {
      onPanesChange(nonEmpty);
    } else {
      setUncontrolledPanes(nonEmpty);
    }
  }, [onPanesChange]);

  React.useEffect(() => {
    if (panes.some((pane) => pane.id === activePaneIdRef.current)) {
      return;
    }

    activePaneIdRef.current = panes.find((pane) => pane.tabIds.includes(activeTabId ?? ''))?.id
      ?? panes[0]?.id
      ?? null;
  }, [activeTabId, paneMembershipKey, panes]);

  React.useEffect(() => {
    if (!activeTabId) {
      return;
    }

    const owningPane = panes.find((pane) => pane.tabIds.includes(activeTabId));
    if (!owningPane || owningPane.activeTabId === activeTabId) {
      return;
    }

    setActivePaneId(owningPane.id);
    setPanes(panes.map((pane) => (
      pane.id === owningPane.id ? { ...pane, activeTabId } : pane
    )));
  // Only external activeTabId changes (e.g. reopening an already-open tab from
  // outside the workbench) should drive this; pane-membership changes are handled above.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTabId]);

  React.useEffect(() => {
    const tabIds = new Set(tabs.map((tab) => tab.id));
    const trackedIds = new Set(panes.flatMap((pane) => pane.tabIds));
    const newIds = tabs.map((tab) => tab.id).filter((id) => !trackedIds.has(id));
    const hasStaleIds = panes.some((pane) => pane.tabIds.some((id) => !tabIds.has(id)));

    if (newIds.length === 0 && !hasStaleIds) {
      return;
    }

    const targetPaneIndex = Math.max(0, panes.findIndex((pane) => pane.id === activePaneIdRef.current));

    const reconciled = panes.map((pane, index) => {
      const prunedTabIds = pane.tabIds.filter((id) => tabIds.has(id));
      const isTargetPane = index === targetPaneIndex;
      const appended = isTargetPane ? [...prunedTabIds, ...newIds] : prunedTabIds;
      const activeStillValid = pane.activeTabId ? appended.includes(pane.activeTabId) : false;
      const nextActiveTabId = isTargetPane && newIds.length > 0
        ? newIds[newIds.length - 1]
        : (activeStillValid ? pane.activeTabId : appended[0] ?? null);
      return {
        ...pane,
        tabIds: appended,
        activeTabId: nextActiveTabId,
      };
    });

    setPanes(reconciled);
  // Controlled panes can arrive after mount with membership that differs from the live tab registry.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabIdsKey, paneMembershipKey]);

  const handleSplitTab = (sourcePaneId: string, tabId: string) => {
    const sourcePane = panes.find((pane) => pane.id === sourcePaneId);
    if (panes.length >= SPLIT_PANE_MAX_COUNT || !sourcePane || sourcePane.tabIds.length <= 1) {
      return;
    }
    const nextPanes = panes.map((pane) => (
      pane.id === sourcePaneId
        ? {
          ...pane,
          tabIds: pane.tabIds.filter((id) => id !== tabId),
          activeTabId: pane.activeTabId === tabId
            ? pane.tabIds.filter((id) => id !== tabId)[0] ?? null
            : pane.activeTabId,
        }
        : pane
    ));
    const nextPaneIdValue = nextPaneId();
    nextPanes.push({ id: nextPaneIdValue, tabIds: [tabId], activeTabId: tabId });
    setActivePaneId(nextPaneIdValue);
    setPanes(nextPanes);
    onActiveTabChange(tabId);
  };

  const handleForeignTabDrop = (
    targetPaneId: string,
    draggedTabId: string,
    targetTabId: string | null,
    position: 'before' | 'after',
  ) => {
    const nextPanes = panes.map((pane) => {
      if (pane.tabIds.includes(draggedTabId) && pane.id !== targetPaneId) {
        const remaining = pane.tabIds.filter((id) => id !== draggedTabId);
        return {
          ...pane,
          tabIds: remaining,
          activeTabId: pane.activeTabId === draggedTabId ? remaining[0] ?? null : pane.activeTabId,
        };
      }
      if (pane.id === targetPaneId) {
        const targetIndex = targetTabId ? pane.tabIds.indexOf(targetTabId) : -1;
        const insertAt = targetIndex < 0
          ? pane.tabIds.length
          : targetIndex + (position === 'after' ? 1 : 0);
        return {
          ...pane,
          tabIds: [...pane.tabIds.slice(0, insertAt), draggedTabId, ...pane.tabIds.slice(insertAt)],
          activeTabId: draggedTabId,
        };
      }
      return pane;
    });
    setActivePaneId(targetPaneId);
    setPanes(nextPanes);
    onActiveTabChange(draggedTabId);
  };

  const handlePaneActiveTabChange = (paneId: string, tabId: string | null) => {
    setActivePaneId(paneId);
    setPanes(panes.map((pane) => (pane.id === paneId ? { ...pane, activeTabId: tabId } : pane)));
    if (tabId) {
      onActiveTabChange(tabId);
    }
  };

  const handlePaneTabsChange = (paneId: string, nextPaneTabs: FileViewerWorkbenchTab[]) => {
    const pane = panes.find((item) => item.id === paneId);
    if (!pane) {
      return;
    }
    const nextIds = nextPaneTabs.map((tab) => tab.id);
    const closedIds = pane.tabIds.filter((id) => !nextIds.includes(id));
    const nextPaneTabsById = new Map(nextPaneTabs.map((tab) => [tab.id, tab]));

    setPanes(panes.map((item) => (item.id === paneId ? { ...item, tabIds: nextIds } : item)));

    const nextTabs = tabs
      .filter((tab) => !closedIds.includes(tab.id))
      .map((tab) => {
        const nextTab = nextPaneTabsById.get(tab.id);
        return nextTab && !areTabsEqual(tab, nextTab) ? nextTab : tab;
      });
    const hasSharedTabsChanged = nextTabs.length !== tabs.length
      || nextTabs.some((tab, index) => tab !== tabs[index]);

    if (hasSharedTabsChanged) {
      onTabsChange(nextTabs);
    }
  };

  return (
    <SplitPaneGroup
      panes={panes}
      direction={direction}
      getPaneKey={(pane) => pane.id}
      sizes={sizes}
      onSizesChange={onSizesChange}
      renderPane={(pane) => {
        const paneTabs = pane.tabIds
          .map((id) => tabs.find((tab) => tab.id === id))
          .filter((tab): tab is FileViewerWorkbenchTab => Boolean(tab));

        return (
          <div
            className="h-full min-w-0"
            onFocusCapture={() => setActivePaneId(pane.id)}
            onPointerDown={() => setActivePaneId(pane.id)}
          >
            <FileViewerWorkbench
              {...workbenchProps}
              tabs={paneTabs}
              activeTabId={pane.activeTabId}
              onTabsChange={(nextPaneTabs) => handlePaneTabsChange(pane.id, nextPaneTabs)}
              onActiveTabChange={(tabId) => handlePaneActiveTabChange(pane.id, tabId)}
              onOpenPath={(path) => {
                setActivePaneId(pane.id);
                onOpenPath?.(path);
              }}
              onSplitTab={(tabId) => handleSplitTab(pane.id, tabId)}
              canSplitTab={() => panes.length < SPLIT_PANE_MAX_COUNT && pane.tabIds.length > 1}
              onForeignTabDrop={(draggedTabId, targetTabId, position) => (
                handleForeignTabDrop(pane.id, draggedTabId, targetTabId, position)
              )}
            />
          </div>
        );
      }}
    />
  );
};
