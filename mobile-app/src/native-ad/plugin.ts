import { registerPlugin } from "@capacitor/core";

// ─────────────────────────────────────────────────────────────────────────
// NativeAd — AdMob 네이티브 고급형(Native Advanced) 광고를 카드 그리드 안에
// 인라인으로 표시하기 위한 커스텀 Capacitor 플러그인의 JS 인터페이스.
//
// @capacitor-community/admob 는 배너/전면/보상/앱오픈만 지원하고 네이티브 광고는
// 지원하지 않으므로(이슈 #110), 네이티브 광고는 이 전용 플러그인이 담당한다.
//
// 렌더링 모델:
//   - 웹(React)은 그리드 안에 "투명한 자리(placeholder)"만 차지하는 NativeAdSlot 을 둔다.
//   - 네이티브(Android/iOS)는 SDK 가 그린 NativeAdView 를 WebView 위에 오버레이로 띄우고,
//     placeholder 의 문서 좌표(docTop)와 크기를 받아 그 위치에 정확히 겹쳐 그린다.
//   - 스크롤 추적은 네이티브가 WebView 의 scrollY/contentOffset 를 직접 관찰해 처리하므로
//     JS↔네이티브 간 매 프레임 통신이 없다(성능·부드러움 확보).
//   - AdMob 정책 준수: 광고 에셋은 반드시 SDK 의 NativeAdView 로 렌더링되며, 클릭/노출
//     트래킹도 SDK 가 담당한다. (에셋만 JS 로 넘겨 HTML 로 그리는 방식은 정책 위반)
// ─────────────────────────────────────────────────────────────────────────

/** placeholder 의 위치·크기(모두 CSS px). docTop 은 문서 최상단 기준 절대 Y. */
export interface NativeAdGeometry {
  /** 슬롯 식별자 (한 화면에 여러 광고가 있을 수 있으므로 고유해야 함) */
  slotId: string;
  /** placeholder 좌측 X (뷰포트 기준 CSS px) */
  x: number;
  /** placeholder 의 문서 최상단 기준 절대 Y (getBoundingClientRect().top + scrollY) */
  docTop: number;
  /** placeholder 너비 (CSS px) */
  width: number;
  /** placeholder 높이 (CSS px) */
  height: number;
}

export interface NativeAdLoadOptions extends NativeAdGeometry {
  /** AdMob 네이티브 광고 단위 ID (ca-app-pub-…/…) */
  adId: string;
  /** 개인 맞춤 광고 비활성(non-personalized) 여부 */
  npa?: boolean;
  /** 테스트 광고 강제 여부 */
  isTesting?: boolean;
}

export type NativeAdEvent =
  | "adLoaded"
  | "adFailedToLoad"
  | "adImpression"
  | "adClicked";

export interface NativeAdEventData {
  slotId: string;
  /** adFailedToLoad 일 때만 채워짐 */
  error?: string;
}

export interface NativeAdPlugin {
  /** 현재 플랫폼에서 네이티브 광고를 지원하는지(iOS/Android 네이티브에서만 true) */
  isSupported(): Promise<{ supported: boolean }>;

  /** 광고를 로드하고 placeholder 위치에 오버레이를 띄운다. */
  loadSlot(options: NativeAdLoadOptions): Promise<{ loaded: boolean }>;

  /** placeholder 위치/크기가 바뀌었을 때(리사이즈·페이지 전환·탭 변경 등) 갱신. */
  updateGeometry(options: NativeAdGeometry): Promise<void>;

  /** 슬롯을 일시적으로 숨김(필터/페이지 전환으로 화면에서 사라질 때). */
  hideSlot(options: { slotId: string }): Promise<void>;

  /** 특정 슬롯의 광고와 오버레이를 완전히 제거. */
  removeSlot(options: { slotId: string }): Promise<void>;

  /** 모든 슬롯 제거(상세 화면 진입 등 그리드 전체가 사라질 때). */
  removeAll(): Promise<void>;

  addListener(
    eventName: NativeAdEvent,
    listenerFunc: (data: NativeAdEventData) => void
  ): Promise<{ remove: () => Promise<void> }>;
}

// 네이티브 미구현 플랫폼(웹 등)에서는 registerPlugin 이 메서드 호출 시 예외를 던지므로,
// NativeAdSlot 컴포넌트가 isSupported() 로 먼저 가드한다.
export const NativeAd = registerPlugin<NativeAdPlugin>("NativeAd");
