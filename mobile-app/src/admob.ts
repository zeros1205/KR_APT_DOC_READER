import { Capacitor } from "@capacitor/core";

const GOOGLE_TEST_BANNER_ANDROID = "ca-app-pub-3940256099942544/6300978111";
const GOOGLE_TEST_BANNER_IOS = "ca-app-pub-3940256099942544/2934735716";
// Google 공개 테스트 — Medium Rectangle (300x250)
const GOOGLE_TEST_MREC_ANDROID = "ca-app-pub-3940256099942544/6300978111";
const GOOGLE_TEST_MREC_IOS = "ca-app-pub-3940256099942544/2934735716";
// Google 공개 테스트 — Interstitial
const GOOGLE_TEST_INTERSTITIAL_ANDROID = "ca-app-pub-3940256099942544/1033173712";
const GOOGLE_TEST_INTERSTITIAL_IOS = "ca-app-pub-3940256099942544/4411468910";
// Google 공개 테스트 — App Open
const GOOGLE_TEST_APP_OPEN_ANDROID = "ca-app-pub-3940256099942544/9257395921";
const GOOGLE_TEST_APP_OPEN_IOS = "ca-app-pub-3940256099942544/5575463023";

// 프로덕션 광고 단위 ID. 환경변수 미설정 시 폴백으로 사용.
// 변경 필요 시 AdMob 콘솔에서 발급받은 ID 로 교체.
const PRODUCTION_BANNER_IOS = "ca-app-pub-8234120897033274/2306903637";
const PRODUCTION_BANNER_ANDROID = "";
const PRODUCTION_MREC_IOS = "ca-app-pub-8234120897033274/1061800806";
const PRODUCTION_MREC_ANDROID = "";
const PRODUCTION_INTERSTITIAL_IOS = "ca-app-pub-8234120897033274/3304820769";
const PRODUCTION_INTERSTITIAL_ANDROID = "";
const PRODUCTION_APP_OPEN_IOS = "ca-app-pub-8234120897033274/6142737093";
const PRODUCTION_APP_OPEN_ANDROID = "";

const USE_TEST_ADS =
  String(import.meta.env.VITE_ADMOB_USE_TEST || "").toLowerCase() === "true" || !import.meta.env.PROD;

type AdMobModule = typeof import("@capacitor-community/admob");

let adMobModulePromise: Promise<AdMobModule | null> | null = null;
let initialized = false;
let bannerVisible = false;
let mrecVisible = false;
let nonPersonalizedOnly = false;
let interstitialReady = false;
let interstitialLoading = false;
let appOpenReady = false;
let appOpenLoading = false;

function isSupportedPlatform(): boolean {
  if (!Capacitor.isNativePlatform()) return false;
  const platform = Capacitor.getPlatform();
  return platform === "ios" || platform === "android";
}

function loadAdMob(): Promise<AdMobModule | null> {
  if (!isSupportedPlatform()) return Promise.resolve(null);
  if (!adMobModulePromise) {
    adMobModulePromise = import("@capacitor-community/admob").catch((error) => {
      console.warn("[admob] plugin import failed", error);
      return null;
    });
  }
  return adMobModulePromise;
}

function resolveBannerAdId(): string {
  const isIos = Capacitor.getPlatform() === "ios";
  if (USE_TEST_ADS) {
    return isIos ? GOOGLE_TEST_BANNER_IOS : GOOGLE_TEST_BANNER_ANDROID;
  }
  const configured = isIos
    ? import.meta.env.VITE_ADMOB_BANNER_ID_IOS
    : import.meta.env.VITE_ADMOB_BANNER_ID_ANDROID;
  if (configured && String(configured).startsWith("ca-app-pub-")) return String(configured);
  const production = isIos ? PRODUCTION_BANNER_IOS : PRODUCTION_BANNER_ANDROID;
  if (production && production.startsWith("ca-app-pub-")) return production;
  return isIos ? GOOGLE_TEST_BANNER_IOS : GOOGLE_TEST_BANNER_ANDROID;
}

function resolveMrecAdId(): string {
  const isIos = Capacitor.getPlatform() === "ios";
  if (USE_TEST_ADS) {
    return isIos ? GOOGLE_TEST_MREC_IOS : GOOGLE_TEST_MREC_ANDROID;
  }
  const configured = isIos
    ? import.meta.env.VITE_ADMOB_MREC_ID_IOS
    : import.meta.env.VITE_ADMOB_MREC_ID_ANDROID;
  if (configured && String(configured).startsWith("ca-app-pub-")) return String(configured);
  const production = isIos ? PRODUCTION_MREC_IOS : PRODUCTION_MREC_ANDROID;
  if (production && production.startsWith("ca-app-pub-")) return production;
  return isIos ? GOOGLE_TEST_MREC_IOS : GOOGLE_TEST_MREC_ANDROID;
}

function resolveInterstitialAdId(): string {
  const isIos = Capacitor.getPlatform() === "ios";
  if (USE_TEST_ADS) {
    return isIos ? GOOGLE_TEST_INTERSTITIAL_IOS : GOOGLE_TEST_INTERSTITIAL_ANDROID;
  }
  const configured = isIos
    ? import.meta.env.VITE_ADMOB_INTERSTITIAL_ID_IOS
    : import.meta.env.VITE_ADMOB_INTERSTITIAL_ID_ANDROID;
  if (configured && String(configured).startsWith("ca-app-pub-")) return String(configured);
  const production = isIos ? PRODUCTION_INTERSTITIAL_IOS : PRODUCTION_INTERSTITIAL_ANDROID;
  if (production && production.startsWith("ca-app-pub-")) return production;
  return isIos ? GOOGLE_TEST_INTERSTITIAL_IOS : GOOGLE_TEST_INTERSTITIAL_ANDROID;
}

function resolveAppOpenAdId(): string {
  const isIos = Capacitor.getPlatform() === "ios";
  if (USE_TEST_ADS) {
    return isIos ? GOOGLE_TEST_APP_OPEN_IOS : GOOGLE_TEST_APP_OPEN_ANDROID;
  }
  const configured = isIos
    ? import.meta.env.VITE_ADMOB_APP_OPEN_ID_IOS
    : import.meta.env.VITE_ADMOB_APP_OPEN_ID_ANDROID;
  if (configured && String(configured).startsWith("ca-app-pub-")) return String(configured);
  const production = isIos ? PRODUCTION_APP_OPEN_IOS : PRODUCTION_APP_OPEN_ANDROID;
  if (production && production.startsWith("ca-app-pub-")) return production;
  return isIos ? GOOGLE_TEST_APP_OPEN_IOS : GOOGLE_TEST_APP_OPEN_ANDROID;
}

export async function initializeAdMob(): Promise<void> {
  if (initialized) return;
  const mod = await loadAdMob();
  if (!mod) return;
  try {
    await mod.AdMob.initialize({
      testingDevices: [],
      initializeForTesting: USE_TEST_ADS
    });
    initialized = true;
  } catch (error) {
    console.warn("[admob] initialize failed", error);
  }
}

export async function requestTrackingConsent(): Promise<void> {
  if (Capacitor.getPlatform() !== "ios") return;
  const mod = await loadAdMob();
  if (!mod) return;
  try {
    const status = await mod.AdMob.trackingAuthorizationStatus();
    if (status.status === "notDetermined") {
      const result = await mod.AdMob.requestTrackingAuthorization();
      nonPersonalizedOnly = result.status !== "authorized";
    } else {
      nonPersonalizedOnly = status.status !== "authorized";
    }
  } catch (error) {
    console.warn("[admob] tracking consent failed", error);
    nonPersonalizedOnly = true;
  }
}

export async function showBanner(): Promise<void> {
  if (bannerVisible) return;
  const mod = await loadAdMob();
  if (!mod) return;
  if (!initialized) {
    await initializeAdMob();
    if (!initialized) return;
  }
  try {
    await mod.AdMob.showBanner({
      adId: resolveBannerAdId(),
      adSize: mod.BannerAdSize.ADAPTIVE_BANNER,
      position: mod.BannerAdPosition.BOTTOM_CENTER,
      margin: 0,
      isTesting: USE_TEST_ADS,
      npa: nonPersonalizedOnly
    });
    bannerVisible = true;
  } catch (error) {
    console.warn("[admob] showBanner failed", error);
  }
}

export async function hideBanner(): Promise<void> {
  if (!bannerVisible) return;
  const mod = await loadAdMob();
  if (!mod) return;
  try {
    await mod.AdMob.hideBanner();
    bannerVisible = false;
  } catch (error) {
    console.warn("[admob] hideBanner failed", error);
  }
}

export async function removeBanner(): Promise<void> {
  const mod = await loadAdMob();
  if (!mod) return;
  try {
    await mod.AdMob.removeBanner();
    bannerVisible = false;
  } catch (error) {
    console.warn("[admob] removeBanner failed", error);
  }
}

// 종료 다이얼로그용 Medium Rectangle (300x250). 일반 배너와 별도 광고 단위.
// SDK 는 한 번에 banner 한 개만 다루므로, 기존 banner view 를 먼저 정리하고 새로 등록한다.
export async function showMediumRectangle(): Promise<void> {
  if (mrecVisible) return;
  const mod = await loadAdMob();
  if (!mod) return;
  if (!initialized) {
    await initializeAdMob();
    if (!initialized) return;
  }
  try {
    await mod.AdMob.removeBanner().catch(() => undefined);
    bannerVisible = false;
    await mod.AdMob.showBanner({
      adId: resolveMrecAdId(),
      adSize: mod.BannerAdSize.MEDIUM_RECTANGLE,
      position: mod.BannerAdPosition.CENTER,
      margin: 0,
      isTesting: USE_TEST_ADS,
      npa: nonPersonalizedOnly
    });
    mrecVisible = true;
  } catch (error) {
    console.warn("[admob] showMediumRectangle failed", error);
  }
}

export async function hideMediumRectangle(): Promise<void> {
  if (!mrecVisible) return;
  const mod = await loadAdMob();
  if (!mod) return;
  try {
    await mod.AdMob.removeBanner();
    mrecVisible = false;
    bannerVisible = false;
  } catch (error) {
    console.warn("[admob] hideMediumRectangle failed", error);
  }
}

// Interstitial — 상세 페이지 10회 진입 + 직전 표시로부터 30분 이상 경과한 경우에만 노출.
// 빈도 제어 자체는 호출자가 담당하고, 본 모듈은 prepare/show 만 처리.
export async function prepareInterstitial(): Promise<void> {
  if (interstitialReady || interstitialLoading) return;
  const mod = await loadAdMob();
  if (!mod) return;
  if (!initialized) {
    await initializeAdMob();
    if (!initialized) return;
  }
  interstitialLoading = true;
  try {
    await mod.AdMob.prepareInterstitial({
      adId: resolveInterstitialAdId(),
      isTesting: USE_TEST_ADS,
      npa: nonPersonalizedOnly
    });
    interstitialReady = true;
  } catch (error) {
    console.warn("[admob] prepareInterstitial failed", error);
  } finally {
    interstitialLoading = false;
  }
}

export async function showInterstitial(): Promise<boolean> {
  if (!interstitialReady) {
    void prepareInterstitial();
    return false;
  }
  const mod = await loadAdMob();
  if (!mod) return false;
  try {
    await mod.AdMob.showInterstitial();
    interstitialReady = false;
    // 다음 호출을 위해 미리 로드.
    void prepareInterstitial();
    return true;
  } catch (error) {
    console.warn("[admob] showInterstitial failed", error);
    interstitialReady = false;
    return false;
  }
}

// App Open Ad — 콜드 스타트 직후 + foreground 복귀 시 (4시간 룰).
export async function prepareAppOpen(): Promise<void> {
  if (appOpenReady || appOpenLoading) return;
  const mod = await loadAdMob();
  if (!mod) return;
  if (!initialized) {
    await initializeAdMob();
    if (!initialized) return;
  }
  appOpenLoading = true;
  try {
    // @capacitor-community/admob v7 의 prepareAppOpen API. 미지원 SDK 버전 대비 optional chain.
    const adMob = mod.AdMob as unknown as {
      prepareAppOpen?: (options: { adId: string; isTesting?: boolean; npa?: boolean }) => Promise<void>;
    };
    if (typeof adMob.prepareAppOpen !== "function") {
      console.warn("[admob] prepareAppOpen not supported by current plugin version");
      return;
    }
    await adMob.prepareAppOpen({
      adId: resolveAppOpenAdId(),
      isTesting: USE_TEST_ADS,
      npa: nonPersonalizedOnly
    });
    appOpenReady = true;
  } catch (error) {
    console.warn("[admob] prepareAppOpen failed", error);
  } finally {
    appOpenLoading = false;
  }
}

export async function showAppOpen(): Promise<boolean> {
  if (!appOpenReady) {
    void prepareAppOpen();
    return false;
  }
  const mod = await loadAdMob();
  if (!mod) return false;
  try {
    const adMob = mod.AdMob as unknown as { showAppOpen?: () => Promise<void> };
    if (typeof adMob.showAppOpen !== "function") {
      console.warn("[admob] showAppOpen not supported by current plugin version");
      appOpenReady = false;
      return false;
    }
    await adMob.showAppOpen();
    appOpenReady = false;
    // 다음 호출을 위해 미리 로드.
    void prepareAppOpen();
    return true;
  } catch (error) {
    console.warn("[admob] showAppOpen failed", error);
    appOpenReady = false;
    return false;
  }
}

export function isAdMobSupported(): boolean {
  return isSupportedPlatform();
}
