import type { Env } from "./env";

const FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging";
const FCM_TOKEN_KEY = "oauth:fcm_token";

interface ServiceAccount {
  client_email: string;
  private_key: string;
  token_uri?: string;
}

interface CachedToken {
  access_token: string;
  exp: number;
}

export interface FcmMessage {
  token: string;
  notification: { title: string; body: string };
  data: Record<string, string>;
  android?: {
    priority?: "HIGH" | "NORMAL";
    notification?: { sound?: string; click_action?: string };
  };
  apns?: {
    headers?: Record<string, string>;
    payload?: {
      aps?: {
        sound?: string;
        "mutable-content"?: number;
      };
    };
  };
}

export type FcmSendResult =
  | { ok: true }
  | { ok: false; status: number; code: string; message: string };

function base64UrlEncode(input: ArrayBuffer | Uint8Array | string): string {
  let bytes: Uint8Array;
  if (typeof input === "string") {
    bytes = new TextEncoder().encode(input);
  } else if (input instanceof Uint8Array) {
    bytes = input;
  } else {
    bytes = new Uint8Array(input);
  }
  let str = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    str += String.fromCharCode(bytes[i]);
  }
  return btoa(str).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function pemToArrayBuffer(pem: string): ArrayBuffer {
  const trimmed = pem
    .replace(/-----BEGIN PRIVATE KEY-----/g, "")
    .replace(/-----END PRIVATE KEY-----/g, "")
    .replace(/\s+/g, "");
  const binary = atob(trimmed);
  const buffer = new ArrayBuffer(binary.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) {
    view[i] = binary.charCodeAt(i);
  }
  return buffer;
}

async function signJwt(serviceAccount: ServiceAccount): Promise<string> {
  const header = { alg: "RS256", typ: "JWT" };
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: serviceAccount.client_email,
    scope: FCM_SCOPE,
    aud: serviceAccount.token_uri || "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  };
  const headerB64 = base64UrlEncode(JSON.stringify(header));
  const payloadB64 = base64UrlEncode(JSON.stringify(payload));
  const unsigned = `${headerB64}.${payloadB64}`;

  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToArrayBuffer(serviceAccount.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(unsigned),
  );
  return `${unsigned}.${base64UrlEncode(signature)}`;
}

async function fetchAccessToken(env: Env): Promise<string> {
  const cached = await env.DEVICES_KV.get(FCM_TOKEN_KEY);
  if (cached) {
    try {
      const parsed = JSON.parse(cached) as CachedToken;
      if (parsed.exp - 60 > Math.floor(Date.now() / 1000)) {
        return parsed.access_token;
      }
    } catch {
      // fall through
    }
  }

  const serviceAccount = JSON.parse(env.FCM_SERVICE_ACCOUNT_JSON) as ServiceAccount;
  const jwt = await signJwt(serviceAccount);
  const tokenUri = serviceAccount.token_uri || "https://oauth2.googleapis.com/token";

  const response = await fetch(tokenUri, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=${encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer")}&assertion=${jwt}`,
  });
  if (!response.ok) {
    throw new Error(`oauth_token_failed: ${response.status} ${await response.text()}`);
  }
  const tokenJson = (await response.json()) as { access_token: string; expires_in: number };
  const exp = Math.floor(Date.now() / 1000) + tokenJson.expires_in;
  await env.DEVICES_KV.put(
    FCM_TOKEN_KEY,
    JSON.stringify({ access_token: tokenJson.access_token, exp }),
    { expirationTtl: Math.max(60, tokenJson.expires_in - 60) },
  );
  return tokenJson.access_token;
}

export async function sendFcm(env: Env, message: FcmMessage): Promise<FcmSendResult> {
  const accessToken = await fetchAccessToken(env);
  const url = `https://fcm.googleapis.com/v1/projects/${env.FCM_PROJECT_ID}/messages:send`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });
  if (response.ok) return { ok: true };
  let code = "UNKNOWN";
  let bodyText = "";
  try {
    bodyText = await response.text();
    const parsed = JSON.parse(bodyText) as {
      error?: { status?: string; message?: string; details?: Array<{ errorCode?: string }> };
    };
    code =
      parsed.error?.details?.[0]?.errorCode ||
      parsed.error?.status ||
      String(response.status);
  } catch {
    code = String(response.status);
  }
  return { ok: false, status: response.status, code, message: bodyText.slice(0, 500) };
}
