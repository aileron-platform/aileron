import { describe, expect, it, vi } from 'vitest';

import {
  AILERON_CANVAS_BRIDGE_SOURCE,
  AILERON_CANVAS_BRIDGE_VERSION,
  createAileronCanvasBridgeMessageHandler,
} from './aileronCanvasBridgeClient';

const bridgeMessage = (type: string, payload: unknown = {}) => ({
  source: AILERON_CANVAS_BRIDGE_SOURCE,
  version: AILERON_CANVAS_BRIDGE_VERSION,
  type,
  payload,
});

const makeIframe = () => ({ contentWindow: {} as Window }) as HTMLIFrameElement;

describe('aileronCanvasBridgeClient', () => {
  it('routes review family events', () => {
    const iframe = makeIframe();
    const onTargetSelected = vi.fn();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, { onTargetSelected });

    handler({ source: iframe.contentWindow, data: bridgeMessage('TARGET_SELECTED', { routePath: '/', target: null }) } as MessageEvent);

    expect(onTargetSelected).toHaveBeenCalledWith({ routePath: '/', target: null });
  });

  it('routes unregistered SKILL_EVENT data to the handoff callback', () => {
    const iframe = makeIframe();
    const onSkillEvent = vi.fn();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, { onSkillEvent });

    handler({ source: iframe.contentWindow, data: bridgeMessage('SKILL_EVENT', { eventType: 'CANDIDATE_PICKED', data: { id: 'A' } }) } as MessageEvent);

    expect(onSkillEvent).toHaveBeenCalledWith('CANDIDATE_PICKED', { id: 'A' });
  });

  it('ignores events from other windows', () => {
    const iframe = makeIframe();
    const onBridgeReady = vi.fn();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, { onBridgeReady });

    handler({ source: {}, data: bridgeMessage('BRIDGE_READY', { routePath: '/' }) } as MessageEvent);

    expect(onBridgeReady).not.toHaveBeenCalled();
  });

  it('ignores unknown sources', () => {
    const iframe = makeIframe();
    const onBridgeReady = vi.fn();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, { onBridgeReady });

    handler({ source: iframe.contentWindow, data: { source: 'other', version: 2, type: 'BRIDGE_READY' } } as MessageEvent);

    expect(onBridgeReady).not.toHaveBeenCalled();
  });
});
