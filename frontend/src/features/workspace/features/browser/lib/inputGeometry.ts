export interface RemotePoint {
  x: number;
  y: number;
}

export function resolveContainedMediaPoint(
  element: HTMLElement,
  clientX: number,
  clientY: number,
  screenWidth: number,
  screenHeight: number,
): RemotePoint | null {
  const rect = element.getBoundingClientRect();
  const dimensions = [rect.width, rect.height, screenWidth, screenHeight, clientX, clientY];
  if (!dimensions.every(Number.isFinite)) {
    return null;
  }
  if (rect.width <= 0 || rect.height <= 0 || screenWidth <= 0 || screenHeight <= 0) {
    return null;
  }

  const scale = Math.min(rect.width / screenWidth, rect.height / screenHeight);
  const contentWidth = screenWidth * scale;
  const contentHeight = screenHeight * scale;
  const contentLeft = rect.left + (rect.width - contentWidth) / 2;
  const contentTop = rect.top + (rect.height - contentHeight) / 2;
  const contentRight = contentLeft + contentWidth;
  const contentBottom = contentTop + contentHeight;

  if (clientX < contentLeft || clientX >= contentRight || clientY < contentTop || clientY >= contentBottom) {
    return null;
  }

  return {
    x: clampRemoteCoordinate(Math.round(((clientX - contentLeft) / contentWidth) * screenWidth), screenWidth),
    y: clampRemoteCoordinate(Math.round(((clientY - contentTop) / contentHeight) * screenHeight), screenHeight),
  };
}

function clampRemoteCoordinate(value: number, limit: number): number {
  return Math.max(0, Math.min(limit - 1, value));
}
