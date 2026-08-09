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

function setupInput() {
  const container = document.createElement('div');
  const video = document.createElement('video');
  container.append(video);
  document.body.append(container);
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
  const client = createClient();
  const detach = attachInputHandlers(video, client);
  const inputSurface = container.querySelector('textarea');
  if (!(inputSurface instanceof HTMLTextAreaElement)) {
    throw new Error('Input surface was not created');
  }
  return { client, container, detach, inputSurface, video };
}

function captureKeyboard(inputSurface: HTMLTextAreaElement): void {
  fireEvent.mouseDown(inputSurface, { button: 0, clientX: 360, clientY: 225 });
  fireEvent.mouseUp(window, { button: 0, clientX: 360, clientY: 225 });
}

describe('attachInputHandlers', () => {
  const detachers: Array<() => void> = [];

  afterEach(() => {
    for (const detach of detachers.splice(0).reverse()) {
      detach();
    }
    document.body.innerHTML = '';
    vi.useRealTimers();
  });

  function setup() {
    const result = setupInput();
    detachers.push(result.detach);
    return result;
  }

  it('focuses only valid video content and keeps the local host cursor visible', () => {
    const { client, inputSurface } = setup();
    const focus = vi.spyOn(inputSurface, 'focus');

    fireEvent.mouseDown(inputSurface, { button: 0, clientX: 360, clientY: 225 });

    expect(inputSurface.style.cursor).toBe('default');
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(client.sendMouseMove).toHaveBeenCalledWith(720, 450);
    expect(client.sendMouseButton).toHaveBeenCalledWith(0, true);
  });

  it('ignores pointer and wheel input in contain letterbox regions', () => {
    const { client, inputSurface, video } = setup();
    vi.mocked(video.getBoundingClientRect).mockReturnValue({
      x: 0, y: 0, top: 0, left: 0, right: 900, bottom: 900, width: 900, height: 900, toJSON: () => ({}),
    });

    fireEvent.mouseDown(inputSurface, { button: 0, clientX: 450, clientY: 100 });
    const wheel = new WheelEvent('wheel', { bubbles: true, cancelable: true, clientX: 450, clientY: 100, deltaY: 2 });
    inputSurface.dispatchEvent(wheel);
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });

    expect(client.sendMouseMove).not.toHaveBeenCalled();
    expect(client.sendMouseButton).not.toHaveBeenCalled();
    expect(client.sendWheel).not.toHaveBeenCalled();
    expect(client.sendKey).not.toHaveBeenCalled();
    expect(wheel.defaultPrevented).toBe(false);
  });

  it('deduplicates repeated keydown and releases the saved keysym', () => {
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    const down = new KeyboardEvent('keydown', { key: 'A', code: 'KeyA', bubbles: true, cancelable: true });
    const repeat = new KeyboardEvent('keydown', { key: 'A', code: 'KeyA', repeat: true, bubbles: true, cancelable: true });
    const up = new KeyboardEvent('keyup', { key: 'a', code: 'KeyA', bubbles: true, cancelable: true });
    window.dispatchEvent(down);
    window.dispatchEvent(repeat);
    window.dispatchEvent(up);

    expect(client.sendKey).toHaveBeenNthCalledWith(1, 0x41, true);
    expect(client.sendKey).toHaveBeenNthCalledWith(2, 0x41, false);
    expect(client.sendKey).toHaveBeenCalledTimes(2);
    expect(down.defaultPrevented).toBe(true);
    expect(repeat.defaultPrevented).toBe(true);
    expect(up.defaultPrevented).toBe(true);
  });

  it('uses distinct X11 keysyms for left and right modifiers', () => {
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    fireEvent.keyDown(window, { key: 'Shift', code: 'ShiftLeft', location: 1 });
    fireEvent.keyDown(window, { key: 'Shift', code: 'ShiftRight', location: 2 });
    fireEvent.keyUp(window, { key: 'Shift', code: 'ShiftLeft', location: 1 });
    fireEvent.keyUp(window, { key: 'Shift', code: 'ShiftRight', location: 2 });

    expect(client.sendKey).toHaveBeenNthCalledWith(1, 0xffe1, true);
    expect(client.sendKey).toHaveBeenNthCalledWith(2, 0xffe2, true);
    expect(client.sendKey).toHaveBeenNthCalledWith(3, 0xffe1, false);
    expect(client.sendKey).toHaveBeenNthCalledWith(4, 0xffe2, false);
  });

  it.each(['outside', 'blur', 'hidden', 'detach'] as const)('releases pressed keys on %s', (reason) => {
    const { client, detach, inputSurface } = setup();
    captureKeyboard(inputSurface);
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });

    if (reason === 'outside') {
      const outside = document.createElement('button');
      document.body.append(outside);
      fireEvent.mouseDown(outside);
    } else if (reason === 'blur') {
      window.dispatchEvent(new Event('blur'));
    } else if (reason === 'hidden') {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
      document.dispatchEvent(new Event('visibilitychange'));
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    } else {
      detach();
      detachers.pop();
    }

    expect(client.sendKey).toHaveBeenNthCalledWith(1, 0x61, true);
    expect(client.sendKey).toHaveBeenNthCalledWith(2, 0x61, false);
  });

  it('releases pressed mouse buttons exactly once when mouseup occurs outside', () => {
    const { client, inputSurface } = setup();

    fireEvent.mouseDown(inputSurface, { button: 0, clientX: 360, clientY: 225 });
    fireEvent.mouseUp(window, { button: 0, clientX: 900, clientY: 900 });
    fireEvent.mouseUp(inputSurface, { button: 0, clientX: 360, clientY: 225 });

    expect(client.sendMouseButton).toHaveBeenNthCalledWith(1, 0, true);
    expect(client.sendMouseButton).toHaveBeenNthCalledWith(2, 0, false);
    expect(client.sendMouseButton).toHaveBeenCalledTimes(2);
  });

  it('commits host IME text once when input follows compositionend', () => {
    vi.useFakeTimers();
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    fireEvent.compositionStart(inputSurface);
    fireEvent.compositionEnd(inputSurface, { data: '\u4e2d\u6587' });
    fireEvent.input(inputSurface, { inputType: 'insertCompositionText', target: { value: '\u4e2d\u6587' } });
    vi.runAllTimers();

    expect(client.sendText).toHaveBeenCalledOnce();
    expect(client.sendText).toHaveBeenCalledWith('\u4e2d\u6587');
  });

  it('commits host IME text once when input occurs before compositionend', () => {
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    fireEvent.compositionStart(inputSurface);
    fireEvent.input(inputSurface, { inputType: 'insertCompositionText', target: { value: '\u4e2d\u6587' } });
    fireEvent.compositionEnd(inputSurface, { data: '\u4e2d\u6587' });

    expect(client.sendText).toHaveBeenCalledOnce();
    expect(client.sendText).toHaveBeenCalledWith('\u4e2d\u6587');
  });

  it('invalidates unfinished composition after focus is lost', () => {
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    fireEvent.compositionStart(inputSurface);
    window.dispatchEvent(new Event('blur'));
    fireEvent.compositionEnd(inputSurface, { data: '\u4e2d\u6587' });
    fireEvent.input(inputSurface, { inputType: 'insertCompositionText', target: { value: '\u4e2d\u6587' } });

    expect(client.sendText).not.toHaveBeenCalled();
  });

  it('releases keyboard keys but not a pressed mouse button when composition starts', () => {
    const { client, inputSurface } = setup();
    fireEvent.mouseDown(inputSurface, { button: 0, clientX: 360, clientY: 225 });
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });

    fireEvent.compositionStart(inputSurface);

    expect(client.sendKey).toHaveBeenLastCalledWith(0x61, false);
    expect(client.sendMouseButton).toHaveBeenCalledTimes(1);
  });

  it('sends non-composition Chinese paste exactly once', () => {
    const { client, inputSurface } = setup();
    captureKeyboard(inputSurface);

    fireEvent.input(inputSurface, { inputType: 'insertFromPaste', target: { value: '\u4e2d\u6587' } });

    expect(client.sendText).toHaveBeenCalledOnce();
    expect(client.sendText).toHaveBeenCalledWith('\u4e2d\u6587');
  });
});
