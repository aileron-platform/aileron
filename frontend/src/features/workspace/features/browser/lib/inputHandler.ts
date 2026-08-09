import type { NekoClient } from './nekoClient';
import { resolveContainedMediaPoint } from './inputGeometry';

export function attachInputHandlers(video: HTMLVideoElement, client: NekoClient): () => void {
  let capturesKeyboard = false;
  let compositionActive = false;
  let suppressNextCompositionInput = false;
  let suppressCompositionTimer: ReturnType<typeof setTimeout> | undefined;
  const pressedKeys = new Map<string, number>();
  const pressedButtons = new Set<number>();
  const inputSurface = createInputSurface(video);

  const clearCompositionSuppression = () => {
    if (suppressCompositionTimer !== undefined) {
      clearTimeout(suppressCompositionTimer);
      suppressCompositionTimer = undefined;
    }
    suppressNextCompositionInput = false;
  };

  const invalidateComposition = () => {
    compositionActive = false;
    clearCompositionSuppression();
    inputSurface.value = '';
  };

  const releasePressedKeys = () => {
    const keys = [...pressedKeys.values()].reverse();
    pressedKeys.clear();
    for (const keysym of keys) {
      client.sendKey(keysym, false);
    }
  };

  const releaseAllPressedInputs = () => {
    releasePressedKeys();
    for (const button of pressedButtons) {
      client.sendMouseButton(button, false);
    }
    pressedButtons.clear();
  };

  const loseInputOwnership = () => {
    releaseAllPressedInputs();
    invalidateComposition();
    capturesKeyboard = false;
  };

  const resolvePoint = (clientX: number, clientY: number) => {
    const { width, height } = client.getScreenResolution();
    return resolveContainedMediaPoint(video, clientX, clientY, width, height);
  };

  const handleMouseMove = (event: MouseEvent) => {
    const point = resolvePoint(event.clientX, event.clientY);
    if (point) {
      client.sendMouseMove(point.x, point.y);
    }
  };

  const handleMouseDown = (event: MouseEvent) => {
    const point = resolvePoint(event.clientX, event.clientY);
    if (!point) {
      return;
    }

    client.sendMouseMove(point.x, point.y);
    if (!pressedButtons.has(event.button)) {
      pressedButtons.add(event.button);
      client.sendMouseButton(event.button, true);
    }
    capturesKeyboard = true;
    focusInputSurface(inputSurface);
  };

  const handleWindowMouseUp = (event: MouseEvent) => {
    if (!pressedButtons.has(event.button)) {
      return;
    }

    const point = resolvePoint(event.clientX, event.clientY);
    if (point) {
      client.sendMouseMove(point.x, point.y);
    }
    pressedButtons.delete(event.button);
    client.sendMouseButton(event.button, false);
  };

  const handleContextMenu = (event: MouseEvent) => {
    if (resolvePoint(event.clientX, event.clientY)) {
      event.preventDefault();
    }
  };

  const handleTouchStart = (event: TouchEvent) => {
    const touch = event.changedTouches[0];
    if (!touch || !resolvePoint(touch.clientX, touch.clientY)) {
      return;
    }
    capturesKeyboard = true;
    focusInputSurface(inputSurface);
  };

  const handleWheel = (event: WheelEvent) => {
    if (!resolvePoint(event.clientX, event.clientY)) {
      return;
    }
    event.preventDefault();
    client.sendWheel(event.deltaX, event.deltaY);
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (!capturesKeyboard || event.isComposing || isCompositionKey(event.key)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const identity = physicalKeyIdentity(event);
    if (event.repeat || pressedKeys.has(identity)) {
      return;
    }

    const keysym = browserKeyToX11Keysym(event.key, event.code);
    if (keysym !== 0) {
      pressedKeys.set(identity, keysym);
      client.sendKey(keysym, true);
    }
  };

  const handleKeyUp = (event: KeyboardEvent) => {
    const identity = physicalKeyIdentity(event);
    const pressed = pressedKeys.get(identity);
    if (pressed) {
      event.preventDefault();
      event.stopPropagation();
      pressedKeys.delete(identity);
      client.sendKey(pressed, false);
      return;
    }

    if (!capturesKeyboard || event.isComposing || isCompositionKey(event.key)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDocumentMouseDown = (event: MouseEvent) => {
    if (event.target instanceof Node && inputSurface.contains(event.target)) {
      return;
    }
    loseInputOwnership();
  };

  const handleWindowBlur = () => {
    loseInputOwnership();
  };

  const handleVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      loseInputOwnership();
    }
  };

  const handleCompositionStart = () => {
    if (!capturesKeyboard) {
      invalidateComposition();
      return;
    }
    releasePressedKeys();
    clearCompositionSuppression();
    compositionActive = true;
    inputSurface.value = '';
  };

  const handleCompositionEnd = (event: CompositionEvent) => {
    if (!compositionActive || !capturesKeyboard) {
      invalidateComposition();
      return;
    }

    const text = event.data || inputSurface.value;
    compositionActive = false;
    inputSurface.value = '';
    if (!text) {
      return;
    }

    client.sendText(text);
    suppressNextCompositionInput = true;
    suppressCompositionTimer = setTimeout(() => {
      suppressNextCompositionInput = false;
      suppressCompositionTimer = undefined;
    }, 0);
  };

  const handleInput = (event: InputEvent) => {
    if (compositionActive) {
      return;
    }

    const text = inputSurface.value;
    inputSurface.value = '';
    if (suppressNextCompositionInput) {
      clearCompositionSuppression();
      return;
    }
    if (!capturesKeyboard || !text || event.inputType === 'deleteContentBackward') {
      return;
    }
    if (event.inputType === 'insertFromPaste' || containsNonAscii(text)) {
      client.sendText(text);
    }
  };

  inputSurface.addEventListener('mousemove', handleMouseMove);
  inputSurface.addEventListener('mousedown', handleMouseDown);
  inputSurface.addEventListener('contextmenu', handleContextMenu);
  inputSurface.addEventListener('touchstart', handleTouchStart, { passive: true });
  inputSurface.addEventListener('wheel', handleWheel, { passive: false });
  inputSurface.addEventListener('compositionstart', handleCompositionStart);
  inputSurface.addEventListener('compositionend', handleCompositionEnd);
  inputSurface.addEventListener('input', handleInput);
  window.addEventListener('mouseup', handleWindowMouseUp, true);
  window.addEventListener('keydown', handleKeyDown, true);
  window.addEventListener('keyup', handleKeyUp, true);
  window.addEventListener('blur', handleWindowBlur);
  document.addEventListener('mousedown', handleDocumentMouseDown, true);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  return () => {
    releaseAllPressedInputs();
    invalidateComposition();
    capturesKeyboard = false;
    inputSurface.removeEventListener('mousemove', handleMouseMove);
    inputSurface.removeEventListener('mousedown', handleMouseDown);
    inputSurface.removeEventListener('contextmenu', handleContextMenu);
    inputSurface.removeEventListener('touchstart', handleTouchStart);
    inputSurface.removeEventListener('wheel', handleWheel);
    inputSurface.removeEventListener('compositionstart', handleCompositionStart);
    inputSurface.removeEventListener('compositionend', handleCompositionEnd);
    inputSurface.removeEventListener('input', handleInput);
    window.removeEventListener('mouseup', handleWindowMouseUp, true);
    window.removeEventListener('keydown', handleKeyDown, true);
    window.removeEventListener('keyup', handleKeyUp, true);
    window.removeEventListener('blur', handleWindowBlur);
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    inputSurface.remove();
  };
}

function createInputSurface(video: HTMLVideoElement): HTMLTextAreaElement {
  const inputSurface = document.createElement('textarea');
  inputSurface.setAttribute('aria-hidden', 'true');
  inputSurface.setAttribute('autocomplete', 'off');
  inputSurface.setAttribute('autocorrect', 'off');
  inputSurface.setAttribute('autocapitalize', 'off');
  inputSurface.setAttribute('spellcheck', 'false');
  inputSurface.tabIndex = 0;
  Object.assign(inputSurface.style, {
    position: 'absolute',
    inset: '0',
    width: '100%',
    height: '100%',
    border: '0',
    outline: '0',
    resize: 'none',
    color: 'transparent',
    caretColor: 'transparent',
    background: 'transparent',
    opacity: '0.01',
    cursor: 'default',
    zIndex: '1',
  });

  const parent = video.parentElement ?? document.body;
  parent.append(inputSurface);
  return inputSurface;
}

function focusInputSurface(inputSurface: HTMLTextAreaElement): void {
  if (document.activeElement !== inputSurface) {
    inputSurface.focus({ preventScroll: true });
  }
}

function physicalKeyIdentity(event: KeyboardEvent): string {
  if (event.code) {
    return `code:${event.code}`;
  }
  const legacyCode = event.keyCode || event.which;
  if (legacyCode) {
    return `legacy:${legacyCode}:${event.location}`;
  }
  return `key:${event.key}:${event.location}`;
}

function isCompositionKey(key: string): boolean {
  return key === 'Process' || key === 'Unidentified' || key === 'Dead' || key === 'Compose';
}

function containsNonAscii(text: string): boolean {
  return /[^\x00-\x7F]/.test(text);
}

function browserKeyToX11Keysym(key: string, code: string): number {
  const modifiers: Record<string, number> = {
    ShiftLeft: 0xffe1,
    ShiftRight: 0xffe2,
    ControlLeft: 0xffe3,
    ControlRight: 0xffe4,
    MetaLeft: 0xffe7,
    MetaRight: 0xffe8,
    AltLeft: 0xffe9,
    AltRight: 0xffea,
  };
  if (modifiers[code] !== undefined) {
    return modifiers[code];
  }

  const special: Record<string, number> = {
    Escape: 0xff1b,
    Enter: 0xff0d,
    Backspace: 0xff08,
    Tab: 0xff09,
    Delete: 0xffff,
    Home: 0xff50,
    End: 0xff57,
    PageUp: 0xff55,
    PageDown: 0xff56,
    ArrowLeft: 0xff51,
    ArrowUp: 0xff52,
    ArrowRight: 0xff53,
    ArrowDown: 0xff54,
    F1: 0xffbe,
    F2: 0xffbf,
    F3: 0xffc0,
    F4: 0xffc1,
    F5: 0xffc2,
    F6: 0xffc3,
    F7: 0xffc4,
    F8: 0xffc5,
    F9: 0xffc6,
    F10: 0xffc7,
    F11: 0xffc8,
    F12: 0xffc9,
    Shift: 0xffe1,
    Control: 0xffe3,
    Alt: 0xffe9,
    Meta: 0xffe7,
    CapsLock: 0xffe5,
    Insert: 0xff63,
    Pause: 0xff13,
  };
  if (special[key] !== undefined) {
    return special[key];
  }

  if (key.length === 1) {
    const codePoint = key.codePointAt(0) ?? 0;
    if (codePoint >= 0x20 && codePoint <= 0x7e) {
      return codePoint;
    }
    return 0x01000000 | codePoint;
  }
  return 0;
}
