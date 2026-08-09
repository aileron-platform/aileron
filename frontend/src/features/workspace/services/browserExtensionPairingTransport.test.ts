import { describe, expect, it, vi } from 'vitest';
import {
  deliverBrowserExtensionPairing,
  type ExternalChromeRuntime,
} from './browserExtensionPairingTransport';

const extensionId = 'abcdefghijklmnopabcdefghijklmnop';
const pairing = {
  assertion: 'header.payload.signature',
  runtimeInstanceId: 'runtime-instance-123',
};

describe('deliverBrowserExtensionPairing', () => {
  it('sends the assertion only in an external extension message', async () => {
    const sendMessage = vi.fn(
      (_id: string, _message: unknown, callback: (response: unknown) => void) => {
        callback({ accepted: true, runtimeInstanceId: pairing.runtimeInstanceId });
      }
    );
    const runtime: ExternalChromeRuntime = { sendMessage };

    await deliverBrowserExtensionPairing(extensionId, pairing, runtime);

    expect(sendMessage).toHaveBeenCalledWith(
      extensionId,
      {
        type: 'configureBrowserExtensionPairing',
        pairing,
      },
      expect.any(Function)
    );
  });

  it.each([
    undefined,
    { accepted: false },
    { accepted: true, runtimeInstanceId: 'old-runtime-instance' },
    {
      accepted: true,
      runtimeInstanceId: pairing.runtimeInstanceId,
      token: 'unsupported',
    },
  ])('rejects a missing, negative, stale, or widened response', async (response) => {
    const runtime: ExternalChromeRuntime = {
      sendMessage: (_id, _message, callback) => callback(response),
    };

    await expect(
      deliverBrowserExtensionPairing(extensionId, pairing, runtime)
    ).rejects.toThrow('BROWSER_EXTENSION_PAIRING_REJECTED');
  });

  it('fails before sending when deployment configuration is invalid', async () => {
    const runtime: ExternalChromeRuntime = { sendMessage: vi.fn() };

    await expect(
      deliverBrowserExtensionPairing('__VITE_BROWSER_EXTENSION_ID__', pairing, runtime)
    ).rejects.toThrow('BROWSER_EXTENSION_UNAVAILABLE');

    expect(runtime.sendMessage).not.toHaveBeenCalled();
  });
});
