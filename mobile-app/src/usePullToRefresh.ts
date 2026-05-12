import { useCallback, useEffect, useRef, useState } from "react";

const PULL_THRESHOLD = 64; // 이 이상 당기면 release 시 리프레시 발동
const PULL_MAX = 96;        // 시각 인디케이터 최대 거리
const PULL_RESISTANCE = 0.55; // 손가락 이동 거리 대비 인디케이터 이동 비율

type UsePullToRefreshOpts = {
  onRefresh: () => Promise<void> | void;
  /** 비활성화 (이미 로딩 중이거나 상세 화면 등) */
  disabled?: boolean;
  /** 풀투리프레시를 감지할 컨테이너. 미지정 시 window scrollY 기준. */
  containerRef?: React.RefObject<HTMLElement>;
};

/**
 * 가벼운 풀투리프레시 hook — 의존성 0.
 *
 * 사용
 *   const { distance, refreshing } = usePullToRefresh({ onRefresh });
 *   <div style={{ transform: `translateY(${distance}px)` }}> ... </div>
 *
 * 컨테이너의 scrollTop 이 0 일 때 down swipe 시작 → threshold 이상 당기면
 * release 시 onRefresh 호출. 중간에 손 떼면 원위치.
 */
export function usePullToRefresh({ onRefresh, disabled, containerRef }: UsePullToRefreshOpts) {
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startYRef = useRef<number | null>(null);
  const trackingRef = useRef(false);
  // Codex P1 — handleTouchEnd 가 effect 클로저에서 잡은 stale distance/refreshing
  // 으로 threshold 검사하면 release 조건이 항상 false 라 풀투리프레시가 발동
  // 하지 않는다. distance/refreshing 의 live 값을 ref 로 동기화해 핸들러 안에서
  // 그 ref 를 읽도록 한다. 효과 재구독 없이 최신 값 사용 가능.
  const distanceRef = useRef(0);
  const refreshingRef = useRef(false);
  useEffect(() => {
    distanceRef.current = distance;
  }, [distance]);
  useEffect(() => {
    refreshingRef.current = refreshing;
  }, [refreshing]);

  const getScrollTop = useCallback(() => {
    if (containerRef?.current) return containerRef.current.scrollTop;
    return window.scrollY;
  }, [containerRef]);

  useEffect(() => {
    if (disabled) return;

    function handleTouchStart(e: TouchEvent) {
      if (refreshingRef.current) return;
      if (getScrollTop() > 0) return;
      const t = e.touches[0];
      if (!t) return;
      startYRef.current = t.clientY;
      trackingRef.current = true;
    }

    function handleTouchMove(e: TouchEvent) {
      if (!trackingRef.current || startYRef.current === null) return;
      const t = e.touches[0];
      if (!t) return;
      const delta = t.clientY - startYRef.current;
      if (delta <= 0) {
        setDistance(0);
        return;
      }
      // resistance 적용해 PULL_MAX 까지만
      const eased = Math.min(PULL_MAX, delta * PULL_RESISTANCE);
      setDistance(eased);
      // browser 가 스크롤 안 하도록 (선택적)
      if (delta > 8) e.preventDefault();
    }

    async function handleTouchEnd() {
      if (!trackingRef.current) return;
      trackingRef.current = false;
      startYRef.current = null;
      // Codex P1 — ref 로 live 값 사용
      if (distanceRef.current >= PULL_THRESHOLD && !refreshingRef.current) {
        setRefreshing(true);
        // 인디케이터를 trigger 위치로 고정
        setDistance(PULL_THRESHOLD);
        try {
          await onRefresh();
        } finally {
          setRefreshing(false);
          setDistance(0);
        }
      } else {
        setDistance(0);
      }
    }

    // passive: false 로 preventDefault 가능
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchmove", handleTouchMove, { passive: false });
    window.addEventListener("touchend", handleTouchEnd);
    window.addEventListener("touchcancel", handleTouchEnd);

    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
      window.removeEventListener("touchcancel", handleTouchEnd);
    };
  }, [disabled, onRefresh, getScrollTop]);

  return {
    distance,
    refreshing,
    /** trigger 임계치 도달 여부 — 인디케이터 색 변경에 사용 */
    armed: distance >= PULL_THRESHOLD,
  };
}
