import React from 'react';
import {
    Copy,
    Clipboard,
    X,
    Eraser,
    Pencil,
    MinusCircle,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { TerminalTab as TerminalTabState } from '@/features/workspace/realtime/terminalStore';

export interface ContextMenuState {
    x: number;
    y: number;
    visible: boolean;
    tabId?: string;
    paneIndex?: number;
}

export const INITIAL_CONTEXT_MENU_STATE: ContextMenuState = {
    x: 0,
    y: 0,
    visible: false,
};

export interface TerminalContextMenuProps {
    state: ContextMenuState;
    selectedText: string;
    tabs: TerminalTabState[];
    assignedTabIds: Set<string>;
    onCopy: () => void;
    onPaste: () => void;
    onCloseTab?: (tabId: string) => void;
    onClear?: (tabId: string) => void;
    onRename?: (tabId: string) => void;
    onUnassign?: (paneIndex: number, tabId: string) => void;
    onAssignTab?: (paneIndex: number, tabId: string) => void;
    onDismiss: () => void;
    labels: {
        copy: string;
        paste: string;
        close: string;
        clear: string;
        rename: string;
        switchTitle: string;
        active: string;
        unassign: string;
    };
}

export const TerminalContextMenu: React.FC<TerminalContextMenuProps> = ({
    state,
    selectedText,
    tabs,
    assignedTabIds,
    onCopy,
    onPaste,
    onCloseTab,
    onClear,
    onRename,
    onUnassign,
    onAssignTab,
    onDismiss,
    labels,
}) => {
    if (!state.visible) return null;

    const hasTab = Boolean(state.tabId);
    const paneIndex = state.paneIndex;
    const isEmptyPane = typeof paneIndex === 'number' && !state.tabId;

    return (
        <div
            className="fixed z-50 w-40 rounded-md border border-border bg-popover p-1 text-sm text-popover-foreground shadow-lg"
            style={{ top: state.y, left: state.x }}
        >
            <button
                type="button"
                className={cn(
                    'flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted',
                    (!selectedText || !hasTab) && 'cursor-not-allowed opacity-60',
                )}
                onClick={() => {
                    onCopy();
                    onDismiss();
                }}
                disabled={!selectedText || !hasTab}
            >
                <Copy className="h-3.5 w-3.5" />
                {labels.copy}
            </button>
            <button
                type="button"
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted"
                onClick={() => {
                    onPaste();
                    onDismiss();
                }}
                disabled={!hasTab}
            >
                <Clipboard className="h-3.5 w-3.5" />
                {labels.paste}
            </button>

            {state.tabId && (
                <>
                    <div className="my-1 h-px bg-border" />
                    <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted"
                        onClick={() => {
                            if (state.tabId) onRename?.(state.tabId);
                            onDismiss();
                        }}
                    >
                        <Pencil className="h-3.5 w-3.5" />
                        {labels.rename}
                    </button>
                    {typeof paneIndex === 'number' && (
                        <button
                            type="button"
                            className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted"
                            onClick={() => {
                                if (state.tabId) onUnassign?.(paneIndex, state.tabId);
                                onDismiss();
                            }}
                        >
                            <MinusCircle className="h-3.5 w-3.5" />
                            {labels.unassign}
                        </button>
                    )}
                    <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-destructive hover:bg-muted hover:text-destructive"
                        onClick={() => {
                            if (state.tabId) onCloseTab?.(state.tabId);
                            onDismiss();
                        }}
                    >
                        <X className="h-3.5 w-3.5" />
                        {labels.close}
                    </button>
                    <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted"
                        onClick={() => {
                            if (state.tabId) onClear?.(state.tabId);
                            onDismiss();
                        }}
                    >
                        <Eraser className="h-3.5 w-3.5" />
                        {labels.clear}
                    </button>
                </>
            )}

            {isEmptyPane && tabs.length > 0 && (
                <>
                    <div className="my-1 h-px bg-border" />
                    <div className="px-2 py-1 text-xs font-medium text-muted-foreground">
                        {labels.switchTitle}
                    </div>
                    <div className="flex max-h-60 flex-col overflow-auto">
                        {tabs.map((tab) => {
                            const isUsed = assignedTabIds.has(tab.tabId);
                            return (
                                <button
                                    key={tab.tabId}
                                    type="button"
                                    className={cn(
                                        'flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-muted',
                                        isUsed && 'cursor-not-allowed opacity-50 hover:bg-transparent',
                                    )}
                                    onClick={() => {
                                        if (isUsed) return;
                                        onAssignTab?.(paneIndex, tab.tabId);
                                        onDismiss();
                                    }}
                                    disabled={isUsed}
                                >
                                    <span className="truncate">{tab.name}</span>
                                    {isUsed && (
                                        <span className="text-[10px] text-muted-foreground">
                                            {labels.active}
                                        </span>
                                    )}
                                </button>
                            )
                        })}
                    </div>
                </>
            )}
        </div>
    );
};
