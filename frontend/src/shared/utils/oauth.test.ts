import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateCodeChallenge } from './oauth';

describe('OAuth PKCE utilities', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the production async fallback to generate the RFC 7636 code challenge', async () => {
    const originalCrypto = globalThis.crypto;
    vi.stubGlobal('crypto', {
      getRandomValues: originalCrypto.getRandomValues.bind(originalCrypto),
      subtle: undefined,
    } as Crypto);

    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';

    await expect(generateCodeChallenge(verifier)).resolves.toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    );
  });
});
