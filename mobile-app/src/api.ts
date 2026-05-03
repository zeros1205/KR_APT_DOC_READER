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

export async function fetchPostsIndex(): Promise<PostsIndex> {
  const response = await fetch(`${SITE_ORIGIN}/posts_index.json`, {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`posts_index.json ${response.status}`);
  }
  const data = (await response.json()) as PostsIndex;
  return {
    ...data,
    cards: data.cards.map((card) => ({
      ...card,
      post_url: absolutePostUrl(card.post_url)
    }))
  };
}

export async function fetchPostHtml(url: string): Promise<string> {
  if (Capacitor.isNativePlatform()) {
    const response = await CapacitorHttp.get({
      url,
      headers: { Accept: "text/html" }
    });
    if (response.status < 200 || response.status >= 300) {
      throw new Error(`post html ${response.status}`);
    }
    return typeof response.data === "string" ? response.data : String(response.data);
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
