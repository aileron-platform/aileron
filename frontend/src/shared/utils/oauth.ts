/**
 * OAuth2 安全參數生成工具 - 修正版本
 */

const SHA256_ROUND_CONSTANTS = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const SHA256_INITIAL_HASH = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

const rightRotate = (value: number, bits: number): number =>
  (value >>> bits) | (value << (32 - bits));

function toBase64Url(input: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < input.length; i++) {
    binary += String.fromCharCode(input[i]);
  }

  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

function sha256Bytes(input: Uint8Array): Uint8Array {
  const bitLength = input.length * 8;
  const paddedLength = (((input.length + 9 + 63) >> 6) << 6);
  const padded = new Uint8Array(paddedLength);
  padded.set(input);
  padded[input.length] = 0x80;

  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 4, bitLength >>> 0, false);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000), false);

  const hash = [...SHA256_INITIAL_HASH];
  const words = new Uint32Array(64);

  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i++) {
      words[i] = view.getUint32(offset + i * 4, false);
    }

    for (let i = 16; i < 64; i++) {
      const s0 = rightRotate(words[i - 15], 7) ^ rightRotate(words[i - 15], 18) ^ (words[i - 15] >>> 3);
      const s1 = rightRotate(words[i - 2], 17) ^ rightRotate(words[i - 2], 19) ^ (words[i - 2] >>> 10);
      words[i] = (((words[i - 16] + s0) >>> 0) + ((words[i - 7] + s1) >>> 0)) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;

    for (let i = 0; i < 64; i++) {
      const s1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (((((h + s1) >>> 0) + ((choice + SHA256_ROUND_CONSTANTS[i]) >>> 0)) >>> 0) + words[i]) >>> 0;
      const s0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + majority) >>> 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    hash[0] = (hash[0] + a) >>> 0;
    hash[1] = (hash[1] + b) >>> 0;
    hash[2] = (hash[2] + c) >>> 0;
    hash[3] = (hash[3] + d) >>> 0;
    hash[4] = (hash[4] + e) >>> 0;
    hash[5] = (hash[5] + f) >>> 0;
    hash[6] = (hash[6] + g) >>> 0;
    hash[7] = (hash[7] + h) >>> 0;
  }

  const digest = new Uint8Array(32);
  const digestView = new DataView(digest.buffer);
  hash.forEach((value, index) => {
    digestView.setUint32(index * 4, value, false);
  });

  return digest;
}

/**
 * 生成 OAuth state 參數（只包含安全字元）
 */
export function generateState(): string {
  // OAuth state 只能包含字母、數字、-、_
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  let result = '';

  // 生成 43 字元的 state（標準長度）
  const randomValues = new Uint8Array(43);
  crypto.getRandomValues(randomValues);

  for (let i = 0; i < 43; i++) {
    result += charset[randomValues[i] % charset.length];
  }

  return result;
}

/**
 * 生成 PKCE code verifier
 * 使用 base64url 編碼，與後端實現一致
 */
export function generateCodeVerifier(): string {
  // 生成 32 bytes 的隨機數據
  const randomBytes = new Uint8Array(32);
  crypto.getRandomValues(randomBytes);

  // 轉換為 base64url 格式（與後端 Python 實現一致）
  let binary = '';
  for (let i = 0; i < randomBytes.length; i++) {
    binary += String.fromCharCode(randomBytes[i]);
  }

  // Base64 編碼並轉換為 base64url（移除 padding）
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

/**
 * 使用 Web Crypto API 生成真正的 SHA256 並轉為 Base64URL
 */
export async function generateCodeChallenge(codeVerifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const subtle = globalThis.crypto?.subtle;

  if (subtle?.digest) {
    const hashBuffer = await subtle.digest('SHA-256', data);
    return toBase64Url(new Uint8Array(hashBuffer));
  }

  return toBase64Url(sha256Bytes(data));
}

/**
 * 同步版本的簡化實作（用於相容性）
 * 在非安全上下文下提供真正的 SHA-256 fallback
 */
export function generateCodeChallengeSync(codeVerifier: string): string {
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  return toBase64Url(sha256Bytes(data));
}

// 為了向後相容，保留舊的函式名稱
export function generateRandomString(length: number): string {
  if (length === 43) {
    return generateState();
  }
  return generateCodeVerifier();
}

export function base64URLEncode(input: string | ArrayBuffer): string {
  let binary = '';

  if (typeof input === 'string') {
    binary = input;
  } else {
    const bytes = new Uint8Array(input);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
  }

  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

export function sha256(plain: string): string {
  return generateCodeChallengeSync(plain);
}
