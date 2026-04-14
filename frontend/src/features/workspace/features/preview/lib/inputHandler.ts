import type { NekoClient } from './nekoClient';

export function attachInputHandlers(video: HTMLVideoElement, client: NekoClient): () => void {
  const handleMouseMove = (event: MouseEvent) => {
    const { width, height } = client.getScreenResolution();
    const { x, y } = resolveRelativePosition(video, event.clientX, event.clientY, width, height);
    client.sendMouseMove(x, y);
  };

  const handleMouseDown = (event: MouseEvent) => {
    client.sendMouseButton(event.button, true);
  };

  const handleMouseUp = (event: MouseEvent) => {
    client.sendMouseButton(event.button, false);
  };

  const handleWheel = (event: WheelEvent) => {
    event.preventDefault();
    client.sendWheel(event.deltaX, event.deltaY);
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    // 當 focus 在 video 身上時攔截鍵盤輸入，避免觸發瀏覽器快捷鍵
    event.preventDefault();
    const keysym = browserKeyToX11Keysym(event.key, event.code);
    if (keysym !== 0) {
      client.sendKey(keysym, true);
    }
  };

  const handleKeyUp = (event: KeyboardEvent) => {
    event.preventDefault();
    const keysym = browserKeyToX11Keysym(event.key, event.code);
    if (keysym !== 0) {
      client.sendKey(keysym, false);
    }
  };

  // video 需要 tabIndex 才能接收鍵盤事件
  if (video.tabIndex < 0) {
    video.tabIndex = 0;
  }

  video.addEventListener('mousemove', handleMouseMove);
  video.addEventListener('mousedown', handleMouseDown);
  video.addEventListener('mouseup', handleMouseUp);
  video.addEventListener('wheel', handleWheel, { passive: false });
  video.addEventListener('keydown', handleKeyDown);
  video.addEventListener('keyup', handleKeyUp);

  return () => {
    video.removeEventListener('mousemove', handleMouseMove);
    video.removeEventListener('mousedown', handleMouseDown);
    video.removeEventListener('mouseup', handleMouseUp);
    video.removeEventListener('wheel', handleWheel);
    video.removeEventListener('keydown', handleKeyDown);
    video.removeEventListener('keyup', handleKeyUp);
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

// Browser KeyboardEvent.key → X11 keysym
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

  // 可印字元直接使用 Unicode codepoint（X11 keysym for BMP = 0x01000000 | codepoint）
  if (key.length === 1) {
    const cp = key.codePointAt(0) ?? 0;
    // ASCII 範圍直接對應
    if (cp >= 0x20 && cp <= 0x7e) {
      return cp;
    }
    // BMP 以上使用 X11 keysym Unicode 規範
    return 0x01000000 | cp;
  }

  return 0;
}
