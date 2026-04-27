import { LocalNotifications } from '@capacitor/local-notifications';
import { App } from '@capacitor/app';
import { storageService } from './storageService';

interface NotificationLog {
  id: number;
  title: string;
  body: string;
  sentAt: string;
  region: string;
}

interface FCMConfig {
  token?: string;
  userId?: string;
  isInitialized: boolean;
}

class NotificationService {
  private fcmConfig: FCMConfig = { isInitialized: false };
  private notificationLogs: NotificationLog[] = [];
  private syncInterval: ReturnType<typeof setInterval> | null = null;

  async initialize(): Promise<void> {
    try {
      // 알림 권한 요청
      const permission = await LocalNotifications.checkPermissions();
      if (permission.display !== 'granted') {
        const result = await LocalNotifications.requestPermissions();
        if (result.display !== 'granted') {
          console.warn('Notification permission denied');
        }
      }

      // 알림 클릭 리스너
      LocalNotifications.addListener(
        'localNotificationActionPerformed',
        (notification) => {
          console.log('Notification clicked:', notification);
          this.logNotificationEvent(notification.notification.title || '', 'clicked');
        }
      );

      // 일일 동기화 스케줄 (자정마다)
      this.scheduleDailySync();

      // FCM 토큰 준비 (Firebase FCM 통합 시 사용)
      await this.initializeFCM();

      console.log('Notification service initialized');
    } catch (error) {
      console.error('Failed to initialize notifications:', error);
    }
  }

  async scheduleLocalNotification(
    title: string,
    body: string,
    id: number,
    delayMs: number = 0,
    region?: string
  ): Promise<void> {
    try {
      const prefs = await storageService.getUserPreferences();

      if (!prefs.notifications.enabled) {
        console.log('Notifications disabled by user');
        return;
      }

      // 조용한 시간 체크
      if (prefs.quiet_hours.enabled) {
        const now = new Date();
        const currentTime = this.formatTime(now);

        if (this.isInQuietHours(currentTime, prefs.quiet_hours.start, prefs.quiet_hours.end)) {
          console.log('Notification suppressed due to quiet hours');
          return;
        }
      }

      await LocalNotifications.schedule({
        notifications: [
          {
            title,
            body,
            id,
            schedule: delayMs > 0 ? { at: new Date(Date.now() + delayMs) } : undefined,
            smallIcon: 'ic_stat_icon_config_sample',
            iconColor: '#3B82F6',
          },
        ],
      });

      this.logNotificationEvent(title, 'sent', region);
    } catch (error) {
      console.error('Failed to schedule local notification:', error);
    }
  }

  async showPostNotification(aptName: string, region: string, delayMs?: number): Promise<void> {
    const id = Math.floor(Math.random() * 100000);
    const title = region;
    const body = `새로운 분양공고: ${aptName}`;

    await this.scheduleLocalNotification(title, body, id, delayMs, region);
  }

  async showBatchNotification(count: number, region: string): Promise<void> {
    const id = Math.floor(Math.random() * 100000);
    const title = region;
    const body = `${region}에 ${count}개의 새로운 분양공고가 등록되었습니다`;

    await this.scheduleLocalNotification(title, body, id, 0, region);
  }

  private isInQuietHours(
    currentTime: string,
    startTime: string,
    endTime: string
  ): boolean {
    const [currentHour, currentMinute] = currentTime.split(':').map(Number);
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);

    const current = currentHour * 60 + currentMinute;
    const start = startHour * 60 + startMinute;
    const end = endHour * 60 + endMinute;

    if (start < end) {
      return current >= start && current < end;
    } else {
      return current >= start || current < end;
    }
  }

  private formatTime(date: Date): string {
    return `${String(date.getHours()).padStart(2, '0')}:${String(
      date.getMinutes()
    ).padStart(2, '0')}`;
  }

  private logNotificationEvent(title: string, event: 'sent' | 'clicked', region?: string): void {
    const log: NotificationLog = {
      id: Math.floor(Math.random() * 1000000),
      title,
      body: '',
      sentAt: new Date().toISOString(),
      region: region || '',
    };

    this.notificationLogs.push(log);

    if (this.notificationLogs.length > 50) {
      this.notificationLogs = this.notificationLogs.slice(-50);
    }

    console.log(`[Notification ${event}] ${title} at ${log.sentAt}`);
  }

  private scheduleDailySync(): void {
    // 매일 자정에 새 포스트 동기화 체크
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(0, 0, 0, 0);

    const timeUntilSync = tomorrow.getTime() - now.getTime();

    this.syncInterval = setTimeout(() => {
      this.performDailySync();
      // 매 24시간마다 반복
      this.syncInterval = setInterval(() => {
        this.performDailySync();
      }, 24 * 60 * 60 * 1000);
    }, timeUntilSync);

    console.log(`Daily sync scheduled at ${tomorrow.toLocaleString()}`);
  }

  private async performDailySync(): Promise<void> {
    try {
      console.log('Performing daily sync for new posts...');
      // 새 포스트 감지 로직 (백엔드 API와 연동 시 구현)
      // const newPosts = await apiService.getNewPosts();
      // if (newPosts.length > 0) {
      //   await this.showBatchNotification(newPosts.length, newPosts[0].region);
      // }
    } catch (error) {
      console.error('Daily sync failed:', error);
    }
  }

  private async initializeFCM(): Promise<void> {
    try {
      // Firebase FCM 초기화 준비
      // 나중에 Firebase 연동 시 구현
      console.log('FCM initialization prepared (awaiting Firebase setup)');
      this.fcmConfig.isInitialized = true;
    } catch (error) {
      console.error('FCM initialization failed:', error);
    }
  }

  async setFCMToken(token: string): Promise<void> {
    this.fcmConfig.token = token;
    console.log('FCM token set:', token.substring(0, 20) + '...');
  }

  getFCMToken(): string | undefined {
    return this.fcmConfig.token;
  }

  getNotificationLogs(): NotificationLog[] {
    return this.notificationLogs;
  }

  clearNotificationLogs(): void {
    this.notificationLogs = [];
  }

  destroy(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }
}

export const notificationService = new NotificationService();
