import { Storage } from '@capacitor/storage';

interface UserPreferences {
  regions: string[];
  quiet_hours: {
    start: string;
    end: string;
    enabled: boolean;
  };
  notifications: {
    enabled: boolean;
  };
}

interface AppearanceSettings {
  palette: 'A' | 'B' | 'C';
  dark_mode: 'light' | 'dark' | 'system';
}

interface Favorite {
  post_id: string;
  added_at: string;
}

class StorageService {
  private prefix = 'apt-note_';

  async getFavorites(): Promise<Favorite[]> {
    try {
      const data = await Storage.getItem(`${this.prefix}favorites`);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.error('Failed to get favorites:', error);
      return [];
    }
  }

  async addFavorite(postId: string): Promise<void> {
    try {
      const favorites = await this.getFavorites();
      if (!favorites.some(f => f.post_id === postId)) {
        favorites.push({
          post_id: postId,
          added_at: new Date().toISOString(),
        });
        await Storage.setItem(
          `${this.prefix}favorites`,
          JSON.stringify(favorites)
        );
      }
    } catch (error) {
      console.error('Failed to add favorite:', error);
    }
  }

  async removeFavorite(postId: string): Promise<void> {
    try {
      const favorites = await this.getFavorites();
      const updated = favorites.filter(f => f.post_id !== postId);
      await Storage.setItem(
        `${this.prefix}favorites`,
        JSON.stringify(updated)
      );
    } catch (error) {
      console.error('Failed to remove favorite:', error);
    }
  }

  async isFavorite(postId: string): Promise<boolean> {
    const favorites = await this.getFavorites();
    return favorites.some(f => f.post_id === postId);
  }

  async getUserPreferences(): Promise<UserPreferences> {
    try {
      const data = await Storage.getItem(`${this.prefix}preferences`);
      return data
        ? JSON.parse(data)
        : {
            regions: [],
            quiet_hours: {
              start: '22:00',
              end: '08:00',
              enabled: true,
            },
            notifications: {
              enabled: true,
            },
          };
    } catch (error) {
      console.error('Failed to get user preferences:', error);
      return {
        regions: [],
        quiet_hours: { start: '22:00', end: '08:00', enabled: true },
        notifications: { enabled: true },
      };
    }
  }

  async setUserPreferences(prefs: UserPreferences): Promise<void> {
    try {
      await Storage.setItem(
        `${this.prefix}preferences`,
        JSON.stringify(prefs)
      );
    } catch (error) {
      console.error('Failed to set user preferences:', error);
    }
  }

  async getAppearanceSettings(): Promise<AppearanceSettings> {
    try {
      const data = await Storage.getItem(`${this.prefix}appearance`);
      return data
        ? JSON.parse(data)
        : { palette: 'A', dark_mode: 'system' };
    } catch (error) {
      console.error('Failed to get appearance settings:', error);
      return { palette: 'A', dark_mode: 'system' };
    }
  }

  async setAppearanceSettings(settings: AppearanceSettings): Promise<void> {
    try {
      await Storage.setItem(
        `${this.prefix}appearance`,
        JSON.stringify(settings)
      );
    } catch (error) {
      console.error('Failed to set appearance settings:', error);
    }
  }

  async getLastOnboardingDate(): Promise<string | null> {
    try {
      return await Storage.getItem(`${this.prefix}onboarding-date`);
    } catch (error) {
      console.error('Failed to get onboarding date:', error);
      return null;
    }
  }

  async setLastOnboardingDate(date: string): Promise<void> {
    try {
      await Storage.setItem(`${this.prefix}onboarding-date`, date);
    } catch (error) {
      console.error('Failed to set onboarding date:', error);
    }
  }

  async getDeviceId(): Promise<string | null> {
    try {
      return await Storage.getItem(`${this.prefix}device-id`);
    } catch (error) {
      console.error('Failed to get device ID:', error);
      return null;
    }
  }

  async setDeviceId(deviceId: string): Promise<void> {
    try {
      await Storage.setItem(`${this.prefix}device-id`, deviceId);
    } catch (error) {
      console.error('Failed to set device ID:', error);
    }
  }

  async getPrivacyAgreedAt(): Promise<string | null> {
    try {
      return await Storage.getItem(`${this.prefix}privacy-agreed-at`);
    } catch (error) {
      console.error('Failed to get privacy agreement date:', error);
      return null;
    }
  }

  async setPrivacyAgreed(agreedAt: string): Promise<void> {
    try {
      await Storage.setItem(`${this.prefix}privacy-agreed-at`, agreedAt);
      await Storage.setItem(`${this.prefix}privacy-version`, '1.0');
    } catch (error) {
      console.error('Failed to set privacy agreement:', error);
    }
  }

  async isPrivacyAgreed(): Promise<boolean> {
    const agreedAt = await this.getPrivacyAgreedAt();
    return agreedAt !== null;
  }

  async clear(): Promise<void> {
    try {
      await Storage.clear();
    } catch (error) {
      console.error('Failed to clear storage:', error);
    }
  }
}

export const storageService = new StorageService();
export type { UserPreferences, AppearanceSettings, Favorite };
