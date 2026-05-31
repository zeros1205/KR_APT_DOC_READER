import { Capacitor, registerPlugin } from "@capacitor/core";

// 커스텀 네이티브 광고 플러그인 (Android 네이티브 NativeAdView 렌더).
// JS 가 박스의 화면 좌표/크기를 측정해 넘기면, 네이티브가 그 위치에 광고를 그린다.
export interface NativeAdShowOptions {
  adUnitId: string;
  testing: boolean;
  /** 물리 px (CSS px * devicePixelRatio) */
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface NativeAdPlugin {
  show(options: NativeAdShowOptions): Promise<void>;
  hide(): Promise<void>;
}

const NativeAdImpl = registerPlugin<NativeAdPlugin>("NativeAd");

// 종료 다이얼로그 네이티브 광고 단위 (Android). 프로덕션에서만 사용, 개발은 테스트 광고.
const EXIT_NATIVE_AD_ANDROID = "ca-app-pub-8234120897033274/2806856268";

const USE_TEST_ADS =
  String(import.meta.env.VITE_ADMOB_USE_TEST || "").toLowerCase() === "true" || !import.meta.env.PROD;

export function isNativeAdSupported(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";
}

/** DOM 요소(광고 슬롯)의 위치/크기를 측정해 그 자리에 네이티브 광고를 띄운다. */
export async function showNativeAdInElement(el: HTMLElement): Promise<void> {
  if (!isNativeAdSupported()) return;
  const rect = el.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  try {
    await NativeAdImpl.show({
      adUnitId: EXIT_NATIVE_AD_ANDROID,
      testing: USE_TEST_ADS,
      x: Math.round(rect.left * dpr),
      y: Math.round(rect.top * dpr),
      width: Math.round(rect.width * dpr),
      height: Math.round(rect.height * dpr)
    });
  } catch (error) {
    console.warn("[native-ad] show failed", error);
  }
}

export async function hideNativeAd(): Promise<void> {
  if (!isNativeAdSupported()) return;
  try {
    await NativeAdImpl.hide();
  } catch (error) {
    console.warn("[native-ad] hide failed", error);
  }
}
