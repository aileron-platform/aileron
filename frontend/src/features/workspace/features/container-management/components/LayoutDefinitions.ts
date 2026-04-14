import { TerminalLayoutType } from './TerminalLayoutSelector';

export interface LayoutNode {
    type: 'panel' | 'group';
    id?: string; // For panels, this maps to the pane index
    direction?: 'horizontal' | 'vertical'; // For groups
    children?: LayoutNode[]; // For groups
    defaultSize?: number; // Percentage
}

export const LAYOUT_DEFINITIONS: Record<TerminalLayoutType, LayoutNode> = {
    'single': {
        type: 'panel',
        id: '0',
        defaultSize: 100
    },
    'split-horizontal': {
        type: 'group',
        direction: 'horizontal',
        children: [
            { type: 'panel', id: '0', defaultSize: 50 },
            { type: 'panel', id: '1', defaultSize: 50 }
        ]
    },
    'split-vertical': {
        type: 'group',
        direction: 'vertical',
        children: [
            { type: 'panel', id: '0', defaultSize: 50 },
            { type: 'panel', id: '1', defaultSize: 50 }
        ]
    },
    'quad': {
        type: 'group',
        direction: 'vertical',
        children: [
            {
                type: 'group',
                direction: 'horizontal',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '0', defaultSize: 50 },
                    { type: 'panel', id: '1', defaultSize: 50 }
                ]
            },
            {
                type: 'group',
                direction: 'horizontal',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '2', defaultSize: 50 },
                    { type: 'panel', id: '3', defaultSize: 50 }
                ]
            }
        ]
    },
    'left-1-right-2': {
        type: 'group',
        direction: 'horizontal',
        children: [
            { type: 'panel', id: '0', defaultSize: 50 },
            {
                type: 'group',
                direction: 'vertical',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '1', defaultSize: 50 },
                    { type: 'panel', id: '2', defaultSize: 50 }
                ]
            }
        ]
    },
    'right-1-left-2': {
        type: 'group',
        direction: 'horizontal',
        children: [
            {
                type: 'group',
                direction: 'vertical',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '0', defaultSize: 50 },
                    { type: 'panel', id: '1', defaultSize: 50 }
                ]
            },
            { type: 'panel', id: '2', defaultSize: 50 }
        ]
    },
    'top-1-bottom-2': {
        type: 'group',
        direction: 'vertical',
        children: [
            { type: 'panel', id: '0', defaultSize: 50 },
            {
                type: 'group',
                direction: 'horizontal',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '1', defaultSize: 50 },
                    { type: 'panel', id: '2', defaultSize: 50 }
                ]
            }
        ]
    },
    'bottom-1-top-2': {
        type: 'group',
        direction: 'vertical',
        children: [
            {
                type: 'group',
                direction: 'horizontal',
                defaultSize: 50,
                children: [
                    { type: 'panel', id: '0', defaultSize: 50 },
                    { type: 'panel', id: '1', defaultSize: 50 }
                ]
            },
            { type: 'panel', id: '2', defaultSize: 50 }
        ]
    }
};

export const getPaneCount = (type: TerminalLayoutType): number => {
    switch (type) {
        case 'single': return 1;
        case 'split-horizontal':
        case 'split-vertical': return 2;
        case 'quad': return 4;
        case 'left-1-right-2':
        case 'right-1-left-2':
        case 'top-1-bottom-2':
        case 'bottom-1-top-2': return 3;
        default: return 1;
    }
};
