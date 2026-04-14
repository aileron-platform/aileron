/**
 * CDP Proxy - HTTP/WebSocket proxy with debug logging
 */

const http = require('http');
const { StringDecoder } = require('string_decoder');
const url = require('url');

const CDP_PORT = parseInt(process.env.CDP_PORT || '9222', 10);
const PROXY_PORT = 9223;

console.log(`CDP Proxy starting: ${PROXY_PORT} -> ${CDP_PORT}`);

const server = http.createServer((clientReq, clientRes) => {
  console.log(`[HTTP] ${clientReq.method} ${clientReq.url} from ${clientReq.socket.remoteAddress}`);

  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: CDP_PORT,
    path: clientReq.url,
    method: clientReq.method,
    headers: {
      ...clientReq.headers,
      host: 'localhost',
    },
  }, (proxyRes) => {
    let body = '';
    const decoder = new StringDecoder('utf8');

    proxyRes.on('data', (chunk) => {
      body += decoder.write(chunk);
    });

    proxyRes.on('end', () => {
      decoder.end();

      // Rewrite WebSocket URL in JSON responses
      let modifiedBody = body;
      try {
        const data = JSON.parse(body);

        // Helper function to rewrite WebSocket URL in an object
        const rewriteWebSocketUrl = (obj) => {
          if (obj && obj.webSocketDebuggerUrl) {
            const originalUrl = obj.webSocketDebuggerUrl;
            // Extract path from ws://localhost/devtools/xxx
            const urlMatch = originalUrl.match(/ws:\/\/localhost\/(.+)/);
            if (urlMatch) {
              const wsPath = urlMatch[1];
              const host = clientReq.headers.host || `workspace-chrome:${PROXY_PORT}`;
              obj.webSocketDebuggerUrl = `ws://${host}/${wsPath}`;
              console.log(`[HTTP] Rewrote WebSocket URL: ${originalUrl} -> ${obj.webSocketDebuggerUrl}`);
              return true;
            }
          }
          return false;
        };

        // Handle both arrays (from /json) and single objects (from /json/version)
        if (Array.isArray(data)) {
          data.forEach(rewriteWebSocketUrl);
          modifiedBody = JSON.stringify(data);
        } else {
          rewriteWebSocketUrl(data);
          modifiedBody = JSON.stringify(data);
        }
      } catch (e) {
        // Not JSON, keep as-is
      }

      // Copy headers, update content-length
      const headers = { ...proxyRes.headers };
      headers['content-length'] = Buffer.byteLength(modifiedBody);
      clientRes.writeHead(proxyRes.statusCode, headers);
      clientRes.end(modifiedBody);
    });
  });

  proxyReq.on('error', (err) => {
    console.error(`[HTTP] Proxy error:`, err.message);
    if (!clientRes.headersSent) {
      clientRes.writeHead(502);
      clientRes.end('Bad Gateway');
    }
  });

  clientReq.pipe(proxyReq);
});

// Handle WebSocket upgrades - forward directly
server.on('upgrade', (clientReq, clientSocket, head) => {
  const parsedUrl = url.parse(`http://${clientReq.headers.host}${clientReq.url}`);
  console.log(`[WS] Upgrade request for: ${parsedUrl.path}`);
  console.log(`[WS] Headers:`, JSON.stringify(clientReq.headers, null, 2));

  const proxySocket = require('net').createConnection(CDP_PORT, '127.0.0.1');

  proxySocket.on('connect', () => {
    console.log(`[WS] Connected to Chrome CDP`);

    // 保持原始的 Host header
    const rawRequest =
      `GET ${parsedUrl.path} HTTP/1.1\r\n` +
      `Host: localhost\r\n` +
      `Connection: Upgrade\r\n` +
      `Upgrade: websocket\r\n` +
      Object.entries(clientReq.headers)
        .filter(([k]) => !['connection', 'upgrade', 'host'].includes(k.toLowerCase()))
        .map(([k, v]) => `${k}: ${v}`)
        .join('\r\n') +
      '\r\n\r\n';

    console.log(`[WS] Forwarding request to Chrome`);
    proxySocket.write(rawRequest);

    if (head && head.length > 0) {
      proxySocket.write(head);
    }

    console.log(`[WS] Setting up bidirectional pipe`);

    // Pipe both ways
    proxySocket.pipe(clientSocket);
    clientSocket.pipe(proxySocket);

    // Handle close events
    proxySocket.on('close', () => {
      console.log(`[WS] Proxy socket closed`);
      clientSocket.end();
    });

    clientSocket.on('close', () => {
      console.log(`[WS] Client socket closed`);
      proxySocket.end();
    });

    proxySocket.on('error', (err) => {
      console.error(`[WS] Proxy socket error:`, err.message);
      clientSocket.end();
    });

    clientSocket.on('error', (err) => {
      console.error(`[WS] Client socket error:`, err.message);
      proxySocket.end();
    });
  });

  proxySocket.on('error', (err) => {
    console.error(`[WS] Connect error:`, err.message);
    clientSocket.end();
  });
});

server.on('error', (err) => {
  console.error('[SERVER] Error:', err);
});

server.listen(PROXY_PORT, '0.0.0.0', () => {
  console.log(`CDP Proxy listening on port ${PROXY_PORT}`);
});

process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
});
