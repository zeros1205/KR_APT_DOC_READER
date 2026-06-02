import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { registerDevice, unregisterDevice } from "./api";
import type { FavoriteNotice, UserSettings } from "./types";

const FAVORITES_KEY = "apt-note:favorites";
const SETTINGS_KEY = "apt-note:settings";

export const defaultSettings: UserSettings = {
  regions: [],
  pushEnabled: false,
  quietHoursEnabled: true,
  // 진단 데이터(크래시 리포트) 수집 기본값. 설정에서 옵트아웃 가능.
  crashReportingEnabled: true
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

function currentPlatform(): "android" | "ios" | "web" {
  const p = Capacitor.getPlatform();
  if (p === "android") return "android";
  if (p === "ios") return "ios";
  return "web";
}

let syncTimer: number | null = null;
let lastSyncedKey = "";

export async function syncDeviceWithBackend(
  settings: UserSettings,
  options: { appVersion?: string; immediate?: boolean } = {}
): Promise<void> {
  if (syncTimer !== null) {
    window.clearTimeout(syncTimer);
    syncTimer = null;
  }
  const run = () => doSyncDevice(settings, options.appVersion);
  if (options.immediate) {
    await run();
    return;
  }
  syncTimer = window.setTimeout(() => {
    void run();
  }, 600);
}

async function doSyncDevice(settings: UserSettings, appVersion?: string): Promise<void> {
  const token = settings.pushToken;

  // OFF + 토큰 보유 시 unregister
  if (!settings.pushEnabled) {
    if (token) {
      const ok = await unregisterDevice(token);
      if (ok) {
        await saveSettings({
          ...settings,
          pushToken: undefined,
          pushSyncedAt: new Date().toISOString(),
          pushPendingSync: false
        });
      } else {
        await saveSettings({ ...settings, pushPendingSync: true });
      }
    }
    return;
  }

  if (!token) return;

  const key = `${token}|${settings.regions.slice().sort().join(",")}`;
  if (key === lastSyncedKey) return;
  const ok = await registerDevice({
    token,
    platform: currentPlatform(),
    regions: settings.regions,
    pushEnabled: true,
    appVersion
  });
  if (ok) {
    lastSyncedKey = key;
    await saveSettings({
      ...settings,
      pushSyncedAt: new Date().toISOString(),
      pushPendingSync: false
    });
  } else {
    await saveSettings({ ...settings, pushPendingSync: true });
  }
}
