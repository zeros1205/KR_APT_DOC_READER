import type { Env } from "./env";

export type DevicePlatform = "android" | "ios" | "web";

export interface DeviceRecord {
  token: string;
  platform: DevicePlatform;
  regions: string[];
  pushEnabled: boolean;
  appVersion?: string;
  updatedAt: string;
}

const DEVICE_PREFIX = "device:";
const REGION_PREFIX = "region:";
const SENT_PREFIX = "sent:";

export function deviceKey(token: string): string {
  return `${DEVICE_PREFIX}${token}`;
}

export function regionMemberKey(region: string, token: string): string {
  return `${REGION_PREFIX}${region}:${token}`;
}

export function sentKey(yyyymmdd: string, noticeId: string, token: string): string {
  return `${SENT_PREFIX}${yyyymmdd}:${noticeId}:${token}`;
}

export async function putDevice(env: Env, record: DeviceRecord): Promise<void> {
  await env.DEVICES_KV.put(deviceKey(record.token), JSON.stringify(record));
}

export async function getDevice(env: Env, token: string): Promise<DeviceRecord | null> {
  const raw = await env.DEVICES_KV.get(deviceKey(token));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as DeviceRecord;
  } catch {
    return null;
  }
}

export async function deleteDevice(env: Env, token: string): Promise<void> {
  const existing = await getDevice(env, token);
  if (existing) {
    await Promise.all(
      existing.regions.map((region) =>
        env.DEVICES_KV.delete(regionMemberKey(region, token)),
      ),
    );
  }
  await env.DEVICES_KV.delete(deviceKey(token));
}

export async function syncRegionMembership(
  env: Env,
  token: string,
  previous: string[],
  next: string[],
): Promise<void> {
  const prev = new Set(previous);
  const cur = new Set(next);
  const toRemove = previous.filter((r) => !cur.has(r));
  const toAdd = next.filter((r) => !prev.has(r));
  await Promise.all([
    ...toRemove.map((region) => env.DEVICES_KV.delete(regionMemberKey(region, token))),
    ...toAdd.map((region) =>
      env.DEVICES_KV.put(regionMemberKey(region, token), "1"),
    ),
  ]);
}

export async function listAllDevices(env: Env): Promise<DeviceRecord[]> {
  const records: DeviceRecord[] = [];
  let cursor: string | undefined;
  do {
    const result = await env.DEVICES_KV.list({ prefix: DEVICE_PREFIX, cursor });
    cursor = result.list_complete ? undefined : result.cursor;
    for (const key of result.keys) {
      const raw = await env.DEVICES_KV.get(key.name);
      if (!raw) continue;
      try {
        records.push(JSON.parse(raw) as DeviceRecord);
      } catch {
        // skip malformed entries
      }
    }
  } while (cursor);
  return records;
}

export async function hasSent(
  env: Env,
  yyyymmdd: string,
  noticeId: string,
  token: string,
): Promise<boolean> {
  const value = await env.DEVICES_KV.get(sentKey(yyyymmdd, noticeId, token));
  return value !== null;
}

export async function markSent(
  env: Env,
  yyyymmdd: string,
  noticeId: string,
  token: string,
): Promise<void> {
  await env.DEVICES_KV.put(sentKey(yyyymmdd, noticeId, token), "1", {
    expirationTtl: 60 * 60 * 48,
  });
}

const PDF_PENDING_PREFIX = "pdfpending:";

export interface PendingPdfSelection {
  fileId: string;
  fileName: string;
}

export function pdfPendingKey(token: string): string {
  return `${PDF_PENDING_PREFIX}${token}`;
}

// 텔레그램으로 받은 PDF 가 공고번호로 바로 확정되지 않을 때, 사용자가 인라인
// 버튼으로 공고를 고를 때까지 file_id 를 임시 보관한다. callback_data 는
// 64바이트 제한이 있어 file_id 를 직접 담지 못하므로 짧은 토큰으로 대신 참조.
export async function putPendingPdf(
  env: Env,
  token: string,
  value: PendingPdfSelection,
): Promise<void> {
  await env.DEVICES_KV.put(pdfPendingKey(token), JSON.stringify(value), {
    expirationTtl: 60 * 60,
  });
}

export async function getPendingPdf(
  env: Env,
  token: string,
): Promise<PendingPdfSelection | null> {
  const raw = await env.DEVICES_KV.get(pdfPendingKey(token));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingPdfSelection;
  } catch {
    return null;
  }
}

export async function deletePendingPdf(env: Env, token: string): Promise<void> {
  await env.DEVICES_KV.delete(pdfPendingKey(token));
}

export function ymdKST(date: Date = new Date()): string {
  const kstMs = date.getTime() + 9 * 60 * 60 * 1000;
  const kst = new Date(kstMs);
  const y = kst.getUTCFullYear();
  const m = String(kst.getUTCMonth() + 1).padStart(2, "0");
  const d = String(kst.getUTCDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}
