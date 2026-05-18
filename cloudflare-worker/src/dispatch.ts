import type { Env } from "./env";
import {
  DeviceRecord,
  deleteDevice,
  hasSent,
  listAllDevices,
  markSent,
  ymdKST,
} from "./kv";
import { FcmMessage, sendFcm } from "./fcm";

export interface PushPost {
  notice_id: string;
  region: string;
  apt_name: string;
  total_households: number;
  post_url: string;
  generated_at: string;
}

export type PushType = 1 | 2 | 3 | 4;

export interface DispatchInput {
  window: "morning" | "afternoon";
  posts: PushPost[];
  dry_run?: boolean;
  override_date?: string;
}

export interface DispatchPlanEntry {
  token: string;
  platform: string;
  type: PushType;
  notice_ids: string[];
  lead_notice_id: string;
  title: string;
  body: string;
  target_url: string;
}

export interface DispatchSummary {
  date: string;
  window: "morning" | "afternoon";
  total_devices: number;
  total_sent: number;
  total_skipped_zero_match: number;
  total_skipped_disabled: number;
  total_failed: number;
  invalid_tokens_removed: number;
  plans?: DispatchPlanEntry[];
}

function sortPosts(posts: PushPost[]): PushPost[] {
  return [...posts].sort((a, b) => {
    const h = (b.total_households || 0) - (a.total_households || 0);
    if (h !== 0) return h;
    return (b.generated_at || "").localeCompare(a.generated_at || "");
  });
}

function regionAlias(region: string): string {
  const shortNames: Record<string, string> = {
    강원도: "강원",
    충청북도: "충북",
    충청남도: "충남",
    전라북도: "전북",
    전라남도: "전남",
    경상북도: "경북",
    경상남도: "경남",
    제주도: "제주",
  };
  return shortNames[region] || region;
}

const PUSH_TITLE = "정과장의 청약노트 도착";

function buildMessageContent(
  type: PushType,
  lead: PushPost,
  extra: number,
): { title: string; body: string; target_url: string } {
  const aptName = lead.apt_name;
  const tail = extra > 0 ? ` 외 ${extra}건` : "";
  if (type === 1) {
    return {
      title: PUSH_TITLE,
      body: `신규 아파트 청약 공고를 확인해보세요.\n${aptName}`,
      target_url: lead.post_url,
    };
  }
  if (type === 2) {
    return {
      title: PUSH_TITLE,
      body: `신규 아파트 청약 공고를 확인해보세요.\n${aptName}${tail}`,
      target_url: "/?tab=preferred",
    };
  }
  if (type === 3) {
    return {
      title: PUSH_TITLE,
      body: `오늘 등록된 신규 아파트 청약 공고를 확인해보세요.\n${aptName}`,
      target_url: lead.post_url,
    };
  }
  return {
    title: PUSH_TITLE,
    body: `오늘 등록된 신규 아파트 청약 공고를 확인해보세요.\n${aptName}${tail}`,
    target_url: "/",
  };
}

function classifyType(device: DeviceRecord, freshCount: number): PushType {
  if (device.regions.length > 0) {
    return freshCount >= 2 ? 2 : 1;
  }
  return freshCount >= 2 ? 4 : 3;
}

function buildFcmMessage(
  device: DeviceRecord,
  type: PushType,
  lead: PushPost,
  extra: number,
): FcmMessage {
  const { title, body, target_url } = buildMessageContent(type, lead, extra);
  return {
    token: device.token,
    notification: { title, body },
    data: {
      type: String(type),
      notice_id: lead.notice_id,
      region: lead.region,
      target_url,
    },
    android: {
      priority: "HIGH",
      notification: { sound: "default" },
    },
    apns: {
      payload: { aps: { sound: "default" } },
    },
  };
}

async function filterUnsentPosts(
  env: Env,
  posts: PushPost[],
  yyyymmdd: string,
  token: string,
): Promise<PushPost[]> {
  const checks = await Promise.all(
    posts.map(async (post) => ({
      post,
      sent: await hasSent(env, yyyymmdd, post.notice_id, token),
    })),
  );
  return checks.filter((entry) => !entry.sent).map((entry) => entry.post);
}

export async function dispatchPush(
  env: Env,
  input: DispatchInput,
): Promise<DispatchSummary> {
  const date = input.override_date || ymdKST();
  const devices = await listAllDevices(env);
  const summary: DispatchSummary = {
    date,
    window: input.window,
    total_devices: devices.length,
    total_sent: 0,
    total_skipped_zero_match: 0,
    total_skipped_disabled: 0,
    total_failed: 0,
    invalid_tokens_removed: 0,
    plans: input.dry_run ? [] : undefined,
  };

  for (const device of devices) {
    if (!device.pushEnabled) {
      summary.total_skipped_disabled++;
      continue;
    }
    const matched = device.regions.length > 0
      ? input.posts.filter((post) => device.regions.includes(post.region))
      : input.posts;
    const fresh = await filterUnsentPosts(env, matched, date, device.token);
    if (fresh.length === 0) {
      summary.total_skipped_zero_match++;
      continue;
    }
    const sorted = sortPosts(fresh);
    const lead = sorted[0];
    const extra = sorted.length - 1;
    const type = classifyType(device, sorted.length);
    const message = buildFcmMessage(device, type, lead, extra);

    if (input.dry_run) {
      summary.plans!.push({
        token: device.token.slice(0, 12) + "...",
        platform: device.platform,
        type,
        notice_ids: sorted.map((p) => p.notice_id),
        lead_notice_id: lead.notice_id,
        title: message.notification.title,
        body: message.notification.body,
        target_url: message.data.target_url,
      });
      summary.total_sent++;
      continue;
    }

    const result = await sendFcm(env, message);
    if (result.ok) {
      summary.total_sent++;
      await Promise.all(
        sorted.map((post) => markSent(env, date, post.notice_id, device.token)),
      );
    } else {
      summary.total_failed++;
      if (
        result.code === "UNREGISTERED" ||
        result.code === "INVALID_ARGUMENT" ||
        result.status === 404 ||
        result.status === 400
      ) {
        await deleteDevice(env, device.token);
        summary.invalid_tokens_removed++;
      }
    }
  }

  return summary;
}

export { buildMessageContent, classifyType, sortPosts };
