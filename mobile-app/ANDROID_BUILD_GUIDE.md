# Android 빌드 및 배포 가이드

## 목차
1. [개발 환경 준비](#1-개발-환경-준비)
2. [로컬 빌드](#2-로컬-빌드)
3. [Google Play 배포](#3-google-play-배포)
4. [문제 해결](#4-문제-해결)

---

## 1. 개발 환경 준비

### 1.1 필수 도구 설치

#### Node.js & npm
```bash
# Node.js 16+ 설치 확인
node -v
npm -v
```

#### Java Development Kit (JDK)
```bash
# JDK 11 이상 필요 (권장: JDK 17)
java -version

# Windows: https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html
# macOS: brew install openjdk@17
# Linux: sudo apt-get install openjdk-17-jdk
```

#### Android Studio
1. **다운로드**: https://developer.android.com/studio
2. **설치** (4-5GB)
3. **SDK 설정**:
   - Android Studio 열기
   - Tools → SDK Manager
   - SDK Platform 설치:
     - Android 13 (API 33) 이상
     - Android SDK Build Tools (최신)
     - Android Emulator (선택사항, 테스트용)

#### 환경 변수 설정 (중요!)

**Windows (PowerShell)**:
```powershell
# 시스템 환경 변수 편집 → 환경 변수
# ANDROID_HOME 추가
$env:ANDROID_HOME = "C:\Users\<YourUsername>\AppData\Local\Android\Sdk"
$env:PATH += ";$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\tools"

# 확인
echo $env:ANDROID_HOME
```

**macOS/Linux**:
```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/tools

source ~/.bashrc  # 또는 source ~/.zshrc
```

#### Capacitor 설치
```bash
cd mobile-app
npm install
```

### 1.2 Android 플랫폼 추가

```bash
cd mobile-app

# Android 플랫폼 추가 (처음 한 번만)
npm run cap:add:android

# 또는 CLI 직접 사용
npx capacitor add android
```

결과: `android/` 폴더 생성

---

## 2. 로컬 빌드

### 2.1 웹 애셋 빌드

```bash
cd mobile-app

# React 앱 빌드
npm run build

# Capacitor와 동기화
npx capacitor sync android
```

결과: `public/` 폴더의 정적 파일이 `android/app/src/main/assets/public/`로 복사

### 2.2 Android 앱 빌드

#### 방법 1: Android Studio (UI)

```bash
# Android Studio에서 프로젝트 열기
npm run cap:open:android
```

1. Android Studio 실행
2. 좌측 Build 메뉴 → Build Bundle(s) / APK(s)
3. Build APK 선택
4. Gradle 빌드 시작 (2-5분)
5. 완료: `android/app/build/outputs/apk/debug/app-debug.apk`

#### 방법 2: 명령어 라인

```bash
cd mobile-app/android

# debug APK 빌드
./gradlew assembleDebug

# 또는 release APK (서명 필요 - 아래 참조)
./gradlew assembleRelease
```

### 2.3 서명 설정 (배포용)

배포하려면 서명된 APK/AAB이 필수입니다.

#### 단계 1: 키스토어 생성

```bash
# 첫 배포 시에만 수행
cd mobile-app/android

# 키스토어 파일 생성 (비밀번호 기억!)
keytool -genkey -v -keystore apt-note.jks -keyalg RSA -keysize 2048 -validity 10000 -alias apt-note-key

# 입력 내용:
# - 키스토어 비밀번호: (강력한 비밀번호 설정)
# - 키 비밀번호: (same as keystore)
# - 이름: Your Name
# - 조직: Your Organization
# - 도시: Seoul
# - 주/지역: Seoul
# - 국가 코드: KR
```

#### 단계 2: 서명 설정 추가

`android/app/build.gradle` 편집:

```gradle
android {
    ...
    signingConfigs {
        release {
            storeFile file("../apt-note.jks")
            storePassword "YOUR_KEYSTORE_PASSWORD"
            keyAlias "apt-note-key"
            keyPassword "YOUR_KEY_PASSWORD"
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

**⚠️ 보안 주의**: 비밀번호를 하드코딩하지 말고, 환경 변수 또는 local.properties 사용:

```gradle
signingConfigs {
    release {
        storeFile file("../apt-note.jks")
        storePassword System.getenv("KEYSTORE_PASSWORD")
        keyAlias System.getenv("KEY_ALIAS")
        keyPassword System.getenv("KEY_PASSWORD")
    }
}
```

#### 단계 3: Release APK/AAB 빌드

```bash
cd mobile-app/android

# 환경 변수 설정 (PowerShell)
$env:KEYSTORE_PASSWORD = "your_password"
$env:KEY_ALIAS = "apt-note-key"
$env:KEY_PASSWORD = "your_password"

# AAB 빌드 (Google Play Store 필수)
./gradlew bundleRelease

# APK 빌드 (테스트용)
./gradlew assembleRelease
```

결과:
- AAB: `app/build/outputs/bundle/release/app-release.aab`
- APK: `app/build/outputs/apk/release/app-release.apk`

---

## 3. Google Play 배포

### 3.1 Google Play Developer 계정 등록

1. **계정 생성**: https://play.google.com/console
2. **비용**: $25 일회성
3. **필요 정보**:
   - Google 계정
   - 신용카드
   - 개인정보 (성명, 주소)

### 3.2 앱 등록

**Google Play Console**에서:

1. **새 앱 만들기**
   - 앱 이름: "apt-note"
   - 기본 언어: 한국어
   - 앱 유형: 무료

2. **앱 정보 입력** (좌측 메뉴)
   - **앱 액세스**: 전체 앱 기능 설명
   - **타겟 연령대**: 13세 이상
   - **콘텐츠 등급**: 자체 평가 작성
     - "부동산 정보"로 분류

3. **콘텐츠 등급** (좌측 메뉴)
   - 자체 평가 설문지 작성 (5분)
   - 결과: 보통 모든 연령대 (General Audiences)

### 3.3 앱 준비 (스토어 정보)

**Play Console → 앱 정보 → 스토어 정보**:

| 항목 | 내용 | 예시 |
|------|------|------|
| **앱 이름** | 한글 40자 이하 | "청약홈 - apt-note" |
| **짧은 설명** | 80자 | "청약홈 공공데이터 기반 아파트 분양공고 정보" |
| **설명** | 4000자 | [아래 참조] |
| **스크린샷** | 5개 최소 | 핸드폰 스크린샷 6장 (540×960px) |
| **피처 그래픽** | 1장 필수 | 1024×500px |
| **아이콘** | 512×512px PNG | 앱 로고 (배경색 포함) |

#### 앱 설명 예시

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

### 3.4 APK/AAB 업로드

**Play Console → 버전 → 프로덕션 → 새 출시 만들기**:

1. **빌드 선택**
   - "앱 서명 포함" 클릭
   - AAB 파일 업로드 (`app-release.aab`)

2. **출시 정보**
   - 출시 이름: "v1.0.0"
   - 출시 노트: "초기 출시"

3. **검토 전 체크리스트**
   - ✅ 개인정보처리방침 URL
   - ✅ 이용약관 URL (선택사항)
   - ✅ 타겟 API 레벨: 33 이상
   - ✅ 기기 호환성 확인

### 3.5 Google Play 심사

1. **앱 검토 제출**
   - 출시 버튼 클릭
   - 상태: "검토 중" (24시간~1주)

2. **심사 기준**
   - 콘텐츠 정책 확인
   - 보안 (암호화, 권한)
   - 성능 (크래시 없음)

3. **승인 후**
   - 상태: "출시 중" (수분 내)
   - Google Play Store에서 검색 가능 (30분~2시간)

4. **거부 시**
   - 이유 이메일로 수신
   - 수정 후 재제출

---

## 4. 문제 해결

### 4.1 빌드 오류

#### "ANDROID_HOME이 설정되지 않음"
```bash
# 환경 변수 확인
echo $ANDROID_HOME

# 설정 안 된 경우
export ANDROID_HOME=$HOME/Android/Sdk
```

#### "Gradle 빌드 실패"
```bash
cd mobile-app/android

# Gradle 캐시 삭제
./gradlew clean

# 재빌드
./gradlew assembleDebug
```

#### "Firebase 토큰 오류"
```bash
# google-services.json 파일 필수
# 1. Firebase Console (https://console.firebase.google.com)
# 2. 프로젝트 생성 또는 선택
# 3. 앱 추가 (com.apta.note)
# 4. google-services.json 다운로드
# 5. mobile-app/android/app/ 폴더에 복사

ls mobile-app/android/app/google-services.json
```

### 4.2 서명 오류

#### "키스토어 비밀번호 오류"
```bash
# 비밀번호 확인 및 다시 입력
keytool -list -v -keystore apt-note.jks -alias apt-note-key
```

#### "APK 서명 실패"
```bash
# build.gradle에서 서명 설정 확인
# 파일 경로가 정확한지 확인
ls -la mobile-app/android/apt-note.jks
```

### 4.3 배포 오류

#### "앱 등록 전 필수 정보 누락"
Play Console 체크리스트:
- ✅ 개인정보처리방침 (약 200자)
- ✅ 연락처 (이메일)
- ✅ 콘텐츠 등급 완료
- ✅ 타겟 API 레벨 33+

#### "스토어에 안 보임"
- 검토 상태 확인 (24시간~1주)
- 국가/지역 설정 확인 (한국)
- 기기 호환성 확인

---

## 5. 배포 후 모니터링

### 5.1 Google Play Console 대시보드

**지표 확인**:
- 📊 설치: 일일/누적 설치 수
- 🔴 충돌: 앱 충돌 및 ANR (Application Not Responding)
- ⭐ 평점: 사용자 리뷰 및 평가
- 💬 댓글: 사용자 피드백

### 5.2 충돌 모니터링

Firebase Crashlytics 설정:
1. Firebase Console → Crashlytics
2. 앱에 Crashlytics 초기화 코드 추가
3. 실시간 충돌 모니터링

### 5.3 버전 업데이트

새 버전 배포:
```bash
# package.json 버전 업데이트
# "version": "1.0.1"

npm run build
npx capacitor sync android
cd android
./gradlew bundleRelease

# Play Console → 새 출시 → AAB 업로드
```

---

## 6. 기타 리소스

- **Capacitor 공식 가이드**: https://capacitorjs.com/docs/android
- **Google Play 정책**: https://play.google.com/intl/ko/about/developer-content-policy/
- **Firebase 설정**: https://console.firebase.google.com
- **Android 공식 문서**: https://developer.android.com

---

## 체크리스트

### 빌드 전
- [ ] Node.js 16+ 설치 확인
- [ ] JDK 11+ 설치 확인
- [ ] Android Studio 설치 및 SDK 설정
- [ ] ANDROID_HOME 환경 변수 설정
- [ ] `npm install` 실행 완료

### 빌드
- [ ] `npm run build` 성공
- [ ] `npx capacitor sync android` 성공
- [ ] `./gradlew assembleDebug` 성공

### 서명 & 배포
- [ ] 키스토어 파일 생성 (`apt-note.jks`)
- [ ] `build.gradle`에 서명 설정 추가
- [ ] `./gradlew bundleRelease` 성공
- [ ] Google Play Developer 계정 생성
- [ ] 앱 정보 모두 입력
- [ ] 스크린샷 및 아이콘 업로드
- [ ] AAB 파일 업로드
- [ ] 출시 제출

### 배포 후
- [ ] 24시간 기다려서 앱 승인 여부 확인
- [ ] Play Store에서 앱 검색 가능 여부 확인
- [ ] 첫 설치 테스트 (다른 기기)
- [ ] Crashlytics 모니터링 설정
