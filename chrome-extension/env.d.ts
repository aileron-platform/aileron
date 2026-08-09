/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RELAY_HOST?: string;
  readonly VITE_RELAY_PORT?: string;
  readonly VITE_RELAY_BASE_PATH?: string;
  readonly WXT_TRUSTED_FRONTEND_ORIGINS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
