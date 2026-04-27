import axios, { AxiosInstance } from 'axios';

interface PostMeta {
  post_id: string;
  apt_name: string;
  notice_date: string;
  region: string;
  price_min?: number;
  price_max?: number;
  thumbnail_url?: string;
}

interface PostDetail {
  post_id: string;
  apt_name: string;
  content: string;
  notice_date: string;
  region: string;
}

class ApiService {
  private api: AxiosInstance;
  private baseURL = 'https://apt-note.com/api';

  constructor() {
    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 10000,
    });
  }

  async getPosts(
    regions?: string[],
    limit: number = 10,
    offset: number = 0
  ): Promise<{ posts: PostMeta[]; total: number }> {
    try {
      const params: any = { limit, offset };
      if (regions && regions.length > 0) {
        params.regions = regions.join(',');
      }
      const response = await this.api.get('/posts', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch posts:', error);
      throw error;
    }
  }

  async getPostDetail(postId: string): Promise<PostDetail> {
    try {
      const response = await this.api.get(`/posts/${postId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch post ${postId}:`, error);
      throw error;
    }
  }

  async registerDevice(
    fcmToken: string,
    deviceId: string,
    platform: 'ios' | 'android'
  ): Promise<{ user_id: string; status: string }> {
    try {
      const response = await this.api.post('/users/register-device', {
        fcm_token: fcmToken,
        device_id: deviceId,
        platform,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to register device:', error);
      throw error;
    }
  }

  async setUserInterests(userId: string, regions: string[]): Promise<any> {
    try {
      const response = await this.api.post(
        `/users/${userId}/interests`,
        { regions }
      );
      return response.data;
    } catch (error) {
      console.error('Failed to set user interests:', error);
      throw error;
    }
  }
}

export const apiService = new ApiService();
export type { PostMeta, PostDetail };
