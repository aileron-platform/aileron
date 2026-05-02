import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent } from '@testing-library/dom';
import { attachInputHandlers } from './inputHandler';
import type { NekoClient } from './nekoClient';

function createClient(): NekoClient {
  return {
    getScreenResolution: vi.fn(() => ({ width: 1440, height: 900 })),
    sendMouseMove: vi.fn(),
    sendMouseButton: vi.fn(),
    sendWheel: vi.fn(),
    sendKey: vi.fn(),
    sendText: vi.fn(),
  } as unknown as NekoClient;
}

function getInputSurface(): HTMLTextAreaElement {
  const inputSurface = document.querySelector('textarea');
  if (!(inputSurface instanceof HTMLTextAreaElement)) {
    throw new Error('Input surface was not created');
  }
  return inputSurface;
}

describe('attachInputHandlers', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('focuses the stream when the user clicks it so keyboard input can be captured', () => {
    const video = document.createElement('video');
    const client = createClient();
    vi.spyOn(video, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 720,
      bottom: 450,
      width: 720,
      height: 450,
      toJSON: () => ({}),
    });

    attachInputHandlers(video, client);
    const inputSurface = getInputSurface();
    const focus = vi.spyOn(inputSurface, 'focus');

    fireEvent.mouseDown(inputSurface, { button: 0, clientX: 360, clientY: 225 });

    expect(inputSurface.tabIndex).toBe(0);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(client.sendMouseMove).toHaveBeenCalledWith(720, 450);
    expect(client.sendMouseButton).toHaveBeenCalledWith(0, true);
  });

  it('sends key down and key up events as X11 keysyms', () => {
    const video = document.createElement('video');
    const client = createClient();

    attachInputHandlers(video, client);
    const inputSurface = getInputSurface();

    fireEvent.mouseDown(inputSurface, { button: 0 });
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });
    fireEvent.keyUp(window, { key: 'a', code: 'KeyA' });
    fireEvent.keyDown(window, { key: 'Enter', code: 'Enter' });

    expect(client.sendKey).toHaveBeenNthCalledWith(1, 0x61, true);
    expect(client.sendKey).toHaveBeenNthCalledWith(2, 0x61, false);
    expect(client.sendKey).toHaveBeenNthCalledWith(3, 0xff0d, true);
  });

  it('releases keyboard capture after clicking outside the stream', () => {
    const video = document.createElement('video');
    const outside = document.createElement('button');
    const client = createClient();
    document.body.append(video, outside);

    attachInputHandlers(video, client);
    const inputSurface = getInputSurface();

    fireEvent.mouseDown(inputSurface, { button: 0 });
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });
    fireEvent.mouseDown(outside);
    fireEvent.keyDown(window, { key: 'b', code: 'KeyB' });

    expect(client.sendKey).toHaveBeenCalledTimes(1);
    expect(client.sendKey).toHaveBeenCalledWith(0x61, true);

    video.remove();
    outside.remove();
  });

  it('sends completed IME composition text without sending process key events', () => {
    const video = document.createElement('video');
    const client = createClient();

    attachInputHandlers(video, client);
    const inputSurface = getInputSurface();

    fireEvent.mouseDown(inputSurface, { button: 0 });
    fireEvent.keyDown(window, { key: 'Process', code: 'KeyA', isComposing: true });
    fireEvent.compositionStart(inputSurface);
    fireEvent.compositionEnd(inputSurface, { data: '中文' });

    expect(client.sendKey).not.toHaveBeenCalledWith(0, true);
    expect(client.sendText).toHaveBeenCalledWith('中文');
  });

  it('stops sending input after handlers are detached', () => {
    const video = document.createElement('video');
    const client = createClient();
    const detach = attachInputHandlers(video, client);
    const inputSurface = getInputSurface();

    detach();
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });
    fireEvent.mouseDown(inputSurface, { button: 0 });

    expect(client.sendKey).not.toHaveBeenCalled();
    expect(client.sendMouseButton).not.toHaveBeenCalled();
  });
});
