import { LocalNotifications } from '@capacitor/local-notifications';
import { App } from '@capacitor/app';
import { storageService } from './storageService';

class NotificationService {
  async initialize(): Promise<void> {
    try {
      const permission = await LocalNotifications.checkPermissions();
      if (permission.display !== 'granted') {
        const result = await LocalNotifications.requestPermissions();
        if (result.display !== 'granted') {
          console.warn('Notification permission denied');
        }
      }

      LocalNotifications.addListener(
        'localNotificationActionPerformed',
        (notification) => {
          console.log('Notification clicked:', notification);
        }
      );
    } catch (error) {
      console.error('Failed to initialize notifications:', error);
    }
  }

  async scheduleLocalNotification(
    title: string,
    body: string,
    id: number,
    delayMs: number = 0
  ): Promise<void> {
    try {
      const prefs = await storageService.getUserPreferences();

      if (!prefs.notifications.enabled) {
        return;
      }

      if (prefs.quiet_hours.enabled) {
        const now = new Date();
        const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(
          now.getMinutes()
        ).padStart(2, '0')}`;

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
    } catch (error) {
      console.error('Failed to schedule local notification:', error);
    }
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

  async showPostNotification(aptName: string, region: string): Promise<void> {
    const id = Math.floor(Math.random() * 10000);
    await this.scheduleLocalNotification(
      region,
      `새로운 분양공고: ${aptName}`,
      id
    );
  }
}

export const notificationService = new NotificationService();
