import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    ChevronLeft,
    ChevronRight,
    Plus,
    Terminal as TerminalIcon,
    X,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import type { TerminalTab as TerminalTabState } from '@/features/workspace/realtime/terminalStore';
import { getTerminalTabTitle } from '../model/terminalTabModel';

const SCROLL_AMOUNT = 200;

export interface TerminalTabBarProps {
    tabs: TerminalTabState[];
    activeTabId: string | null;
    onSwitchTab: (tabId: string) => void;
    onCloseTab: (tabId: string) => void;
    onAddTab: () => void;
    onContextMenu: (event: React.MouseEvent, tabId: string, paneIndex?: number) => void;
    closeLabel: string;
    newTooltip: string;
    scrollLeftLabel: string;
    scrollRightLabel: string;
    contextPaneIndex?: number;
}

export const TerminalTabBar: React.FC<TerminalTabBarProps> = ({
    tabs,
    activeTabId,
    onSwitchTab,
    onCloseTab,
    onAddTab,
    onContextMenu,
    closeLabel,
    newTooltip,
    contextPaneIndex,
    scrollLeftLabel,
    scrollRightLabel,
}) => {
    const tabsListRef = useRef<HTMLDivElement>(null);
    const [showLeftScroll, setShowLeftScroll] = useState(false);
    const [showRightScroll, setShowRightScroll] = useState(false);
    const canCloseTabs = tabs.length > 1;

    const checkScroll = useCallback(() => {
        if (tabsListRef.current) {
            const { scrollLeft, scrollWidth, clientWidth } = tabsListRef.current;
            setShowLeftScroll(scrollLeft > 0);
            setShowRightScroll(scrollLeft < scrollWidth - clientWidth - 1);
        }
    }, []);

    const scrollTabs = useCallback(
        (direction: 'left' | 'right') => {
            if (tabsListRef.current) {
                tabsListRef.current.scrollBy({
                    left: direction === 'left' ? -SCROLL_AMOUNT : SCROLL_AMOUNT,
                    behavior: 'smooth',
                });
                setTimeout(checkScroll, 300);
            }
        },
        [checkScroll],
    );

    useEffect(() => {
        checkScroll();
        window.addEventListener('resize', checkScroll);
        return () => window.removeEventListener('resize', checkScroll);
    }, [checkScroll, tabs]);

    return (
        <div className="ml-4 flex h-full min-w-0 flex-1 items-center">
            <div className="relative flex-1 overflow-hidden">
                {showLeftScroll && (
                    <div className="absolute left-0 top-0 z-10 flex h-full items-center bg-gradient-to-r from-card to-transparent px-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 rounded-full bg-background shadow-sm"
                            onClick={() => scrollTabs('left')}
                            aria-label={scrollLeftLabel}
                        >
                            <ChevronLeft className="h-3 w-3" />
                        </Button>
                    </div>
                )}

                <div
                    ref={tabsListRef}
                    className="flex h-full items-center gap-1 overflow-x-auto px-2 [&::-webkit-scrollbar]:!h-1.5 [&::-webkit-scrollbar-thumb]:!rounded-full [&::-webkit-scrollbar-thumb]:!bg-gray-500/30 [&::-webkit-scrollbar-thumb:hover]:!bg-gray-500/50 [&::-webkit-scrollbar-track]:!bg-transparent"
                    onScroll={checkScroll}
                >
                    {tabs.map((tab) => {
                        const title = getTerminalTabTitle(tab.workingDirectory);
                        return (
                            <div
                                key={tab.tabId}
                                className={cn(
                                    'group flex h-8 min-w-[120px] max-w-[200px] cursor-pointer items-center justify-between gap-2 rounded-md border px-3 text-xs transition-colors',
                                    tab.tabId === activeTabId
                                        ? 'border-border bg-muted text-foreground'
                                        : 'border-transparent text-muted-foreground hover:bg-muted/50',
                                )}
                                onContextMenu={(event) => (
                                    onContextMenu(event, tab.tabId, contextPaneIndex)
                                )}
                            >
                                <button
                                    type="button"
                                    role="tab"
                                    aria-label={title}
                                    aria-selected={tab.tabId === activeTabId}
                                    title={tab.workingDirectory}
                                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                    onClick={() => onSwitchTab(tab.tabId)}
                                >
                                    <TerminalIcon
                                        aria-hidden="true"
                                        className="h-3.5 w-3.5 shrink-0"
                                    />
                                    <span className="truncate">{title}</span>
                                </button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className={cn(
                                        'h-4 w-4 rounded-full opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100',
                                        tab.tabId === activeTabId && 'opacity-100',
                                    )}
                                    disabled={!canCloseTabs}
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        if (!canCloseTabs) return;
                                        onCloseTab(tab.tabId);
                                    }}
                                    aria-label={closeLabel}
                                >
                                    <X className="h-3 w-3" />
                                </Button>
                            </div>
                        );
                    })}
                </div>

                {showRightScroll && (
                    <div className="absolute right-0 top-0 z-10 flex h-full items-center bg-gradient-to-l from-card to-transparent px-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 rounded-full bg-background shadow-sm"
                            onClick={() => scrollTabs('right')}
                            aria-label={scrollRightLabel}
                        >
                            <ChevronRight className="h-3 w-3" />
                        </Button>
                    </div>
                )}
            </div>

            <div className="flex items-center px-2">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={onAddTab}
                    title={newTooltip}
                    aria-label={newTooltip}
                >
                    <Plus className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
};
