import type { NekoClient } from './nekoClient';

export function attachInputHandlers(video: HTMLVideoElement, client: NekoClient): () => void {
  let capturesKeyboard = false;
  let composing = false;
  const inputSurface = createInputSurface(video);

  const handleMouseMove = (event: MouseEvent) => {
    const { width, height } = client.getScreenResolution();
    const { x, y } = resolveRelativePosition(video, event.clientX, event.clientY, width, height);
    client.sendMouseMove(x, y);
  };

  const handleMouseDown = (event: MouseEvent) => {
    capturesKeyboard = true;
    focusInputSurface(inputSurface);
    sendMousePosition(video, client, event.clientX, event.clientY);
    client.sendMouseButton(event.button, true);
  };

  const handleMouseUp = (event: MouseEvent) => {
    sendMousePosition(video, client, event.clientX, event.clientY);
    client.sendMouseButton(event.button, false);
  };

  const handleTouchStart = () => {
    capturesKeyboard = true;
    focusInputSurface(inputSurface);
  };

  const handleWheel = (event: WheelEvent) => {
    event.preventDefault();
    client.sendWheel(event.deltaX, event.deltaY);
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (!capturesKeyboard) {
      return;
    }
    if (event.isComposing || isCompositionKey(event.key)) {
      return;
    }

    // Intercept keyboard input while the stream owns focus.
    event.preventDefault();
    event.stopPropagation();
    const keysym = browserKeyToX11Keysym(event.key, event.code);
    if (keysym !== 0) {
      client.sendKey(keysym, true);
    }
  };

  const handleKeyUp = (event: KeyboardEvent) => {
    if (!capturesKeyboard) {
      return;
    }
    if (event.isComposing || isCompositionKey(event.key)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const keysym = browserKeyToX11Keysym(event.key, event.code);
    if (keysym !== 0) {
      client.sendKey(keysym, false);
    }
  };

  const handleDocumentMouseDown = (event: MouseEvent) => {
    if (event.target instanceof Node && inputSurface.contains(event.target)) {
      return;
    }

    capturesKeyboard = false;
  };

  const handleCompositionStart = () => {
    composing = true;
    inputSurface.value = '';
  };

  const handleCompositionEnd = (event: CompositionEvent) => {
    composing = false;
    const text = event.data || inputSurface.value;
    inputSurface.value = '';
    client.sendText(text);
  };

  const handleInput = (event: InputEvent) => {
    if (composing) {
      return;
    }

    const text = inputSurface.value;
    inputSurface.value = '';
    if (!text || event.inputType === 'deleteContentBackward') {
      return;
    }

    if (event.inputType === 'insertFromPaste' || containsNonAscii(text)) {
      client.sendText(text);
    }
  };

  inputSurface.addEventListener('mousemove', handleMouseMove);
  inputSurface.addEventListener('mousedown', handleMouseDown);
  inputSurface.addEventListener('mouseup', handleMouseUp);
  inputSurface.addEventListener('touchstart', handleTouchStart, { passive: true });
  inputSurface.addEventListener('wheel', handleWheel, { passive: false });
  inputSurface.addEventListener('compositionstart', handleCompositionStart);
  inputSurface.addEventListener('compositionend', handleCompositionEnd);
  inputSurface.addEventListener('input', handleInput);
  window.addEventListener('keydown', handleKeyDown, true);
  window.addEventListener('keyup', handleKeyUp, true);
  document.addEventListener('mousedown', handleDocumentMouseDown, true);

  return () => {
    inputSurface.removeEventListener('mousemove', handleMouseMove);
    inputSurface.removeEventListener('mousedown', handleMouseDown);
    inputSurface.removeEventListener('mouseup', handleMouseUp);
    inputSurface.removeEventListener('touchstart', handleTouchStart);
    inputSurface.removeEventListener('wheel', handleWheel);
    inputSurface.removeEventListener('compositionstart', handleCompositionStart);
    inputSurface.removeEventListener('compositionend', handleCompositionEnd);
    inputSurface.removeEventListener('input', handleInput);
    window.removeEventListener('keydown', handleKeyDown, true);
    window.removeEventListener('keyup', handleKeyUp, true);
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
    inputSurface.remove();
  };
}

function resolveRelativePosition(
  element: HTMLElement,
  clientX: number,
  clientY: number,
  screenWidth: number,
  screenHeight: number,
): { x: number; y: number } {
  const rect = element.getBoundingClientRect();
  const relativeX = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
  const relativeY = rect.height > 0 ? (clientY - rect.top) / rect.height : 0;

  return {
    x: Math.max(0, Math.min(screenWidth - 1, Math.round(relativeX * screenWidth))),
    y: Math.max(0, Math.min(screenHeight - 1, Math.round(relativeY * screenHeight))),
  };
}

function sendMousePosition(video: HTMLVideoElement, client: NekoClient, clientX: number, clientY: number): void {
  const { width, height } = client.getScreenResolution();
  const { x, y } = resolveRelativePosition(video, clientX, clientY, width, height);
  client.sendMouseMove(x, y);
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
    zIndex: '1',
  });

  const parent = video.parentElement ?? document.body;
  parent.append(inputSurface);
  return inputSurface;
}

function focusInputSurface(inputSurface: HTMLTextAreaElement): void {
  if (document.activeElement === inputSurface) {
    return;
  }

  inputSurface.focus({ preventScroll: true });
}

function isCompositionKey(key: string): boolean {
  return key === 'Process' || key === 'Unidentified' || key === 'Dead' || key === 'Compose';
}

function containsNonAscii(text: string): boolean {
  return /[^\x00-\x7F]/.test(text);
}

// Browser KeyboardEvent.key to X11 keysym.
function browserKeyToX11Keysym(key: string, _code: string): number {
  const SPECIAL: Record<string, number> = {
    Escape:      0xff1b,
    Enter:       0xff0d,
    Backspace:   0xff08,
    Tab:         0xff09,
    Delete:      0xffff,
    Home:        0xff50,
    End:         0xff57,
    PageUp:      0xff55,
    PageDown:    0xff56,
    ArrowLeft:   0xff51,
    ArrowUp:     0xff52,
    ArrowRight:  0xff53,
    ArrowDown:   0xff54,
    F1:  0xffbe, F2:  0xffbf, F3:  0xffc0, F4:  0xffc1,
    F5:  0xffc2, F6:  0xffc3, F7:  0xffc4, F8:  0xffc5,
    F9:  0xffc6, F10: 0xffc7, F11: 0xffc8, F12: 0xffc9,
    Shift:    0xffe1,
    Control:  0xffe3,
    Alt:      0xffe9,
    Meta:     0xffe7,
    CapsLock: 0xffe5,
    Insert:   0xff63,
    Pause:    0xff13,
  };

  if (SPECIAL[key] !== undefined) {
    return SPECIAL[key];
  }

  // Printable characters use Unicode code points directly.
  if (key.length === 1) {
    const cp = key.codePointAt(0) ?? 0;
    // ASCII maps directly to X11 keysyms.
    if (cp >= 0x20 && cp <= 0x7e) {
      return cp;
    }
    // Non-ASCII printable keys follow the X11 Unicode keysym encoding.
    return 0x01000000 | cp;
  }

  return 0;
}
