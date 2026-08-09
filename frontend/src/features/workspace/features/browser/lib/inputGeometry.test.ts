import { describe, expect, it, vi } from 'vitest';
import { resolveContainedMediaPoint } from './inputGeometry';

function createElement(rect: Partial<DOMRect> = {}): HTMLElement {
  const element = document.createElement('div');
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 1600,
    bottom: 900,
    width: 1600,
    height: 900,
    toJSON: () => ({}),
    ...rect,
  });
  return element;
}

describe('resolveContainedMediaPoint', () => {
  it('maps the center and final in-bounds pixel for matching aspect ratios', () => {
    const element = createElement({ right: 1440, width: 1440 });

    expect(resolveContainedMediaPoint(element, 720, 450, 1440, 900)).toEqual({ x: 720, y: 450 });
    expect(resolveContainedMediaPoint(element, 1439.99, 899.99, 1440, 900)).toEqual({ x: 1439, y: 899 });
  });

  it('ignores pillarbox regions in a wider container', () => {
    const element = createElement();

    expect(resolveContainedMediaPoint(element, 79.99, 450, 1440, 900)).toBeNull();
    expect(resolveContainedMediaPoint(element, 80, 450, 1440, 900)).toEqual({ x: 0, y: 450 });
    expect(resolveContainedMediaPoint(element, 1520, 450, 1440, 900)).toBeNull();
  });

  it('ignores letterbox regions in a taller container', () => {
    const element = createElement({ right: 900, bottom: 900, width: 900, height: 900 });

    expect(resolveContainedMediaPoint(element, 450, 168.74, 1440, 900)).toBeNull();
    expect(resolveContainedMediaPoint(element, 450, 168.75, 1440, 900)).toEqual({ x: 720, y: 0 });
    expect(resolveContainedMediaPoint(element, 450, 731.25, 1440, 900)).toBeNull();
  });

  it('uses the current DOM rect on every call so resize does not require reattachment', () => {
    const element = document.createElement('div');
    const getRect = vi.spyOn(element, 'getBoundingClientRect');
    getRect.mockReturnValueOnce({
      x: 0, y: 0, top: 0, left: 0, right: 1600, bottom: 900, width: 1600, height: 900, toJSON: () => ({}),
    });
    getRect.mockReturnValueOnce({
      x: 0, y: 0, top: 0, left: 0, right: 900, bottom: 900, width: 900, height: 900, toJSON: () => ({}),
    });

    expect(resolveContainedMediaPoint(element, 80, 450, 1440, 900)).toEqual({ x: 0, y: 450 });
    expect(resolveContainedMediaPoint(element, 450, 168.75, 1440, 900)).toEqual({ x: 720, y: 0 });
  });

  it.each([
    [0, 900, 1440, 900],
    [1600, 0, 1440, 900],
    [1600, 900, 0, 900],
    [1600, 900, 1440, 0],
    [Number.NaN, 900, 1440, 900],
    [1600, Number.POSITIVE_INFINITY, 1440, 900],
  ])('returns null for invalid dimensions', (rectWidth, rectHeight, screenWidth, screenHeight) => {
    const element = createElement({ width: rectWidth, height: rectHeight });

    expect(resolveContainedMediaPoint(element, 0, 0, screenWidth, screenHeight)).toBeNull();
  });
});
