import { Capacitor } from "@capacitor/core";

const GOOGLE_TEST_BANNER_ANDROID = "ca-app-pub-3940256099942544/6300978111";
const GOOGLE_TEST_BANNER_IOS = "ca-app-pub-3940256099942544/2934735716";
// Google 공개 테스트 — Interstitial
const GOOGLE_TEST_INTERSTITIAL_ANDROID = "ca-app-pub-3940256099942544/1033173712";
const GOOGLE_TEST_INTERSTITIAL_IOS = "ca-app-pub-3940256099942544/4411468910";
// Google 공개 테스트 — Native Advanced (네이티브 고급형)
const GOOGLE_TEST_NATIVE_ANDROID = "ca-app-pub-3940256099942544/2247696110";
const GOOGLE_TEST_NATIVE_IOS = "ca-app-pub-3940256099942544/3986624511";

// 프로덕션 광고 단위 ID. 환경변수 미설정 시 폴백으로 사용.
// 변경 필요 시 AdMob 콘솔에서 발급받은 ID 로 교체.
const PRODUCTION_BANNER_IOS = "ca-app-pub-8234120897033274/2306903637";
const PRODUCTION_BANNER_ANDROID = "ca-app-pub-8234120897033274/1613349625";
const PRODUCTION_INTERSTITIAL_IOS = "ca-app-pub-8234120897033274/3304820769";
const PRODUCTION_INTERSTITIAL_ANDROID = "ca-app-pub-8234120897033274/9024935783";
// 네이티브 고급형(Native Advanced) — 메인 카드 그리드 인피드 광고용.
// 플랫폼별 분리 발급. .env(VITE_ADMOB_NATIVE_ID_*) 설정 시 그것으로 덮어쓰기.
const PRODUCTION_NATIVE_IOS = "ca-app-pub-8234120897033274/1061800806";
const PRODUCTION_NATIVE_ANDROID = "ca-app-pub-8234120897033274/6818939220";

const USE_TEST_ADS =
  String(import.meta.env.VITE_ADMOB_USE_TEST || "").toLowerCase() === "true" || !import.meta.env.PROD;

type AdMobModule = typeof import("@capacitor-community/admob");

let adMobModulePromise: Promise<AdMobModule | null> | null = null;
let initialized = false;
type ActiveBanner = "none" | "adaptive" | "large-bottom" | "mrec-bottom";
let activeBanner: ActiveBanner = "none";
let nonPersonalizedOnly = false;
let interstitialReady = false;
let interstitialLoading = false;

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
    const initial = await mod.AdMob.trackingAuthorizationStatus();
    if (initial.status === "notDetermined") {
      // v7: requestTrackingAuthorization 은 void 반환. 권한 결과는 다시 status 조회로 확인.
      await mod.AdMob.requestTrackingAuthorization();
      const after = await mod.AdMob.trackingAuthorizationStatus();
      nonPersonalizedOnly = after.status !== "authorized";
    } else {
      nonPersonalizedOnly = initial.status !== "authorized";
    }
  } catch (error) {
    console.warn("[admob] tracking consent failed", error);
    nonPersonalizedOnly = true;
  }
}

// SDK 는 한 번에 banner view 한 개만 다루므로, 모든 banner/MREC 전환을 한 함수에서 처리.
// mode 별 광고 단위 / 사이즈 / 위치:
//   "adaptive"      : 일반 하단 sticky banner   — 배너 단위 ID, ADAPTIVE_BANNER (~60px), BOTTOM_CENTER
//   "large-bottom"  : 설정 메인 페이지 하단      — 배너 단위 ID, ADAPTIVE_BANNER (풀폭), BOTTOM_CENTER
//       (구) LARGE_BANNER(320x100 고정) 은 plugin 이 (화면폭-광고폭)/2 좌우 여백으로
//       중앙 정렬하는데, targetSdk 35 edge-to-edge 에서 이 여백 계산이 어긋나 배너가
//       한쪽으로 쏠리는 회귀가 있었다. 풀폭 ADAPTIVE 는 여백 계산이 필요 없어 항상 균형.
//   "mrec-bottom"   : 즐겨찾기 빈 화면 하단      — 배너 단위 ID, MEDIUM_RECTANGLE (300x250), BOTTOM_CENTER
// (종료 다이얼로그용 "mrec-center" 는 NativeAd 카드로 대체되어 제거됨)
export async function setBannerMode(target: ActiveBanner): Promise<void> {
  if (activeBanner === target) return;
  const mod = await loadAdMob();
  if (!mod) return;
  if (!initialized) {
    await initializeAdMob();
    if (!initialized) return;
  }
  try {
    if (activeBanner !== "none") {
      await mod.AdMob.removeBanner().catch(() => undefined);
      activeBanner = "none";
    }
    if (target === "none") return;
    // 모든 모드가 배너 단위 ID 를 쓰며, mrec-bottom 만 MEDIUM_RECTANGLE 사이즈로 키운다.
    // 위치는 전부 하단 중앙(BOTTOM_CENTER).
    const adId = resolveBannerAdId();
    const adSize =
      target === "mrec-bottom" ? mod.BannerAdSize.MEDIUM_RECTANGLE : mod.BannerAdSize.ADAPTIVE_BANNER;
    const position = mod.BannerAdPosition.BOTTOM_CENTER;
    await mod.AdMob.showBanner({
      adId,
      adSize,
      position,
      margin: 0,
      isTesting: USE_TEST_ADS,
      npa: nonPersonalizedOnly
    });
    activeBanner = target;
  } catch (error) {
    console.warn("[admob] setBannerMode failed", target, error);
  }
}

// 하위 호환 헬퍼들. App.tsx 의 토글 useEffect 는 setBannerMode 를 직접 사용 권장.
export function showBanner(): Promise<void> {
  return setBannerMode("adaptive");
}
export function hideBanner(): Promise<void> {
  return activeBanner === "adaptive" ? setBannerMode("none") : Promise.resolve();
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

function resolveNativeAdId(): string {
  const isIos = Capacitor.getPlatform() === "ios";
  if (USE_TEST_ADS) {
    return isIos ? GOOGLE_TEST_NATIVE_IOS : GOOGLE_TEST_NATIVE_ANDROID;
  }
  const configured = isIos
    ? import.meta.env.VITE_ADMOB_NATIVE_ID_IOS
    : import.meta.env.VITE_ADMOB_NATIVE_ID_ANDROID;
  if (configured && String(configured).startsWith("ca-app-pub-")) return String(configured);
  const production = isIos ? PRODUCTION_NATIVE_IOS : PRODUCTION_NATIVE_ANDROID;
  if (production && production.startsWith("ca-app-pub-")) return production;
  return isIos ? GOOGLE_TEST_NATIVE_IOS : GOOGLE_TEST_NATIVE_ANDROID;
}

// 카드 그리드 인피드 네이티브 광고가 사용할 설정. NativeAdSlot 컴포넌트가 호출.
// 광고 단위 ID 와 개인맞춤(npa) 여부를 한 번에 제공한다.
export function getNativeAdConfig(): { adId: string; npa: boolean; isTesting: boolean } {
  return { adId: resolveNativeAdId(), npa: nonPersonalizedOnly, isTesting: USE_TEST_ADS };
}

export function isAdMobSupported(): boolean {
  return isSupportedPlatform();
}
