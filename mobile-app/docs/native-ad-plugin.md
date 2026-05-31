# 네이티브 고급형 광고(인피드) — 카드 그리드 통합

메인 카드 그리드 안에 **AdMob 네이티브 고급형(Native Advanced)** 광고를 카드와
유사한 모양으로 끼워 넣기 위한 커스텀 Capacitor 플러그인(`NativeAd`) 설계·구현·검증 문서.

## 왜 커스텀 플러그인인가

`@capacitor-community/admob`(현재 의존성)는 배너·전면·보상·앱오픈만 지원하고
**네이티브 광고는 미지원**(업스트림 이슈 #110, 미해결)이다. 따라서 네이티브 고급형은
이 전용 플러그인이 담당한다.

## 렌더링 모델 (핵심)

WebView 안의 React 카드 그리드에 SDK 네이티브 뷰를 직접 인라인할 수 없으므로,
**"placeholder + 오버레이"** 방식을 쓴다.

```
[ React 그리드 ]                 [ 네이티브 레이어 ]
 ┌──────────┐
 │ 카드 1    │
 ├──────────┤
 │ 카드 …    │
 ├──────────┤
 │ NativeAdSlot   ←─ docTop/크기 보고 ─→  NativeAdView(SDK) 가
 │ (투명 자리)│                            이 위치에 오버레이로 겹쳐 그림
 ├──────────┤
 │ 카드 …    │
 └──────────┘
```

- **JS(`NativeAdSlot.tsx`)**: 그리드에서 카드 한 칸 크기의 투명 자리만 차지하고,
  자신의 문서 좌표(`docTop = rect.top + scrollY`)·크기(CSS px)를 네이티브로 보고한다.
- **네이티브(Android/iOS)**: SDK 가 그린 `NativeAdView`를 WebView 위 오버레이로 추가하고,
  WebView의 스크롤(`scrollY` / `contentOffset`)을 **직접 추적**해 placeholder 위치에
  정확히 겹쳐 그린다. 화면 밖으로 나가면 숨긴다.
- 스크롤 추적은 네이티브가 담당하므로 매 프레임 JS↔네이티브 통신이 없다(부드러움).
- **AdMob 정책 준수**: 광고 에셋·노출·클릭 트래킹은 전부 SDK의 `NativeAdView`가 처리한다.
  (에셋 데이터만 JS로 넘겨 HTML로 그리는 방식은 정책 위반 → 사용 안 함)
- 우상단 **"광고" 배지**는 정책상 필수이며 제거 금지.

## 구성 파일

| 파일 | 역할 |
|---|---|
| `src/native-ad/plugin.ts` | JS 플러그인 인터페이스(`registerPlugin<NativeAdPlugin>`) |
| `src/native-ad/NativeAdSlot.tsx` | 그리드 안 placeholder + 좌표 보고 React 컴포넌트 |
| `src/App.tsx` | `AD_EVERY_N_CARDS`(=6)마다 `NativeAdSlot` 삽입 |
| `src/admob.ts` | `getNativeAdConfig()` — 네이티브 광고 단위 ID/npa 제공 |
| `src/styles.css` | `.native-ad-slot` placeholder 스켈레톤 |
| `android/.../NativeAdPlugin.kt` | Android 네이티브 광고 로드/오버레이/스크롤 추적 |
| `android/.../res/layout/native_ad_card.xml` | Android 광고 카드 레이아웃(웹 카드 모양) |
| `android/.../res/drawable/bg_native_ad_*.xml` | 카드/CTA/배지 배경 |
| `ios/App/App/NativeAdPlugin.swift` | iOS 동등 구현 |

## 광고 단위 ID

`admob.ts`에 프로덕션 폴백으로 박혀 있고, `.env`로 덮어쓸 수 있다.

- 네이티브 고급형(현재 단일 단위): `ca-app-pub-8234120897033274/6818939220`
- 테스트: Android `…/2247696110`, iOS `…/3986624511`
- 앱 ID(이미 설정됨): Android `…~3125849648`(Manifest), iOS `…~4486344416`(Info.plist)
- `.env`: `VITE_ADMOB_NATIVE_ID_ANDROID`, `VITE_ADMOB_NATIVE_ID_IOS`

## 빌드/검증 절차 (⚠️ 실기기 필요)

웹/React/TS 레이어는 CI에서 검증되지만(타입체크·vite build 통과), **네이티브 코드는
실기기 빌드로 검증해야 한다.**

```bash
cd mobile-app
npm run build          # tsc + vite build (dist/ 생성)
npx cap sync           # 네이티브 프로젝트에 동기화 + pod install / gradle 반영
```

### Android
1. `npx cap open android` → Android Studio에서 빌드.
2. `play-services-ads:23.6.0` 의존성이 추가됨(`app/build.gradle`) — Gradle sync 필요.
3. `MainActivity`에 `registerPlugin(NativeAdPlugin.class)` 등록됨.
4. 테스트 광고로 먼저 확인(`VITE_ADMOB_USE_TEST=true` 또는 dev 빌드).

### iOS
1. **`NativeAdPlugin.swift`를 Xcode App 타깃에 추가해야 한다**
   (`npx cap sync`는 임의 swift 파일을 타깃에 자동 추가하지 않음).
   Xcode → App 그룹에 파일 추가 → Target Membership: App 체크.
2. `Podfile`에 `pod 'Google-Mobile-Ads-SDK'` 추가됨 → `npx cap sync`(pod install) 필요.
3. SDK 11+ prefix-free Swift API(`NativeAd`/`AdLoader`/`Request`/`NativeAdView`/`MediaView`)
   사용. 더 낮은 SDK면 `GAD` 접두사로 교체.

### 검증 체크리스트
- [ ] 그리드 6번째 카드 뒤에 광고 카드가 카드와 같은 라운드/테두리로 표시
- [ ] 우상단 "광고" 배지 노출
- [ ] 스크롤 시 광고가 카드와 함께 자연스럽게 따라 움직임(어긋남·잔상 없음)
- [ ] 화면 밖으로 나가면 숨겨짐(상단/하단 경계)
- [ ] 지역 필터/페이지 전환 시 슬롯이 재생성되고 위치가 갱신됨
- [ ] 상세 화면 진입 시 그리드 언마운트 → 광고 제거됨
- [ ] 클릭 시 광고 랜딩으로 이동, 노출/클릭이 AdMob 콘솔에 집계됨
- [ ] 회전(orientation) 시 위치 재계산

## 알려진 리스크 / TODO
- **iOS Podfile에 `@capacitor-community/admob` pod이 보이지 않음** — iOS의 기존 배너/전면이
  실제로 동작하는지, admob pod 통합 상태를 함께 점검할 것. 네이티브 SDK는 별도로 추가했다.
- 오버레이 좌표 동기화는 스크롤 성능에 민감 → 저사양 기기에서 잔상/지터 여부 확인.
- `AD_EVERY_N_CARDS`(=6) 빈도는 정책·UX 보며 조정.
- 페이지당 첫 광고가 6번째 뒤이므로, 한 페이지(12개) 기준 광고 1개. 필요 시 12번째 뒤 추가.
