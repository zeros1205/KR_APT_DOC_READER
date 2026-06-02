import { Capacitor } from "@capacitor/core";

// 크래시 리포팅(Firebase Crashlytics) 얇은 래퍼.
//
// 설계 원칙
//  - 네이티브(Android/iOS)에서만 동작. 웹/미지원 환경에서는 전부 no-op 으로 조용히 통과.
//  - 플러그인 import 는 지연 로드(admob.ts 와 동일 패턴)하여 웹 번들과 분리하고,
//    import/호출 실패가 앱 본체를 죽이지 않게 모든 경로를 try/catch 로 감싼다.
//  - 실제 수집 활성화 여부는 사용자 동의(설정 crashReportingEnabled)에 따른다.
//    기본값은 storage.ts 의 defaultSettings 에서 관리.
//  - Firebase 가 구성되지 않은 빌드(google-services.json / GoogleService-Info.plist 미주입)
//    에서는 네이티브 플러그인 호출이 실패할 수 있는데, 그 또한 경고 로그만 남기고 무시한다.

type CrashlyticsPlugin =
  typeof import("@capacitor-firebase/crashlytics")["FirebaseCrashlytics"];

let pluginPromise: Promise<CrashlyticsPlugin | null> | null = null;
let handlersInstalled = false;

function supported(): boolean {
  return Capacitor.isNativePlatform();
}

async function getPlugin(): Promise<CrashlyticsPlugin | null> {
  if (!supported()) return null;
  if (!pluginPromise) {
    pluginPromise = import("@capacitor-firebase/crashlytics")
      .then((mod) => mod.FirebaseCrashlytics)
      .catch((error) => {
        console.warn("[crash] plugin import failed", error);
        return null;
      });
  }
  return pluginPromise;
}

function describeError(value: unknown): string {
  if (value instanceof Error) {
    return value.stack ? `${value.name}: ${value.message}\n${value.stack}` : `${value.name}: ${value.message}`;
  }
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

// 수집 on/off. 사용자가 설정 토글을 바꿀 때마다 호출한다.
export async function setCrashCollectionEnabled(enabled: boolean): Promise<void> {
  const plugin = await getPlugin();
  if (!plugin) return;
  try {
    await plugin.setEnabled({ enabled });
  } catch (error) {
    console.warn("[crash] setEnabled failed", error);
  }
}

// 비치명적(non-fatal) 예외 기록. context 는 custom key 로 함께 첨부.
export async function recordError(
  error: unknown,
  context?: Record<string, string | number | boolean>
): Promise<void> {
  const plugin = await getPlugin();
  if (!plugin) return;
  try {
    const keysAndValues = context
      ? Object.entries(context).map(([key, value]) => ({
          key,
          value: typeof value === "object" ? JSON.stringify(value) : value,
          type:
            typeof value === "boolean"
              ? ("boolean" as const)
              : typeof value === "number"
              ? Number.isInteger(value)
                ? ("int" as const)
                : ("double" as const)
              : ("string" as const)
        }))
      : undefined;
    await plugin.recordException({ message: describeError(error), keysAndValues });
  } catch (e) {
    console.warn("[crash] recordException failed", e);
  }
}

// 크래시 직전까지의 흐름을 남기는 breadcrumb 로그.
export async function logCrashBreadcrumb(message: string): Promise<void> {
  const plugin = await getPlugin();
  if (!plugin) return;
  try {
    await plugin.log({ message });
  } catch (e) {
    console.warn("[crash] log failed", e);
  }
}

// 전역 에러/거부 핸들러 설치 (한 번만). 이미 swallow 되던 비동기 오류를 잡아 비치명적으로 보고.
function installGlobalHandlers(): void {
  if (handlersInstalled) return;
  handlersInstalled = true;
  window.addEventListener("error", (event) => {
    void recordError(event.error ?? event.message, { source: "window.onerror" });
  });
  window.addEventListener("unhandledrejection", (event) => {
    void recordError(event.reason ?? "unhandledrejection", { source: "unhandledrejection" });
  });
}

// 앱 부팅 시 1회 호출. 동의 상태를 반영하고 전역 핸들러를 건다.
export async function initCrashReporting(enabled: boolean): Promise<void> {
  if (!supported()) return;
  await setCrashCollectionEnabled(enabled);
  if (enabled) installGlobalHandlers();
}

// 통합 검증용 강제 크래시. 절대 프로덕션 UI 에 노출하지 말 것 (문서의 테스트 절차에서만 사용).
export async function forceCrashForTest(): Promise<void> {
  const plugin = await getPlugin();
  if (!plugin) return;
  await plugin.crash({ message: "Test crash from forceCrashForTest()" });
}
