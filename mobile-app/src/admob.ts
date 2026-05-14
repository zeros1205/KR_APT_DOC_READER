import { Capacitor } from "@capacitor/core";
import {
  AdMob,
  BannerAdPosition,
  BannerAdSize
} from "@capacitor-community/admob";

// Google 공개 테스트 광고 단위 ID (Android).
// 실광고 ID 는 .env 로만 주입; 테스트 빌드에 실ID 가 섞이지 않도록 코드엔 하드코딩 금지.
// https://developers.google.com/admob/android/test-ads
const TEST_BANNER_ID_ANDROID = "ca-app-pub-3940256099942544/6300978111";

type BannerEnvironment = {
  enabled: boolean;
  isTesting: boolean;
  bannerAdId: string;
};

function resolveEnvironment(): BannerEnvironment | null {
  if (!Capacitor.isNativePlatform()) return null;
  if (Capacitor.getPlatform() !== "android") return null;

  const realBannerId = import.meta.env.VITE_ADMOB_BANNER_ID_ANDROID?.trim();
  const useTestEnv = import.meta.env.VITE_ADMOB_USE_TEST === "true";
  const isTesting = useTestEnv || !realBannerId;

  return {
    enabled: true,
    isTesting,
    bannerAdId: isTesting ? TEST_BANNER_ID_ANDROID : realBannerId!
  };
}

let initialized = false;
let initializePromise: Promise<void> | null = null;
let bannerVisible = false;

export async function initializeAdMob(): Promise<void> {
  const env = resolveEnvironment();
  if (!env) return;
  if (initialized) return;
  if (initializePromise) return initializePromise;

  initializePromise = AdMob.initialize({
    initializeForTesting: env.isTesting,
    testingDevices: []
  })
    .then(() => {
      initialized = true;
    })
    .catch((error) => {
      initializePromise = null;
      console.warn("[AdMob] initialize failed", error);
    });

  return initializePromise;
}

export async function showBottomBanner(): Promise<void> {
  const env = resolveEnvironment();
  if (!env) return;
  if (!initialized) await initializeAdMob();
  if (!initialized) return;
  if (bannerVisible) return;

  try {
    await AdMob.showBanner({
      adId: env.bannerAdId,
      adSize: BannerAdSize.ADAPTIVE_BANNER,
      position: BannerAdPosition.BOTTOM_CENTER,
      isTesting: env.isTesting,
      margin: 0
    });
    bannerVisible = true;
  } catch (error) {
    console.warn("[AdMob] showBanner failed", error);
  }
}

export async function hideBottomBanner(): Promise<void> {
  const env = resolveEnvironment();
  if (!env) return;
  if (!bannerVisible) return;

  try {
    await AdMob.hideBanner();
    bannerVisible = false;
  } catch (error) {
    console.warn("[AdMob] hideBanner failed", error);
  }
}

export async function removeBottomBanner(): Promise<void> {
  const env = resolveEnvironment();
  if (!env) return;

  try {
    await AdMob.removeBanner();
  } catch (error) {
    console.warn("[AdMob] removeBanner failed", error);
  } finally {
    bannerVisible = false;
  }
}
