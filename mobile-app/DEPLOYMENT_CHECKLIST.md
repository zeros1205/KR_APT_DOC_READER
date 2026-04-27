# Android 배포 최종 체크리스트

**목표**: Android 앱을 Google Play Store에 배포  
**예상 소요 시간**: 2-3주  
**우선순위**: Android 우선 → iOS는 나중에 결정

---

## 📋 1단계: 개발 환경 준비 (1일)

### 1.1 필수 도구 설치
**참고**: [ANDROID_BUILD_GUIDE.md](./ANDROID_BUILD_GUIDE.md#1-개발-환경-준비)

- [ ] JDK 17 설치 및 확인
  ```bash
  java -version
  # openjdk version "17.x.x" 이상
  ```

- [ ] Android Studio 설치 (4-5GB)
  - https://developer.android.com/studio

- [ ] Android SDK 설정
  - Android Studio 열기
  - Tools → SDK Manager
  - SDK Platforms: Android 13 (API 33) 이상 설치
  - SDK Tools: 최신 버전 설치

- [ ] 환경 변수 설정 (중요!)
  ```bash
  # Windows PowerShell
  $env:ANDROID_HOME = "C:\Users\YourName\AppData\Local\Android\Sdk"
  echo $env:ANDROID_HOME  # 확인
  
  # macOS/Linux
  export ANDROID_HOME=$HOME/Android/Sdk
  echo $ANDROID_HOME
  ```

### 1.2 프로젝트 준비

- [ ] 저장소 최신 버전 가져오기
  ```bash
  git pull origin claude/review-recent-changes-9nGMM
  ```

- [ ] 의존성 설치
  ```bash
  cd mobile-app
  npm install
  ```

- [ ] Android 플랫폼 추가 (처음만)
  ```bash
  npx capacitor add android
  ```

---

## 🔐 2단계: Firebase 설정 (1일)

**참고**: [FIREBASE_SETUP.md](./FIREBASE_SETUP.md)

### 2.1 Firebase 프로젝트 생성
- [ ] Firebase Console 접속 (https://console.firebase.google.com)
- [ ] Google 계정으로 로그인
- [ ] 새 프로젝트 생성
  ```
  이름: apt-note
  분석: 사용 (권장)
  위치: 대한민국
  ```

### 2.2 Android 앱 등록
- [ ] Firebase에서 Android 앱 추가
  ```
  패키지 이름: com.apta.note
  ```

- [ ] `google-services.json` 다운로드
  ```bash
  # 다운로드 후 이 위치로 이동
  mobile-app/android/app/google-services.json
  
  # 확인
  ls mobile-app/android/app/google-services.json
  ```

- [ ] 설정 파일이 git 무시 목록에 있는지 확인
  ```bash
  # android/app/.gitignore 또는 .gitignore 확인
  # google-services.json은 커밋하지 않기 (보안)
  ```

### 2.3 Firebase 플러그인 설치
- [ ] npm 패키지 설치 (이미 완료됨)
  ```bash
  npm list @capacitor-firebase/messaging
  # ^5.4.0 이상 설치되어 있어야 함
  ```

---

## 🔑 3단계: 앱 서명 설정 (1-2시간)

**참고**: [ANDROID_BUILD_GUIDE.md#23-서명-설정](./ANDROID_BUILD_GUIDE.md#23-서명-설정)

### 3.1 키스토어 생성 (첫 배포만)

```bash
cd mobile-app/android

# 강력한 비밀번호 설정 (20자 이상 권장)
keytool -genkey -v -keystore apt-note.jks -keyalg RSA -keysize 2048 -validity 10000 -alias apt-note-key

# 입력 내용:
# 키스토어 비밀번호: ________________ (기억!)
# 키 비밀번호: ________________ (같은 비밀번호 OK)
# 이름: Your Name
# 조직: Your Organization
# 도시: Seoul
# 주/지역: Seoul
# 국가: KR
```

**생성 확인**:
```bash
ls -la mobile-app/android/apt-note.jks
# 약 2KB 파일이 생성되어야 함
```

### 3.2 서명 설정 추가

`mobile-app/android/app/build.gradle` 편집:

```gradle
android {
    signingConfigs {
        release {
            storeFile file("../apt-note.jks")
            storePassword System.getenv("KEYSTORE_PASSWORD")
            keyAlias System.getenv("KEY_ALIAS")
            keyPassword System.getenv("KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
```

- [ ] 환경 변수 설정 (매번 빌드할 때)
  ```bash
  # Windows PowerShell
  $env:KEYSTORE_PASSWORD = "your_keystore_password"
  $env:KEY_ALIAS = "apt-note-key"
  $env:KEY_PASSWORD = "your_key_password"
  
  # macOS/Linux
  export KEYSTORE_PASSWORD="your_keystore_password"
  export KEY_ALIAS="apt-note-key"
  export KEY_PASSWORD="your_key_password"
  ```

---

## 🏗️ 4단계: 로컬 빌드 테스트 (1-2시간)

### 4.1 웹 리소스 빌드

```bash
cd mobile-app

# React 앱 프로덕션 빌드
npm run build

# 확인
ls -la public/
# index.html, manifest.json 등이 있어야 함
```

### 4.2 Capacitor 동기화

```bash
npx capacitor sync android

# 또는
npm run cap:build
```

### 4.3 Release AAB 빌드

```bash
cd mobile-app/android

# 환경 변수 설정 (위의 3.2 참조)

# AAB 빌드 (Google Play Store 필수)
./gradlew bundleRelease

# 또는 APK (테스트용)
./gradlew assembleRelease

# 확인
ls -la app/build/outputs/bundle/release/app-release.aab
```

**빌드 완료**: `app-release.aab` 파일이 생성되어야 함 (약 50-100MB)

### 4.4 디버그 빌드 테스트 (선택)

실제 기기나 에뮬레이터에서 테스트하려면:

```bash
cd mobile-app/android

# Debug APK 빌드
./gradlew assembleDebug

# 결과
ls app/build/outputs/apk/debug/app-debug.apk

# 기기에 설치 (기기 연결 필요)
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

---

## 📱 5단계: Google Play Console 등록 (1-2시간)

**참고**: [FIREBASE_SETUP.md#4-google-play-console-설정](./FIREBASE_SETUP.md#4-google-play-console-설정)

### 5.1 개발자 계정 생성

- [ ] Google Play Console 접속
  - https://play.google.com/console

- [ ] Google 계정 로그인

- [ ] 개발자 등록
  - 비용: **$25** (일회성)
  - 필요: 신용카드, 개인정보

- [ ] 승인 대기 (보통 즉시)

### 5.2 앱 만들기

**Play Console → 새 앱 만들기**

- [ ] 앱 이름: `apt-note` 또는 `청약홈 - apt-note`
- [ ] 기본 언어: `한국어`
- [ ] 앱 유형: `무료`
- [ ] 생성

---

## 📝 6단계: 스토어 정보 입력 (2-3시간)

**참고**: [FIREBASE_SETUP.md#앱-정보-스토어-정보](./FIREBASE_SETUP.md#61-필수-이미지)

### 6.1 기본 정보

**Play Console → 앱 정보 → 스토어 정보**

| 항목 | 내용 | 길이 제한 |
|------|------|---------|
| 앱 이름 | 청약홈 - apt-note | 40자 |
| 짧은 설명 | 청약홈 공공데이터 기반 아파트 분양공고 | 80자 |
| 설명 | (아래 참조) | 4000자 |

**설명 예시** (약 1000자):
```
🏢 청약홈 공공데이터 기반 아파트 분양공고 정보 앱

✨ 주요 기능:
• 최신 분양공고 검색: 모든 지역의 최신 아파트 분양공고를 한 곳에서 확인
• 관심 지역 설정: 최대 3개 지역 선택 후 새로운 공고 알림 수신
• 즐겨찾기: 관심 있는 아파트를 저장하고 언제든 확인
• 오프라인 모드: 네트워크가 없어도 저장된 공고 확인 가능
• 조용한 시간 설정: 심야시간(22:00~08:00) 자동 알림 조용히 설정

📊 데이터:
한국부동산원 청약홈 공공데이터 (매일 업데이트)

⚠️ 주의:
본 앱의 정보는 청약홈 공공데이터 기반으로 제공되며, 정확한 공고 정보는 청약홈 공식사이트(applyhome.co.kr)에서 확인하시기 바랍니다.
```

### 6.2 개발자 정보

- [ ] 개발자 이름
- [ ] 이메일 (지원 요청 받을 이메일)
- [ ] 전화번호 (선택)

### 6.3 필수 정보

**Play Console → 앱 정보**

- [ ] 개인정보처리방침 URL
  ```
  예: https://apt-note.com/privacy
  최소 200자 이상
  
  포함 내용:
  - 수집 항목 (FCM 토큰, 기기 ID, 관심지역)
  - 수집 목적 (푸시 알림, 기기 식별)
  - 보유 기간 (앱 삭제 시 즉시 삭제)
  - 사용자 권리 (언제든 거부 가능)
  ```

- [ ] 이용약관 (선택, 있으면 등록)

### 6.4 콘텐츠 등급

**Play Console → 앱 정보 → 콘텐츠 등급**

- [ ] 자체 평가 설문지 작성
  ```
  예상 시간: 5-10분
  
  질문 예:
  - 폭력성: 아니요
  - 성인 콘텐츠: 아니요
  - 위험 물질: 아니요
  
  결과: 대부분 "General Audiences"
  ```

### 6.5 타겟 연령

**Play Console → 앱 정보 → 정보 보안**

- [ ] 타겟 연령대: `13세 이상`
- [ ] 데이터 수집: `FCM 토큰, 기기 ID, 관심지역`
- [ ] 민감한 정보: `없음`

---

## 🖼️ 7단계: 스크린샷 & 이미지 준비 (1-2시간)

**Play Console → 앱 정보 → 스토어 정보 → 그래픽**

### 7.1 필수 이미지

| 항목 | 크기 | 수량 | 형식 |
|------|------|------|------|
| **스크린샷** | 540×960px | 5-8장 | PNG/JPG |
| **피처 그래픽** | 1024×500px | 1장 | PNG/JPG |
| **아이콘** | 512×512px | 1장 | PNG |

### 7.2 스크린샷 구성 (예시)

1. **홈 화면**: 포스트 그리드 + 검색
2. **포스트 상세**: 분양 정보 + 일정
3. **즐겨찾기**: 저장된 아파트 목록
4. **설정**: 관심지역 + 알림 설정
5. **오프라인**: 네트워크 없이 동작

### 7.3 이미지 준비 방법

```bash
# 개발 서버에서 스크린샷 촬영 (Chrome 개발자 도구)
npm start

# 브라우저에서 각 화면 캡처
# DevTools → 기기 모드 설정 (540×960)
# 스크린샷 저장

# 또는 이미지 편집 도구로 텍스트 추가
# Figma, Photoshop, GIMP 등
```

---

## 📦 8단계: APK/AAB 업로드 (1시간)

**참고**: [FIREBASE_SETUP.md#배포-전-체크리스트](./FIREBASE_SETUP.md#배포-전-체크리스트)

### 8.1 최종 빌드 확인

- [ ] 프로덕션 환경 빌드 완료
  ```bash
  cd mobile-app/android
  ./gradlew bundleRelease
  ```

- [ ] AAB 파일 존재 확인
  ```bash
  ls app/build/outputs/bundle/release/app-release.aab
  ```

### 8.2 Play Console에 업로드

**Play Console → 테스트 → 프로덕션 (또는 테스트 트랙)**

- [ ] 새 출시 만들기
- [ ] "앱 서명 포함" 클릭
- [ ] AAB 파일 업로드
  ```
  app/build/outputs/bundle/release/app-release.aab
  ```
- [ ] 출시 정보 입력
  ```
  출시 이름: v1.0.0
  출시 노트: 초기 출시
  ```

### 8.3 최종 검토

**필수 체크리스트:**

- [ ] 앱 이름 확인
- [ ] 앱 ID 확인: `com.apta.note`
- [ ] 버전 코드: `1`
- [ ] 버전 명: `1.0.0`
- [ ] 타겟 API 레벨: `33` 이상
- [ ] 개인정보처리방침 URL 등록됨
- [ ] 스크린샷 5장 이상
- [ ] 피처 그래픽 업로드됨
- [ ] 콘텐츠 등급 완료

---

## 🚀 9단계: 출시 및 심사 (1-7일)

### 9.1 출시 제출

**Play Console → 프로덕션 → 출시**

- [ ] "출시" 또는 "검토를 위해 제출" 버튼 클릭
- [ ] 최종 확인 메시지 읽기
- [ ] "제출" 클릭

**상태**: `검토 중` (24시간 ~ 1주일)

### 9.2 심사 진행 모니터링

- [ ] Play Console 대시보드 확인
  - 상태: `검토 중` → `출시 중` (승인)
  - 또는 거부 시 이유 이메일 수신

### 9.3 승인 후

- [ ] 상태: `출시 중` (수분 내)
- [ ] Google Play에서 검색 가능 (30분~2시간)

**축하합니다! 🎉**

---

## ✅ 10단계: 배포 후 모니터링 (지속)

### 10.1 Google Play Console 확인

**Play Console 대시보드**

- [ ] 설치 통계 모니터링
  - 신규 설치
  - 활성 사용자
  - 제거된 사용자

- [ ] 충돌 모니터링
  - Crashes & ANR
  - 문제가 없는지 확인

- [ ] 사용자 피드백
  - 별점 및 리뷰 확인
  - 답글 작성

- [ ] 성능 모니터링
  - 조기 액세스 및 베타 테스트 고려

### 10.2 Firebase 모니터링 (선택)

```
Firebase Console → Analytics
- 사용자 이벤트 추적
- 기기 유형별 통계
```

---

## 📋 최종 체크리스트 (출시 전 확인)

### 환경 설정
- [ ] JDK 17 설치 및 PATH 설정
- [ ] Android SDK 설치
- [ ] ANDROID_HOME 환경 변수 설정
- [ ] npm install 완료

### Firebase & 서명
- [ ] Firebase 프로젝트 생성
- [ ] google-services.json 다운로드 및 배치
- [ ] 키스토어 파일 생성 (apt-note.jks)
- [ ] 환경 변수 설정 (KEYSTORE_PASSWORD, 등)

### 빌드 & 테스트
- [ ] npm run build 성공
- [ ] npx capacitor sync android 성공
- [ ] ./gradlew bundleRelease 성공
- [ ] app-release.aab 파일 생성됨

### Google Play 정보
- [ ] Play Console 계정 생성 ($25 결제)
- [ ] 앱 생성
- [ ] 스토어 정보 모두 입력
- [ ] 스크린샷 5장 이상 업로드
- [ ] 피처 그래픽 업로드
- [ ] 개인정보처리방침 URL 등록
- [ ] 콘텐츠 등급 완료

### 최종 검증
- [ ] 앱 ID: com.apta.note 확인
- [ ] 버전: 1.0.0 확인
- [ ] 타겟 API: 33 이상 확인
- [ ] 모든 필수 정보 입력 확인

---

## 🆘 문제 발생 시

**빌드 오류:**
- [ANDROID_BUILD_GUIDE.md#4-문제-해결](./ANDROID_BUILD_GUIDE.md#4-문제-해결)

**Firebase 오류:**
- [FIREBASE_SETUP.md#11-문제-해결](./FIREBASE_SETUP.md#11-문제-해결)

**배포 거부:**
- [FIREBASE_SETUP.md#배포-거부-시](./FIREBASE_SETUP.md)

---

## 📞 연락처 & 리소스

- **Google Play 정책**: https://play.google.com/intl/ko/about/developer-content-policy/
- **Capacitor 가이드**: https://capacitorjs.com/docs/android
- **Android 개발**: https://developer.android.com
- **Firebase**: https://console.firebase.google.com

---

**시작 날짜**: 2026년 4월 27일  
**목표 배포**: 2026년 5월 15일 (약 2-3주)  
**우선순위**: Android 배포 → 피드백 수집 → iOS 결정

**다음 단계**: 위 체크리스트를 순서대로 진행하세요! 🚀
