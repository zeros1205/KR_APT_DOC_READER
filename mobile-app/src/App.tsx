import { useEffect, useState } from 'react';
import { StatusBar, Style } from '@capacitor/status-bar';
import { SplashScreen } from '@capacitor/splash-screen';
import { storageService } from './services/storageService';
import { notificationService } from './services/notificationService';
import OnboardingScreen from './screens/OnboardingScreen';
import HomeScreen from './screens/HomeScreen';
import FavoritesScreen from './screens/FavoritesScreen';
import SettingsScreen from './screens/SettingsScreen';
import './styles/index.css';

type Screen = 'onboarding' | 'home' | 'favorites' | 'settings';

function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('home');
  const [isOnboarded, setIsOnboarded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initialize = async () => {
      try {
        await StatusBar.setStyle({ style: Style.Dark });
        await SplashScreen.hide();

        const onboardingDate = await storageService.getLastOnboardingDate();
        if (!onboardingDate) {
          setCurrentScreen('onboarding');
        } else {
          setIsOnboarded(true);
        }

        await notificationService.initialize();
      } catch (error) {
        console.error('App initialization error:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initialize();
  }, []);

  const handleOnboardingComplete = async () => {
    await storageService.setLastOnboardingDate(new Date().toISOString());
    setIsOnboarded(true);
    setCurrentScreen('home');
  };

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          backgroundColor: 'var(--c-bg)',
        }}
      >
        <div style={{ fontSize: '18px', color: 'var(--c-dark)' }}>로딩 중...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>
      {!isOnboarded ? (
        <OnboardingScreen onComplete={handleOnboardingComplete} />
      ) : (
        <>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {currentScreen === 'home' && <HomeScreen />}
            {currentScreen === 'favorites' && <FavoritesScreen />}
            {currentScreen === 'settings' && <SettingsScreen />}
          </div>
          <FloatingMenu currentScreen={currentScreen} onScreenChange={setCurrentScreen} />
        </>
      )}
    </div>
  );
}

interface FloatingMenuProps {
  currentScreen: Screen;
  onScreenChange: (screen: Screen) => void;
}

function FloatingMenu({ currentScreen, onScreenChange }: FloatingMenuProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const menuItems: { screen: Screen; icon: string; label: string }[] = [
    { screen: 'home', icon: '🏠', label: '홈' },
    { screen: 'favorites', icon: '⭐', label: '즐겨찾기' },
    { screen: 'settings', icon: '⚙️', label: '설정' },
  ];

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 1000,
      }}
    >
      {isExpanded && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginBottom: '16px',
            alignItems: 'flex-end',
          }}
        >
          {menuItems.map(item => (
            <button
              key={item.screen}
              onClick={() => {
                onScreenChange(item.screen);
                setIsExpanded(false);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                backgroundColor: 'var(--c-surface)',
                color:
                  currentScreen === item.screen
                    ? 'var(--c-primary)'
                    : 'var(--c-dark)',
                border: `2px solid ${
                  currentScreen === item.screen
                    ? 'var(--c-primary)'
                    : 'var(--c-light-gray)'
                }`,
                borderRadius: '24px',
                fontSize: '14px',
                fontWeight: '500',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '28px',
          backgroundColor: 'var(--c-primary)',
          color: '#ffffff',
          border: 'none',
          fontSize: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          transition: 'transform 200ms',
          transform: isExpanded ? 'rotate(45deg)' : 'rotate(0)',
        }}
      >
        +
      </button>
    </div>
  );
}

export default App;
