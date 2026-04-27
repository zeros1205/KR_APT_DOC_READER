import { FirebaseMessaging } from '@capacitor-firebase/messaging';
import { storageService } from './storageService';
import { apiService } from './apiService';

interface DeviceRegistration {
  fcm_token: string;
  device_id: string;
  platform: 'ios' | 'android';
  user_id?: string;
  regions?: string[];
}

class FirebaseService {
  private isInitialized = false;
  private deviceId: string | null = null;

  async initialize(): Promise<void> {
    try {
      const messaging = FirebaseMessaging.getInstance();

      // 권한 요청
      const result = await messaging.requestPermissions();
      console.log('FCM permissions:', result);

      // FCM 토큰 획득
      const token = await this.getToken();
      if (token) {
        await this.registerDevice(token);
      }

      // 포그라운드 메시지 리스너
      await messaging.addListener(
        'messageReceived',
        (event) => {
          console.log('Foreground message received:', event.message);
          this.handleMessageReceived(event.message);
        }
      );

      this.isInitialized = true;
      console.log('Firebase service initialized');
    } catch (error) {
      console.error('Failed to initialize Firebase service:', error);
    }
  }

  async getToken(): Promise<string | null> {
    try {
      const messaging = FirebaseMessaging.getInstance();
      const token = await messaging.getToken();
      console.log('FCM token obtained:', token.token.substring(0, 20) + '...');
      return token.token;
    } catch (error) {
      console.error('Failed to get FCM token:', error);
      return null;
    }
  }

  private async registerDevice(fcmToken: string): Promise<void> {
    try {
      const deviceId = await this.getOrCreateDeviceId();
      const platform = this.getPlatform();

      const prefs = await storageService.getUserPreferences();

      const registration: DeviceRegistration = {
        fcm_token: fcmToken,
        device_id: deviceId,
        platform,
        regions: prefs.regions,
      };

      // 백엔드에 디바이스 등록
      // NOTE: 실제 구현 시 API 엔드포인트 필요
      // await apiService.post('/api/devices/register', registration);

      console.log('Device registered:', registration.device_id);
    } catch (error) {
      console.error('Failed to register device:', error);
    }
  }

  private async getOrCreateDeviceId(): Promise<string> {
    try {
      const stored = await storageService.getDeviceId();
      if (stored) {
        this.deviceId = stored;
        return stored;
      }

      const newDeviceId = this.generateDeviceId();
      await storageService.setDeviceId(newDeviceId);
      this.deviceId = newDeviceId;
      return newDeviceId;
    } catch (error) {
      console.error('Failed to get/create device ID:', error);
      const fallback = this.generateDeviceId();
      this.deviceId = fallback;
      return fallback;
    }
  }

  private generateDeviceId(): string {
    return `device_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private getPlatform(): 'ios' | 'android' {
    const userAgent = navigator.userAgent.toLowerCase();
    return userAgent.includes('iphone') || userAgent.includes('ipad') ? 'ios' : 'android';
  }

  private async handleMessageReceived(message: any): Promise<void> {
    try {
      const title = message.notification?.title || '새로운 알림';
      const body = message.notification?.body || '';
      const data = message.data || {};

      console.log('Processing received message:', { title, body, data });

      // 데이터 페이로드 처리
      if (data.post_id) {
        console.log('Message is about post:', data.post_id);
      }

      if (data.region) {
        console.log('Message region:', data.region);
      }

      // 추가 처리 (예: 로컬 저장, UI 업데이트)
      // 이는 notificationService에서 처리
    } catch (error) {
      console.error('Failed to handle received message:', error);
    }
  }

  async updateRegions(regions: string[]): Promise<void> {
    try {
      if (!this.deviceId) {
        await this.getOrCreateDeviceId();
      }

      // 백엔드에 지역 업데이트
      // NOTE: 실제 구현 시 API 엔드포인트 필요
      // await apiService.put(`/api/devices/${this.deviceId}/regions`, { regions });

      console.log('Device regions updated:', regions);
    } catch (error) {
      console.error('Failed to update device regions:', error);
    }
  }

  async unsubscribeFromRegion(region: string): Promise<void> {
    try {
      const prefs = await storageService.getUserPreferences();
      const updated = prefs.regions.filter(r => r !== region);
      await this.updateRegions(updated);
      console.log('Unsubscribed from region:', region);
    } catch (error) {
      console.error('Failed to unsubscribe from region:', error);
    }
  }

  getIsInitialized(): boolean {
    return this.isInitialized;
  }

  getDeviceId(): string | null {
    return this.deviceId;
  }
}

export const firebaseService = new FirebaseService();
