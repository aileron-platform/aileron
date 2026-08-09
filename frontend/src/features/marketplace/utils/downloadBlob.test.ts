import { describe, expect, it, vi } from 'vitest';

import { downloadBlob } from './downloadBlob';

describe('downloadBlob', () => {
  it('downloads blobs through a temporary anchor and revokes object URLs', () => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:marketplace-download');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const anchor = document.createElement('a');
    const click = vi.spyOn(anchor, 'click').mockImplementation(() => undefined);
    const remove = vi.spyOn(anchor, 'remove').mockImplementation(() => undefined);
    const appendChild = vi.spyOn(document.body, 'appendChild');
    const createElement = vi.spyOn(document, 'createElement');

    createElement.mockReturnValue(anchor);

    downloadBlob(new Blob(['content'], { type: 'text/plain' }), 'package.zip');

    expect(createObjectURL).toHaveBeenCalled();
    expect(appendChild).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:marketplace-download');

    createElement.mockRestore();
    appendChild.mockRestore();
    click.mockRestore();
    remove.mockRestore();
    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
  });
});
