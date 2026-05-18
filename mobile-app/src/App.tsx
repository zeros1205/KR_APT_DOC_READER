import { useEffect, useMemo, useRef, useState } from "react";
import { usePullToRefresh } from "./usePullToRefresh";
import {
  ArrowLeft,
  Bell,
  Bookmark,
  BookmarkCheck,
  Check,
  ChevronRight,
  Home,
  Menu,
  Search,
  Settings,
  Share2,
  Trash2
} from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { AppLauncher } from "@capacitor/app-launcher";
import { Browser } from "@capacitor/browser";
import { PushNotifications } from "@capacitor/push-notifications";
import { Share } from "@capacitor/share";
import { absolutePostUrl, extractPriceRange, fetchLatestVersion, fetchPostHtml, fetchPostsIndex, SITE_ORIGIN } from "./api";
import introBackground from "./assets/intro_without_text.png";
import {
  defaultSettings,
  loadFavorites,
  loadSettings,
  resetLocalData,
  saveFavorites,
  saveSettings,
  syncDeviceWithBackend
} from "./storage";
import type { FavoriteNotice, NoticeCard, PushDataPayload, UserSettings } from "./types";

const REGIONS = [
  "서울",
  "경기도",
  "인천",
  "부산",
  "대구",
  "광주",
  "대전",
  "울산",
  "세종",
  "강원도",
  "충청북도",
  "충청남도",
  "전라북도",
  "전라남도",
  "경상북도",
  "경상남도",
  "제주"
];
const APP_VERSION = import.meta.env.VITE_APP_VERSION || "0.1.0";
const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=app.aptnote.mobile";
const APP_STORE_URL = import.meta.env.VITE_APP_STORE_URL || "https://apps.apple.com/app/id6745796757";
const PLAY_STORE_NATIVE_URL = "market://details?id=app.aptnote.mobile";
const APP_STORE_NATIVE_URL = "itms-apps://itunes.apple.com/app/id6745796757";

async function openStorePage(): Promise<void> {
  const isIos = Capacitor.getPlatform() === "ios";
  const nativeUrl = isIos ? APP_STORE_NATIVE_URL : PLAY_STORE_NATIVE_URL;
  const webUrl = isIos ? APP_STORE_URL : PLAY_STORE_URL;

  if (Capacitor.isNativePlatform()) {
    try {
      const result = await AppLauncher.openUrl({ url: nativeUrl });
      if (result.completed) return;
    } catch {
      // 스토어 앱 미설치 또는 OS 거부 — 웹으로 폴백
    }
  }
  await Browser.open({ url: webUrl });
}
const POSTS_PER_PAGE = 12;
const PREFERRED_REGION_KEY = "__preferred__";

type View = "home" | "favorites" | "settings" | "detail";
type FavoriteSort = "nameAsc" | "nameDesc" | "newest" | "oldest";
type SettingsPage = "main" | "notifications" | "regions" | "favorites";
type ConfirmDialogState = {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  resolve: (confirmed: boolean) => void;
};
type DetailPage = {
  url: string;
  title: string;
  card?: NoticeCard;
  returnView?: Exclude<View, "detail">;
};

function normalizeRegion(region: string): string {
  return region.replace("특별시", "").replace("광역시", "").replace("제주도", "제주").trim();
}

function displayRegion(region: string): string {
  const shortNames: Record<string, string> = {
    강원도: "강원",
    충청북도: "충북",
    충청남도: "충남",
    전라북도: "전북",
    전라남도: "전남",
    경상북도: "경북",
    경상남도: "경남",
    제주도: "제주",
    제주: "제주"
  };
  return shortNames[region] || region;
}

function buildShareText(card: NoticeCard): string {
  const lines: string[] = [`[${card.apt_name}] 청약 정보 한눈에 보기`, ""];
  const region = card.region?.trim();
  if (region) lines.push(`📍 ${region}`);
  const noticeDate = card.notice_date?.trim();
  if (noticeDate) lines.push(`🗓 모집공고일 ${noticeDate}`);
  const price = (card as FavoriteNotice).price_range || extractPriceRange(card);
  if (price) lines.push(`💰 ${price}`);
  if (lines.length > 2) lines.push("");
  lines.push(
    "🏠 분양가·일정·입지·자격 핵심 정리",
    "📋 청약 전 꼭 확인해야 할 정보 모음",
    "✨ 정과장의 청약노트"
  );
  return lines.join("\n");
}

function buildGenericShareText(title: string): string {
  return [
    title,
    "",
    "🏠 복잡한 청약 공고문, 깔끔하게 정리",
    "📋 분양가·일정·입지·자격 한눈에",
    "✨ 정과장의 청약노트"
  ].join("\n");
}

function sanitizeCardHtml(card: NoticeCard): string {
  const html = card.html || "";
  const titleClass = card.apt_name.replace(/\s+/g, "").length >= 13 ? "card-title is-long-title" : "card-title";
  return html
    .replace(/\sonclick="[^"]*"/g, "")
    .replace(/\shref="([^"]+)"/g, (_, href: string) => ` href="${absolutePostUrl(href)}"`)
    .replace(/class="card-title"/, `class="${titleClass}"`);
}

function isApplyHomeCard(card?: NoticeCard): boolean {
  return card?.index_action === "applyhome";
}

function App() {
  const [introVisible, setIntroVisible] = useState(true);
  const [view, setView] = useState<View>("home");
  const [cards, setCards] = useState<NoticeCard[]>([]);
  const [favorites, setFavorites] = useState<FavoriteNotice[]>([]);
  const [settings, setSettings] = useState<UserSettings>(defaultSettings);
  const [activeRegion, setActiveRegion] = useState("전체");
  const [detailPage, setDetailPage] = useState<DetailPage | null>(null);
  const [settingsPage, setSettingsPage] = useState<SettingsPage>("main");
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [latestVersion, setLatestVersion] = useState(APP_VERSION);
  const [installedVersion, setInstalledVersion] = useState(APP_VERSION);
  const [toastMessage, setToastMessage] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const lastHomeBackAtRef = useRef(0);
  const toastTimerRef = useRef<number | null>(null);
  const pendingPushPayloadRef = useRef<PushDataPayload | null>(null);
  const cardsRef = useRef<NoticeCard[]>([]);
  const settingsRef = useRef<UserSettings>(defaultSettings);

  useEffect(() => {
    void Promise.all([loadFavorites(), loadSettings()]).then(([savedFavorites, savedSettings]) => {
      setFavorites(savedFavorites);
      setSettings(savedSettings);
    });
    void refreshPosts();
    void fetchLatestVersion(Capacitor.getPlatform()).then((version) => {
      if (version) setLatestVersion(version);
    });
    if (Capacitor.isNativePlatform()) {
      void CapacitorApp.getInfo().then((info) => {
        if (info.version) setInstalledVersion(info.version);
      });
    }
  }, []);

  useEffect(() => {
    if (view !== "home") return;
    setActiveRegion(settings.regions.length > 0 ? PREFERRED_REGION_KEY : "전체");
  }, [view, settings.regions]);

  useEffect(() => {
    cardsRef.current = cards;
    const pending = pendingPushPayloadRef.current;
    if (pending && cards.length > 0) {
      pendingPushPayloadRef.current = null;
      handlePushPayload(pending);
    }
  }, [cards]);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    if (settings.pushPendingSync && settings.pushEnabled) {
      void syncDeviceWithBackend(settings, { appVersion: installedVersion });
    }
  }, [settings.pushPendingSync, settings.pushEnabled, installedVersion]);

  useEffect(() => {
    if (loading) return;
    const timer = window.setTimeout(() => setIntroVisible(false), 300);
    return () => window.clearTimeout(timer);
  }, [loading]);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    const handle = CapacitorApp.addListener("appStateChange", ({ isActive }) => {
      if (isActive) void refreshPosts();
    });
    return () => {
      void handle.then((h) => h.remove());
    };
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    const registrationListener = PushNotifications.addListener("registration", (token) => {
      void savePushToken(token.value);
    });
    const registrationErrorListener = PushNotifications.addListener("registrationError", () => {
      showToast("알림 등록을 완료하지 못했습니다.");
    });
    const pushListener = PushNotifications.addListener("pushNotificationReceived", (notification) => {
      showToast(notification.title || "새 알림이 도착했습니다.");
    });
    const actionListener = PushNotifications.addListener("pushNotificationActionPerformed", (event) => {
      const payload = (event?.notification?.data || {}) as PushDataPayload;
      handlePushPayload(payload);
    });

    const registration = CapacitorApp.addListener("backButton", ({ canGoBack }) => {
      if (menuOpen) {
        setMenuOpen(false);
        return;
      }
      if (view === "detail") {
        goBackFromDetail();
        return;
      }
      if (view === "settings" && settingsPage !== "main") {
        setSettingsPage("main");
        return;
      }
      if (view !== "home") {
        setView("home");
        return;
      }
      if (canGoBack) {
        window.history.back();
        return;
      }
      handleHomeBack();
    });

    return () => {
      void registration.then((handle) => handle.remove());
      void registrationListener.then((handle) => handle.remove());
      void registrationErrorListener.then((handle) => handle.remove());
      void pushListener.then((handle) => handle.remove());
      void actionListener.then((handle) => handle.remove());
    };
  }, [detailPage, menuOpen, settingsPage, view]);

  async function refreshPosts() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchPostsIndex();
      setCards(data.cards);
      setLastUpdated(data.generated_at);
    } catch {
      setError("공고 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  const regionTabs = useMemo(() => {
    const cardRegions = new Set(cards.map((card) => normalizeRegion(card.region)).filter(Boolean));
    const ordered = REGIONS.filter((region) => cardRegions.has(normalizeRegion(region)));
    const tabs = ["전체"];
    if (settings.regions.length > 0) tabs.push(PREFERRED_REGION_KEY);
    return [...tabs, ...ordered];
  }, [cards, settings.regions]);

  const filteredCards = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return cards.filter((card) => {
      const cardRegion = normalizeRegion(card.region);
      const matchesRegion =
        activeRegion === "전체"
          ? true
          : activeRegion === PREFERRED_REGION_KEY
            ? settings.regions.some((r) => cardRegion.includes(normalizeRegion(r)))
            : cardRegion.includes(normalizeRegion(activeRegion));
      const matchesQuery =
        !keyword ||
        card.apt_name.toLowerCase().includes(keyword) ||
        card.region.toLowerCase().includes(keyword) ||
        card.notice_id.includes(keyword);
      return matchesRegion && matchesQuery;
    });
  }, [activeRegion, cards, query, settings.regions]);

  const favoriteIds = useMemo(() => new Set(favorites.map((favorite) => favorite.notice_id)), [favorites]);

  async function persistFavorites(next: FavoriteNotice[]) {
    setFavorites(next);
    await saveFavorites(next);
  }

  async function toggleFavorite(card: NoticeCard) {
    if (favoriteIds.has(card.notice_id)) {
      await persistFavorites(favorites.filter((favorite) => favorite.notice_id !== card.notice_id));
      return;
    }
    const favorite: FavoriteNotice = {
      ...card,
      post_url: absolutePostUrl(card.post_url),
      price_range: extractPriceRange(card),
      saved_at: new Date().toISOString()
    };
    await persistFavorites([favorite, ...favorites]);
  }

  async function updateSettings(next: UserSettings) {
    setSettings(next);
    await saveSettings(next);
  }

  async function savePushToken(token: string) {
    setSettings((current) => {
      const next: UserSettings = {
        ...current,
        pushEnabled: true,
        pushToken: token,
        pushTokenUpdatedAt: new Date().toISOString()
      };
      void saveSettings(next);
      void syncDeviceWithBackend(next, { appVersion: installedVersion, immediate: true });
      return next;
    });
  }

  async function setPushEnabled(enabled: boolean) {
    setSettings((current) => {
      const next: UserSettings = { ...current, pushEnabled: enabled };
      void saveSettings(next);
      void syncDeviceWithBackend(next, { appVersion: installedVersion, immediate: true });
      return next;
    });
  }

  async function toggleRegion(region: string) {
    const exists = settings.regions.includes(region);
    const nextRegions = exists ? settings.regions.filter((item) => item !== region) : [...settings.regions, region];
    const next: UserSettings = { ...settings, regions: nextRegions };
    await updateSettings(next);
    void syncDeviceWithBackend(next, { appVersion: installedVersion });
  }

  async function enablePush() {
    if (settings.pushEnabled) {
      await setPushEnabled(false);
      return;
    }

    if (!settings.pushConsentedAt) {
      const consented = await askConfirm({
        title: "푸시 알림 수신 동의",
        message:
          "신규 청약 공고를 알려드리기 위해 단말 푸시 토큰과 선택한 관심지역 정보를 서버에 안전하게 저장합니다. 동의하시겠어요?",
        confirmLabel: "동의",
        cancelLabel: "취소"
      });
      if (!consented) return;
      const consented_settings: UserSettings = {
        ...settings,
        pushConsentedAt: new Date().toISOString()
      };
      await updateSettings(consented_settings);
    }

    if (!Capacitor.isNativePlatform()) {
      await setPushEnabled(true);
      return;
    }
    try {
      const permission = await PushNotifications.requestPermissions();
      if (permission.receive !== "granted") {
        await setPushEnabled(false);
        showToast("알림 권한이 거부되어 푸시를 켤 수 없어요.");
        return;
      }
      await setPushEnabled(true);
      await PushNotifications.register();
    } catch {
      await setPushEnabled(false);
      showToast("알림 권한 설정을 완료하지 못했습니다.");
    }
  }

  function handlePushPayload(payload: PushDataPayload) {
    const type = String(payload.type || "");
    const noticeId = (payload.notice_id || "").trim();

    if ((type === "1" || type === "3") && noticeId) {
      const ready = cardsRef.current.length > 0;
      if (!ready) {
        pendingPushPayloadRef.current = payload;
        return;
      }
      const card = cardsRef.current.find((c) => c.notice_id === noticeId);
      if (card) {
        void openUrl(card.post_url, card.apt_name, card);
        return;
      }
      pendingPushPayloadRef.current = payload;
      return;
    }

    if (type === "2") {
      setView("home");
      const hasPreferred = settingsRef.current.regions.length > 0;
      setActiveRegion(hasPreferred ? PREFERRED_REGION_KEY : "전체");
      return;
    }

    setView("home");
    setActiveRegion("전체");
  }

  function askConfirm(options: Omit<ConfirmDialogState, "resolve">): Promise<boolean> {
    return new Promise((resolve) => {
      setConfirmDialog({ ...options, resolve });
    });
  }

  function closeConfirmDialog(confirmed: boolean) {
    setConfirmDialog((dialog) => {
      dialog?.resolve(confirmed);
      return null;
    });
  }

  async function confirmResetLocalData() {
    const ok = await askConfirm({
      title: "저장 데이터 초기화",
      message: "즐겨찾기와 앱 설정을 모두 삭제할까요?",
      confirmLabel: "초기화",
      cancelLabel: "취소"
    });
    if (!ok) return;
    await clearLocalData();
    showToast("저장 데이터가 초기화되었습니다.");
  }

  async function openUrl(url: string, title = "정과장의 청약노트", card?: NoticeCard) {
    if (isApplyHomeCard(card)) {
      const targetUrl = card?.notice_url || url;
      const ok = await askConfirm({
        title: "청약Home 이동",
        message: "이 공고는 청약Home에서 자세히 확인할 수 있어요. 이동할까요?",
        confirmLabel: "확인",
        cancelLabel: "취소"
      });
      if (!ok) return;
      await Browser.open({ url: absolutePostUrl(targetUrl) });
      return;
    }
    setDetailPage({ url: absolutePostUrl(url), title, card, returnView: view === "detail" ? "home" : view });
    setView("detail");
  }

  function goBackFromDetail() {
    setView(detailPage?.returnView || "home");
    setDetailPage(null);
  }

  function showToast(message: string) {
    setToastMessage(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToastMessage(""), 1800);
  }

  function handleHomeBack() {
    const now = Date.now();
    if (now - lastHomeBackAtRef.current < 1800) {
      lastHomeBackAtRef.current = 0;
      setToastMessage("");
      CapacitorApp.exitApp();
      return;
    }
    lastHomeBackAtRef.current = now;
    showToast("한 번 더 누르면 앱이 종료됩니다.");
  }

  async function shareCard(card: NoticeCard) {
    const url = absolutePostUrl(card.post_url);
    const text = buildShareText(card);
    await Share.share({ text, url });
  }

  async function clearLocalData() {
    await resetLocalData();
    setFavorites([]);
    setSettings(defaultSettings);
  }

  function goHome() {
    setDetailPage(null);
    setSettingsPage("main");
    setView("home");
    setMenuOpen(false);
  }

  function openMenuView(nextView: Exclude<View, "detail">) {
    setDetailPage(null);
    if (nextView === "settings") setSettingsPage("main");
    setView(nextView);
    setMenuOpen(false);
  }

  function getSettingsTitle() {
    if (settingsPage === "notifications") return "알림 설정";
    if (settingsPage === "regions") return "관심지역 설정";
    if (settingsPage === "favorites") return "즐겨찾기 관리";
    return "설정";
  }

  function goBackFromSubpage() {
    if (view === "settings" && settingsPage !== "main") {
      setSettingsPage("main");
      return;
    }
    goHome();
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  function toggleMenu() {
    setMenuOpen((open) => !open);
  }

  return (
    <main className={`app-shell ${view === "detail" ? "detail-mode" : ""}`}>
      {introVisible && <IntroScreen />}
      {view === "detail" && detailPage ? (
        <DetailNav
          page={detailPage}
          isFavorite={detailPage.card ? favoriteIds.has(detailPage.card.notice_id) : false}
          onBack={goBackFromDetail}
          onShare={() =>
            detailPage.card
              ? void shareCard(detailPage.card)
              : void Share.share({
                  text: buildGenericShareText(detailPage.title),
                  url: detailPage.url
                })
          }
          onToggleFavorite={() => detailPage.card && void toggleFavorite(detailPage.card)}
        />
      ) : view === "favorites" || view === "settings" ? (
        <SubpageNav
          title={view === "favorites" ? "즐겨찾기" : getSettingsTitle()}
          onBack={goBackFromSubpage}
          onMenu={toggleMenu}
        />
      ) : (
        <SiteNav view={view} onMenu={toggleMenu} />
      )}

      {view === "home" && (
        <HomeView
          activeRegion={activeRegion}
          cards={filteredCards}
          error={error}
          favoriteIds={favoriteIds}
          loading={loading}
          query={query}
          regions={regionTabs}
          onOpen={openUrl}
          onQuery={setQuery}
          onRefresh={refreshPosts}
          onRegion={setActiveRegion}
          onShare={shareCard}
          onToggleFavorite={toggleFavorite}
        />
      )}

      {view === "favorites" && (
        <FavoritesView
          favorites={favorites}
          onOpen={openUrl}
          onRemove={(noticeId) =>
            void persistFavorites(favorites.filter((favorite) => favorite.notice_id !== noticeId))
          }
          onShare={shareCard}
        />
      )}

      {view === "settings" && (
        <SettingsView
          favorites={favorites}
          installedVersion={installedVersion}
          latestVersion={latestVersion}
          page={settingsPage}
          settings={settings}
          onClear={confirmResetLocalData}
          onOpen={openUrl}
          onPage={setSettingsPage}
          onPush={enablePush}
          onQuietHours={(enabled) => void updateSettings({ ...settings, quietHoursEnabled: enabled })}
          onRegion={toggleRegion}
          onRemoveFavorite={(noticeId) =>
            void persistFavorites(favorites.filter((favorite) => favorite.notice_id !== noticeId))
          }
          onShare={shareCard}
          onUpdate={() => void openStorePage()}
        />
      )}

      {view === "detail" && detailPage && <DetailView page={detailPage} />}

      {menuOpen && view !== "detail" && (
        <AppMenu
          currentView={view}
          onClose={closeMenu}
          onFavorites={() => openMenuView("favorites")}
          onHome={() => openMenuView("home")}
          onSettings={() => openMenuView("settings")}
        />
      )}

      {confirmDialog && (
        <ConfirmDialog
          cancelLabel={confirmDialog.cancelLabel}
          confirmLabel={confirmDialog.confirmLabel}
          message={confirmDialog.message}
          title={confirmDialog.title}
          onCancel={() => closeConfirmDialog(false)}
          onConfirm={() => closeConfirmDialog(true)}
        />
      )}

      {toastMessage && <div className="app-toast">{toastMessage}</div>}
    </main>
  );
}

function IntroScreen() {
  return (
    <section className="intro-screen" aria-label="앱 시작 화면">
      <img className="intro-background" src={introBackground} alt="" />
      <div className="intro-copy" aria-hidden="true">
        <h1>정과장의 청약노트</h1>
        <p>
          복잡한 아파트 공고문,
          <br />
          쉽게 정리해드려요.
        </p>
      </div>
      <div className="intro-loading" aria-live="polite">
        <div className="intro-progress" aria-hidden="true">
          <span />
        </div>
        <p>로딩 중...</p>
      </div>
    </section>
  );
}

function SiteNav({ view, onMenu }: { view: View; onMenu: () => void }) {
  return (
    <header className="site-header-v3">
      <div className="site-header-v3-inner">
        <button className="site-header-v3-brand" type="button" aria-label="정과장의 청약노트">
          <img src="/app_logo_80x80_rounded.png" alt="" className="site-header-v3-logo" />
          <span>
            <span className="site-header-v3-title">
              {view === "home" ? "정과장의 청약노트" : view === "favorites" ? "즐겨찾기" : "설정"}
            </span>
            <span className="site-header-v3-sub">APT-NOTE.COM</span>
          </span>
        </button>
        <div className="nav-actions">
          <button className="nav-icon-button" onClick={onMenu} aria-label="메뉴">
            <Menu size={19} />
          </button>
        </div>
      </div>
    </header>
  );
}

function SubpageNav({ title, onBack, onMenu }: { title: string; onBack: () => void; onMenu: () => void }) {
  return (
    <header className="subpage-nav">
      <button className="nav-icon-button" onClick={onBack} aria-label="뒤로">
        <ArrowLeft size={21} />
      </button>
      <h1>{title}</h1>
      <button className="nav-icon-button" onClick={onMenu} aria-label="메뉴">
        <Menu size={19} />
      </button>
    </header>
  );
}

function AppMenu({
  currentView,
  onClose,
  onFavorites,
  onHome,
  onSettings
}: {
  currentView: Exclude<View, "detail">;
  onClose: () => void;
  onFavorites: () => void;
  onHome: () => void;
  onSettings: () => void;
}) {
  return (
    <>
      <button className="menu-backdrop" aria-label="메뉴 닫기" onClick={onClose} />
      <nav className="header-menu-layer" aria-label="앱 메뉴">
        {currentView !== "home" && (
          <button onClick={onHome}>
            <Home size={18} /> 홈
          </button>
        )}
        {currentView !== "favorites" && (
          <button onClick={onFavorites}>
            <Bookmark size={18} /> 즐겨찾기
          </button>
        )}
        {currentView !== "settings" && (
          <button onClick={onSettings}>
            <Settings size={18} /> 설정
          </button>
        )}
      </nav>
    </>
  );
}

function ConfirmDialog({
  cancelLabel = "취소",
  confirmLabel = "확인",
  message,
  title,
  onCancel,
  onConfirm
}: {
  cancelLabel?: string;
  confirmLabel?: string;
  message: string;
  title: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="app-dialog-backdrop" role="presentation">
      <section className="app-dialog" role="dialog" aria-modal="true" aria-labelledby="app-dialog-title">
        <h2 id="app-dialog-title">{title}</h2>
        <p>{message}</p>
        <div className="app-dialog-actions">
          <button className="app-dialog-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className="app-dialog-confirm" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}

function DetailNav({
  page,
  isFavorite,
  onBack,
  onShare,
  onToggleFavorite
}: {
  page: DetailPage;
  isFavorite: boolean;
  onBack: () => void;
  onShare: () => void;
  onToggleFavorite: () => void;
}) {
  return (
    <header className="detail-nav">
      <button className="detail-icon" onClick={onBack} aria-label="뒤로">
        <ArrowLeft size={21} />
      </button>
      <div className="detail-title">
        <span>{page.card ? "청약 공고문 분석" : page.title}</span>
      </div>
      <div className="detail-actions">
        {page.card && (
          <button className="detail-icon" onClick={onToggleFavorite} aria-label="즐겨찾기">
            {isFavorite ? <BookmarkCheck size={20} /> : <Bookmark size={20} />}
          </button>
        )}
        <button className="detail-icon" onClick={onShare} aria-label="공유">
          <Share2 size={20} />
        </button>
      </div>
    </header>
  );
}

function DetailView({ page }: { page: DetailPage }) {
  const [html, setHtml] = useState("");
  const [error, setError] = useState("");
  const screenRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    setHtml("");
    setError("");
    window.scrollTo({ top: 0, left: 0 });
    screenRef.current?.scrollTo({ top: 0, left: 0 });
    void fetchPostHtml(page.url)
      .then((postHtml) => {
        if (!cancelled) {
          setHtml(toAppPostContent(postHtml));
          window.requestAnimationFrame(() => {
            window.scrollTo({ top: 0, left: 0 });
            screenRef.current?.scrollTo({ top: 0, left: 0 });
          });
        }
      })
      .catch(() => {
        if (!cancelled) setError("포스트 페이지를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [page.url]);

  if (error) {
    return (
      <section className="detail-screen detail-message">
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>다시 시도</button>
      </section>
    );
  }

  if (!html) {
    return (
      <section className="detail-screen detail-message">
        <p>포스트 페이지를 불러오는 중입니다.</p>
      </section>
    );
  }

  return (
    <section ref={screenRef} className="detail-screen detail-document" aria-label={page.title}>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </section>
  );
}

function toAppPostContent(html: string): string {
  const parser = new DOMParser();
  const document = parser.parseFromString(html, "text/html");
  document
    .querySelectorAll(
      [
        "script",
        "noscript",
        "ins",
        "iframe",
        ".site-header-v3",
        "#post-compact-bar",
        "[class*='ad']",
        "[class*='ads']",
        "[id*='ad']",
        "[id*='ads']",
        "[data-ad-client]"
      ].join(", ")
    )
    .forEach((node) => node.remove());
  const styles = Array.from(document.querySelectorAll("style"))
    .map((style) => style.outerHTML)
    .join("\n");
  const body = document.querySelector("#post-body")?.outerHTML || document.body.innerHTML;
  return `
    ${styles}
    <style>
      #post-body {
        padding-top: 18px !important;
        padding-bottom: max(24px, env(safe-area-inset-bottom)) !important;
      }
      #post-body * {
        max-width: 100%;
      }
    </style>
    ${body}
  `;
}

type HomeProps = {
  activeRegion: string;
  cards: NoticeCard[];
  error: string;
  favoriteIds: Set<string>;
  loading: boolean;
  query: string;
  regions: string[];
  onOpen: (url: string, title?: string, card?: NoticeCard) => Promise<void>;
  onQuery: (value: string) => void;
  onRefresh: () => Promise<void>;
  onRegion: (region: string) => void;
  onShare: (card: NoticeCard) => Promise<void>;
  onToggleFavorite: (card: NoticeCard) => Promise<void>;
};

function HomeView(props: HomeProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const filterDockRef = useRef<HTMLDivElement | null>(null);
  const totalPages = Math.max(1, Math.ceil(props.cards.length / POSTS_PER_PAGE));
  const visibleCards = props.cards.slice((currentPage - 1) * POSTS_PER_PAGE, currentPage * POSTS_PER_PAGE);

  // 풀투리프레시 — 카드 목록 화면에서만 활성. 이미 로딩 중이면 비활성.
  const { distance: pullDistance, refreshing: pullRefreshing, armed: pullArmed } = usePullToRefresh({
    onRefresh: props.onRefresh,
    disabled: props.loading,
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [props.activeRegion, props.query, props.cards.length]);

  function goPage(page: number) {
    const nextPage = Math.min(Math.max(page, 1), totalPages);
    setCurrentPage(nextPage);
    window.requestAnimationFrame(() => {
      const filterDock = filterDockRef.current;
      if (!filterDock) return;
      const headerHeight = document.querySelector(".site-header-v3")?.getBoundingClientRect().height || 0;
      const targetTop = window.scrollY + filterDock.getBoundingClientRect().top - headerHeight + 1;
      window.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
    });
  }

  return (
    <>
      <PullToRefreshIndicator distance={pullDistance} refreshing={pullRefreshing} armed={pullArmed} />
      <section className="web-hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <h1>
              <span className="hero-muted">복잡한</span>
              <br />
              아파트 분양 공고문,
              <br />
              <span>정과장이 쉽게!</span>
              <br />
              정리해드립니다.
            </h1>
            <p>
              한국부동산원 청약홈 데이터를 꼼꼼히 분석했어요.
              <br />
              분양가 · 일정 · 입지 · Q&amp;A를 한 눈에 확인해보세요.
            </p>
          </div>
          <div className="hero-art-anchor" aria-hidden="true">
            <svg className="hero-skyline" viewBox="0 0 1200 240" focusable="false">
              <path d="M0 202 H48 V168 H76 V132 H114 L142 154 V202 H166 V122 L196 92 L226 122 V202 H250 V154 H286 L316 186 V202 H344 V138 L372 108 L400 138 V202 H430 V164 H462 V112 L496 78 H538 L572 110 V202 H594 V92 L628 64 H672 L706 96 V202 H728 V52 H784 V202 H806 V132 L840 96 L876 132 V202 H900 V158 H930 V126 H964 V202 H986 V146 H1014 V112 H1048 V202 H1070 V156 L1098 132 L1128 156 V202 H1150 V164 H1178 V142 H1200" />
              <path d="M48 202 V184 H64 V168" />
              <path d="M142 154 V238" />
              <path d="M226 202 V240" />
              <path d="M286 154 V222" />
              <path d="M344 138 V198" />
              <path d="M400 138 V230" />
              <path d="M462 112 V202" />
              <path d="M572 110 V226" />
              <path d="M594 92 V202" />
              <path d="M706 96 V224" />
              <path d="M806 132 V202" />
              <path d="M876 132 V226" />
              <path d="M986 146 V214" />
              <path d="M1048 112 V202" />
              <path d="M1128 156 V236" />
              <path className="detail" d="M500 94 H562 M500 116 H562 M500 138 H562 M500 160 H562" />
              <path className="detail" d="M620 82 H690 M620 106 H690 M620 130 H690 M620 154 H690" />
              <path className="detail" d="M748 52 V202 M768 52 V202" />
              <path className="detail" d="M840 108 V188 M858 112 V192" />
              <path className="detail" d="M930 126 V202 M948 126 V202" />
              <path className="detail" d="M1014 126 H1048 M1014 146 H1048 M1014 166 H1048" />
              <path className="detail" d="M1098 144 V202" />
              <path className="detail" d="M1170 150 V202" />
            </svg>
          </div>
        </div>
      </section>

      <div className="hero-rule" />

      <section className="reports-main">
        <div className="reports-heading">
          <div>
            <p className="section-eyebrow">ANALYSIS REPORTS</p>
            <h2>분양 정보</h2>
          </div>
          <div className="section-search">
            <label className="search-wrap">
              <Search className="search-icon" size={13} />
              <input
                className="search-input"
                value={props.query}
                onChange={(event) => props.onQuery(event.target.value)}
                placeholder="단지명 검색"
                autoComplete="off"
              />
            </label>
          </div>
        </div>

        <div id="filter-dock" ref={filterDockRef}>
          <div className="mobile-tab-scroll" role="tablist">
            {props.regions.map((region) => (
              <button
                className={region === props.activeRegion ? "tab-btn active" : "tab-btn"}
                key={region}
                onClick={() => props.onRegion(region)}
              >
                {region === PREFERRED_REGION_KEY ? "관심지역" : displayRegion(region)}
              </button>
            ))}
          </div>
          <div id="filter-dock-progress" />
        </div>

        {props.error && (
          <div className="empty-state">
            <p>{props.error}</p>
            <button onClick={() => void props.onRefresh()}>새로고침</button>
          </div>
        )}

        {!props.error && props.loading && (
          <div className="cards-grid">
            <div className="cards-loading">분양 공고 목록을 불러오는 중입니다.</div>
          </div>
        )}

        {!props.error && !props.loading && props.cards.length === 0 && (
          <div className="empty-state">
            <p>선택한 조건의 신규 공고가 없습니다.</p>
          </div>
        )}

        {!props.error && !props.loading && props.cards.length > 0 && (
          <>
            <div className="cards-grid">
              {visibleCards.map((card) => (
                <NoticeCardItem
                  card={card}
                  isFavorite={props.favoriteIds.has(card.notice_id)}
                  key={card.notice_id}
                  onOpen={props.onOpen}
                  onShare={props.onShare}
                  onToggleFavorite={props.onToggleFavorite}
                />
              ))}
            </div>
            {totalPages > 1 && (
              <Pagination currentPage={currentPage} totalPages={totalPages} onPage={goPage} />
            )}
          </>
        )}
      </section>
    </>
  );
}

function Pagination({
  currentPage,
  onPage,
  totalPages
}: {
  currentPage: number;
  onPage: (page: number) => void;
  totalPages: number;
}) {
  const blockSize = 5;
  const startPage = Math.floor((currentPage - 1) / blockSize) * blockSize + 1;
  const endPage = Math.min(totalPages, startPage + blockSize - 1);
  const pages = Array.from({ length: endPage - startPage + 1 }, (_, index) => startPage + index);

  return (
    <nav className="pagination" aria-label="공고 목록 페이지">
      {startPage > 1 && (
        <button onClick={() => onPage(startPage - 1)} aria-label="이전 5페이지">
          ‹
        </button>
      )}
      {pages.map((page) => (
        <button
          className={page === currentPage ? "active" : ""}
          key={page}
          onClick={() => onPage(page)}
          aria-current={page === currentPage ? "page" : undefined}
        >
          {page}
        </button>
      ))}
      {endPage < totalPages && (
        <button onClick={() => onPage(endPage + 1)} aria-label="다음 5페이지">
          ›
        </button>
      )}
    </nav>
  );
}

type CardItemProps = {
  card: NoticeCard;
  isFavorite: boolean;
  onOpen: (url: string, title?: string, card?: NoticeCard) => Promise<void>;
  onShare: (card: NoticeCard) => Promise<void>;
  onToggleFavorite: (card: NoticeCard) => Promise<void>;
};

function NoticeCardItem({ card, isFavorite, onOpen, onShare, onToggleFavorite }: CardItemProps) {
  const sanitizedHtml = sanitizeCardHtml(card);
  return (
    <div className="app-card-shell">
      <div
        className="web-card-click"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void onOpen(absolutePostUrl(card.post_url), card.apt_name, card);
        }}
        dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
      />
      <div className="app-card-tools" onClick={(event) => event.stopPropagation()}>
        <button
          className={isFavorite ? "favorite-action active" : "favorite-action"}
          onClick={() => void onToggleFavorite(card)}
          aria-label="즐겨찾기"
        >
          {isFavorite ? <BookmarkCheck size={20} /> : <Bookmark size={20} />}
        </button>
        <button onClick={() => void onShare(card)} aria-label="공유">
          <Share2 size={20} />
        </button>
      </div>
    </div>
  );
}

function FavoritesView({
  favorites,
  onOpen,
  onRemove,
  onShare
}: {
  favorites: FavoriteNotice[];
  onOpen: (url: string, title?: string, card?: NoticeCard) => Promise<void>;
  onRemove: (noticeId: string) => void;
  onShare: (card: NoticeCard) => Promise<void>;
}) {
  if (favorites.length === 0) {
    return (
      <section className="screen empty-state">
        <p>아직 저장한 공고가 없습니다.</p>
      </section>
    );
  }

  return (
    <section className="screen notice-list">
      {favorites.map((favorite) => (
        <article className="notice-card" key={favorite.notice_id}>
          <button className="card-main" onClick={() => void onOpen(favorite.post_url, favorite.apt_name, favorite)}>
            <span className="notice-region">{favorite.region}</span>
            <h2>{favorite.apt_name}</h2>
            <div className="notice-meta">
              <span>공고일 {favorite.notice_date || "-"}</span>
              <span>{new Date(favorite.saved_at).toLocaleDateString("ko-KR")} 저장</span>
            </div>
            {favorite.price_range && <p className="price-chip">{favorite.price_range}</p>}
          </button>
          <div className="card-tools">
            <button onClick={() => onRemove(favorite.notice_id)} aria-label="삭제">
              <Trash2 size={20} />
            </button>
            <button onClick={() => void onShare(favorite)} aria-label="공유">
              <Share2 size={20} />
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}

function SettingsView({
  favorites,
  installedVersion,
  latestVersion,
  page,
  settings,
  onClear,
  onOpen,
  onPage,
  onPush,
  onQuietHours,
  onRegion,
  onRemoveFavorite,
  onShare,
  onUpdate
}: {
  favorites: FavoriteNotice[];
  installedVersion: string;
  latestVersion: string;
  page: SettingsPage;
  settings: UserSettings;
  onClear: () => Promise<void>;
  onOpen: (url: string, title?: string, card?: NoticeCard) => Promise<void>;
  onPage: (page: SettingsPage) => void;
  onPush: () => Promise<void>;
  onQuietHours: (enabled: boolean) => void;
  onRegion: (region: string) => Promise<void>;
  onRemoveFavorite: (noticeId: string) => void;
  onShare: (card: NoticeCard) => Promise<void>;
  onUpdate: () => void;
}) {
  const [favoriteSort, setFavoriteSort] = useState<FavoriteSort>("newest");
  const sortedFavorites = useMemo(() => {
    const next = [...favorites];
    if (favoriteSort === "nameAsc") {
      return next.sort((a, b) => a.apt_name.localeCompare(b.apt_name, "ko-KR"));
    }
    if (favoriteSort === "nameDesc") {
      return next.sort((a, b) => b.apt_name.localeCompare(a.apt_name, "ko-KR"));
    }
    if (favoriteSort === "oldest") {
      return next.sort((a, b) => new Date(a.saved_at).getTime() - new Date(b.saved_at).getTime());
    }
    return next.sort((a, b) => new Date(b.saved_at).getTime() - new Date(a.saved_at).getTime());
  }, [favoriteSort, favorites]);
  const hasUpdate = installedVersion !== latestVersion;

  if (page === "notifications") {
    return (
      <section className="screen settings-screen">
        <section className="settings-list settings-flat-list">
          <div className="settings-row">
            <div>
              <strong>신규 공고 알림 받기</strong>
              <span>{settings.pushEnabled ? "알림 켜짐" : "알림 꺼짐"}</span>
            </div>
            <button className={settings.pushEnabled ? "switch on" : "switch"} onClick={() => void onPush()}>
              <span />
            </button>
          </div>

          <div className="settings-row">
            <div>
              <strong>심야 시간에도 알림 받기</strong>
              <span>{settings.quietHoursEnabled ? "심야시간 알림 차단 중" : "심야시간 알림 허용 중"}</span>
              <span>22:00 ~ 07:00</span>
            </div>
            <button
              className={!settings.quietHoursEnabled ? "switch on" : "switch"}
              onClick={() => onQuietHours(!settings.quietHoursEnabled)}
            >
              <span />
            </button>
          </div>

          <button className="settings-link-row settings-nav-row" onClick={() => onPage("regions")}>
            <div>
              <strong>관심지역 설정</strong>
              <span>{settings.regions.length > 0 ? `${settings.regions.length}개 지역 선택됨` : "전체 지역 알림"}</span>
            </div>
            <ChevronRight size={18} />
          </button>
        </section>
      </section>
    );
  }

  if (page === "regions") {
    return (
      <section className="screen settings-screen">
        <p className="settings-page-copy">홈에서 우선 표시할 관심지역을 선택해주세요.</p>
        <section className="settings-list settings-open-panel">
          <div className="settings-section">
            <div className="settings-check-grid">
              {REGIONS.map((region) => {
                const selected = settings.regions.includes(region);
                return (
                  <button
                    className={selected ? "settings-check selected" : "settings-check"}
                    key={region}
                    onClick={() => void onRegion(region)}
                  >
                    <span>{selected && <Check size={14} />}</span>
                    {region}
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      </section>
    );
  }

  if (page === "favorites") {
    return (
      <section className="screen settings-screen">
        <p className="settings-page-copy">자주 보는 공고를 관리할 수 있어요.</p>

        <section className="settings-list settings-open-panel">
          <div className="settings-section">
            <div className="settings-section-head">
              <div>
                <strong>즐겨찾기 설정한 공고 리스트</strong>
                <span>{favorites.length}개 저장됨</span>
              </div>
            </div>

            <div className="sort-control" role="tablist" aria-label="즐겨찾기 정렬">
              {[
                ["nameAsc", "이름순↑"],
                ["nameDesc", "이름순↓"],
                ["newest", "최신순"],
                ["oldest", "오래된순"]
              ].map(([value, label]) => (
                <button
                  className={favoriteSort === value ? "active" : ""}
                  key={value}
                  onClick={() => setFavoriteSort(value as FavoriteSort)}
                >
                  {label}
                </button>
              ))}
            </div>

            {sortedFavorites.length === 0 ? (
              <p className="settings-empty">아직 저장한 공고가 없습니다.</p>
            ) : (
              <div className="settings-favorites">
                {sortedFavorites.map((favorite) => (
                  <article className="settings-favorite-card" key={favorite.notice_id}>
                    <button
                      className="settings-favorite-main"
                      onClick={() => void onOpen(favorite.post_url, favorite.apt_name, favorite)}
                    >
                      <span>{favorite.region}</span>
                      <strong>{favorite.apt_name}</strong>
                      <small>{new Date(favorite.saved_at).toLocaleDateString("ko-KR")} 저장</small>
                    </button>
                    <div className="settings-favorite-actions">
                      <button onClick={() => void onShare(favorite)} aria-label="공유">
                        <Share2 size={17} />
                      </button>
                      <button onClick={() => onRemoveFavorite(favorite.notice_id)} aria-label="삭제">
                        <Trash2 size={17} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      </section>
    );
  }

  return (
    <section className="screen settings-screen">
      <section className="settings-list settings-flat-list">
        <button className="settings-link-row settings-nav-row" onClick={() => onPage("regions")}>
          <div>
            <strong>관심지역 설정</strong>
            <span>{settings.regions.length > 0 ? `${settings.regions.length}개 지역 선택됨` : "전체 지역 표시"}</span>
          </div>
          <ChevronRight size={18} />
        </button>

        <button className="settings-link-row settings-nav-row" onClick={() => onPage("favorites")}>
          <div>
            <strong>즐겨찾기 관리</strong>
            <span>{favorites.length}개 저장됨</span>
          </div>
          <ChevronRight size={18} />
        </button>

        <button className="settings-link-row" onClick={() => void onOpen(`${SITE_ORIGIN}/terms.html`, "이용약관")}>
          <span>이용약관</span>
          <ChevronRight size={18} />
        </button>
        <button className="settings-link-row" onClick={() => void onOpen(`${SITE_ORIGIN}/privacy.html`, "개인정보 처리방침")}>
          <span>개인정보 처리방침</span>
          <ChevronRight size={18} />
        </button>
        <div className="settings-row version-row">
          <div>
            <strong>앱 정보</strong>
            <span>현재 {installedVersion} · 최신 {latestVersion}</span>
          </div>
          <button className="update-button" disabled={!hasUpdate} onClick={onUpdate}>
            업데이트
          </button>
        </div>
        <button className="settings-reset" onClick={() => void onClear()}>
          저장 데이터 초기화
        </button>
      </section>
    </section>
  );
}

type PullIndicatorProps = {
  distance: number;
  refreshing: boolean;
  armed: boolean;
};

function PullToRefreshIndicator({ distance, refreshing, armed }: PullIndicatorProps) {
  // distance 0 일 때 화면에서 숨김. 진행 중엔 인디케이터 고정.
  if (distance <= 0 && !refreshing) return null;
  const translateY = Math.max(0, distance);
  const opacity = Math.min(1, distance / 64);
  const label = refreshing ? "새로고침 중…" : armed ? "놓으면 새로고침" : "당겨서 새로고침";
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        pointerEvents: "none",
        transform: `translateY(${translateY - 40}px)`,
        transition: refreshing ? "transform 180ms ease" : "none",
        zIndex: 60,
      }}
    >
      <div
        style={{
          background: "rgba(44, 41, 37, 0.92)",
          color: "#fff",
          fontSize: 13,
          fontWeight: 600,
          padding: "8px 14px",
          borderRadius: 999,
          boxShadow: "0 4px 16px rgba(0,0,0,0.18)",
          opacity,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span
          style={{
            display: "inline-block",
            width: 14,
            height: 14,
            border: "2px solid rgba(255,255,255,0.35)",
            borderTopColor: "#fff",
            borderRadius: "50%",
            animation: refreshing ? "ptr-spin 700ms linear infinite" : "none",
            transform: refreshing ? "none" : `rotate(${Math.min(360, distance * 5)}deg)`,
            transition: refreshing ? "none" : "transform 80ms linear",
          }}
        />
        {label}
      </div>
      <style>{`@keyframes ptr-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default App;
