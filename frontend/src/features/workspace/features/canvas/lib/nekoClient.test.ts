import { describe, expect, it } from 'vitest';
import { NekoClient } from './nekoClient';

describe('NekoClient input data channel messages', () => {
  it('encodes keyboard input using the Neko binary data protocol', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendKey(0x61, true);
    client.sendKey(0x61, false);

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
  });

  it('encodes mouse clicks with the same key event payload expected by Neko', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendMouseButton(0, true);
    client.sendMouseButton(0, false);

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
  });

  it('encodes non-ASCII text as X11 Unicode keysyms', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendText('中');

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x2d, 0x4e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x2d, 0x4e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]);
  });
});

function toBytes(buffer: ArrayBuffer): number[] {
  return Array.from(new Uint8Array(buffer));
}
