import { useEffect, useLayoutEffect, useRef } from "react";
import { getNativeAdConfig } from "../admob";
import { NativeAd } from "./plugin";

// 그리드 안에 끼워 넣는 네이티브 광고 자리(placeholder).
//
// - 이 컴포넌트 자체는 "투명한 빈 카드"로서 그리드에서 한 칸의 공간만 차지한다.
// - 실제 광고는 네이티브 SDK 가 그린 NativeAdView 가 이 자리 위에 오버레이로 겹쳐 그려진다.
// - 따라서 placeholder 의 화면상 위치/크기를 측정해 네이티브로 전달하는 것이 핵심 역할.
//
// 스크롤 추적은 네이티브가 WebView 스크롤을 직접 관찰하므로 여기서 scroll 이벤트를
// 듣지 않는다. 다만 위(상단) 콘텐츠 리플로우로 docTop 이 바뀔 수 있어 ResizeObserver 로
// 레이아웃 변화를 감지해 좌표를 재전송한다.

type Props = {
  /** 슬롯 고유 ID (페이지·인덱스로 구성 권장: 예 `feed-ad-p1-6`) */
  slotId: string;
  /** 광고 카드 높이(px). 일반 카드 높이와 비슷하게 잡아 그리드 리듬을 유지. */
  height?: number;
  /**
   * 뷰포트 고정(modal) 슬롯 여부. 종료 다이얼로그처럼 `position:fixed` 컨테이너
   * 안에 둘 때 true. 이때 좌표는 뷰포트 기준(rect.top, scrollY 미포함)으로 보고하고
   * 네이티브도 스크롤을 빼지 않아 배경 스크롤과 무관하게 모달에 고정된다.
   */
  fixed?: boolean;
  /** placeholder 의 CSS 클래스(기본 `native-ad-slot`). 다이얼로그 전용 스타일 주입용. */
  className?: string;
};

const DEFAULT_HEIGHT = 312;

let supportPromise: Promise<boolean> | null = null;
function checkSupported(): Promise<boolean> {
  if (!supportPromise) {
    supportPromise = NativeAd.isSupported()
      .then((r) => r.supported)
      .catch(() => false);
  }
  return supportPromise;
}

export default function NativeAdSlot({
  slotId,
  height = DEFAULT_HEIGHT,
  fixed = false,
  className = "native-ad-slot"
}: Props) {
  const elRef = useRef<HTMLDivElement | null>(null);
  const loadedRef = useRef(false);

  // 현재 placeholder 의 좌표/크기를 측정.
  // - 일반(문서 흐름) 슬롯: docTop 은 문서 절대 Y(rect.top + scrollY). 네이티브가 스크롤을 빼서 배치.
  // - fixed(모달) 슬롯: docTop 은 뷰포트 Y(rect.top). 네이티브가 스크롤을 빼지 않고 그대로 배치.
  function measure() {
    const el = elRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return {
      slotId,
      x: Math.round(rect.left),
      docTop: Math.round(fixed ? rect.top : rect.top + window.scrollY),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      fixed
    };
  }

  useLayoutEffect(() => {
    let cancelled = false;
    let ro: ResizeObserver | null = null;
    let bodyRo: ResizeObserver | null = null;

    function pushGeometry() {
      const geo = measure();
      if (!geo || geo.width <= 0) return;
      if (loadedRef.current) {
        void NativeAd.updateGeometry(geo).catch(() => undefined);
      }
    }

    async function start() {
      const supported = await checkSupported();
      if (cancelled || supported === false) return;
      const geo = measure();
      if (!geo || geo.width <= 0) return;
      const { adId, npa, isTesting } = getNativeAdConfig();
      try {
        await NativeAd.loadSlot({ ...geo, adId, npa, isTesting });
        if (cancelled) {
          void NativeAd.removeSlot({ slotId }).catch(() => undefined);
          return;
        }
        loadedRef.current = true;
        // 로드 직후 한 번 더 보정(이미지·폰트 로딩 등으로 레이아웃이 늦게 안정화될 수 있음).
        requestAnimationFrame(pushGeometry);
        setTimeout(pushGeometry, 300);
      } catch {
        // 로드 실패 시 자리는 비워둔다(빈 공간만 남음).
      }
    }

    const el = elRef.current;
    if (el && "ResizeObserver" in window) {
      ro = new ResizeObserver(() => pushGeometry());
      ro.observe(el);
      // 상단 콘텐츠 리플로우로 docTop 이 변하는 경우까지 잡기 위해 body 도 관찰.
      bodyRo = new ResizeObserver(() => pushGeometry());
      bodyRo.observe(document.body);
    }
    window.addEventListener("resize", pushGeometry);
    window.addEventListener("orientationchange", pushGeometry);

    void start();

    return () => {
      cancelled = true;
      ro?.disconnect();
      bodyRo?.disconnect();
      window.removeEventListener("resize", pushGeometry);
      window.removeEventListener("orientationchange", pushGeometry);
      if (loadedRef.current) {
        loadedRef.current = false;
        void NativeAd.removeSlot({ slotId }).catch(() => undefined);
      }
    };
    // slotId 가 바뀌면 다른 슬롯이므로 재설정.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slotId]);

  // placeholder 자체는 그리드 한 칸을 차지하는 투명 박스. 네이티브 광고가 그 위에 겹쳐 그려진다.
  // 네이티브 미지원(웹 미리보기 등)에서는 광고가 안 떠도 빈 자리만 남으므로,
  // 시각적 잔여를 줄이기 위해 아주 옅은 안내 박스를 둔다.
  return (
    <div
      ref={elRef}
      className={className}
      data-slot-id={slotId}
      style={{ minHeight: height }}
      aria-label="광고"
    />
  );
}
