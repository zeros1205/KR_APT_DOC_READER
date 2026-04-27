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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {!isOnboarded ? (
        <OnboardingScreen onComplete={handleOnboardingComplete} />
      ) : (
        <>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {currentScreen === 'home' && <HomeScreen />}
            {currentScreen === 'favorites' && <FavoritesScreen />}
            {currentScreen === 'settings' && <SettingsScreen />}
          </div>
          <BottomTabBar currentScreen={currentScreen} onScreenChange={setCurrentScreen} />
        </>
      )}
    </div>
  );
}

interface BottomTabBarProps {
  currentScreen: Screen;
  onScreenChange: (screen: Screen) => void;
}

function BottomTabBar({ currentScreen, onScreenChange }: BottomTabBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-around',
        alignItems: 'center',
        height: '60px',
        backgroundColor: 'var(--c-surface)',
        borderTop: '1px solid var(--c-light-gray)',
        gap: '4px',
      }}
    >
      {['home', 'favorites', 'settings'].map((screen) => (
        <button
          key={screen}
          onClick={() => onScreenChange(screen as Screen)}
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            padding: '8px',
            backgroundColor: 'transparent',
            borderBottom:
              currentScreen === screen ? '3px solid var(--c-primary)' : 'none',
            color: currentScreen === screen ? 'var(--c-primary)' : 'var(--c-mid)',
            fontSize: '12px',
            fontWeight: currentScreen === screen ? '600' : '400',
          }}
        >
          {getTabIcon(screen as Screen)}
          {getTabLabel(screen as Screen)}
        </button>
      ))}
    </div>
  );
}

function getTabIcon(screen: Screen) {
  switch (screen) {
    case 'home':
      return '🏠';
    case 'favorites':
      return '⭐';
    case 'settings':
      return '⚙️';
    default:
      return '';
  }
}

function getTabLabel(screen: Screen) {
  switch (screen) {
    case 'home':
      return '홈';
    case 'favorites':
      return '즐겨찾기';
    case 'settings':
      return '설정';
    default:
      return '';
  }
}

export default App;
