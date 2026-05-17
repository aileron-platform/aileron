import { createLogger } from '@/shared/services/logger';
import { dispatchInsertDraftEvent } from '../../../components/ChatPanel/chatEvents';
import type { CanvasReviewTarget } from '../../../services/workspaceRuntimeApi';

const logger = createLogger('AileronCanvasBridgeClient');

export const AILERON_CANVAS_BRIDGE_SOURCE = 'aileron-canvas-bridge';
export const AILERON_CANVAS_BRIDGE_VERSION = 2;

export type BridgeRectUpdate = {
  id?: string;
  selector?: string;
  resolved?: boolean;
  rect?: CanvasReviewTarget['rect'];
  documentRect?: CanvasReviewTarget['rect'];
};

export type AileronCanvasBridgeMessage =
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'BRIDGE_READY'; payload?: { routePath?: string } }
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'ROUTE_CHANGED'; payload?: { routePath?: string } }
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'TARGET_SELECTED'; payload?: { routePath?: string; target?: CanvasReviewTarget | null } }
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'TARGET_RECTS'; payload?: { routePath?: string; rects?: BridgeRectUpdate[] } }
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'BRIDGE_ERROR'; payload?: { errorCode?: string } }
  | { source: typeof AILERON_CANVAS_BRIDGE_SOURCE; version: typeof AILERON_CANVAS_BRIDGE_VERSION; type: 'SKILL_EVENT'; payload?: { eventType?: string; data?: unknown } };

export type SkillEventHandler = (data: unknown) => void;

const skillEventHandlers = new Map<string, SkillEventHandler>();

export const registerSkillEventHandler = (eventType: string, handler: SkillEventHandler): (() => void) => {
  skillEventHandlers.set(eventType, handler);
  return () => {
    if (skillEventHandlers.get(eventType) === handler) {
      skillEventHandlers.delete(eventType);
    }
  };
};

export const composeSkillEventPrompt = (eventType: string, data: unknown): string => {
  const serialized = JSON.stringify(data ?? {}, null, 2);
  return [`/canvas-event`, `eventType: ${eventType}`, `data:`, serialized].join('\n');
};

export const isAileronCanvasBridgeMessage = (value: unknown): value is AileronCanvasBridgeMessage => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { source?: unknown; version?: unknown; type?: unknown };
  return (
    candidate.source === AILERON_CANVAS_BRIDGE_SOURCE
    && candidate.version === AILERON_CANVAS_BRIDGE_VERSION
    && typeof candidate.type === 'string'
  );
};

export type AileronCanvasBridgeHandlers = {
  onBridgeReady?: (payload?: { routePath?: string }) => void;
  onRouteChanged?: (payload?: { routePath?: string }) => void;
  onTargetSelected?: (payload?: { routePath?: string; target?: CanvasReviewTarget | null }) => void;
  onTargetRects?: (payload?: { routePath?: string; rects?: BridgeRectUpdate[] }) => void;
  onBridgeError?: (payload?: { errorCode?: string }) => void;
};

export const createAileronCanvasBridgeMessageHandler = (
  iframe: HTMLIFrameElement | null,
  handlers: AileronCanvasBridgeHandlers
) => {
  return (event: MessageEvent) => {
    if (event.source !== iframe?.contentWindow) return;
    if (!isAileronCanvasBridgeMessage(event.data)) return;

    switch (event.data.type) {
      case 'BRIDGE_READY':
        handlers.onBridgeReady?.(event.data.payload);
        return;
      case 'ROUTE_CHANGED':
        handlers.onRouteChanged?.(event.data.payload);
        return;
      case 'TARGET_SELECTED':
        handlers.onTargetSelected?.(event.data.payload);
        return;
      case 'TARGET_RECTS':
        handlers.onTargetRects?.(event.data.payload);
        return;
      case 'BRIDGE_ERROR':
        handlers.onBridgeError?.(event.data.payload);
        return;
      case 'SKILL_EVENT': {
        const eventType = event.data.payload?.eventType;
        if (!eventType) return;
        const handler = skillEventHandlers.get(eventType);
        if (handler) {
          handler(event.data.payload?.data);
          return;
        }
        dispatchInsertDraftEvent({
          content: composeSkillEventPrompt(eventType, event.data.payload?.data),
          mode: 'append',
        });
        return;
      }
      default:
        logger.warn('Unknown Aileron Canvas bridge event', { type: (event.data as { type?: unknown }).type });
    }
  };
};
