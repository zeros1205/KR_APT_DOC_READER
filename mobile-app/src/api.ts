import type { NoticeCard, PostsIndex } from "./types";
import { Capacitor, CapacitorHttp } from "@capacitor/core";

export const SITE_ORIGIN = "https://apt-note.com";
export const WORKER_ORIGIN =
  (import.meta.env.VITE_WORKER_ORIGIN as string | undefined) ||
  "https://apt-note-tg-bot.zeros1205.workers.dev";

export type DeviceRegistration = {
  token: string;
  platform: "android" | "ios" | "web";
  regions: string[];
  pushEnabled: boolean;
  appVersion?: string;
};

async function workerFetch(path: string, init: RequestInit): Promise<Response> {
  const url = `${WORKER_ORIGIN}${path}`;
  return fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) }
  });
}

export async function registerDevice(payload: DeviceRegistration): Promise<boolean> {
  try {
    const response = await workerFetch("/devices", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function unregisterDevice(token: string): Promise<boolean> {
  if (!token) return true;
  try {
    const response = await workerFetch(`/devices/${encodeURIComponent(token)}`, {
      method: "DELETE"
    });
    return response.ok;
  } catch {
    return false;
  }
}

export function absolutePostUrl(postUrl: string): string {
  return new URL(postUrl.replace(/^\/+/, ""), `${SITE_ORIGIN}/`).toString();
}

export function extractPriceRange(card: NoticeCard): string | undefined {
  if (!card.html) return undefined;
  const match = card.html.match(/>\s*([0-9,억만원 ~]+원)\s*</);
  return match?.[1]?.replace(/\s+/g, " ").trim();
}

export async function fetchLatestVersion(platform?: string): Promise<string | undefined> {
  try {
    const response = await fetch(`${SITE_ORIGIN}/app-version.json`, {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    if (!response.ok) return undefined;
    const data = (await response.json()) as { android?: string; ios?: string; latest?: string };
    if (platform === "ios" && data.ios) return data.ios;
    if (platform === "android" && data.android) return data.android;
    return data.latest;
  } catch {
    return undefined;
  }
}

export async function fetchPostsIndex(): Promise<PostsIndex> {
  if (Capacitor.isNativePlatform()) {
    try {
      const response = await fetch(`${SITE_ORIGIN}/posts_index.json`, {
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      if (response.ok) {
        return normalizePostsIndex((await response.json()) as PostsIndex);
      }
    } catch {
      // Network failed — fall back to bundled snapshot for offline support.
    }
    return normalizePostsIndex(await fetchBundledPostsIndex());
  }

  const response = await fetch(`${SITE_ORIGIN}/posts_index.json`, {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`posts_index.json ${response.status}`);
  }
  return normalizePostsIndex((await response.json()) as PostsIndex);
}

async function fetchBundledPostsIndex(): Promise<PostsIndex> {
  const response = await fetch("/posts_index.json", {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`bundled posts_index.json ${response.status}`);
  }
  return (await response.json()) as PostsIndex;
}

function normalizePostsIndex(data: PostsIndex): PostsIndex {
  return {
    ...data,
    cards: data.cards.map((card) => ({
      ...card,
      post_url: absolutePostUrl(card.post_url)
    }))
  };
}

export async function fetchPostHtml(url: string): Promise<string> {
  const noticeId = getNoticeIdFromPostUrl(url);

  if (Capacitor.isNativePlatform()) {
    // 1순위: 원격(Cloudflare Pages). 빌드 시점 스냅샷인 번들은 stale 위험이
    //         있어 항상 최신을 우선 시도. 실패하면 번들 fallback.
    try {
      const response = await CapacitorHttp.get({
        url,
        headers: { Accept: "text/html" }
      });
      if (response.status >= 200 && response.status < 300) {
        return typeof response.data === "string" ? response.data : String(response.data);
      }
    } catch {
      // 네트워크 실패 등 → 번들 fallback 으로 진행
    }

    // 2순위: 앱 번들된 정적 파일 (오프라인·네트워크 차단 대비)
    if (noticeId) {
      try {
        const response = await fetch(`/posts/${noticeId}/post.html`, {
          headers: { Accept: "text/html" },
          cache: "no-store"
        });
        if (response.ok) {
          return response.text();
        }
      } catch {
        // Fall through
      }
    }

    // 3순위: URL 형식 변형 재시도 (예: /post 확장자 누락 케이스)
    const fallbackUrl = url.replace(/\/post(?:\.html)?([?#].*)?$/, "/$1");
    if (fallbackUrl !== url) {
      const response = await CapacitorHttp.get({
        url: fallbackUrl,
        headers: { Accept: "text/html" }
      });
      if (response.status >= 200 && response.status < 300) {
        return typeof response.data === "string" ? response.data : String(response.data);
      }
    }
    throw new Error(`post html unavailable: ${url}`);
  }

  const response = await fetch(url, {
    headers: { Accept: "text/html" },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`post html ${response.status}`);
  }
  return response.text();
}

function getNoticeIdFromPostUrl(url: string): string | undefined {
  const pathname = new URL(url).pathname;
  return pathname.match(/^\/posts\/([^/]+)\//)?.[1];
}
