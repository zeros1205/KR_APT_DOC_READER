import { useState } from 'react';
import { storageService } from '../services/storageService';

const KOREAN_REGIONS = [
  '서울', '부산', '대구', '인천', '광주', '대전', '울산',
  '세종', '경기도', '강원도', '충청북도', '충청남도',
  '전라북도', '전라남도', '경상북도', '경상남도', '제주도'
];

interface OnboardingScreenProps {
  onComplete: () => void;
}

export default function OnboardingScreen({ onComplete }: OnboardingScreenProps) {
  const [step, setStep] = useState(1);
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [privacyAgreed, setPrivacyAgreed] = useState(false);

  const toggleRegion = (region: string) => {
    if (selectedRegions.includes(region)) {
      setSelectedRegions(selectedRegions.filter(r => r !== region));
    } else if (selectedRegions.length < 3) {
      setSelectedRegions([...selectedRegions, region]);
    }
  };

  const handleNext = async () => {
    if (step === 4) {
      // 최종 단계: 개인정보처리방침 동의 기록
      if (!privacyAgreed) {
        alert('개인정보처리방침에 동의해야 앱을 사용할 수 있습니다.');
        return;
      }

      await storageService.setUserPreferences({
        regions: selectedRegions,
        quiet_hours: { start: '22:00', end: '08:00', enabled: true },
        notifications: { enabled: true },
      });

      // 동의 기록 저장
      await storageService.setPrivacyAgreed(new Date().toISOString());
      onComplete();
    } else {
      setStep(step + 1);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--c-bg)',
        padding: '24px',
      }}
    >
      <div style={{ flex: 1 }}>
        {step === 1 && (
          <div>
            <h1 style={{ fontSize: '28px', marginBottom: '16px' }}>apt-note</h1>
            <p style={{ fontSize: '16px', color: 'var(--c-mid)', lineHeight: '1.6' }}>
              청약홈 공공데이터 기반 아파트 분양공고 정보를 한 곳에서 확인하세요.
            </p>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>관심 지역 선택</h2>
            <p style={{ fontSize: '14px', color: 'var(--c-mid)', marginBottom: '16px' }}>
              최대 3개 지역을 선택하세요
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {KOREAN_REGIONS.map(region => (
                <button
                  key={region}
                  onClick={() => toggleRegion(region)}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    backgroundColor: selectedRegions.includes(region)
                      ? 'var(--c-primary)'
                      : 'var(--c-surface)',
                    color: selectedRegions.includes(region)
                      ? '#ffffff'
                      : 'var(--c-dark)',
                    border: `1px solid ${selectedRegions.includes(region) ? 'var(--c-primary)' : 'var(--c-light-gray)'}`,
                    fontSize: '14px',
                    fontWeight: '500',
                  }}
                >
                  {region}
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>알림 설정</h2>
            <div style={{ backgroundColor: 'var(--c-surface)', padding: '16px', borderRadius: '8px' }}>
              <p style={{ fontSize: '14px', marginBottom: '12px' }}>
                선택한 지역({selectedRegions.length}개)에 새 분양공고가 등록되면 알림을 받습니다.
              </p>
              <p style={{ fontSize: '13px', color: 'var(--c-mid)' }}>
                밤 10시~아침 8시에는 조용한 모드가 자동 활성화됩니다.
              </p>
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>개인정보처리방침</h2>
            <div style={{ backgroundColor: 'var(--c-surface)', padding: '16px', borderRadius: '8px', marginBottom: '16px', maxHeight: '300px', overflowY: 'auto' }}>
              <h3 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px' }}>주요 내용</h3>
              <ul style={{ fontSize: '13px', color: 'var(--c-dark)', lineHeight: '1.8', marginLeft: '20px' }}>
                <li>✅ 수집 정보: FCM 토큰, 디바이스 ID, 관심지역, 즐겨찾기</li>
                <li>✅ 목적: 분양공고 알림 및 서비스 제공</li>
                <li>✅ 보관: 로컬 저장소 (기기에만)</li>
                <li>✅ 삭제: 앱 삭제 시 자동 삭제</li>
                <li>✅ 보안: HTTPS + 암호화</li>
                <li>❌ 수집 안 함: 이름, 이메일, 위치, 금융정보</li>
              </ul>
              <p style={{ fontSize: '12px', color: 'var(--c-mid)', marginTop: '12px', marginBottom: 0 }}>
                전체 내용: https://apt-note.com/privacy
              </p>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={privacyAgreed}
                onChange={(e) => setPrivacyAgreed(e.target.checked)}
                style={{
                  width: '20px',
                  height: '20px',
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--c-dark)' }}>
                개인정보처리방침에 동의합니다
              </span>
            </label>

            <p style={{ fontSize: '12px', color: 'var(--c-mid)', marginTop: '12px' }}>
              동의하지 않으면 앱을 사용할 수 없습니다. 언제든 설정에서 거부할 수 있습니다.
            </p>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button
          onClick={() => setStep(Math.max(1, step - 1))}
          disabled={step === 1}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: step === 1 ? 'var(--c-light-gray)' : 'var(--c-surface)',
            color: 'var(--c-dark)',
            border: '1px solid var(--c-light-gray)',
            fontSize: '16px',
            fontWeight: '600',
            cursor: step === 1 ? 'default' : 'pointer',
            opacity: step === 1 ? 0.5 : 1,
          }}
        >
          이전
        </button>
        <button
          onClick={handleNext}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: 'var(--c-primary)',
            color: '#ffffff',
            border: 'none',
            fontSize: '16px',
            fontWeight: '600',
          }}
        >
          {step === 4 ? '시작하기' : '다음'}
        </button>
      </div>

      <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '12px', color: 'var(--c-mid)' }}>
        {step}/4
      </div>
    </div>
  );
}
