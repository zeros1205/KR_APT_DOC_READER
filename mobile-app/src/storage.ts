import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import type { FavoriteNotice, UserSettings } from "./types";

const FAVORITES_KEY = "apt-note:favorites";
const SETTINGS_KEY = "apt-note:settings";

export const defaultSettings: UserSettings = {
  regions: [],
  pushEnabled: false,
  quietHoursEnabled: true
};

async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = Capacitor.isNativePlatform()
      ? (await Preferences.get({ key })).value
      : localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

async function writeJson<T>(key: string, value: T): Promise<void> {
  const serialized = JSON.stringify(value);
  if (Capacitor.isNativePlatform()) {
    await Preferences.set({ key, value: serialized });
    return;
  }
  localStorage.setItem(key, serialized);
}

export function loadFavorites(): Promise<FavoriteNotice[]> {
  return readJson<FavoriteNotice[]>(FAVORITES_KEY, []);
}

export function saveFavorites(favorites: FavoriteNotice[]): Promise<void> {
  return writeJson(FAVORITES_KEY, favorites);
}

export function loadSettings(): Promise<UserSettings> {
  return readJson<UserSettings>(SETTINGS_KEY, defaultSettings);
}

export function saveSettings(settings: UserSettings): Promise<void> {
  return writeJson(SETTINGS_KEY, {
    ...settings,
    updatedAt: new Date().toISOString()
  });
}

export async function resetLocalData(): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    await Preferences.remove({ key: FAVORITES_KEY });
    await Preferences.remove({ key: SETTINGS_KEY });
    return;
  }
  localStorage.removeItem(FAVORITES_KEY);
  localStorage.removeItem(SETTINGS_KEY);
}
