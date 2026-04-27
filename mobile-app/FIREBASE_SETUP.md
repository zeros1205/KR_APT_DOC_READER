# Firebase & Google Services 설정 가이드

## 1. Firebase 프로젝트 생성

### 1.1 Firebase Console 접속
1. https://console.firebase.google.com 방문
2. Google 계정 로그인
3. **새 프로젝트** 클릭

### 1.2 프로젝트 정보 입력
```
프로젝트 이름: apt-note
분석: 사용 (권장)
위치: 대한민국
```

### 1.3 프로젝트 생성 완료
- 좌측 메뉴: 프로젝트 설정 → 프로젝트 ID 확인
- 예: `apt-note-abc123`

---

## 2. Android 앱 등록

### 2.1 Firebase에 Android 앱 추가

**Firebase Console → 프로젝트 설정 → 앱 추가**

1. **Android 아이콘** 선택
2. **Android 패키지 이름** 입력
   ```
   com.apta.note
   ```
3. **앱 닉네임** (선택사항)
   ```
   apt-note Android
   ```
4. **Google Play 서명 인증서** (선택사항, 나중에 추가 가능)

### 2.2 google-services.json 다운로드

1. Firebase에서 **google-services.json** 다운로드
2. **위치**: `mobile-app/android/app/` 폴더에 복사

```bash
# 확인
ls mobile-app/android/app/google-services.json
```

### 2.3 Firebase 플러그인 설정

`android/build.gradle`에 Firebase 플러그인 의존성 추가:

```gradle
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.google.gms:google-services:4.4.0'  // Firebase
    }
}
```

`android/app/build.gradle`에 Firebase 플러그인 적용:

```gradle
plugins {
    id 'com.android.application'
    id 'com.google.gms.google-services'  // 추가
}

dependencies {
    // Firebase Messaging
    implementation 'com.google.firebase:firebase-messaging:23.4.0'
    // Firebase Analytics (선택사항)
    implementation 'com.google.firebase:firebase-analytics:21.5.0'
}
```

---

## 3. Cloud Messaging (FCM) 설정

### 3.1 Firebase Console에서 FCM 활성화

1. **Firebase Console → Cloud Messaging**
2. **팀 구성원 권한** (선택사항)
3. 기본적으로 활성화됨

### 3.2 FCM 토큰 얻기

app이 처음 실행될 때 `firebaseService.ts`가 자동으로 토큰을 획득합니다:

```typescript
// src/services/firebaseService.ts
const token = await this.getToken();
// 백엔드에 등록
await this.registerDevice(token);
```

### 3.3 테스트 메시지 발송 (Optional)

**Firebase Console → Messaging → 캠페인 만들기**

1. **새 캠페인** → Firebase Messaging
2. **제목**: "테스트"
3. **메시지**: "테스트 푸시"
4. **대상 설정**:
   - 앱: apt-note
   - 사용자 지정 타겟팅 (선택)
5. **일정**: 지금 발송
6. **검토 및 게시**

---

## 4. Google Play Console 설정

### 4.1 개발자 계정 등록

**Google Play Console**: https://play.google.com/console

1. **계정 생성**
   - Google 계정 로그인
   - 결제 수단 추가 ($25)
   - 개인정보 입력
   
2. **신청 완료**
   - 이메일 확인 (인증)
   - 승인 대기 (1-2일)

### 4.2 앱 만들기

**Play Console → 새 앱 만들기**

```
앱 이름: apt-note
기본 언어: 한국어
앱 유형: 무료
```

### 4.3 필수 정보 입력

#### 앱 정보 → 스토어 정보

| 항목 | 내용 |
|------|------|
| 앱 이름 | 청약홈 - apt-note (40자) |
| 짧은 설명 | 청약홈 공공데이터 기반 아파트 분양공고 (80자) |
| 설명 | 상세 설명 (4000자) |
| 개발자 이름 | 개발자명 |
| 이메일 | 지원 이메일 |
| 개인정보 보호 정책 | 앱 웹사이트 링크 |

#### 앱 정보 → 콘텐츠 등급

**자체 평가 설문지 작성**:

1. **앱 카테고리**
   - 부동산

2. **콘텐츠 평가**
   - 모든 항목: "아니요" (기본값)
   - 결과: 대부분 "General Audiences"

3. **저장 후 게시**

### 4.4 정보 보안 & 프라이버시

**앱 정보 → 정보 보안 및 프라이버시**

```
타겟 연령대: 13세 이상
데이터 수집: 최소화 (IP주소, 기기 ID만)
민감한 정보: 없음
```

---

## 5. 앱 서명 설정 (Google Play App Signing)

### 5.1 서명 인증서 업로드

**Google Play Console → 설정 → 앱 보안**

1. **앱 서명 인증서**
   - Google Play가 자동으로 관리 (권장)
   - 또는 직접 관리 (고급)

2. **업로드 인증서** (선택사항)
   ```bash
   # 개발 중 사용하는 인증서 (필수 아님)
   keytool -export -alias apt-note-key -keystore apt-note.jks -rfc -file cert.pem
   ```

3. **SHA-1 지문** 확인
   ```bash
   keytool -list -v -keystore apt-note.jks -alias apt-note-key | grep SHA1
   ```

---

## 6. 스크린샷 & 미디어 준비

### 6.1 필수 이미지

| 파일 | 크기 | 수량 | 용도 |
|------|------|------|------|
| 스크린샷 | 540×960px | 5-8장 | 앱 기능 소개 |
| 피처 그래픽 | 1024×500px | 1장 | 스토어 배너 |
| 아이콘 | 512×512px | 1장 | 앱 로고 |

### 6.2 스크린샷 예시

1. **홈 화면**: 포스트 그리드
2. **포스트 상세**: 분양 정보
3. **즐겨찾기**: 저장된 아파트
4. **설정**: 관심지역 + 알림 설정
5. **검색**: 지역별 필터
6. **오프라인**: 네트워크 없이 접근

---

## 7. 개인정보처리방침 & 이용약관

### 7.1 개인정보처리방침

최소 요구사항:
```
1. 수집 항목
   - FCM 토큰
   - 기기 ID
   - 관심지역

2. 수집 목적
   - 푸시 알림 제공
   - 기기 식별 및 통계

3. 보유 기간
   - 앱 삭제 시 즉시 삭제

4. 사용자 권리
   - 언제든 삭제/거부 가능

5. 보안
   - HTTPS 암호화
   - 로컬 저장소 암호화
```

### 7.2 이용약관 (선택사항)

```
1. 데이터 정확성
   - 청약홈 공공데이터 기반
   - 공식사이트 확인 권장

2. 면책 조항
   - 데이터 지연/오류에 대해 책임 없음
   - 투자 결정의 근거로 사용 금지
```

---

## 8. 배포 전 체크리스트

### 빌드 & 서명
- [ ] `npm run build` 성공
- [ ] `./gradlew bundleRelease` 성공
- [ ] AAB 파일 생성: `app/build/outputs/bundle/release/app-release.aab`

### Firebase 설정
- [ ] Firebase 프로젝트 생성
- [ ] Android 앱 등록
- [ ] `google-services.json` 다운로드 및 배치
- [ ] `build.gradle` 플러그인 적용

### Google Play 설정
- [ ] 개발자 계정 생성 ($25 결제)
- [ ] 앱 생성
- [ ] 스토어 정보 모두 입력
- [ ] 콘텐츠 등급 완료
- [ ] 스크린샷 5장 이상 업로드
- [ ] 개인정보처리방침 URL 등록

### 앱 설정
- [ ] 타겟 API 레벨: 33 이상
- [ ] 최소 API 레벨: 24 이상
- [ ] 인터넷 권한 확인
- [ ] 알림 권한 확인
- [ ] 저장소 권한 확인

### 최종 검사
- [ ] 앱 이름 확인
- [ ] 앱 ID 확인: `com.apta.note`
- [ ] 버전 코드: 1
- [ ] 버전 명: 1.0.0

---

## 9. 배포 후 모니터링

### Google Play Console 대시보드

**매일 확인 항목**:
1. **설치 통계**: 신규/활성/제거된 사용자
2. **충돌**: ANR 또는 크래시 발생 여부
3. **평점**: 사용자 리뷰 및 평가
4. **댓글**: 사용자 피드백

### Firebase 모니터링

1. **Crashlytics**: 실시간 충돌 모니터링
2. **Analytics**: 사용자 이벤트 추적
3. **Performance**: 앱 성능 분석

---

## 10. 업데이트 배포

### 새 버전 배포 프로세스

```bash
# 1. 버전 업데이트
# package.json: "version": "1.0.1"

# 2. 빌드
npm run build
npx capacitor sync android

# 3. 서명
cd android
./gradlew bundleRelease

# 4. Google Play Console에 업로드
# Play Console → 새 출시 → AAB 파일 업로드
# 출시 노트: "v1.0.1 - 버그 수정"
# 제출

# 5. 모니터링
# 자동 승인 (보통 1시간 이내)
```

---

## 11. 문제 해결

### firebase/app 불러오기 오류

```
TS2307: Cannot find module 'firebase/app'
```

**해결**:
```bash
npm install firebase@latest
npm install @capacitor-firebase/messaging@latest
```

### google-services.json 찾을 수 없음

```
java.io.FileNotFoundException: google-services.json not found
```

**해결**:
```bash
# 파일 위치 확인
ls mobile-app/android/app/google-services.json

# 없으면 Firebase Console에서 다시 다운로드
```

### FCM 토큰 오류 (프로덕션)

앱 설치 후 FCM 토큰 미수신 → 백엔드 API 응답 확인

**디버그**:
```typescript
// src/services/firebaseService.ts
console.log('FCM token:', await firebaseService.getToken());
```

---

## 12. 참고 링크

- **Firebase 공식**: https://firebase.google.com
- **Google Play Console**: https://play.google.com/console
- **Capacitor Firebase**: https://capacitorjs.com/docs/plugins/firebase
- **Google Play 정책**: https://play.google.com/intl/ko/about/developer-content-policy/
