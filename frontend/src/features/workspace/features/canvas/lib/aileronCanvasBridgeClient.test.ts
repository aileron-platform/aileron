import { beforeEach, describe, expect, it, vi } from 'vitest';

const dispatchInsertDraftEvent = vi.hoisted(() => vi.fn());

vi.mock('../../../components/ChatPanel/chatEvents', () => ({
  dispatchInsertDraftEvent,
}));

import {
  AILERON_CANVAS_BRIDGE_SOURCE,
  AILERON_CANVAS_BRIDGE_VERSION,
  composeSkillEventPrompt,
  createAileronCanvasBridgeMessageHandler,
  registerSkillEventHandler,
} from './aileronCanvasBridgeClient';

const bridgeMessage = (type: string, payload: unknown = {}) => ({
  source: AILERON_CANVAS_BRIDGE_SOURCE,
  version: AILERON_CANVAS_BRIDGE_VERSION,
  type,
  payload,
});

const makeIframe = () => ({ contentWindow: {} as Window }) as HTMLIFrameElement;

describe('aileronCanvasBridgeClient', () => {
  beforeEach(() => {
    dispatchInsertDraftEvent.mockClear();
  });

  it('routes review family events', () => {
    const iframe = makeIframe();
    const onTargetSelected = vi.fn();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, { onTargetSelected });

    handler({ source: iframe.contentWindow, data: bridgeMessage('TARGET_SELECTED', { routePath: '/', target: null }) } as MessageEvent);

    expect(onTargetSelected).toHaveBeenCalledWith({ routePath: '/', target: null });
  });

  it('uses registered SKILL_EVENT handler without fallback', () => {
    const iframe = makeIframe();
    const registered = vi.fn();
    const unregister = registerSkillEventHandler('STYLE_SELECTED', registered);
    const handler = createAileronCanvasBridgeMessageHandler(iframe, {});

    handler({ source: iframe.contentWindow, data: bridgeMessage('SKILL_EVENT', { eventType: 'STYLE_SELECTED', data: { direction: 'B' } }) } as MessageEvent);
    unregister();

    expect(registered).toHaveBeenCalledWith({ direction: 'B' });
    expect(dispatchInsertDraftEvent).not.toHaveBeenCalled();
  });

  it('falls back to chat draft for unregistered SKILL_EVENT', () => {
    const iframe = makeIframe();
    const handler = createAileronCanvasBridgeMessageHandler(iframe, {});

    handler({ source: iframe.contentWindow, data: bridgeMessage('SKILL_EVENT', { eventType: 'CANDIDATE_PICKED', data: { id: 'A' } }) } as MessageEvent);

    expect(dispatchInsertDraftEvent).toHaveBeenCalledWith({
      content: composeSkillEventPrompt('CANDIDATE_PICKED', { id: 'A' }),
      mode: 'append',
    });
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
