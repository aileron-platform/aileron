/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RELAY_HOST?: string;
  readonly VITE_RELAY_PORT?: string;
  readonly VITE_RELAY_BASE_PATH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
