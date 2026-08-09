import dns from 'node:dns';
import http from 'node:http';
import net from 'node:net';
import type { AddressInfo } from 'node:net';

import { afterEach, describe, expect, it, vi } from 'vitest';
import { createServer as createViteServer, type ViteDevServer } from 'vite';

import viteConfig from '../vite.config';

const WORKSPACE_ID = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';
const CANVAS_HOST = `workspace-canvas-${WORKSPACE_ID}`;
const FORWARDED_PREFIX = `/workspaces/${WORKSPACE_ID}/canvas`;

const listen = async (server: http.Server, port: number): Promise<void> => {
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => {
      server.off('error', reject);
      resolve();
    });
  });
};

const close = async (server: http.Server | ViteDevServer | undefined): Promise<void> => {
  if (!server) return;
  await new Promise<void>((resolve, reject) => {
    const callback = (error?: Error) => (error ? reject(error) : resolve());
    if ('httpServer' in server) {
      void server.close().then(resolve, reject);
      return;
    }
    server.close(callback);
  });
};

describe('Vite Workspace Canvas gateway', () => {
  let manager: http.Server | undefined;
  let canvas: http.Server | undefined;
  let vite: ViteDevServer | undefined;

  afterEach(async () => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    await close(vite);
    await close(canvas);
    await close(manager);
  });

  it('forwards the canonical Canvas prefix to the HTTP upstream', async () => {
    vi.stubEnv('DOCKER_ENV', 'false');
    manager = http.createServer((_request, response) => {
      response.writeHead(204).end();
    });
    await listen(manager, 3001);

    let receivedPrefix: string | undefined;
    canvas = http.createServer((request, response) => {
      receivedPrefix = request.headers['x-forwarded-prefix'] as string | undefined;
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      response.end('<!doctype html><html><body>Canvas</body></html>');
    });
    await listen(canvas, 3003);

    const originalLookup = dns.lookup.bind(dns);
    vi.spyOn(dns, 'lookup').mockImplementation(((hostname, options, callback) => {
      if (hostname === CANVAS_HOST) {
        const done = typeof options === 'function' ? options : callback;
        if (typeof options === 'object' && options?.all) {
          done?.(null, [{ address: '127.0.0.1', family: 4 }]);
        } else {
          done?.(null, '127.0.0.1', 4);
        }
        return;
      }
      return originalLookup(hostname, options as never, callback as never);
    }) as typeof dns.lookup);

    const config = await viteConfig({
      command: 'serve',
      mode: 'test',
      isSsrBuild: false,
      isPreview: false,
    });
    vite = await createViteServer({
      ...config,
      configFile: false,
      logLevel: 'silent',
      server: {
        ...config.server,
        host: '127.0.0.1',
        port: 0,
        strictPort: false,
      },
    });
    await vite.listen();
    const address = vite.httpServer?.address() as AddressInfo;

    const response = await fetch(
      `http://127.0.0.1:${address.port}${FORWARDED_PREFIX}/?lang=zh-TW`,
      {
        headers: {
          cookie: 'aileron_workspace_gateway_session=test-session',
        },
      },
    );

    expect(response.status).toBe(200);
    expect(receivedPrefix).toBe(FORWARDED_PREFIX);
  });

  it('forwards the canonical Canvas prefix to the WebSocket upstream', async () => {
    vi.stubEnv('DOCKER_ENV', 'false');
    manager = http.createServer((_request, response) => {
      response.writeHead(204).end();
    });
    await listen(manager, 3001);

    let receivedPrefix: string | undefined;
    canvas = http.createServer();
    canvas.on('upgrade', (request, socket) => {
      receivedPrefix = request.headers['x-forwarded-prefix'] as string | undefined;
      socket.end(
        'HTTP/1.1 101 Switching Protocols\r\n'
        + 'Connection: Upgrade\r\n'
        + 'Upgrade: websocket\r\n\r\n',
      );
    });
    await listen(canvas, 3003);

    const originalLookup = dns.lookup.bind(dns);
    vi.spyOn(dns, 'lookup').mockImplementation(((hostname, options, callback) => {
      if (hostname === CANVAS_HOST) {
        const done = typeof options === 'function' ? options : callback;
        if (typeof options === 'object' && options?.all) {
          done?.(null, [{ address: '127.0.0.1', family: 4 }]);
        } else {
          done?.(null, '127.0.0.1', 4);
        }
        return;
      }
      return originalLookup(hostname, options as never, callback as never);
    }) as typeof dns.lookup);

    const config = await viteConfig({
      command: 'serve',
      mode: 'test',
      isSsrBuild: false,
      isPreview: false,
    });
    vite = await createViteServer({
      ...config,
      configFile: false,
      logLevel: 'silent',
      server: {
        ...config.server,
        host: '127.0.0.1',
        port: 0,
        strictPort: false,
      },
    });
    await vite.listen();
    const address = vite.httpServer?.address() as AddressInfo;

    await new Promise<void>((resolve, reject) => {
      const socket = net.connect(address.port, '127.0.0.1', () => {
        socket.write(
          `GET ${FORWARDED_PREFIX}/ws HTTP/1.1\r\n`
          + `Host: 127.0.0.1:${address.port}\r\n`
          + 'Connection: Upgrade\r\n'
          + 'Upgrade: websocket\r\n'
          + 'Sec-WebSocket-Key: dGVzdC1nYXRld2F5LWtleQ==\r\n'
          + 'Sec-WebSocket-Version: 13\r\n'
          + 'Cookie: aileron_workspace_gateway_session=test-session\r\n\r\n',
        );
      });
      socket.once('data', () => socket.end());
      socket.once('close', () => resolve());
      socket.once('error', reject);
    });

    expect(receivedPrefix).toBe(FORWARDED_PREFIX);
  });
});
