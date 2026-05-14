/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_VERSION?: string;
  readonly VITE_APP_STORE_URL?: string;
  readonly VITE_ADMOB_BANNER_ID_ANDROID?: string;
  readonly VITE_ADMOB_USE_TEST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
