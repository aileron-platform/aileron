import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const normalizeModuleId = (id: string) => id.split(path.sep).join('/');

const dependencyChunk = (id: string): string | undefined => {
  const normalizedId = normalizeModuleId(id);
  if (!normalizedId.includes('/node_modules/')) {
    return undefined;
  }

  if (/[\\/]node_modules[\\/](react|react-dom|react-router-dom|scheduler)[\\/]/.test(id)) {
    return 'vendor-react';
  }
  if (normalizedId.includes('/node_modules/@radix-ui/') || normalizedId.includes('/node_modules/@headlessui/')) {
    return 'vendor-ui';
  }
  if (normalizedId.includes('/node_modules/@monaco-editor/') || normalizedId.includes('/node_modules/monaco-editor/')) {
    return 'vendor-monaco';
  }
  if (normalizedId.includes('/node_modules/@xterm/')) {
    return 'vendor-terminal';
  }

  return undefined;
};

const optionalPreloadPattern = /^assets\/vendor-(mermaid|monaco|syntax-highlighter|terminal)-/;

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Use the service name inside Docker; use localhost for local development.
  const backendTarget = process.env.DOCKER_ENV === 'true'
    ? 'http://workspace-manager:3001'
    : 'http://localhost:3001';

  return {
    server: {
      host: "0.0.0.0",
      port: 8082,
      strictPort: true,
      hmr: {
        overlay: true,
      },
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          ws: true
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
