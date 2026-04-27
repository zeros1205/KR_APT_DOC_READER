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

  const toggleRegion = (region: string) => {
    if (selectedRegions.includes(region)) {
      setSelectedRegions(selectedRegions.filter(r => r !== region));
    } else if (selectedRegions.length < 3) {
      setSelectedRegions([...selectedRegions, region]);
    }
  };

  const handleNext = async () => {
    if (step === 3) {
      await storageService.setUserPreferences({
        regions: selectedRegions,
        quiet_hours: { start: '22:00', end: '08:00', enabled: true },
        notifications: { enabled: true },
      });
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
          {step === 3 ? '시작하기' : '다음'}
        </button>
      </div>

      <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '12px', color: 'var(--c-mid)' }}>
        {step}/3
      </div>
    </div>
  );
}
