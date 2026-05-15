import type { Env } from "../env";
import {
  DeviceRecord,
  deleteDevice,
  getDevice,
  putDevice,
  syncRegionMembership,
} from "../kv";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

export function handleOptions(): Response {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

interface RegisterBody {
  token?: unknown;
  platform?: unknown;
  regions?: unknown;
  pushEnabled?: unknown;
  appVersion?: unknown;
}

function sanitizeRegions(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return Array.from(
    new Set(
      value.filter((r): r is string => typeof r === "string" && r.length > 0 && r.length <= 32),
    ),
  );
}

export async function registerDevice(request: Request, env: Env): Promise<Response> {
  let body: RegisterBody;
  try {
    body = (await request.json()) as RegisterBody;
  } catch {
    return jsonResponse({ error: "invalid_json" }, 400);
  }

  const token = typeof body.token === "string" ? body.token.trim() : "";
  if (!token || token.length > 4096) {
    return jsonResponse({ error: "invalid_token" }, 400);
  }
  const platform =
    body.platform === "android" || body.platform === "ios" || body.platform === "web"
      ? body.platform
      : null;
  if (!platform) {
    return jsonResponse({ error: "invalid_platform" }, 400);
  }
  const regions = sanitizeRegions(body.regions);
  const pushEnabled = body.pushEnabled !== false;
  const appVersion =
    typeof body.appVersion === "string" && body.appVersion.length <= 32
      ? body.appVersion
      : undefined;

  const existing = await getDevice(env, token);
  const record: DeviceRecord = {
    token,
    platform,
    regions,
    pushEnabled,
    appVersion,
    updatedAt: new Date().toISOString(),
  };
  await putDevice(env, record);
  await syncRegionMembership(env, token, existing?.regions ?? [], regions);

  return jsonResponse({ ok: true });
}

export async function unregisterDevice(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const token = decodeURIComponent(url.pathname.replace(/^\/devices\//, ""));
  if (!token) {
    return jsonResponse({ error: "missing_token" }, 400);
  }
  await deleteDevice(env, token);
  return jsonResponse({ ok: true });
}
