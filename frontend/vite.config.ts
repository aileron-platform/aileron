import { defineConfig } from "vite";
import type { Plugin, ProxyOptions } from 'vite';
import react from "@vitejs/plugin-react-swc";
import path from "path";

import { getReactRuntimeChunk } from './config/dependencyChunk';
import {
  createWorkspaceGatewayAuthorizationGate,
  removeWorkspaceGatewayCredentials,
  resolveWorkspaceGatewayRequest,
  WORKSPACE_GATEWAY_PROXY_PATTERN,
} from './config/workspaceGateway';

const normalizeModuleId = (id: string) => id.split(path.sep).join('/');

const getNodeModuleChunk = (id: string): string | undefined => {
  const normalizedId = normalizeModuleId(id);
  const match = normalizedId.match(/\/node_modules\/((?:@[^/]+\/[^/]+)|[^/]+)/);

  if (!match) {
    return undefined;
  }

  return `vendor-${match[1].replace('@', 'at-').replace('/', '-')}`;
};

const dependencyChunk = (id: string): string | undefined => {
  const normalizedId = normalizeModuleId(id);
  if (!normalizedId.includes('/node_modules/')) {
    return undefined;
  }

  const reactRuntimeChunk = getReactRuntimeChunk(id);
  if (reactRuntimeChunk) {
    return reactRuntimeChunk;
  }
  if (normalizedId.includes('/node_modules/@monaco-editor/') || normalizedId.includes('/node_modules/monaco-editor/')) {
    return 'vendor-monaco';
  }
  if (normalizedId.includes('/node_modules/@xterm/')) {
    return 'vendor-terminal';
  }

  return getNodeModuleChunk(normalizedId);
};

const optionalPreloadPattern = /^assets\/vendor-(mermaid|monaco|syntax-highlighter|terminal)-/;

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Use the service name inside Docker; use localhost for local development.
  const backendTarget = process.env.DOCKER_ENV === 'true'
    ? 'http://workspace-manager:3001'
    : 'http://localhost:3001';
  type WorkspaceGatewayProxy = Parameters<NonNullable<ProxyOptions['configure']>>[0];
  let workspaceGatewayProxy: WorkspaceGatewayProxy | null = null;
  const workspaceGatewayAuthorization = createWorkspaceGatewayAuthorizationGate({
    managerTarget: backendTarget,
  });
  const workspaceGatewayAuthorizationPlugin: Plugin = {
    name: 'workspace-gateway-authorization',
    configureServer: (server) => {
      server.middlewares.use((request, response, next) => {
        const resolved = resolveWorkspaceGatewayRequest(request.url);
        if (!resolved) {
          next();
          return;
        }
        void workspaceGatewayAuthorization.handleHttp(request, response, () => {
          if (!workspaceGatewayProxy) {
            response.statusCode = 503;
            response.end();
            return;
          }
          removeWorkspaceGatewayCredentials(request);
          request.headers['x-forwarded-prefix'] = resolved.forwardedPrefix;
          request.url = resolved.rewrittenPath;
          workspaceGatewayProxy.web(request, response, { target: resolved.target });
        });
      });
      server.httpServer?.on('upgrade', (request, socket, head) => {
        const resolved = resolveWorkspaceGatewayRequest(request.url);
        if (!resolved) return;

        void workspaceGatewayAuthorization.handleUpgrade(request, socket, () => {
          if (!workspaceGatewayProxy) {
            throw new Error('Workspace gateway proxy is unavailable');
          }
          removeWorkspaceGatewayCredentials(request);
          request.headers['x-forwarded-prefix'] = resolved.forwardedPrefix;
          request.url = resolved.rewrittenPath;
          workspaceGatewayProxy.ws(request, socket, head, { target: resolved.target });
        });
      });
    },
  };

  return {
    server: {
      host: "0.0.0.0",
      port: 8082,
      strictPort: true,
      hmr: {
        overlay: true,
      },
      proxy: {
        '/api/v1': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          xfwd: true,
        },
        [WORKSPACE_GATEWAY_PROXY_PATTERN]: {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          ws: false,
          xfwd: true,
          configure: (proxy) => {
            workspaceGatewayProxy = proxy;
          },
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        },
        '/docs': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        },
        '/openapi.json': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        },
        '/redoc': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        }
      }
    },
    plugins: [
      workspaceGatewayAuthorizationPlugin,
      react(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@/app': path.resolve(__dirname, './src/app'),
        '@/features': path.resolve(__dirname, './src/features'),
        '@/shared': path.resolve(__dirname, './src/shared'),
        '@/hubs': path.resolve(__dirname, './src/hubs'),
        '@/pages': path.resolve(__dirname, './src/pages'),
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode === 'development',
      modulePreload: {
        polyfill: false,
        resolveDependencies: (_filename, deps) => deps.filter((dep) => !optionalPreloadPattern.test(dep)),
      },
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        output: {
          manualChunks: dependencyChunk,
        }
      }
    },
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-router-dom']
    }
  };
});
