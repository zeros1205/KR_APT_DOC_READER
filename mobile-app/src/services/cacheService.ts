import { Storage } from '@capacitor/storage';
import { PostDetail, PostMeta } from './apiService';

interface CacheEntry<T> {
  data: T;
  cached_at: string;
  expires_at?: string;
}

class CacheService {
  private prefix = 'cache_';
  private ttlMs = 24 * 60 * 60 * 1000;

  async getCachedPost(postId: string): Promise<PostDetail | null> {
    return this.get<PostDetail>(`post_${postId}`);
  }

  async setCachedPost(postId: string, post: PostDetail): Promise<void> {
    await this.set(`post_${postId}`, post);
  }

  async getCachedPostsList(): Promise<PostMeta[] | null> {
    return this.get<PostMeta[]>('posts_list');
  }

  async setCachedPostsList(posts: PostMeta[]): Promise<void> {
    await this.set('posts_list', posts);
  }

  async getManifest(): Promise<any | null> {
    return this.get('manifest');
  }

  async setManifest(data: any): Promise<void> {
    await this.set('manifest', data);
  }

  private async get<T>(key: string): Promise<T | null> {
    try {
      const data = await Storage.getItem(`${this.prefix}${key}`);
      if (!data) return null;

      const entry: CacheEntry<T> = JSON.parse(data);

      if (entry.expires_at && new Date(entry.expires_at) < new Date()) {
        await Storage.removeItem(`${this.prefix}${key}`);
        return null;
      }

      return entry.data;
    } catch (error) {
      console.error(`Failed to get cached item ${key}:`, error);
      return null;
    }
  }

  private async set<T>(key: string, data: T): Promise<void> {
    try {
      const entry: CacheEntry<T> = {
        data,
        cached_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + this.ttlMs).toISOString(),
      };
      await Storage.setItem(
        `${this.prefix}${key}`,
        JSON.stringify(entry)
      );
    } catch (error) {
      console.error(`Failed to cache item ${key}:`, error);
    }
  }

  async getCacheSize(): Promise<number> {
    try {
      const data = await Storage.keys();
      const keys = data.keys.filter(k => k.startsWith(this.prefix));
      let size = 0;
      for (const key of keys) {
        const item = await Storage.getItem(key);
        if (item) {
          size += new Blob([item]).size;
        }
      }
      return size;
    } catch (error) {
      console.error('Failed to get cache size:', error);
      return 0;
    }
  }

  async clearCache(): Promise<void> {
    try {
      const data = await Storage.keys();
      const keys = data.keys.filter(k => k.startsWith(this.prefix));
      for (const key of keys) {
        await Storage.removeItem(key);
      }
    } catch (error) {
      console.error('Failed to clear cache:', error);
    }
  }
}

export const cacheService = new CacheService();
