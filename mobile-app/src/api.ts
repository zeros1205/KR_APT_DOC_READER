import type { NoticeCard, PostsIndex } from "./types";
import { Capacitor, CapacitorHttp } from "@capacitor/core";

export const SITE_ORIGIN = "https://apt-note.com";

export function absolutePostUrl(postUrl: string): string {
  return new URL(postUrl.replace(/^\/+/, ""), `${SITE_ORIGIN}/`).toString();
}

export function extractPriceRange(card: NoticeCard): string | undefined {
  if (!card.html) return undefined;
  const match = card.html.match(/>\s*([0-9,억만원 ~]+원)\s*</);
  return match?.[1]?.replace(/\s+/g, " ").trim();
}

export async function fetchLatestVersion(): Promise<string | undefined> {
  try {
    const response = await fetch(`${SITE_ORIGIN}/app-version.json`, {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    if (!response.ok) return undefined;
    const data = (await response.json()) as { latest?: string };
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
        // Fall through to the live request for older APKs or missing bundled posts.
      }
    }

    try {
      const response = await CapacitorHttp.get({
        url,
        headers: { Accept: "text/html" }
      });
      if (response.status < 200 || response.status >= 300) {
        throw new Error(`post html ${response.status}`);
      }
      return typeof response.data === "string" ? response.data : String(response.data);
    } catch (error) {
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
      throw error;
    }
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
