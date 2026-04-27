import { useEffect, useState } from 'react';
import { storageService, UserPreferences, AppearanceSettings } from '../services/storageService';
import { cacheService } from '../services/cacheService';

const KOREAN_REGIONS = [
  '서울', '부산', '대구', '인천', '광주', '대전', '울산',
  '세종', '경기도', '강원도', '충청북도', '충청남도',
  '전라북도', '전라남도', '경상북도', '경상남도', '제주도'
];

export default function SettingsScreen() {
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [appearance, setAppearance] = useState<AppearanceSettings | null>(null);
  const [editingRegions, setEditingRegions] = useState(false);
  const [cacheSize, setCacheSize] = useState('0 KB');

  useEffect(() => {
    const loadSettings = async () => {
      const userPrefs = await storageService.getUserPreferences();
      const appSettings = await storageService.getAppearanceSettings();
      setPrefs(userPrefs);
      setAppearance(appSettings);

      const size = await cacheService.getCacheSize();
      const sizeKB = Math.round(size / 1024);
      setCacheSize(sizeKB > 1024 ? `${(sizeKB / 1024).toFixed(1)} MB` : `${sizeKB} KB`);
    };

    loadSettings();
  }, []);

  const handleNotificationToggle = async () => {
    if (prefs) {
      const updated = { ...prefs };
      updated.notifications.enabled = !updated.notifications.enabled;
      await storageService.setUserPreferences(updated);
      setPrefs(updated);
    }
  };

  const handleQuietHoursToggle = async () => {
    if (prefs) {
      const updated = { ...prefs };
      updated.quiet_hours.enabled = !updated.quiet_hours.enabled;
      await storageService.setUserPreferences(updated);
      setPrefs(updated);
    }
  };

  const handleRegionToggle = async (region: string) => {
    if (prefs) {
      const updated = { ...prefs };
      if (updated.regions.includes(region)) {
        updated.regions = updated.regions.filter(r => r !== region);
      } else if (updated.regions.length < 3) {
        updated.regions = [...updated.regions, region];
      }
      await storageService.setUserPreferences(updated);
      setPrefs(updated);
    }
  };

  const handleClearCache = async () => {
    await cacheService.clearCache();
    setCacheSize('0 KB');
  };

  if (!prefs || !appearance) {
    return <div style={{ padding: '24px', color: 'var(--c-mid)' }}>로딩 중...</div>;
  }

  return (
    <div style={{ padding: '24px', overflowY: 'auto', height: '100%' }}>
      <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '24px' }}>설정</h1>

      <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px', marginBottom: '16px', border: '1px solid var(--c-light-gray)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px', color: 'var(--c-dark)' }}>
          🔔 알림 설정
        </h2>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid var(--c-light-gray)' }}>
          <div>
            <p style={{ fontSize: '14px', fontWeight: '500', color: 'var(--c-dark)', margin: 0 }}>
              알림 활성화
            </p>
            <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: '4px 0 0 0' }}>
              새로운 분양공고 알림 받기
            </p>
          </div>
          <button
            onClick={handleNotificationToggle}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              backgroundColor: prefs.notifications.enabled ? 'var(--c-primary)' : '#cccccc',
              color: '#ffffff',
              border: 'none',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 200ms',
            }}
          >
            {prefs.notifications.enabled ? 'ON' : 'OFF'}
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '14px', fontWeight: '500', color: 'var(--c-dark)', margin: 0 }}>
              조용한 시간 설정
            </p>
            <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: '4px 0 0 0' }}>
              {prefs.quiet_hours.enabled ? `${prefs.quiet_hours.start} ~ ${prefs.quiet_hours.end}` : '비활성화'}
            </p>
          </div>
          <button
            onClick={handleQuietHoursToggle}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              backgroundColor: prefs.quiet_hours.enabled ? 'var(--c-primary)' : '#cccccc',
              color: '#ffffff',
              border: 'none',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            {prefs.quiet_hours.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px', marginBottom: '16px', border: '1px solid var(--c-light-gray)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px', color: 'var(--c-dark)' }}>
          📍 관심 지역
        </h2>

        {!editingRegions ? (
          <div>
            <div style={{ marginBottom: '12px' }}>
              {prefs.regions.length > 0 ? (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {prefs.regions.map(region => (
                    <span
                      key={region}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: 'var(--c-primary)',
                        color: '#ffffff',
                        borderRadius: '6px',
                        fontSize: '13px',
                        fontWeight: '500',
                      }}
                    >
                      {region}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '13px', color: 'var(--c-mid)', margin: 0 }}>
                  선택된 지역이 없습니다 (최대 3개)
                </p>
              )}
            </div>
            <button
              onClick={() => setEditingRegions(true)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                backgroundColor: 'var(--c-primary)',
                color: '#ffffff',
                border: 'none',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
              }}
            >
              지역 변경
            </button>
          </div>
        ) : (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
              {KOREAN_REGIONS.map(region => (
                <button
                  key={region}
                  onClick={() => handleRegionToggle(region)}
                  style={{
                    padding: '10px',
                    borderRadius: '6px',
                    backgroundColor: prefs.regions.includes(region) ? 'var(--c-primary)' : 'var(--c-light-gray)',
                    color: prefs.regions.includes(region) ? '#ffffff' : 'var(--c-dark)',
                    border: 'none',
                    fontSize: '13px',
                    fontWeight: '600',
                    cursor: 'pointer',
                  }}
                >
                  {region}
                </button>
              ))}
            </div>
            <button
              onClick={() => setEditingRegions(false)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                backgroundColor: 'var(--c-primary)',
                color: '#ffffff',
                border: 'none',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
              }}
            >
              완료
            </button>
          </div>
        )}
      </div>

      <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px', border: '1px solid var(--c-light-gray)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px', color: 'var(--c-dark)' }}>
          💾 저장소
        </h2>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <p style={{ fontSize: '14px', fontWeight: '500', color: 'var(--c-dark)', margin: 0 }}>
              캐시 용량
            </p>
            <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: '4px 0 0 0' }}>
              {cacheSize}
            </p>
          </div>
          <button
            onClick={handleClearCache}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#ff6b6b',
              color: '#ffffff',
              border: 'none',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            초기화
          </button>
        </div>

        <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: 0 }}>
          오프라인 모드에서 사용할 수 있는 저장된 데이터
        </p>
      </div>
    </div>
  );
}
