import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 在 Docker 容器內使用服務名稱，否則使用 localhost
  const backendTarget = process.env.DOCKER_ENV === 'true'
    ? 'http://workspace-manager:3001'
    : 'http://localhost:3001';

  return {
    server: {
      host: "0.0.0.0",
      port: 8082,
      strictPort: true,
      // 強制清除快取
      hmr: {
        overlay: true,
      },
      // 代理所有 API 請求到後端服務
      proxy: {
        // API 路由代理
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          ws: true
        },
        // 健康檢查
        '/health': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        },
        // 文檔相關
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
    // 構建配置
    build: {
      outDir: 'dist',
      sourcemap: mode === 'development',
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            ui: ['@headlessui/react']
          }
        }
      }
    },
    // 優化依賴
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-router-dom']
    }
  };
});