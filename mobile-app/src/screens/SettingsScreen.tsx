import { useEffect, useState } from 'react';
import { storageService, UserPreferences, AppearanceSettings } from '../services/storageService';

export default function SettingsScreen() {
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [appearance, setAppearance] = useState<AppearanceSettings | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      const userPrefs = await storageService.getUserPreferences();
      const appSettings = await storageService.getAppearanceSettings();
      setPrefs(userPrefs);
      setAppearance(appSettings);
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

  if (!prefs || !appearance) {
    return <div style={{ padding: '24px' }}>로딩 중...</div>;
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', marginBottom: '24px' }}>설정</h1>

      <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>알림</h2>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <span style={{ fontSize: '14px' }}>알림 활성화</span>
          <button
            onClick={handleNotificationToggle}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              backgroundColor: prefs.notifications.enabled ? 'var(--c-primary)' : 'var(--c-light-gray)',
              color: prefs.notifications.enabled ? '#ffffff' : 'var(--c-dark)',
              border: 'none',
              fontSize: '12px',
            }}
          >
            {prefs.notifications.enabled ? 'ON' : 'OFF'}
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '14px' }}>조용한 시간</span>
          <button
            onClick={handleQuietHoursToggle}
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              backgroundColor: prefs.quiet_hours.enabled ? 'var(--c-primary)' : 'var(--c-light-gray)',
              color: prefs.quiet_hours.enabled ? '#ffffff' : 'var(--c-dark)',
              border: 'none',
              fontSize: '12px',
            }}
          >
            {prefs.quiet_hours.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
        {prefs.quiet_hours.enabled && (
          <p style={{ fontSize: '12px', color: 'var(--c-mid)', marginTop: '8px' }}>
            {prefs.quiet_hours.start} ~ {prefs.quiet_hours.end}
          </p>
        )}
      </div>

      <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>관심 지역</h2>
        <p style={{ fontSize: '14px' }}>
          {prefs.regions.length > 0 ? prefs.regions.join(', ') : '선택된 지역이 없습니다'}
        </p>
      </div>
    </div>
  );
}
