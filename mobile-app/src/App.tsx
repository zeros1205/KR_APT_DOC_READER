import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bell,
  Bookmark,
  BookmarkCheck,
  Check,
  Home,
  Menu,
  RefreshCw,
  Search,
  Settings,
  Share2,
  Trash2,
  X
} from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { Browser } from "@capacitor/browser";
import { PushNotifications } from "@capacitor/push-notifications";
import { Share } from "@capacitor/share";
import { absolutePostUrl, extractPriceRange, fetchPostHtml, fetchPostsIndex, SITE_ORIGIN } from "./api";
import introBackground from "./assets/intro_without_text.png";
import {
  defaultSettings,
  loadFavorites,
  loadSettings,
  resetLocalData,
  saveFavorites,
  saveSettings
} from "./storage";
import type { FavoriteNotice, NoticeCard, UserSettings } from "./types";

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

type View = "home" | "favorites" | "settings" | "detail";
type DetailPage = {
  url: string;
  title: string;
  card?: NoticeCard;
  returnView?: Exclude<View, "detail">;
};

function normalizeRegion(region: string): string {
  return region.replace("특별시", "").replace("광역시", "").trim();
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

function sanitizeCardHtml(card: NoticeCard): string {
  const html = card.html || "";
  return html
    .replace(/\sonclick="[^"]*"/g, "")
    .replace(/\shref="([^"]+)"/g, (_, href: string) => ` href="${absolutePostUrl(href)}"`);
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
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const lastHomeBackAtRef = useRef(0);
  const toastTimerRef = useRef<number | null>(null);

  useEffect(() => {
    void Promise.all([loadFavorites(), loadSettings()]).then(([savedFavorites, savedSettings]) => {
      setFavorites(savedFavorites);
      setSettings(savedSettings);
    });
    void refreshPosts();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setIntroVisible(false), 1500);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    const registration = CapacitorApp.addListener("backButton", ({ canGoBack }) => {
      if (menuOpen) {
        setMenuOpen(false);
        return;
      }
      if (view === "detail") {
        goBackFromDetail();
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
    };
  }, [detailPage, menuOpen, view]);

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
    return ["전체", ...ordered];
  }, [cards]);

  const filteredCards = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return cards.filter((card) => {
      const matchesRegion =
        activeRegion === "전체" || normalizeRegion(card.region).includes(normalizeRegion(activeRegion));
      const matchesQuery =
        !keyword ||
        card.apt_name.toLowerCase().includes(keyword) ||
        card.region.toLowerCase().includes(keyword) ||
        card.notice_id.includes(keyword);
      return matchesRegion && matchesQuery;
    });
  }, [activeRegion, cards, query]);

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

  async function toggleRegion(region: string) {
    const exists = settings.regions.includes(region);
    await updateSettings({
      ...settings,
      regions: exists ? settings.regions.filter((item) => item !== region) : [...settings.regions, region]
    });
  }

  async function enablePush() {
    if (!Capacitor.isNativePlatform()) {
      await updateSettings({ ...settings, pushEnabled: !settings.pushEnabled });
      return;
    }
    const permission = await PushNotifications.requestPermissions();
    if (permission.receive === "granted") {
      await PushNotifications.register();
      await updateSettings({ ...settings, pushEnabled: true });
    }
  }

  async function openUrl(url: string, title = "정과장의 청약노트", card?: NoticeCard) {
    if (isApplyHomeCard(card)) {
      const targetUrl = card?.notice_url || url;
      const ok = window.confirm(
        "이 공공분양 공고는 청약Home에서 자세히 확인할 수 있어요.\n청약Home 공고 페이지로 이동할까요?"
      );
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
    await Share.share({
      title: card.apt_name,
      text: `${card.apt_name} 분양 공고`,
      url
    });
  }

  async function clearLocalData() {
    await resetLocalData();
    setFavorites([]);
    setSettings(defaultSettings);
  }

  return (
    <main className="app-shell">
      {introVisible && <IntroScreen />}
      {view === "detail" && detailPage ? (
        <DetailNav
          page={detailPage}
          isFavorite={detailPage.card ? favoriteIds.has(detailPage.card.notice_id) : false}
          onBack={goBackFromDetail}
          onShare={() =>
            detailPage.card
              ? void shareCard(detailPage.card)
              : void Share.share({ title: detailPage.title, url: detailPage.url })
          }
          onToggleFavorite={() => detailPage.card && void toggleFavorite(detailPage.card)}
        />
      ) : (
        <SiteNav view={view} onRefresh={refreshPosts} />
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
          settings={settings}
          onClear={clearLocalData}
          onOpen={openUrl}
          onPush={enablePush}
          onQuietHours={(enabled) => void updateSettings({ ...settings, quietHoursEnabled: enabled })}
          onRegion={toggleRegion}
        />
      )}

      {view === "detail" && detailPage && <DetailView page={detailPage} />}

      {menuOpen && <button className="fab-backdrop" aria-label="메뉴 닫기" onClick={() => setMenuOpen(false)} />}

      <nav className={`fab-menu ${menuOpen ? "open" : ""}`} aria-label="플로팅 메뉴">
        {menuOpen && (
          <div className="fab-actions">
            <button onClick={() => { setView("home"); setMenuOpen(false); }}>
              <Home size={18} /> 홈
            </button>
            <button onClick={() => { setView("favorites"); setMenuOpen(false); }}>
              <Bookmark size={18} /> 즐겨찾기
            </button>
            <button onClick={() => { setView("settings"); setMenuOpen(false); }}>
              <Settings size={18} /> 설정
            </button>
          </div>
        )}
        <button className="fab-main" onClick={() => setMenuOpen((open) => !open)} aria-label="메뉴">
          {menuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </nav>

      {toastMessage && <div className="app-toast">{toastMessage}</div>}
      <div className="system-nav-scrim" aria-hidden="true" />
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

function SiteNav({ view, onRefresh }: { view: View; onRefresh: () => Promise<void> }) {
  return (
    <header className="site-header-v3">
      <div className="site-header-v3-inner">
        <button className="site-header-v3-brand" type="button" aria-label="정과장의 청약노트">
          <img src={`${SITE_ORIGIN}/app_logo_80x80_rounded.png`} alt="" className="site-header-v3-logo" />
          <span>
            <span className="site-header-v3-title">
              {view === "home" ? "정과장의 청약노트" : view === "favorites" ? "즐겨찾기" : "설정"}
            </span>
            <span className="site-header-v3-sub">APT-NOTE.COM</span>
          </span>
        </button>
        <div className="nav-actions">
          <button className="nav-refresh" onClick={() => void onRefresh()} aria-label="새로고침">
            <RefreshCw size={17} />
          </button>
        </div>
      </div>
    </header>
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
        <span>{page.title}</span>
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

  useEffect(() => {
    let cancelled = false;
    setHtml("");
    setError("");
    void fetchPostHtml(page.url)
      .then((postHtml) => {
        if (!cancelled) setHtml(toAppPostDocument(postHtml, page.url));
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
    <section className="detail-screen">
      <iframe title={page.title} srcDoc={html} />
    </section>
  );
}

function toAppPostDocument(html: string, url: string): string {
  const baseHref = url.endsWith("/") ? url : url.replace(/[^/]*$/, "");
  const appStyle = `
    <base href="${baseHref}">
    <style>
      .site-header-v3,
      #post-compact-bar { display: none !important; }
      body { padding-top: 0 !important; }
      html { scroll-padding-top: 0 !important; }
    </style>
  `;
  if (html.includes("</head>")) {
    return html.replace("</head>", `${appStyle}</head>`);
  }
  return `<!doctype html><html><head>${appStyle}</head><body>${html}</body></html>`;
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
  return (
    <>
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

        <div id="filter-dock">
          <div className="mobile-tab-scroll" role="tablist">
            {props.regions.map((region) => (
              <button
                className={region === props.activeRegion ? "tab-btn active" : "tab-btn"}
                key={region}
                onClick={() => props.onRegion(region)}
              >
                {displayRegion(region)}
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
          <div className="cards-grid">
            {props.cards.map((card) => (
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
        )}
      </section>
    </>
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
        onClick={() => void onOpen(absolutePostUrl(card.post_url), card.apt_name, card)}
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
  settings,
  onClear,
  onOpen,
  onPush,
  onQuietHours,
  onRegion
}: {
  settings: UserSettings;
  onClear: () => Promise<void>;
  onOpen: (url: string, title?: string, card?: NoticeCard) => Promise<void>;
  onPush: () => Promise<void>;
  onQuietHours: (enabled: boolean) => void;
  onRegion: (region: string) => Promise<void>;
}) {
  return (
    <section className="screen settings-screen">
      <section className="panel">
        <div className="panel-title">
          <Bell size={18} />
          <h2>알림</h2>
        </div>
        <label className="switch-row">
          <span>앱 푸시 알림</span>
          <button className={settings.pushEnabled ? "switch on" : "switch"} onClick={() => void onPush()}>
            <span />
          </button>
        </label>
        <label className="switch-row">
          <span>오후 10시부터 오전 8시까지 조용한 시간</span>
          <button
            className={settings.quietHoursEnabled ? "switch on" : "switch"}
            onClick={() => onQuietHours(!settings.quietHoursEnabled)}
          >
            <span />
          </button>
        </label>
      </section>

      <section className="panel">
        <div className="panel-title">
          <Settings size={18} />
          <h2>관심지역</h2>
        </div>
        <div className="region-grid">
          {REGIONS.map((region) => {
            const selected = settings.regions.includes(region);
            return (
              <button className={selected ? "selected" : ""} key={region} onClick={() => void onRegion(region)}>
                {selected && <Check size={15} />}
                {region}
              </button>
            );
          })}
        </div>
      </section>

      <section className="panel link-panel">
        <button onClick={() => void onOpen(`${SITE_ORIGIN}/privacy.html`, "개인정보 보호정책")}>개인정보 보호정책</button>
        <button onClick={() => void onOpen(`${SITE_ORIGIN}/terms.html`, "이용약관")}>이용약관</button>
        <button onClick={() => void onClear()}>저장 데이터 초기화</button>
      </section>

      <p className="version">앱 버전 0.1.0</p>
    </section>
  );
}

export default App;
