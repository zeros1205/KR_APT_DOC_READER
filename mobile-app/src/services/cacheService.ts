import { Storage } from '@capacitor/storage';
import { PostDetail, PostMeta } from './apiService';

interface CacheEntry<T> {
  data: T;
  cached_at: string;
  expires_at?: string;
  version: number;
}

interface CacheStats {
  totalSize: number;
  itemCount: number;
  oldestEntry?: { key: string; cachedAt: string };
  newestEntry?: { key: string; cachedAt: string };
  expiredCount: number;
}

class CacheService {
  private prefix = 'cache_';
  private ttlMs = 24 * 60 * 60 * 1000;
  private currentVersion = 1;
  private maxCacheItems = 100;
  private isOfflineMode = false;

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

      if (entry.version !== this.currentVersion) {
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
      await this.enforceMaxCacheSize();

      const entry: CacheEntry<T> = {
        data,
        cached_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + this.ttlMs).toISOString(),
        version: this.currentVersion,
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

  async getCacheStats(): Promise<CacheStats> {
    try {
      const data = await Storage.keys();
      const cacheKeys = data.keys.filter(k => k.startsWith(this.prefix));
      let totalSize = 0;
      let oldestEntry: { key: string; cachedAt: string } | undefined;
      let newestEntry: { key: string; cachedAt: string } | undefined;
      let expiredCount = 0;

      for (const key of cacheKeys) {
        const item = await Storage.getItem(key);
        if (item) {
          totalSize += new Blob([item]).size;

          const entry: CacheEntry<any> = JSON.parse(item);
          const cachedAt = entry.cached_at;

          if (entry.expires_at && new Date(entry.expires_at) < new Date()) {
            expiredCount++;
          } else {
            if (!oldestEntry || new Date(cachedAt) < new Date(oldestEntry.cachedAt)) {
              oldestEntry = { key, cachedAt };
            }
            if (!newestEntry || new Date(cachedAt) > new Date(newestEntry.cachedAt)) {
              newestEntry = { key, cachedAt };
            }
          }
        }
      }

      return {
        totalSize,
        itemCount: cacheKeys.length,
        oldestEntry,
        newestEntry,
        expiredCount,
      };
    } catch (error) {
      console.error('Failed to get cache stats:', error);
      return { totalSize: 0, itemCount: 0, expiredCount: 0 };
    }
  }

  async clearExpiredCache(): Promise<void> {
    try {
      const data = await Storage.keys();
      const keys = data.keys.filter(k => k.startsWith(this.prefix));
      for (const key of keys) {
        const item = await Storage.getItem(key);
        if (item) {
          const entry: CacheEntry<any> = JSON.parse(item);
          if (entry.expires_at && new Date(entry.expires_at) < new Date()) {
            await Storage.removeItem(key);
          }
        }
      }
      console.log('Expired cache entries cleared');
    } catch (error) {
      console.error('Failed to clear expired cache:', error);
    }
  }

  async invalidateCache(): Promise<void> {
    this.currentVersion++;
    console.log(`Cache invalidated, new version: ${this.currentVersion}`);
  }

  private async enforceMaxCacheSize(): Promise<void> {
    try {
      const data = await Storage.keys();
      const cacheKeys = data.keys.filter(k => k.startsWith(this.prefix));

      if (cacheKeys.length >= this.maxCacheItems) {
        const entries: Array<{ key: string; cachedAt: string }> = [];

        for (const key of cacheKeys) {
          const item = await Storage.getItem(key);
          if (item) {
            const entry: CacheEntry<any> = JSON.parse(item);
            entries.push({ key, cachedAt: entry.cached_at });
          }
        }

        entries.sort((a, b) => new Date(a.cachedAt).getTime() - new Date(b.cachedAt).getTime());

        const toRemove = entries.slice(0, Math.ceil(entries.length * 0.1));
        for (const entry of toRemove) {
          await Storage.removeItem(entry.key);
        }
        console.log(`Removed ${toRemove.length} oldest cache entries to enforce quota`);
      }
    } catch (error) {
      console.error('Failed to enforce cache quota:', error);
    }
  }

  getOfflineMode(): boolean {
    return this.isOfflineMode;
  }

  setOfflineMode(enabled: boolean): void {
    this.isOfflineMode = enabled;
    console.log(`Offline mode ${enabled ? 'enabled' : 'disabled'}`);
  }
}

export const cacheService = new CacheService();
