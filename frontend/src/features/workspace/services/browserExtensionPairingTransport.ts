import type { BrowserExtensionPairingAssertionResponse } from '../api/workspaceBrowserExtensionApi';
import { resolveBrowserExtensionId } from '../config/browserExtensionConfig';

const PAIRING_RESPONSE_TIMEOUT_MS = 5_000;

interface BrowserExtensionPairingResponse {
  accepted: boolean;
  runtimeInstanceId?: string;
}

export interface ExternalChromeRuntime {
  readonly lastError?: { readonly message?: string };
  sendMessage(
    extensionId: string,
    message: unknown,
    callback: (response: unknown) => void
  ): void;
}

function getExternalChromeRuntime(): ExternalChromeRuntime | null {
  const chromeGlobal = (globalThis as {
    chrome?: { runtime?: ExternalChromeRuntime };
  }).chrome;
  return chromeGlobal?.runtime ?? null;
}

function isPairingResponse(value: unknown): value is BrowserExtensionPairingResponse {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const response = value as Record<string, unknown>;
  return (
    Object.keys(response).every(
      (key) => key === 'accepted' || key === 'runtimeInstanceId'
    ) &&
    typeof response.accepted === 'boolean' &&
    (response.runtimeInstanceId === undefined ||
      typeof response.runtimeInstanceId === 'string')
  );
}

function validatePairing(pairing: BrowserExtensionPairingAssertionResponse): void {
  if (
    typeof pairing.assertion !== 'string' ||
    pairing.assertion.length === 0 ||
    pairing.assertion.length > 16_384 ||
    /\s/.test(pairing.assertion) ||
    typeof pairing.runtimeInstanceId !== 'string' ||
    pairing.runtimeInstanceId.length === 0 ||
    pairing.runtimeInstanceId !== pairing.runtimeInstanceId.trim()
  ) {
    throw new Error('BROWSER_EXTENSION_PAIRING_INVALID');
  }
}

export async function deliverBrowserExtensionPairing(
  extensionId: string,
  pairing: BrowserExtensionPairingAssertionResponse,
  runtime: ExternalChromeRuntime | null = getExternalChromeRuntime()
): Promise<void> {
  if (resolveBrowserExtensionId(extensionId) === null || runtime === null) {
    throw new Error('BROWSER_EXTENSION_UNAVAILABLE');
  }
  validatePairing(pairing);

  await new Promise<void>((resolve, reject) => {
    let settled = false;
    const finish = (callback: () => void) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeoutId);
      callback();
    };
    const timeoutId = setTimeout(() => {
      finish(() => reject(new Error('BROWSER_EXTENSION_PAIRING_TIMEOUT')));
    }, PAIRING_RESPONSE_TIMEOUT_MS);

    try {
      runtime.sendMessage(
        extensionId,
        {
          type: 'configureBrowserExtensionPairing',
          pairing,
        },
        (response) => {
          finish(() => {
            if (runtime.lastError) {
              reject(new Error('BROWSER_EXTENSION_UNAVAILABLE'));
              return;
            }
            if (
              !isPairingResponse(response) ||
              response.accepted !== true ||
              response.runtimeInstanceId !== pairing.runtimeInstanceId
            ) {
              reject(new Error('BROWSER_EXTENSION_PAIRING_REJECTED'));
              return;
            }
            resolve();
          });
        }
      );
    } catch {
      finish(() => reject(new Error('BROWSER_EXTENSION_UNAVAILABLE')));
    }
  });
}
