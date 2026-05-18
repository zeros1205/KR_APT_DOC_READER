export interface Env {
  TELEGRAM_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  GITHUB_PAT: string;
  GITHUB_REPO: string;

  // Push notification additions
  DEVICES_KV: KVNamespace;
  DISPATCH_TOKEN: string;
  FCM_PROJECT_ID: string;
  FCM_SERVICE_ACCOUNT_JSON: string;
}
